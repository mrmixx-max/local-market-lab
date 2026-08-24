"""Regression tests for the demo-portfolio CASH bug (rc.1 external test cycle).

Reproduced: `lml backtest demo` raised MissingPriceError for 'CASH' because
demo fixtures include a CASH deposit transaction but no CASH price series.
Fix: backtest_from_workspace excludes non-tradable cash symbols, consistent
with the scenarios replay path (apps/cli/main.py `- {"CASH"}`).
"""
import os

import pytest

from packages.backtest.engine import (
    Assumptions,
    BuyAndHold,
    PeriodicRebalance,
    backtest_from_workspace,
)


@pytest.fixture()
def demo_ws(tmp_path):
    from packages.ingest.fixtures import load_demo
    from packages.storage.workspace import Workspace

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        ws = Workspace(str(tmp_path / "marketlab.db"))
        load_demo(ws, workspace_dir=str(tmp_path / "data"))
        yield ws
    finally:
        os.chdir(old_cwd)


def test_backtest_demo_excludes_cash(demo_ws):
    """Demo portfolio contains a CASH deposit; backtest must not require a CASH price."""
    result = backtest_from_workspace(demo_ws, "demo", BuyAndHold(), Assumptions())
    assert "CASH" not in result["symbols"]
    assert result["symbols"] == ["AGGH", "EIMI", "IWDA"]
    assert "cagr_pct" in result["metrics"]


def test_backtest_demo_rebalance_strategy(demo_ws):
    result = backtest_from_workspace(
        demo_ws, "demo", PeriodicRebalance(63), Assumptions()
    )
    assert result["metrics"]["cagr_pct"] is not None


def test_backtest_unknown_symbol_still_fails(demo_ws):
    """A genuinely missing symbol must still raise (no silent substitution)."""
    from packages.marketdata.series import MissingPriceError

    ws = demo_ws
    ws.ensure_instrument("XXXX", "Unknown", "equity", "USD")
    ws.add_transaction({
        "portfolio": "demo", "symbol": "XXXX", "txn_type": "buy",
        "date": "2024-01-02", "quantity": 1, "price": 10.0,
        "fees": 1.0, "currency": "USD", "note": "",
    })
    with pytest.raises(MissingPriceError):
        backtest_from_workspace(ws, "demo", BuyAndHold(), Assumptions())
