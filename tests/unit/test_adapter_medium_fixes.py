"""Regression tests for the v0.9.1 medium-fix batch:

1. Adapter currency detection — no silent 1:1 FX, unknown stays 'unknown'.
2. Consolidated adapters — shared BaseAdapter, API compatibility kept.
3. Cache versioning — schema changes invalidate, corrupt entries purge.
4. Alpha Vantage key in header — never in URL/logs/errors.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from packages.marketdata.base_adapter import (
    CACHE_SCHEMA_VERSION,
    AdapterError,
    BaseAdapter,
    RateLimitError,
    detect_currency,
)
from packages.marketdata.cache import MarketDataCache


# ---------------------------------------------------------------------
# 1. Currency detection / FX policy
# ---------------------------------------------------------------------

class TestCurrencyDetection:
    @pytest.mark.parametrize("symbol,expected", [
        ("BTC-EUR", "EUR"),
        ("AAPL", "unknown"),
        ("SAP.DE", "EUR"),
        ("IWDA.AS", "EUR"),
        ("AIR.PA", "EUR"),
        ("ENEL.MI", "EUR"),
        ("HSBA.L", "GBp"),      # LSE quotes in pence — intentionally NOT GBP
        ("NESN.SW", "CHF"),
        ("7203.T", "JPY"),
    ])
    def test_known_markers(self, symbol, expected):
        assert detect_currency(symbol) == expected

    def test_unknown_is_explicit(self):
        # bare US ticker: must be 'unknown', never a guessed default
        assert detect_currency("MSFT") == "unknown"

    def test_series_carries_currency(self):
        from packages.domain.entities import PriceBar
        adapter = _DummyAdapter()
        s = adapter.make_series("sap.de", [PriceBar("2024-01-02", 100.0)], "eur")
        assert s.currency == "EUR"
        assert s.symbol == "SAP.DE"


class _DummyAdapter(BaseAdapter):
    SOURCE_NAME = "dummy"


# ---------------------------------------------------------------------
# 2/3. Versioned cache
# ---------------------------------------------------------------------

class TestVersionedCache:
    def test_hit_miss_roundtrip(self, tmp_path):
        c = MarketDataCache(tmp_path / "c.db")
        parts = {"provider": "yahoo", "symbol": "AAPL", "interval": "1d",
                 "period": "5y", "currency": "USD", "adjusted": True,
                 "schema": CACHE_SCHEMA_VERSION}
        flat = "|".join(f"{k}={v}" for k, v in sorted(parts.items()))
        assert c.get_versioned(flat) is None            # miss
        c.put_versioned(flat, [{"date": "2024-01-02", "close": 1.0}])
        assert c.get_versioned(flat) is not None         # hit

    def test_schema_change_invalidates(self, tmp_path):
        c = MarketDataCache(tmp_path / "c.db")
        old_key = "adjusted=True|currency=USD|interval=1d|provider=yahoo|schema=1|symbol=AAPL"
        new_key = old_key.replace("schema=1", f"schema={CACHE_SCHEMA_VERSION}")
        c.put_versioned(old_key, [{"date": "2024-01-02", "close": 1.0}])
        # new schema key must MISS even though data exists under the old key
        assert c.get_versioned(new_key) is None
        # and the old-schema purge removes it
        removed = c.purge_old_schema(CACHE_SCHEMA_VERSION)
        assert removed == 1

    def test_corrupt_entry_purged_not_raised(self, tmp_path):
        db = tmp_path / "c.db"
        MarketDataCache(db)
        key = "corrupt-test-entry"
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO cache(key,data,created_at,quality_status) VALUES(?,?,?,?)",
            (key, "{not valid json", __import__("time").time(), "unchecked"))
        conn.commit(); conn.close()
        c = MarketDataCache(db)
        assert c.get_versioned(key) is None              # None + purged, no crash

    def test_ttl_respected(self, tmp_path):
        import time as _t
        c = MarketDataCache(tmp_path / "c.db", ttl=1)
        key = "ttl-key"
        c.put_versioned(key, [{"date": "2024-01-02", "close": 1.0}])
        assert c.get_versioned(key) is not None
        # age the entry artificially beyond TTL
        conn = sqlite3.connect(tmp_path / "c.db")
        conn.execute("UPDATE cache SET created_at=?", (_t.time() - 3600,))
        conn.commit(); conn.close()
        assert c.get_versioned(key) is None              # expired -> miss
        assert c.get_versioned(key, respect_ttl=False) is not None  # offline override


# ---------------------------------------------------------------------
# 4. AV key handling + retry behavior
# ---------------------------------------------------------------------

class TestApiKeySecurity:
    def test_missing_key_raises_clearly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ALPHAVANTAGE_KEY", raising=False)
        with pytest.raises(ValueError, match="ALPHAVANTAGE_KEY"):
            from packages.marketdata.alpha_vantage_adapter import AlphaVantageAdapter
            AlphaVantageAdapter(cache_path=str(tmp_path / "c.db"))

    def test_key_never_in_url(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ALPHAVANTAGE_KEY", "SECRETKEY123")
        from packages.marketdata.alpha_vantage_adapter import AlphaVantageAdapter
        a = AlphaVantageAdapter(cache_path=str(tmp_path / "c.db"))
        captured = {}

        def fake_request_with_retry(url, headers=None, timeout=30):
            captured["url"] = url
            captured["headers"] = headers
            return b"{}"

        monkeypatch.setattr(a, "request_with_retry", fake_request_with_retry)
        with pytest.raises(ValueError):
            a._download("IBM", "compact")   # empty payload -> ValueError
        assert "SECRETKEY123" not in captured["url"]
        assert captured["headers"]["apikey"] == "SECRETKEY123"


class TestRetryBackoff:
    def test_exhaustion_raises_ratelimit(self, tmp_path, monkeypatch):
        import urllib.error
        a = _DummyAdapter(cache_path=str(tmp_path / "c.db"),
                          max_retries=2, retry_base_delay=0)
        calls = {"n": 0}

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 429, "slow down",
                                         hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(RateLimitError):
            a.request_with_retry("https://example.invalid/x")
        assert calls["n"] == 2

    def test_http_404_raises_immediately(self, tmp_path, monkeypatch):
        import urllib.error
        a = _DummyAdapter(cache_path=str(tmp_path / "c.db"),
                          max_retries=3, retry_base_delay=0)
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 404, "nope",
                                         hdrs=None, fp=None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(AdapterError):
            a.request_with_retry("https://example.invalid/x")
        assert calls["n"] == 1  # non-429 -> no retry
