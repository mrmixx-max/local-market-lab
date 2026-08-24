"""Alpha Vantage adapter — API-key-based with rate-limit handling.

Free tier: 25 requests/day. Premium: 75/min.
Exponential backoff on 429 responses (inherited from BaseAdapter).

Security: the API key is sent ONLY via the ``apikey`` HTTP header —
never in the URL query string, never logged, never embedded in error
messages or exported metadata.
"""
from __future__ import annotations

import json
import logging
import os

from packages.domain.entities import PriceBar

from .base_adapter import AdapterError, BaseAdapter, RateLimitError, detect_currency  # noqa: F401

log = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"
REQUEST_SPACING = 12  # seconds between free-tier requests


class AlphaVantageAdapter(BaseAdapter):
    """Fetch daily adjusted OHLCV from Alpha Vantage with cache."""

    SOURCE_NAME = "alphavantage"

    def __init__(
        self,
        api_key: str | None = None,
        cache_path: str = "~/.local-market-lab/cache/market.db",
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_KEY")
        if not self.api_key:
            raise ValueError(
                "AlphaVantageAdapter requires api_key or ALPHAVANTAGE_KEY env var"
            )
        super().__init__(cache_path=cache_path, **kwargs)
        self._last_request_ts = 0.0

    def fetch(self, symbol: str, output_size: str = "full",
              offline: bool = False) -> "PriceSeries":
        """Fetch daily adjusted OHLCV from Alpha Vantage.

        Args:
            symbol: ticker (e.g. 'IBM', 'MSFT')
            output_size: 'compact' (100 bars) or 'full' (20+ years)
            offline: skip network, use cached data only
        """
        from packages.domain.entities import PriceSeries

        sym = symbol.upper()
        currency = detect_currency(sym)
        parts = self.cache_key_parts(sym, "daily", currency, True, output_size)

        cached = self._cache_get(parts)
        if cached is not None:
            return PriceSeries(sym, currency, self.bars_from_dicts(cached)).sorted()

        if offline:
            # legacy fallback: pre-schema entries use the simple composite key
            legacy = self.cache.get_offline(sym, "daily", self.SOURCE_NAME)
            if legacy is None:
                raise AdapterError(f"no cached data for {sym} in offline mode")
            return PriceSeries(sym, currency, self.bars_from_dicts(legacy)).sorted()

        bars = self._download(sym, output_size)
        self._cache_put(parts, bars)
        return PriceSeries(sym, currency, bars).sorted()

    def _download(self, symbol: str, output_size: str) -> list[PriceBar]:
        # API key goes in the HEADER, not the URL — keeps it out of server
        # logs, proxies and any exception text containing the URL.
        url = (
            f"{BASE_URL}?function=TIME_SERIES_DAILY_ADJUSTED"
            f"&symbol={symbol}&outputsize={output_size}&datatype=json"
        )
        raw = self._throttled_get(url)
        data = json.loads(raw)
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

    def _throttled_get(self, url: str) -> bytes:
        import time as _t
        elapsed = _t.time() - self._last_request_ts
        if elapsed < REQUEST_SPACING:
            wait = REQUEST_SPACING - elapsed
            log.debug("rate-limit wait: %.1fs", wait)
            _t.sleep(wait)
        try:
            out = self.request_with_retry(url, headers={"apikey": self.api_key})
        finally:
            self._last_request_ts = _t.time()
        return out
