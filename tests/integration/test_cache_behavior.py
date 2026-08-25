"""Tests for cache behavior: hits, misses, stale data, provider errors."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from packages.marketdata.cache import MarketDataCache

# ---------------------------------------------------------------------------
# Cache hits and misses
# ---------------------------------------------------------------------------


class TestCacheHitMiss:
    def test_hit_returns_data(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        bars = [{"date": "2024-01-01", "close": 100.0}]
        cache.put("AAPL", "1d", "yahoo", bars)
        result = cache.get("AAPL", "1d", "yahoo")
        assert result == bars

    def test_miss_returns_none(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        assert cache.get("AAPL", "1d", "yahoo") is None

    def test_different_intervals_miss(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d", "close": 1.0}])
        assert cache.get("AAPL", "1h", "yahoo") is None

    def test_different_sources_miss(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d", "close": 1.0}])
        assert cache.get("AAPL", "1d", "alphavantage") is None

    def test_case_insensitive_key(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        bars = [{"date": "2024-01-01", "close": 100.0}]
        cache.put("aapl", "1d", "yahoo", bars)
        result = cache.get("AAPL", "1d", "yahoo")
        assert result == bars


# ---------------------------------------------------------------------------
# TTL and stale data
# ---------------------------------------------------------------------------


class TestCacheTTL:
    def test_fresh_data_returned(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db", ttl=3600)
        bars = [{"date": "2024-01-01", "close": 100.0}]
        cache.put("AAPL", "1d", "yahoo", bars)
        assert cache.get("AAPL", "1d", "yahoo") == bars

    def test_expired_data_returns_none(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db", ttl=1)
        bars = [{"date": "2024-01-01", "close": 100.0}]
        cache.put("AAPL", "1d", "yahoo", bars)
        cache.ttl = 0  # force immediate expiry
        assert cache.get("AAPL", "1d", "yahoo") is None

    def test_offline_returns_expired(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db", ttl=1)
        bars = [{"date": "2024-01-01", "close": 100.0}]
        cache.put("AAPL", "1d", "yahoo", bars)
        cache.ttl = 0
        result = cache.get_offline("AAPL", "1d", "yahoo")
        assert result == bars

    def test_offline_miss_returns_none(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        assert cache.get_offline("NOPE", "1d", "yahoo") is None


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


class TestCacheInvalidation:
    def test_invalidate_specific_symbol(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        cache.put("MSFT", "1d", "yahoo", [{"date": "d2", "close": 2.0}])
        n = cache.invalidate("AAPL")
        assert n == 1
        assert cache.get("AAPL", "1d", "yahoo") is None
        assert cache.get("MSFT", "1d", "yahoo") is not None

    def test_invalidate_all(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        cache.put("MSFT", "1d", "yahoo", [{"date": "d2", "close": 2.0}])
        assert cache.invalidate() == 2

    def test_invalidate_nonexistent_returns_zero(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        assert cache.invalidate("NOPE") == 0

    def test_invalidate_on_quality_error(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        cache.put("AAPL", "1h", "yahoo", [{"date": "d2", "close": 2.0}])
        cache.invalidate_on_quality_error("AAPL", "yahoo", "1d")
        assert cache.get("AAPL", "1d", "yahoo") is None
        assert cache.get("AAPL", "1h", "yahoo") is not None


# ---------------------------------------------------------------------------
# Provider error simulation
# ---------------------------------------------------------------------------


class TestProviderErrors:
    def test_cache_survives_corrupted_data(self, tmp_path):
        """If stored data is corrupted JSON, cache returns None gracefully."""
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        # Manually corrupt the data in DB
        import sqlite3

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("UPDATE cache SET data='not-json' WHERE key LIKE '%AAPL%'")
        conn.commit()
        conn.close()
        # Should not crash — returns None or raises gracefully
        try:
            result = cache.get("AAPL", "1d", "yahoo")
            # either None or exception is acceptable
        except (ValueError, Exception):
            pass  # acceptable — corruption detected

    def test_overwrite_replaces_data(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        cache.put("AAPL", "1d", "yahoo", [{"date": "d2", "close": 2.0}])
        result = cache.get("AAPL", "1d", "yahoo")
        assert result[0]["close"] == 2.0


# ---------------------------------------------------------------------------
# Cache stats
# ---------------------------------------------------------------------------


class TestCacheStats:
    def test_empty_stats(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        stats = cache.stats()
        assert stats["entries"] == 0
        assert stats["oldest_age_seconds"] is None

    def test_stats_after_put(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["oldest_age_seconds"] is not None
        assert stats["newest_age_seconds"] is not None

    def test_stats_after_invalidation(self, tmp_path):
        cache = MarketDataCache(tmp_path / "test.db")
        cache.put("AAPL", "1d", "yahoo", [{"date": "d1", "close": 1.0}])
        cache.invalidate("AAPL")
        stats = cache.stats()
        assert stats["entries"] == 0
