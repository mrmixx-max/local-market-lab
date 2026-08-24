"""Tests for market data adapters and cache."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from packages.domain.entities import PriceBar, PriceSeries
from packages.marketdata.cache import MarketDataCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_cache(tmp_path):
    return MarketDataCache(tmp_path / "test.db", ttl=2)


@pytest.fixture
def sample_series():
    bars = [PriceBar(f"2024-01-0{i+1}", 100.0 + i * 2, 1000) for i in range(5)]
    return PriceSeries("AAPL", "USD", bars)


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------
class TestMarketDataCache:
    def test_put_and_get(self, tmp_cache):
        bars = [{"date": "2024-01-01", "close": 100.0, "volume": 500}]
        tmp_cache.put("AAPL", "1d", "yahoo", bars)
        result = tmp_cache.get("AAPL", "1d", "yahoo")
        assert result == bars

    def test_cache_miss(self, tmp_cache):
        assert tmp_cache.get("MSFT", "1d", "yahoo") is None

    def test_ttl_expiry(self, tmp_cache):
        bars = [{"date": "2024-01-01", "close": 100.0}]
        tmp_cache.put("AAPL", "1d", "yahoo", bars)
        tmp_cache.ttl = 0  # force expiry
        assert tmp_cache.get("AAPL", "1d", "yahoo") is None

    def test_offline_fallback(self, tmp_cache):
        bars = [{"date": "2024-01-01", "close": 100.0}]
        tmp_cache.put("AAPL", "1d", "yahoo", bars)
        tmp_cache.ttl = 0
        result = tmp_cache.get_offline("AAPL", "1d", "yahoo")
        assert result == bars

    def test_invalidate_symbol(self, tmp_cache):
        tmp_cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        tmp_cache.put("MSFT", "1d", "yahoo", [{"date": "d2", "close": 2.0}])
        n = tmp_cache.invalidate("AAPL")
        assert n == 1
        assert tmp_cache.get("AAPL", "1d", "yahoo") is None
        assert tmp_cache.get_offline("MSFT", "1d", "yahoo") is not None

    def test_invalidate_all(self, tmp_cache):
        tmp_cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        tmp_cache.put("MSFT", "1d", "yahoo", [{"date": "d2", "close": 2.0}])
        assert tmp_cache.invalidate() == 2

    def test_stats(self, tmp_cache):
        tmp_cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        stats = tmp_cache.stats()
        assert stats["entries"] == 1
        assert "ttl_seconds" in stats

    def test_overwrite(self, tmp_cache):
        tmp_cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        tmp_cache.put("AAPL", "1d", "yahoo", [{"date": "d2", "close": 2.0}])
        result = tmp_cache.get("AAPL", "1d", "yahoo")
        assert result[0]["close"] == 2.0

    def test_quality_status(self, tmp_cache):
        bars = [{"date": "2024-01-01", "close": 100.0}]
        tmp_cache.put("AAPL", "1d", "yahoo", bars, quality_status="valid")
        # quality_status is stored but doesn't affect get
        result = tmp_cache.get("AAPL", "1d", "yahoo")
        assert result == bars

    def test_invalidate_on_quality_error(self, tmp_cache):
        tmp_cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        tmp_cache.put("AAPL", "1h", "yahoo", [{"date": "d2", "close": 2.0}])
        tmp_cache.invalidate_on_quality_error("AAPL", "yahoo", "1d")
        assert tmp_cache.get_offline("AAPL", "1d", "yahoo") is None
        assert tmp_cache.get_offline("AAPL", "1h", "yahoo") is not None


# ---------------------------------------------------------------------------
# PriceBar OHLCV format
# ---------------------------------------------------------------------------
class TestPriceBarFormat:
    def test_to_ohlcv_complete(self):
        bar = PriceBar("2024-01-01", 100.0, open=99.0, high=101.0, low=98.5, volume=1000, currency="USD")
        d = bar.to_ohlcv()
        assert d["open"] == 99.0
        assert d["high"] == 101.0
        assert d["low"] == 98.5
        assert d["close"] == 100.0
        assert d["volume"] == 1000
        assert d["currency"] == "USD"

    def test_to_ohlcv_fallback(self):
        bar = PriceBar("2024-01-01", 100.0)
        d = bar.to_ohlcv()
        assert d["open"] == 100.0  # falls back to close
        assert d["high"] == 100.0
        assert d["low"] == 100.0
        assert d["volume"] == 0.0
        assert d["currency"] == "USD"


# ---------------------------------------------------------------------------
# Adapter offline tests (no network)
# ---------------------------------------------------------------------------
class TestYahooAdapterOffline:
    def test_offline_with_cached_data(self, tmp_cache):
        from packages.marketdata.yahoo_adapter import YahooAdapter

        bars = [{"date": "2024-01-01", "close": 150.0, "volume": 1000}]
        tmp_cache.put("AAPL", "1d", "yahoo", bars)
        adapter = YahooAdapter(cache=tmp_cache)
        series = adapter.fetch("AAPL", interval="1d", offline=True)
        assert series.symbol == "AAPL"
        assert len(series.bars) == 1
        assert series.bars[0].close == 150.0

    def test_offline_no_cache_raises(self, tmp_cache):
        from packages.marketdata.yahoo_adapter import YahooAdapter

        adapter = YahooAdapter(cache=tmp_cache)
        with pytest.raises(RuntimeError, match="no cached data"):
            adapter.fetch("XXXX", interval="1d", offline=True)


class TestAlphaVantageAdapterOffline:
    def test_offline_with_cached_data(self, tmp_cache):
        from packages.marketdata.alpha_vantage_adapter import AlphaVantageAdapter

        bars = [{"date": "2024-01-01", "close": 200.0, "volume": 500}]
        tmp_cache.put("IBM", "daily", "alphavantage", bars)
        adapter = AlphaVantageAdapter(api_key="test_key", cache=tmp_cache)
        series = adapter.fetch("IBM", offline=True)
        assert series.symbol == "IBM"
        assert series.bars[0].close == 200.0

    def test_missing_key_raises(self):
        import os

        from packages.marketdata.alpha_vantage_adapter import AlphaVantageAdapter

        os.environ.pop("ALPHAVANTAGE_KEY", None)
        with pytest.raises(ValueError, match="ALPHAVANTAGE_KEY"):
            AlphaVantageAdapter(api_key=None)
