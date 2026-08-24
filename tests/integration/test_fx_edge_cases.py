"""Tests for FX data handling: missing rates, wrong currencies, explicit conversion."""
from __future__ import annotations

import pytest

from packages.marketdata.fx import FxPolicy


# ---------------------------------------------------------------------------
# Missing FX rates
# ---------------------------------------------------------------------------

class TestMissingFxRates:
    def test_unknown_currency_returns_none(self):
        fx = FxPolicy("EUR", {"USD": 1.08})
        result = fx.convert(100.0, "GBP")
        assert result is None

    def test_missing_rate_raises_on_require(self):
        fx = FxPolicy("EUR", {"USD": 1.08})
        with pytest.raises(KeyError, match="missing FX rate"):
            fx.require(100.0, "GBP")

    def test_reporting_currency_no_conversion(self):
        fx = FxPolicy("EUR", {"USD": 1.08})
        assert fx.convert(100.0, "EUR") == 100.0

    def test_known_currency_converts(self):
        fx = FxPolicy("EUR", {"USD": 1.08})
        result = fx.convert(100.0, "USD")
        assert result == pytest.approx(108.0)

    def test_known_method(self):
        fx = FxPolicy("EUR", {"USD": 1.08})
        assert fx.known("USD")
        assert not fx.known("GBP")
        assert fx.known("EUR")  # reporting currency always known


# ---------------------------------------------------------------------------
# Wrong FX data
# ---------------------------------------------------------------------------

class TestWrongFxData:
    def test_zero_rate_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            FxPolicy("EUR", {"USD": 0.0})

    def test_negative_rate_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            FxPolicy("EUR", {"USD": -1.5})

    def test_set_rate_valid(self):
        fx = FxPolicy("EUR")
        fx.set_rate("USD", 1.08)
        assert fx.rates["USD"] == 1.08

    def test_set_rate_zero_rejected(self):
        fx = FxPolicy("EUR")
        with pytest.raises(ValueError, match="positive"):
            fx.set_rate("USD", 0.0)

    def test_set_rate_negative_rejected(self):
        fx = FxPolicy("EUR")
        with pytest.raises(ValueError, match="positive"):
            fx.set_rate("USD", -0.5)

    def test_case_insensitive_currency(self):
        fx = FxPolicy("eur", {"usd": 1.08})
        assert fx.known("USD")
        assert fx.known("usd")
        assert fx.convert(100.0, "usd") == pytest.approx(108.0)


# ---------------------------------------------------------------------------
# Multi-currency scenarios
# ---------------------------------------------------------------------------

class TestMultiCurrency:
    def test_multiple_rates(self):
        fx = FxPolicy("EUR", {"USD": 1.08, "GBP": 0.85, "CHF": 0.95})
        assert fx.convert(100.0, "USD") == pytest.approx(108.0)
        assert fx.convert(100.0, "GBP") == pytest.approx(85.0)
        assert fx.convert(100.0, "CHF") == pytest.approx(95.0)

    def test_partial_coverage(self):
        """Some currencies known, others not."""
        fx = FxPolicy("EUR", {"USD": 1.08})
        assert fx.convert(100.0, "USD") is not None
        assert fx.convert(100.0, "JPY") is None

    def test_reporting_currency_always_one(self):
        """Reporting currency always has rate 1.0."""
        fx = FxPolicy("CHF")
        assert fx.rates["CHF"] == 1.0
        assert fx.convert(500.0, "CHF") == 500.0


# ---------------------------------------------------------------------------
# Integration with portfolio valuation
# ---------------------------------------------------------------------------

class TestFxPortfolioIntegration:
    def test_incomplete_fx_markers(self, tmp_path):
        """When FX is missing, portfolio valuation must mark incomplete."""
        from packages.portfolio.engine import value_portfolio
        from packages.storage.workspace import Workspace
        from packages.ingest.csv_import import import_prices

        ws = Workspace(str(tmp_path / "test.db"))
        ws.ensure_instrument("AAPL", "Apple", "equity", "USD")
        p = tmp_path / "prices.csv"
        with p.open("w") as f:
            f.write("date,close\n")
            for i in range(10):
                f.write(f"2024-01-{i+1:02d},100.0\n")
        import_prices(ws, p, "AAPL", "test")
        ws.add_transaction({
            "portfolio": "p1", "symbol": "AAPL", "txn_type": "buy",
            "date": "2024-01-01", "quantity": 10, "price": 100,
            "fees": 0, "currency": "USD", "note": "",
        })
        # No USD rate set → incomplete
        val = value_portfolio(ws, "p1", FxPolicy("EUR"))
        assert len(val["incomplete_fx"]) > 0
        assert val["incomplete_fx"][0]["symbol"] == "AAPL"

    def test_complete_fx_valuation(self, tmp_path):
        """With FX rate set, valuation succeeds."""
        from packages.portfolio.engine import value_portfolio
        from packages.storage.workspace import Workspace
        from packages.ingest.csv_import import import_prices

        ws = Workspace(str(tmp_path / "test.db"))
        ws.ensure_instrument("AAPL", "Apple", "equity", "USD")
        p = tmp_path / "prices.csv"
        with p.open("w") as f:
            f.write("date,close\n")
            for i in range(10):
                f.write(f"2024-01-{i+1:02d},100.0\n")
        import_prices(ws, p, "AAPL", "test")
        ws.add_transaction({
            "portfolio": "p1", "symbol": "AAPL", "txn_type": "buy",
            "date": "2024-01-01", "quantity": 10, "price": 100,
            "fees": 0, "currency": "USD", "note": "",
        })
        fx = FxPolicy("EUR", {"USD": 0.92})
        val = value_portfolio(ws, "p1", fx)
        assert len(val["incomplete_fx"]) == 0
        assert val["total_value"] > 0
