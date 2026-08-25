"""Synthetic fixtures — seeded price series + demo portfolio.

Only synthetic data is committed to the repo (fixture policy).
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DEMO_PORTFOLIO = [
    # symbol, name, asset_class, currency
    ("IWDA", "iShares Core MSCI World (synthetic)", "etf", "EUR"),
    ("EIMI", "iShares Core MSCI EM (synthetic)", "etf", "EUR"),
    ("AGGH", "Global Aggregate Bond (synthetic)", "bond", "EUR"),
]

# start_price, annual_drift, daily_vol
PRICE_SPECS = {
    "IWDA": (80.0, 0.08, 0.011),
    "EIMI": (26.0, 0.06, 0.015),
    "AGGH": (50.0, 0.02, 0.004),
}


def generate_prices(out_dir: str | Path, symbol: str, days: int = 756) -> Path:
    """Deterministic geometric random walk (seeded by symbol)."""
    rng = random.Random(hash(symbol) % 2**31)
    start, drift, vol = PRICE_SPECS[symbol]
    px = start
    d0 = date.today() - timedelta(days=days)
    out = Path(out_dir) / f"prices-{symbol}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        for i in range(days):
            d = d0 + timedelta(days=i)
            if d.weekday() < 5:
                px *= 1 + rng.gauss(drift / 252, vol)
                w.writerow([d.isoformat(), f"{px:.4f}"])
    return out


def generate_transactions(out_path: str | Path) -> Path:
    """Buy-and-hold demo: initial buys + one deposit, 2 years ago."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    start = date.today() - timedelta(days=730)
    rows = [
        ["date", "symbol", "type", "quantity", "price", "fees"],
        [start.isoformat(), "IWDA", "buy", "60", "71.20", "9.95"],
        [
            (start + timedelta(days=1)).isoformat(),
            "EIMI",
            "buy",
            "150",
            "24.80",
            "9.95",
        ],
        [
            (start + timedelta(days=2)).isoformat(),
            "AGGH",
            "buy",
            "100",
            "49.90",
            "9.95",
        ],
        [
            (start + timedelta(days=365)).isoformat(),
            "CASH",
            "deposit",
            "1",
            "5000",
            "0",
        ],
        [
            (start + timedelta(days=366)).isoformat(),
            "IWDA",
            "buy",
            "25",
            "76.40",
            "9.95",
        ],
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    return out


def load_demo(ws, workspace_dir: str = "./data") -> dict:
    """Full onboarding: instruments, prices, transactions into 'demo' portfolio."""
    report = {
        "prices": {},
    }
    for symbol, name, cls, ccy in DEMO_PORTFOLIO:
        ws.ensure_instrument(symbol, name, cls, ccy)
        p = generate_prices(f"{workspace_dir}/cache", symbol)
        r = __import__(
            "packages.ingest.csv_import", fromlist=["import_prices"]
        ).import_prices(ws, p, symbol, source="synthetic-fixture")
        report["prices"][symbol] = r["upserted"]
    txn_path = generate_transactions(f"{workspace_dir}/demo-transactions.csv")
    from packages.ingest.csv_import import import_transactions

    report["transactions"] = import_transactions(ws, txn_path, portfolio="demo")
    return report
