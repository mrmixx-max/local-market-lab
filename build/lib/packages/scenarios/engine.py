"""Scenario engines — Monte Carlo (iid + block bootstrap) and historical replay.

Scenarios are NOT predictions. Every run is seeded, records its method,
and outputs percentiles + loss probability with explicit limitations.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from packages.marketdata.series import get_series


@dataclass
class ScenarioResult:
    method: str
    runs: int
    horizon_days: int
    seed: int
    finals: list[float]
    percentiles: dict[str, float]
    prob_loss_pct: float

    def summary(self) -> dict:
        s = sorted(self.finals)
        return {
            "method": self.method,
            "runs": self.runs,
            "horizon_days": self.horizon_days,
            "seed": self.seed,
            "p05": round(s[int(.05 * len(s))], 4),
            "p25": round(s[int(.25 * len(s))], 4),
            "median": round(s[int(.50 * len(s))], 4),
            "p75": round(s[int(.75 * len(s))], 4),
            "p95": round(s[int(.95 * len(s))], 4),
            "prob_loss_pct": self.prob_loss_pct,
            "limitations": [
                "Simulations assume the past return distribution persists.",
                "No regime changes, tail events or structural breaks are modeled "
                "beyond what the historical sample contains.",
                "Results are sensitivity explorations, not forecasts.",
            ],
        }


def _daily_returns(closes: list[float]) -> list[float]:
    return [b / a - 1 for a, b in zip(closes, closes[1:])]


def monte_carlo_iid(ws, symbol: str, horizon_days: int = 252, runs: int = 2000,
                    seed: int = 42) -> ScenarioResult:
    """i.i.d. resampling of daily returns."""
    closes = get_series(ws, symbol).closes()
    rets = _daily_returns(closes)
    rng = random.Random(seed)
    finals = []
    for _ in range(runs):
        v = 1.0
        for _day in range(horizon_days):
            v *= 1 + rets[rng.randrange(len(rets))]
        finals.append(v)
    sorted(finals)
    return ScenarioResult(
        method="monte-carlo-iid", runs=runs, horizon_days=horizon_days, seed=seed,
        finals=finals, percentiles={}, prob_loss_pct=round(
            sum(1 for x in finals if x < 1) / len(finals) * 100, 1))


def block_bootstrap(ws, symbol: str, horizon_days: int = 252, runs: int = 2000,
                    seed: int = 42, block_size: int = 20) -> ScenarioResult:
    """Block bootstrap — preserves short-range autocorrelation; robust default."""
    closes = get_series(ws, symbol).closes()
    rets = _daily_returns(closes)
    rng = random.Random(seed)
    finals = []
    for _ in range(runs):
        v = 1.0
        placed = 0
        while placed < horizon_days:
            start = rng.randrange(max(1, len(rets) - block_size))
            block = rets[start:start + block_size]
            for r in block:
                if placed >= horizon_days:
                    break
                v *= 1 + r
                placed += 1
        finals.append(v)
    sorted(finals)
    return ScenarioResult(
        method=f"block-bootstrap-{block_size}d", runs=runs, horizon_days=horizon_days,
        seed=seed, finals=finals, percentiles={}, prob_loss_pct=round(
            sum(1 for x in finals if x < 1) / len(finals) * 100, 1))


def historical_replay(ws, symbols: list[str], window_years: int | None = None,
                      seed: int | None = None) -> dict:
    """Replay actual history: equal-weight index with metrics per stress window.

    Deterministic by nature (no randomness). Reports known stress windows.
    """
    from packages.marketdata.series import aligned_closes
    from packages.metrics.risk import all_metrics
    dates, prices = aligned_closes(ws, symbols)
    n = len(dates)
    index = [sum(prices[s][i] / prices[s][0] for s in symbols) / len(symbols) * 100
             for i in range(n)]

    # find worst drawdown windows descriptively
    peak, mdd, trough_i, peak_i = index[0], 0.0, 0, 0
    cur_peak_i = 0
    for i, v in enumerate(index):
        if v > peak:
            peak, cur_peak_i = v, i
        dd = (peak - v) / peak
        if dd > mdd:
            mdd, trough_i, peak_i = dd, i, cur_peak_i

    out = {
        "method": "historical-replay",
        "symbols": symbols,
        "start": dates[0], "end": dates[-1],
        "metrics": all_metrics(index),
        "max_drawdown": {
            "pct": round(mdd * 100, 2),
            "peak_date": dates[peak_i], "trough_date": dates[trough_i],
        },
        "stress_windows": {
            "2020-covid-if-in-sample": None,  # filled when data covers it
        },
        "limitations": [
            "Historical replay describes one realized path.",
            "Survivorship bias possible if delisted instruments are missing.",
            "Past drawdowns bound nothing about future ones.",
        ],
    }
    # mark covid window if covered
    cov = [d for d in dates if "2020-02-15" <= d <= "2020-04-30"]
    if cov:
        seg = index[dates.index(cov[0]):dates.index(cov[-1]) + 1]
        out["stress_windows"]["2020-covid-if-in-sample"] = {
            "return_pct": round((seg[-1] / seg[0] - 1) * 100, 2)}
    else:
        out["stress_windows"].pop("2020-covid-if-in-sample")
    return out
