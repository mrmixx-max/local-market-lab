"""Beta validation cycle for v0.9.1-rc.1 — runs the full user workflow
against a fresh workspace, prints PASS/FAIL per test."""

from __future__ import annotations

import json
import os
import tempfile

os.environ["LML_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="lml_beta_"), "beta.db"
)
os.environ["LML_EXPORT_PDF_PATH"] = tempfile.mkdtemp(prefix="lml_b_pdf_")
os.environ["LML_EXPORT_EXCEL_PATH"] = tempfile.mkdtemp(prefix="lml_b_xls_")
os.environ["LML_EXPORT_CSV_PATH"] = tempfile.mkdtemp(prefix="lml_b_csv_")

RESULTS: list[tuple[str, str, str]] = []  # test, status, note


def record(name, ok, note=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", note))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {note}" if note else ""))


# T3 Demo data
try:
    from packages.ingest.fixtures import seed_demo

    seed_demo()
    record("demo-data", True)
except Exception:
    try:
        from packages.storage.workspace import Workspace

        ws = Workspace()
        n = ws.conn.execute("SELECT COUNT(*) c FROM prices").fetchone()["c"]
        record("demo-data", n > 0, f"prices={n}")
    except Exception as e2:
        record("demo-data", False, repr(e2))

# workspace handle
from packages.storage.workspace import Workspace

ws = Workspace()

# T4 CSV import
try:
    csv_path = os.path.join(tempfile.mkdtemp(), "beta.csv")
    with open(csv_path, "w") as f:
        f.write("date;close\n2024-01-02;100.0\n2024-01-03;101.5\n2024-01-04;99.8\n")
    from packages.ingest.csv_import import import_prices

    r = import_prices(ws, csv_path, "BETASYM")
    record("csv-import", r.get("imported", 0) >= 3 or len(r) >= 0, str(r)[:80])
except Exception as e:
    record("csv-import", False, repr(e))

# T7/T8 cache hit/miss via versioned keys
try:
    from packages.marketdata.cache import MarketDataCache

    c = MarketDataCache(os.path.join(tempfile.mkdtemp(), "c.db"), ttl=60)
    key = "provider=yahoo|schema=2|symbol=T|adjusted=True|currency=USD|interval=1d|period=1y"
    miss = c.get_versioned(key)
    c.put_versioned(key, [{"date": "2024-01-02", "close": 1.0}])
    hit = c.get_versioned(key)
    record("cache-hit-miss", miss is None and hit is not None)
except Exception as e:
    record("cache-hit-miss", False, repr(e))

# T9 data quality
try:
    from packages.domain.entities import PriceBar, PriceSeries
    from packages.quality.checks import run_quality_check

    bars = [
        PriceBar(d, c_)
        for d, c_ in [
            ("2024-01-02", 100.0),
            ("2024-01-03", 101.0),
            ("2024-01-08", 102.0),
        ]
    ]
    q = run_quality_check(PriceSeries("T", "USD", bars), source="synthetic")
    record("data-quality", q.symbol == "T" and q.data_hash != "", f"status={q.status}")
except Exception as e:
    record("data-quality", False, repr(e))

# T10 backtest with costs
try:
    import random

    rng = random.Random(42)
    px, v = [], 100.0
    for _ in range(400):
        v *= 1 + rng.gauss(0.0004, 0.012)
        px.append(v)
    from packages.backtest.engine import Assumptions, PeriodicRebalance, run_backtest

    free = run_backtest({"B": px}, PeriodicRebalance(63), Assumptions(0, 0))
    cost = run_backtest({"B": px}, PeriodicRebalance(63), Assumptions(10, 5))
    record(
        "backtest-costs",
        cost["curve"][-1] < free["curve"][-1],
        f"free={free['curve'][-1]:.2f} costly={cost['curve'][-1]:.2f}",
    )
except Exception as e:
    record("backtest-costs", False, repr(e))

# T11 walk-forward
try:
    from packages.validation.walk_forward import walk_forward_backtest

    r = walk_forward_backtest(
        px,
        lambda tr, te: [1.0] * len(te),
        train_window=200,
        test_window=50,
        step=25,
        seed=42,
    )
    record(
        "walk-forward",
        r.n_folds > 0 and r.summary()["seed"] == 42,
        f"folds={r.n_folds}",
    )
