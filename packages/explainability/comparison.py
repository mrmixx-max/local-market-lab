"""Model comparison: Walk-Forward results + Diebold-Mariano test.

Pure numpy. Results include run_id, data_hash, and splits_used
to align with walk-forward validation (packages/domain/constants.py).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

import numpy as np

from packages.domain.constants import (
    WALK_FORWARD_STEP,
    WALK_FORWARD_TEST_WINDOW,
    WALK_FORWARD_TRAIN_WINDOW,
)
from packages.domain.entities import ExportQuality, ModelComparison


def _data_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _splits_str() -> str:
    return (f"walk_forward_{WALK_FORWARD_TRAIN_WINDOW}_"
            f"{WALK_FORWARD_TEST_WINDOW}_{WALK_FORWARD_STEP}")


@dataclass
class WalkForwardResult:
    """Single walk-forward window result."""
    window: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    model_name: str
    mse: float
    mae: float
    predictions: list[float] = field(default_factory=list)
    actuals: list[float] = field(default_factory=list)


def walkforward_table(results: list[WalkForwardResult]) -> dict:
    """Aggregate walk-forward results into a summary table."""
    headers = ["Window", "Model", "Train", "Test", "MSE", "MAE"]
    rows = []
    for r in results:
        rows.append({
            "Window": r.window, "Model": r.model_name,
            "Train": f"{r.train_start}:{r.train_end}",
            "Test": f"{r.test_start}:{r.test_end}",
            "MSE": round(r.mse, 6), "MAE": round(r.mae, 6),
        })
    models = sorted({r.model_name for r in results})
    summary = {}
    for m in models:
        sub = [r for r in results if r.model_name == m]
        summary[m] = {
            "mean_mse": round(np.mean([r.mse for r in sub]), 6),
            "std_mse": round(np.std([r.mse for r in sub]), 6),
            "mean_mae": round(np.mean([r.mae for r in sub]), 6),
            "std_mae": round(np.std([r.mae for r in sub]), 6),
            "n_windows": len(sub),
        }
    return {"headers": headers, "rows": rows, "summary": summary}


def diebold_mariano(pred1: list[float], pred2: list[float],
                    actual: list[float], loss: str = "mse",
                    h: int = 1) -> dict:
    """Diebold-Mariano test for equal forecast accuracy (normal approximation)."""
    a = np.asarray(actual, dtype=float)
    p1 = np.asarray(pred1, dtype=float)
    p2 = np.asarray(pred2, dtype=float)
    if loss == "mse":
        d = (p1 - a) ** 2 - (p2 - a) ** 2
    elif loss == "mae":
        d = np.abs(p1 - a) - np.abs(p2 - a)
    else:
        raise ValueError(f"unknown loss: {loss}")
    n = len(d)
    mean_d = np.mean(d)
    gamma0 = np.sum((d - mean_d) ** 2) / n
    var_d = gamma0
    for lag in range(1, h + 1):
        w = 1 - lag / (h + 1)
        gamma_l = np.sum((d[lag:] - mean_d) * (d[:-lag] - mean_d)) / n
        var_d += 2 * w * gamma_l
    if var_d <= 0:
        better = "model1" if mean_d < 0 else "model2" if mean_d > 0 else "tie"
        return {"dm_stat": 0.0, "p_value": 1.0, "better_model": better,
                "significant": False, "loss": loss, "h": h, "n_obs": n,
                "note": "zero variance in loss differential"}
    dm_stat = mean_d / np.sqrt(var_d / n)
    p_value = 2 * (1 - _norm_cdf(abs(dm_stat)))
    sig = p_value < 0.05
    better = "model1" if mean_d < 0 else "model2" if mean_d > 0 else "tie"
    return {
        "dm_stat": round(float(dm_stat), 4), "p_value": round(float(p_value), 4),
        "better_model": better, "significant": sig, "loss": loss, "h": h, "n_obs": n,
    }


def _norm_cdf(x: float) -> float:
    import math
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def compare_models(results_a: list[WalkForwardResult],
                   results_b: list[WalkForwardResult],
                   data_quality: ExportQuality | None = None) -> ModelComparison:
    """Compare two models across matched walk-forward windows. Returns ModelComparison."""
    map_a = {r.window: r for r in results_a}
    map_b = {r.window: r for r in results_b}
    common = sorted(set(map_a) & set(map_b))
    per_window = []
    all_p1, all_p2, all_act = [], [], []
    for w in common:
        a, b = map_a[w], map_b[w]
        per_window.append({
            "window": w, "mse_a": round(a.mse, 6),
            "mse_b": round(b.mse, 6), "delta_mse": round(a.mse - b.mse, 6),
        })
        all_p1.extend(a.predictions)
        all_p2.extend(b.predictions)
        all_act.extend(a.actuals)
    dm = diebold_mariano(all_p1, all_p2, all_act) if all_p1 else {}
    models = sorted({r.model_name for r in results_a + results_b})
    wf_rows = []
    for w in common:
        a, b = map_a[w], map_b[w]
        wf_rows.append({"window": w, "model_a_mse": a.mse, "model_b_mse": b.mse})
    return ModelComparison(
        run_id=str(uuid.uuid4())[:12],
        models=models,
        walk_forward_results=wf_rows,
        diebold_mariano=dm,
        data_quality=data_quality or ExportQuality(0, 0.0, "unknown"),
        splits_used=_splits_str(),
        data_hash=_data_hash(np.array(all_act)) if all_act else "",
    )
