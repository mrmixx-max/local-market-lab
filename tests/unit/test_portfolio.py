"""Portfolio engine tests with real SQLite workspace."""

from __future__ import annotations

import pytest

from packages.storage.workspace import Workspace
from packages.portfolio.engine import build_positions, value_portfolio
from packages.marketdata.fx import FxPolicy
from packages.ingest.csv_import import import_prices
from pathlib import Path


@pytest.fixture
def ws(tmp_path):
    w = Workspace(str(tmp_path / "test.db"))
    # instrument
    w.ensure_instrument("TEST", "Test ETF", "etf", "EUR")
    # prices: deterministic 10-bar series
    import_prices(w, _price_csv(tmp_path, "TEST", [100.0] * 10), "TEST", "test")
    return w


def _price_csv(path, symbol, closes):
    p = Path(path) / "p.csv"
    with p.open("w") as f:
        f.write("date,close\n")
        for i, c in enumerate(closes):
            f.write(f"2026-01-{i+1:02d},{c}\n")
    return p


class TestBuildPositions:
    def test_buy_increases_qty(self, ws):
        ws.add_transaction(
            {
                "portfolio": "p1",
                "symbol": "TEST",
                "txn_type": "buy",
                "date": "2026-01-01",
                "quantity": 10,
                "price": 100,
                "fees": 5,
                "currency": "EUR",
                "note": "",
            }
        )
        pos = build_positions(ws, "p1")
        assert "TEST" in pos
        assert abs(pos["TEST"].quantity - 10.0) < 1e-9

    def test_sell_consumes_fifo_lots(self, ws):
        ws.add_transaction(
            {
                "portfolio": "p",
                "symbol": "TEST",
                "txn_type": "buy",
                "date": "2026-01-01",
                "quantity": 10,
                "price": 100,
                "fees": 0,
                "currency": "EUR",
                "note": "",
            }
        )
        ws.add_transaction(
            {
                "portfolio": "p",
                "symbol": "TEST",
                "txn_type": "buy",
                "date": "2026-01-02",
                "quantity": 10,
                "price": 110,
                "fees": 0,
                "currency": "EUR",
                "note": "",
            }
        )
        ws.add_transaction(
            {
                "portfolio": "p",
                "symbol": "TEST",
                "txn_type": "sell",
                "date": "2026-01-03",
                "quantity": 5,
                "price": 120,
                "fees": 0,
                "currency": "EUR",
                "note": "",
            }
        )
        pos = build_positions(ws, "p")
        assert abs(pos["TEST"].quantity - 15.0) < 1e-9
        assert len(pos["TEST"].lots) == 2  # lot 0 partially consumed
        assert abs(pos["TEST"].lots[0].quantity - 5.0) < 1e-9


class TestValuePortfolio:
    def test_basic_valuation(self, ws):
        ws.add_transaction(
            {
                "portfolio": "p",
                "symbol": "TEST",
                "txn_type": "buy",
                "date": "2026-01-01",
                "quantity": 10,
                "price": 90,
                "fees": 0,
                "currency": "EUR",
                "note": "",
            }
        )
        val = value_portfolio(ws, "p")
        assert val["positions"][0]["symbol"] == "TEST"
        assert val["total_value"] > 0

    def test_missing_fx_incomplete(self, ws):
        ws.ensure_instrument("USD1", "USD asset", "etf", "USD")
        import_prices(
            ws,
            _price_csv(Path(ws.db_path).parent, "USD1", [100.0] * 10),
            "USD1",
            "test",
        )
        ws.add_transaction(
            {
                "portfolio": "p",
                "symbol": "USD1",
                "txn_type": "buy",
                "date": "2026-01-01",
                "quantity": 1,
                "price": 100,
                "fees": 0,
                "currency": "USD",
                "note": "",
            }
        )
        val = value_portfolio(ws, "p", FxPolicy("EUR"))  # no USD rate set
        assert val["incomplete_fx"] != []