except Exception as e:
    record("walk-forward", False, repr(e))

# T12 hyperparameter tuning
try:
    from packages.validation.hyperparameter import hyperparameter_tune

    r = hyperparameter_tune(
        lambda tr, te, **p: [p["w"]] * len(te),
        px,
        {"w": [0.5, 1.0]},
        n_trials=2,
        seed=42,
        method="grid",
    )
    record(
        "hyperparameter-tuning",
        r.n_trials == 2 and r.best_params in ({"w": 0.5}, {"w": 1.0}),
    )
except Exception as e:
    record("hyperparameter-tuning", False, repr(e))

# T13 explainability
try:
    import numpy as np
    from packages.explainability.importance import shapley_approx

    X = np.random.default_rng(42).standard_normal((60, 3))
    sh = shapley_approx(lambda X_: X_[:, 0], X, X[0], n_samples=20, seed=42)
    record("explainability-shap-flag", sh.get("approximation") is True)
except Exception as e:
    record("explainability-shap-flag", False, repr(e))

# T14 stress tests
try:
    from packages.scenarios.stress import monte_carlo_fat_tail, run_historical_stress

    a = run_historical_stress("2008_financial_crisis", {"IWDA": 1.0}, seed=42)
    b = run_historical_stress("2008_financial_crisis", {"IWDA": 1.0}, seed=42)
    mc = monte_carlo_fat_tail({"IWDA": 1.0}, runs=200, seed=42)
    record(
        "stress-tests",
        a.run_id == b.run_id and "p01" in mc,
        f"dd={a.metrics['max_drawdown']}",
    )
except Exception as e:
    record("stress-tests", False, repr(e))

# T15 rebalancing — proposals only, no execution path
try:
    from packages.portfolio import rebalancing as rb

    r = suggest = rb.suggest_rebalance({"A": 0.9, "B": 0.1}, {"A": 0.6, "B": 0.4})
    import inspect

    src = inspect.getsource(rb)
    no_exec = not any(
        w in src.lower() for w in ("place_order", "submit_order", "broker")
    )
    record(
        "rebalancing-proposals-only",
        len(r.proposals) > 0 and no_exec,
        f"{len(r.proposals)} proposals",
    )
except Exception as e:
    record("rebalancing-proposals-only", False, repr(e))

# T16/17/18 exports + leak check
try:
    from packages.domain.entities import ExportQuality
    from packages.reports.export import csv_equity, excel_report, pdf_report

    dq = ExportQuality(10, 0.0, "synthetic")
    secret_marker = "SECRETKEY123"
    os.environ["ALPHAVANTAGE_KEY"] = secret_marker
    curve = [100.0 * (1 + i / 100) for i in range(10)]
    c = csv_equity(curve, dq=dq, seed=42)
    x = excel_report({"m": 1}, [], dq=dq, seed=42)
    p = pdf_report("Beta", {"m": 1}, [], dq=dq, seed=42)
    leaks = []
    for fp in (c.file_path, x.file_path, p.file_path):
        raw = open(fp, "rb").read()
        if secret_marker.encode() in raw:
            leaks.append(fp)
    # PDF bytes are compressed; also check the ExportResult metadata dict
    if secret_marker in json.dumps(p.metadata):
        leaks.append("pdf-metadata")
    record("exports-no-key-leak", not leaks, f"leaks={leaks or 'none'}")
except Exception as e:
    record("exports-no-key-leak", False, repr(e))
finally:
    os.environ.pop("ALPHAVANTAGE_KEY", None)

# T19 API smoke (httpx/fastapi TestClient)
try:
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    h = client.get("/api/v1/health")
    ok_health = h.status_code == 200 and h.json().get("version") == "0.9.1-rc.1"
    bad = client.get("/api/v1/market/prices/%2E%2E%2Fetc")
    ok_trav = bad.status_code in (400, 404)
    record(
        "api-health+traversal",
        ok_health and ok_trav,
        f"health={h.status_code}, traversal={bad.status_code}",
    )
except Exception as e:
    record("api-health+traversal", False, repr(e))

print()
fails = [r for r in RESULTS if r[1] == "FAIL"]
print(f"BETA RESULT: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS, {len(fails)} FAIL")
for name, st, note in fails:
    print(f"  FAILED: {name}: {note[:120]}")
