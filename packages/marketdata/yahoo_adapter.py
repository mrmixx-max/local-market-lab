"""Yahoo Finance adapter — OHLCV data for stocks, crypto, and ETFs.

Uses yfinance to fetch 5-year history at 1d or 1h intervals.
Integrates with the versioned MarketDataCache for offline support.

Shared plumbing (cache key schema, retry, currency handling) lives in
packages/marketdata/base_adapter.py.
"""

from __future__ import annotations

import logging
from datetime import date

from packages.domain.entities import PriceBar, PriceSeries

from .base_adapter import (
    AdapterError,
    BaseAdapter,
    RateLimitError,  # noqa: F401  (re-exported for API compat)
    detect_currency,
)

log = logging.getLogger(__name__)

INTERVAL_MAP = {
    "1d": "1d",
    "1h": "1h",
    "1m": "1m",
    "5m": "5m",
    "1wk": "1wk",
    "1mo": "1mo",
}
RANGE_MAP = {"1h": "60d", "1m": "5d", "5m": "60d"}


class YahooAdapter(BaseAdapter):
    """Fetch OHLCV from Yahoo Finance with local caching."""

    SOURCE_NAME = "yahoo"
    DEFAULT_INTERVALS = ("1d", "1h")

    def __init__(
        self,
        cache: MarketDataCache | None = None,  # noqa: F821
        cache_path: str = "~/.local-market-lab/cache/market.db",
    ):
        from .cache import MarketDataCache as _C  # local import avoids cycle

        self.cache = cache if cache is not None else _C(cache_path)
        super().__init__(cache=self.cache, cache_path=cache_path)
        self._yf = None  # lazy-loaded

    @property
    def yf(self):
        if self._yf is None:
            try:
                import yfinance as yf
            except ImportError as exc:
                raise ImportError(
                    "YahooAdapter requires: pip install yfinance"
                ) from exc
            self._yf = yf
        return self._yf

    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        years: int = 5,
        use_cache: bool = True,
        offline: bool = False,
    ) -> PriceSeries:
        """Fetch OHLCV bars. Cache-first strategy with offline fallback.

        Currency is detected from the ticker; when it cannot be determined
        the series carries currency='unknown' and callers must treat FX
        conversion as INCOMPLETE (no silent 1:1).
        """
        if interval not in INTERVAL_MAP:
            raise ValueError(
                f"unsupported interval {interval!r}; use {list(INTERVAL_MAP)}"
            )
        sym = symbol.upper()
        currency = detect_currency(sym)
        adjusted = True  # auto_adjust=True
        period = f"{years}y" if interval == "1d" else RANGE_MAP.get(interval, "60d")
        parts = self.cache_key_parts(sym, interval, currency, adjusted, period)

        cached = self._cache_get(parts)
        if cached is not None:
            return PriceSeries(sym, currency, self.bars_from_dicts(cached)).sorted()

        if offline:
            # legacy fallback: entries written before schema versioning used
            # the simple source:symbol:interval key
            legacy = self.cache.get_offline(sym, interval, self.SOURCE_NAME)
            if legacy is None:
                raise AdapterError(
                    f"no cached data for {sym} ({interval}) in offline mode"
                )
            return PriceSeries(sym, currency, self.bars_from_dicts(legacy)).sorted()

        bars = self._download(sym, interval, years, currency)
        self._cache_put(parts, bars)
        return PriceSeries(sym, currency, bars).sorted()

    def _download(
        self, symbol: str, interval: str, years: int, currency: str
    ) -> list[PriceBar]:
        yf = self.yf
        period = f"{years}y" if interval == "1d" else RANGE_MAP.get(interval, "60d")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(
            period=period, interval=INTERVAL_MAP[interval], auto_adjust=True
        )
        if hist.empty:
            raise ValueError(f"no data returned for {symbol!r}")
        bars: list[PriceBar] = []
        for idx, row in hist.iterrows():
            d = (
                idx.date()
                if hasattr(idx, "date")
                else date.fromisoformat(str(idx)[:10])
            )
            bars.append(
                PriceBar(
                    date=d.isoformat(),
                    close=round(float(row["Close"]), 6),
                    volume=int(row["Volume"]) if row["Volume"] > 0 else None,
                )
            )
        log.info(
            "Yahoo: %s %d bars (%s, ccy=%s)", symbol, len(bars), interval, currency
        )
        return bars
