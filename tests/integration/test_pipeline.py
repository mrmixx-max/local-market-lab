"""Scenario + backtest integration — seeded determinism + replay."""
import pytest

from packages.scenarios.engine import (block_bootstrap, historical_replay,
                                       monte_carlo_iid)
from packages.backtest.engine import (Assumptions, BuyAndHold,
                                       PeriodicRebalance, run_backtest)
from packages.metrics.risk import all_metrics
from packages.ingest.csv_import import import_prices
from packages.storage.workspace import Workspace


@pytest.fixture
def ws(tmp_path):
    w = Workspace(str(tmp_path / "test.db"))
    # 3 symbols, 500 bars each, seeded
    import_prices(w, _csv(tmp_path, "A", 500, 0.0005, 0.012), "A", "test")
    import_prices(w, _csv(tmp_path, "B", 500, 0.0003, 0.015), "B", "test")
    import_prices(w, _csv(tmp_path, "C", 500, 0.0001, 0.010), "C", "test")
    return w


def _csv(path, symbol, n, drift, vol):
    import random
    from pathlib import Path
    rng = random.Random(hash(symbol) % 2**31)
    p = Path(path) / f"{symbol}.csv"
    px = 100.0
    with p.open("w") as f:
        f.write("date,close\n")
        for i in range(n):
            px *= 1 + rng.gauss(drift, vol)
            f.write(f"2024-01-{i+1:02d},{px:.4f}\n")
    return p


class TestScenarioDeterminism:
    def test_same_seed_same_result(self, ws):
        a = monte_carlo_iid(ws, "A", 252, 100, 42)
        b = monte_carlo_iid(ws, "A", 252, 100, 42)
        assert a.finals == b.finals

    def test_different_seed_different(self, ws):
        a = block_bootstrap(ws, "B", 252, 100, 1)
        b = block_bootstrap(ws, "B", 252, 100, 2)
        assert a.finals != b.finals


class TestBacktest:
    def test_buy_and_hold_vs_rebalance(self, ws):
        from packages.marketdata.series import aligned_closes
        dates, prices = aligned_closes(ws, ["A", "B", "C"])
        bh = run_backtest(prices, BuyAndHold(), Assumptions())
        rb = run_backtest(prices, PeriodicRebalance(63), Assumptions())
        # both should have metrics and be roughly sane
        assert bh["metrics"]["total_return_pct"] is not None
        assert rb["metrics"]["total_return_pct"] is not None

    def test_fee_assumptions(self):
        """Assumptions carry fee info correctly."""
        free = Assumptions(fees_bps=0, slippage_bps=0)
        cost = Assumptions(fees_bps=50, slippage_bps=25)
        assert free.trade_cost_fraction() == 0.0
        assert cost.trade_cost_fraction() == 0.0075

    def test_rebalance_generates_trades(self, ws):
        """Quarterly rebalance should execute at least one trade after t0."""
        from packages.marketdata.series import aligned_closes
        _, prices = aligned_closes(ws, ["A", "B", "C"])
        rb = run_backtest(prices, PeriodicRebalance(63), Assumptions())
        assert rb["trades"] > 0
        assert rb["turnover"] > 0


class TestReplay:
    def test_replay_has_drawdown_info(self, ws):
        out = historical_replay(ws, ["A", "B"])
        assert "max_drawdown" in out
        assert "metrics" in out
