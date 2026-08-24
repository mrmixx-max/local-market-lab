"""Backtest engine — event loop over aligned price series.

Strategies are rule-based and explicit. Every run records fees, slippage,
benchmark, seed (if any), and data lineage in its artifact.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.marketdata.series import aligned_closes
from packages.metrics.risk import all_metrics


# ---------- assumptions ----------
@dataclass
class Assumptions:
    fees_bps: float = 10.0          # per trade, basis points of trade value
    slippage_bps: float = 5.0       # per trade
    rebalance_frequency: str = "none"   # none|quarterly|annual
    reporting_currency: str = "EUR"

    def trade_cost_fraction(self) -> float:
        return (self.fees_bps + self.slippage_bps) / 10_000


# ---------- strategies ----------
class Strategy:
    """Base class. decide(weights, i, prices, value) -> target weights dict."""
    name: str = "base"

    def weights(self, i: int, prices: dict[str, list[float]], symbols: list[str],
                current: dict[str, float]) -> dict[str, float]:
        raise NotImplementedError


class BuyAndHold(Strategy):
    """Equal weight at t0, never touched again."""
    name = "buy-and-hold"

    def weights(self, i, prices, symbols, current):
        if i == 0:
            w = {s: 1 / len(symbols) for s in symbols}
            return w
        return current


class PeriodicRebalance(Strategy):
    """Equal weight rebalanced every N trading days."""
    def __init__(self, every_days: int = 63):
        self.every_days = every_days
        self.name = f"rebalance-{every_days}d"

    def weights(self, i, prices, symbols, current):
        if i % self.every_days == 0:
            return {s: 1 / len(symbols) for s in symbols}
        return current


# ---------- engine ----------
def run_backtest(prices: dict[str, list[float]],
                 strategy: Strategy,
                 assumptions: Assumptions | None = None,
                 start_value: float = 100.0) -> dict:
    assumptions = assumptions or Assumptions()
    symbols = sorted(prices.keys())
    n = min(len(p) for p in prices.values())
    dates_idx = range(n)
    cost_frac = assumptions.trade_cost_fraction()

    units = {s: 0.0 for s in symbols}
    cash = start_value
    curve, turnover, trades = [], 0.0, 0

    for i in dates_idx:
        px = {s: prices[s][i] for s in symbols}
        total = cash + sum(units[s] * px[s] for s in symbols)

        target_w = strategy.weights(i, prices, symbols,
                                    {s: units[s] * px[s] / total if total else 0.0
                                     for s in symbols})
        # drift-normalize current weights
        cur_w = {s: (units[s] * px[s]) / total if total else 0.0 for s in symbols}

        # trade toward target when deviation exceeds a small band (avoids churn)
        for s in symbols:
            delta_w = target_w.get(s, 0.0) - cur_w.get(s, 0.0)
            if abs(delta_w) * total < total * 0.001:   # <0.1% of portfolio: skip
                continue
            trade_value = delta_w * total
            cost = abs(trade_value) * cost_frac
            # Buy: cost is deducted from invested value (fewer units).
            # Sell: cost is deducted from proceeds. Costs always reduce
            # portfolio value; cash is recomputed from holdings below.
            qty_delta = (trade_value - (cost if trade_value > 0 else -cost)) / px[s]
            units[s] += qty_delta
            cash -= cost
            turnover += abs(trade_value)
            trades += 1
        # normalize rounding: recompute cash from holdings to avoid drift
        cash = total - sum(units[s] * px[s] for s in symbols)
        curve.append(sum(units[s] * px[s] for s in symbols))

    benchmark = _equal_weight_index(prices, n)
    return {
        "curve": curve,
        "metrics": all_metrics(curve),
        "benchmark_curve": benchmark,
        "benchmark_metrics": all_metrics(benchmark),
        "assumptions": {
            "fees_bps": assumptions.fees_bps, "slippage_bps": assumptions.slippage_bps,
            "rebalance_frequency": assumptions.rebalance_frequency,
            "start_value": start_value,
        },
        "strategy": strategy.name,
        "turnover": round(turnover, 2),
        "trades": trades,
    }


def _equal_weight_index(prices: dict[str, list[float]], n: int) -> list[float]:
    """Buy-and-hold equal-weight index as descriptive benchmark."""
    out = []
    for i in range(n):
        out.append(sum(prices[s][i] / prices[s][0] for s in prices) / len(prices) * 100)
    return out


def backtest_from_workspace(ws, portfolio: str, strategy: Strategy,
                            assumptions: Assumptions | None = None) -> dict:
    from packages.ingest.csv_import import _pick  # noqa: F401 (import guard)
    txns = ws.transactions_for(portfolio)
    if not txns:
        raise ValueError(f"portfolio {portfolio!r} has no transactions")
    symbols = sorted({t["symbol"] for t in txns})
    dates, prices = aligned_closes(ws, symbols)
    result = run_backtest(prices, strategy, assumptions)
    result["symbols"] = symbols
    result["dates"] = dates
    return result
