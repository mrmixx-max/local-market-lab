"""Alpha Vantage adapter — API-key-based with rate-limit handling.

Free tier: 25 requests/day. Premium: 75/min.
Implements exponential backoff on 429 responses.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

from packages.domain.entities import PriceBar, PriceSeries

from .cache import MarketDataCache

log = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 12  # seconds between free-tier requests


class RateLimitError(Exception):
    """Raised when rate limit is exceeded and retries exhausted."""


class AlphaVantageAdapter:
    """Fetch daily OHLCV from Alpha Vantage with rate-limit awareness."""

    SOURCE_NAME = "alphavantage"

    def __init__(
        self,
        api_key: str | None = None,
        cache: MarketDataCache | None = None,
        cache_path: str = "~/.local-market-lab/cache/market.db",
    ):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_KEY")
        if not self.api_key:
            raise ValueError(
                "AlphaVantageAdapter requires api_key or ALPHAVANTAGE_KEY env var"
            )
        self.cache = cache or MarketDataCache(cache_path)
        self._last_request_ts = 0.0

    def fetch(
        self,
        symbol: str,
        interval: str = "daily",
        output_size: str = "full",
        use_cache: bool = True,
        offline: bool = False,
    ) -> PriceSeries:
        """Fetch daily adjusted OHLCV from Alpha Vantage.

        Args:
            symbol: ticker (e.g. 'IBM', 'MSFT')
            interval: only 'daily' supported
            output_size: 'compact' (100 bars) or 'full' (20+ years)
            use_cache: read from cache if fresh
            offline: skip network, use cached data only
        """
        sym = symbol.upper()
        if use_cache and not offline:
            cached = self.cache.get(sym, interval, self.SOURCE_NAME)
            if cached is not None:
                return self._from_cached(sym, cached)
        if offline:
            cached = self.cache.get_offline(sym, interval, self.SOURCE_NAME)
            if cached is None:
                raise RuntimeError(f"no cached data for {sym} in offline mode")
            return self._from_cached(sym, cached)
        bars = self._download(sym, output_size)
        self.cache.put(sym, interval, self.SOURCE_NAME, [b.__dict__ for b in bars], quality_status="unchecked")
        return PriceSeries(sym, "USD", bars).sorted()

    def _download(self, symbol: str, output_size: str) -> list[PriceBar]:
        url = (
            f"{BASE_URL}?function=TIME_SERIES_DAILY_ADJUSTED"
            f"&symbol={symbol}&apikey={self.api_key}"
            f"&outputsize={output_size}&datatype=json"
        )
        data = self._request_with_retry(url)
        key = "Time Series (Daily)"
        if key not in data:
            note = data.get("Note") or data.get("Information", "")
            raise ValueError(f"unexpected response: {note or list(data.keys())}")
        bars = []
        for d, row in data[key].items():
            bars.append(
                PriceBar(
                    date=d,
                    close=round(float(row["5. adjusted close"]), 6),
                    volume=int(row.get("6. volume", 0)),
                )
            )
        log.info("AlphaVantage: %s %d bars", symbol, len(bars))
        return bars

    def _request_with_retry(self, url: str) -> dict:
        """GET with rate-limit backoff. Respects free-tier spacing."""
        for attempt in range(MAX_RETRIES):
            elapsed = time.time() - self._last_request_ts
            if elapsed < RETRY_BASE_DELAY:
                wait = RETRY_BASE_DELAY - elapsed
                log.debug("rate-limit wait: %.1fs", wait)
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self._last_request_ts = time.time()
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                self._last_request_ts = time.time()
                if exc.code == 429:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    log.warning("rate limited, retry in %ds (attempt %d)", delay, attempt + 1)
                    time.sleep(delay)
                    continue
                raise
        raise RateLimitError(f"rate limit exceeded after {MAX_RETRIES} retries")

    @staticmethod
    def _from_cached(symbol: str, data: list[dict]) -> PriceSeries:
        return PriceSeries(
            symbol=symbol,
            currency="USD",
            bars=[PriceBar(d["date"], d["close"], d.get("volume")) for d in data],
        ).sorted()
