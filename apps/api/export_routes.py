"""Export and Explainability API routes.

Endpoints:
  POST /api/v1/export/pdf
  POST /api/v1/export/excel
  POST /api/v1/export/csv
  GET  /api/v1/explainability/importance
  GET  /api/v1/explainability/compare

@experimental: Explainability endpoints are experimental and may change.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import re

from apps.api.deps import get_workspace
from packages.reports.export import csv_equity, csv_scenario, csv_trades, excel_report, pdf_report
from packages.explainability.importance import permutation_importance, shapley_approx
from packages.explainability.comparison import (
    WalkForwardResult, compare_models, diebold_mariano, walkforward_table,
)
from packages.domain.entities import ExportQuality

# Allowed CSV export kinds — prevents path traversal via filename construction
_EXPORT_KIND_ALLOWED = frozenset({"trades", "equity", "scenario"})

# Symbol validation: only allow safe ticker characters
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-^=]{1,20}$")


def _validate_symbol(symbol: str) -> str:
    """Validate and normalize a ticker symbol. Raises HTTPException if invalid."""
    if not symbol or not _SYMBOL_RE.match(symbol):
        raise HTTPException(400, f"invalid symbol format: {symbol!r}")
    return symbol.upper()

export_router = APIRouter(prefix="/api/v1/export", tags=["export"])
explain_router = APIRouter(prefix="/api/v1/explainability", tags=["explainability"])


def _make_dq(payload: dict) -> ExportQuality:
    """Build ExportQuality from payload or defaults."""
    dq = payload.get("data_quality", {})
    return ExportQuality(
        n_observations=dq.get("n_observations", 0),
        missing_pct=dq.get("missing_pct", 0.0),
        source=dq.get("source", "unknown"),
        start_date=dq.get("start_date", ""),
        end_date=dq.get("end_date", ""),
        warnings=dq.get("warnings", []),
    )


# ---------- export ----------
@export_router.post("/pdf", summary="Export PDF report")
async def export_pdf(payload: dict):
    """Generate a PDF report from metrics, trades, and optional PIL chart images.

    @experimental: Chart image handling is experimental.
    """
    title = payload.get("title", "Local Market Lab Report")
    metrics = payload.get("metrics", {})
    trades = payload.get("trades", [])
    charts = payload.get("chart_paths")
    equity = payload.get("equity_curve")
    dq = _make_dq(payload)
    try:
        result = pdf_report(title, metrics, trades, charts, equity, dq)
    except Exception as exc:
        raise HTTPException(500, f"PDF generation failed: {exc}")
    return Response(content=result.file_bytes or b"", media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=report_{result.run_id}.pdf",
                             "X-Run-ID": result.run_id, "X-Data-Hash": result.data_hash})


@export_router.post("/excel", summary="Export Excel workbook")
async def export_excel(payload: dict):
    """Generate multi-sheet Excel workbook (Summary, Trades, Equity, Drawdown, Quality)."""
    dq = _make_dq(payload)
    try:
        result = excel_report(
            metrics=payload.get("metrics", {}),
            trades=payload.get("trades", []),
            equity_curve=payload.get("equity_curve"),
            drawdown=payload.get("drawdown"),
            dq=dq,
        )
    except Exception as exc:
        raise HTTPException(500, f"Excel generation failed: {exc}")
    return Response(content=result.file_bytes or b"",
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=report_{result.run_id}.xlsx",
                             "X-Run-ID": result.run_id, "X-Data-Hash": result.data_hash})


@export_router.post("/csv", summary="Export CSV data")
async def export_csv(payload: dict):
    """Export trades, equity curve, or scenario results as CSV."""
    kind = payload.get("kind", "trades")
    if kind not in _EXPORT_KIND_ALLOWED:
        raise HTTPException(400, f"unknown CSV kind: {kind}. allowed: {sorted(_EXPORT_KIND_ALLOWED)}")
    dq = _make_dq(payload)
    if kind == "trades":
        result = csv_trades(payload.get("trades", []), dq)
    elif kind == "equity":
        result = csv_equity(payload.get("equity_curve", []), payload.get("dates"), dq)
    elif kind == "scenario":
        result = csv_scenario(payload.get("runs", []), dq)
    else:
        raise HTTPException(400, f"unknown CSV kind: {kind}")
    return Response(content=result.file_bytes or b"", media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={kind}_{result.run_id}.csv",
                             "X-Run-ID": result.run_id, "X-Data-Hash": result.data_hash})


# ---------- explainability ----------
@explain_router.get("/importance", summary="Feature importance analysis")
async def explain_importance(payload: dict):
    """Compute permutation importance and SHAP-like values for a model.

    @experimental: SHAP approximation is experimental.
    """
    import numpy as np
    X = np.asarray(payload.get("X", []), dtype=float)
    y = np.asarray(payload.get("y", []), dtype=float)
    if X.ndim != 2 or y.ndim != 1:
        raise HTTPException(400, "X must be 2D, y must be 1D")
    names = payload.get("feature_names")
    metric = payload.get("metric", "mse")
    model_name = payload.get("model_name", "model")
    dq = _make_dq(payload)
    predict = (lambda X, y=y: np.full(len(X), np.mean(y))) if not payload.get("predict") \
        else _make_predict(payload["predict"])
    result = permutation_importance(predict, X, y, names, metric=metric,
                                    model_name=model_name, data_quality=dq)
    if payload.get("shap_instance") is not None:
        instance = np.asarray(payload["shap_instance"], dtype=float)
        result.shap_values = shapley_approx(predict, X, instance)
    return result.to_dict()


def _make_predict(spec: dict):
    """Build a predict callable from a simple spec (linear weights)."""
    import numpy as np
    w = np.asarray(spec.get("weights", []), dtype=float)
    b = float(spec.get("bias", 0.0))
    return lambda X: X @ w + b


@explain_router.get("/compare", summary="Compare two models")
async def explain_compare(payload: dict):
    """Compare models via walk-forward results and Diebold-Mariano test.

    @experimental: Diebold-Mariano test uses normal approximation.
    """
    mode = payload.get("mode", "walkforward")
    dq = _make_dq(payload)
    if mode == "walkforward":
        results = payload.get("results", [])
        wf = [_parse_wf(r) for r in results]
        return walkforward_table(wf)
    if mode == "dm":
        return diebold_mariano(payload["pred1"], payload["pred2"], payload["actual"],
                               payload.get("loss", "mse"), payload.get("h", 1))
    if mode == "compare":
        a = [_parse_wf(r) for r in payload.get("model_a", [])]
        b = [_parse_wf(r) for r in payload.get("model_b", [])]
        return compare_models(a, b, dq).to_dict()
    raise HTTPException(400, f"unknown mode: {mode}")


def _parse_wf(d: dict) -> WalkForwardResult:
    return WalkForwardResult(
        window=d.get("window", 0), train_start=d.get("train_start", 0),
        train_end=d.get("train_end", 0), test_start=d.get("test_start", 0),
        test_end=d.get("test_end", 0), model_name=d.get("model_name", "model"),
        mse=d.get("mse", 0.0), mae=d.get("mae", 0.0),
        predictions=d.get("predictions", []), actuals=d.get("actuals", []),
    )
