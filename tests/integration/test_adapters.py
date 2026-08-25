"""Integration tests for market data adapters with mocked HTTP."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from packages.marketdata.adapters import (
    ADAPTERS,
    AlphaVantageAdapter,
    FetchResult,
    SyntheticAdapter,
    YahooAdapter,
    get_adapter,
)
from packages.storage.workspace import Workspace


class TestSyntheticAdapter:
    def test_fetch_returns_series(self):
        adapter = SyntheticAdapter(seed=42)
        result = adapter.fetch("AAPL", days=60)
        assert isinstance(result, FetchResult)
        assert result.series.symbol == "AAPL"
        assert len(result.series.bars) > 0
        assert result.source.name == "synthetic-seeded"

    def test_deterministic(self):
        a1 = SyntheticAdapter(seed=42).fetch("MSFT", days=30)
        a2 = SyntheticAdapter(seed=42).fetch("MSFT", days=30)
        assert [b.close for b in a1.series.bars] == [b.close for b in a2.series.bars]

    def test_different_symbols_different_series(self):
        a1 = SyntheticAdapter(seed=42).fetch("A", days=30)
        a2 = SyntheticAdapter(seed=42).fetch("B", days=30)
        assert [b.close for b in a1.series.bars] != [b.close for b in a2.series.bars]

    def test_source_metadata(self):
        adapter = SyntheticAdapter()
        assert adapter.SOURCE.license == "public-domain"
        assert not adapter.SOURCE.requires_key


class TestYahooAdapter:
    def _make_hist(self, closes):
        """Build a minimal history object that mimics yfinance DataFrame."""
        from datetime import date as dt_date

        hist = MagicMock()
        hist.empty = len(closes) == 0

        if not closes:
            hist.iterrows.return_value = iter([])
            return hist

        rows = []
        for i, c in enumerate(closes):
            dt = dt_date(2024, 1, i + 1)
            row = {"Close": float(c)}
            rows.append((dt, row))

        hist.iterrows.return_value = iter(rows)
        return hist

    def _install_yfinance_mock(self, hist):
        """Install a mock yfinance module in sys.modules."""
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_yf.Ticker.return_value = mock_ticker
        sys.modules["yfinance"] = mock_yf

    def test_fetch_mocked_ticker(self):
        hist = self._make_hist([100.0 + i for i in range(10)])
        self._install_yfinance_mock(hist)

        adapter = YahooAdapter()
        result = adapter.fetch("AAPL", days=10)

        assert result.series.symbol == "AAPL"
        assert len(result.series.bars) == 10
        assert result.source.name == "yahoo-finance"

    def test_empty_history_raises(self):
        hist = self._make_hist([])
        self._install_yfinance_mock(hist)

        adapter = YahooAdapter()
        with pytest.raises(ValueError, match="no data"):
            adapter.fetch("INVALID", days=10)

    def test_import_error_without_yfinance(self):
        """If yfinance is not installed, ImportError is raised."""
        # Remove yfinance from sys.modules if present
        saved = sys.modules.pop("yfinance", None)

        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yfinance":
                raise ImportError("No module named 'yfinance'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            adapter = YahooAdapter()
            with pytest.raises(ImportError, match="yfinance"):
                adapter.fetch("AAPL")

        # Restore
        if saved:
            sys.modules["yfinance"] = saved


class TestAlphaVantageAdapter:
    def _mock_response(self, data: dict):
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        mock.read.return_value = json.dumps(data).encode()
        mock.__iter__ = MagicMock(return_value=iter([json.dumps(data).encode()]))
        return mock

    def test_fetch_success(self, monkeypatch):
        monkeypatch.setenv("ALPHAVANTAGE_KEY", "test-key")
        payload = {
            "Time Series (Daily)": {
                "2024-01-05": {"5. adjusted close": "150.0"},
                "2024-01-04": {"5. adjusted close": "149.0"},
                "2024-01-03": {"5. adjusted close": "148.0"},
            }
        }
        with patch("urllib.request.urlopen", return_value=self._mock_response(payload)):
            adapter = AlphaVantageAdapter()
            result = adapter.fetch("IBM")

        assert result.series.symbol == "IBM"
        assert len(result.series.bars) == 3
        assert result.source.name == "alpha-vantage"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("ALPHAVANTAGE_KEY", raising=False)
        adapter = AlphaVantageAdapter()
        with pytest.raises(ValueError, match="ALPHAVANTAGE_KEY not set"):
            adapter.fetch("IBM")

    def test_unexpected_response_raises(self, monkeypatch):
        monkeypatch.setenv("ALPHAVANTAGE_KEY", "test-key")
        payload = {"Error Message": "invalid api key"}
        with patch("urllib.request.urlopen", return_value=self._mock_response(payload)):
            adapter = AlphaVantageAdapter()
            with pytest.raises(ValueError, match="unexpected response"):
                adapter.fetch("IBM")


class TestAdapterRegistry:
    def test_get_adapter_synthetic(self):
        adapter = get_adapter("synthetic", seed=99)
        assert isinstance(adapter, SyntheticAdapter)
        assert adapter.seed == 99

    def test_get_adapter_yahoo(self):
        adapter = get_adapter("yahoo")
        assert isinstance(adapter, YahooAdapter)

    def test_get_adapter_alphavantage(self):
        adapter = get_adapter("alphavantage")
        assert isinstance(adapter, AlphaVantageAdapter)

    def test_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="unknown adapter"):
            get_adapter("nonexistent")

    def test_registry_contains_all(self):
        assert set(ADAPTERS.keys()) == {"synthetic", "yahoo", "alphavantage"}


class TestImportPricesToWs:
    def test_import_synthetic_prices(self, tmp_path):
        ws = Workspace(str(tmp_path / "test.db"))
        ws.ensure_instrument("TEST", "Test", "etf", "EUR")
        # Use adapter directly to avoid passing days to constructor
        adapter = get_adapter("synthetic", seed=42)
        result = adapter.fetch("TEST", days=30)
        for bar in result.series.bars:
            ws.upsert_price("TEST", bar.date, bar.close, source=result.source.name)
        ws.commit_prices()
        assert ws.price_count("TEST") > 0
