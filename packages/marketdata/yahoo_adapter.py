"""Yahoo Finance adapter — OHLCV data for stocks, crypto, and ETFs.

Uses yfinance to fetch 5-year history at 1d or 1h intervals.
Integrates with MarketDataCache for offline support.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from packages.domain.entities import PriceBar, PriceSeries

from .cache import MarketDataCache

log = logging.getLogger(__name__)

INTERVAL_MAP = {"1d": "1d", "1h": "1h", "1m": "1m", "5m": "5m", "1wk": "1wk", "1mo": "1mo"}
RANGE_MAP = {"1h": "60d", "1m": "5d", "5m": "60d"}


class YahooAdapter:
    """Fetch OHLCV from Yahoo Finance with local caching."""

    SOURCE_NAME = "yahoo"
    DEFAULT_INTERVALS = ("1d", "1h")

    def __init__(
        self,
        cache: MarketDataCache | None = None,
        cache_path: str = "~/.local-market-lab/cache/market.db",
    ):
        self.cache = cache or MarketDataCache(cache_path)
        self._yf = None  # lazy-loaded

    @property
    def yf(self):
        if self._yf is None:
            try:
                import yfinance as yf
            except ImportError as exc:
                raise ImportError("YahooAdapter requires: pip install yfinance") from exc
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

        Args:
            symbol: ticker symbol (e.g. 'AAPL', 'BTC-USD', 'IWDA.AS')
            interval: '1d' or '1h' (1h limited to 60 days by Yahoo)
            years: number of years of history (only applies to 1d)
            use_cache: whether to read from cache
            offline: skip network, return cached data only
        """
        if interval not in INTERVAL_MAP:
            raise ValueError(f"unsupported interval {interval!r}; use {list(INTERVAL_MAP)}")
        sym = symbol.upper()
        if use_cache and not offline:
            cached = self.cache.get(sym, interval, self.SOURCE_NAME)
            if cached is not None:
                return self._from_cached(sym, cached)
        if offline:
            cached = self.cache.get_offline(sym, interval, self.SOURCE_NAME)
            if cached is None:
                raise RuntimeError(f"no cached data for {sym} ({interval}) in offline mode")
            return self._from_cached(sym, cached)
        bars = self._download(sym, interval, years)
        self.cache.put(sym, interval, self.SOURCE_NAME, [b.__dict__ for b in bars], quality_status="unchecked")
        return PriceSeries(sym, self._detect_currency(bars), bars).sorted()

    def _download(self, symbol: str, interval: str, years: int) -> list[PriceBar]:
        yf = self.yf

        if interval == "1d":
            period = f"{years}y"
        else:
            period = RANGE_MAP.get(interval, "60d")

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=INTERVAL_MAP[interval], auto_adjust=True)
        if hist.empty:
            raise ValueError(f"no data returned for {symbol!r}")
        bars: list[PriceBar] = []
        for idx, row in hist.iterrows():
            d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            bars.append(
                PriceBar(
                    date=d.isoformat(),
                    close=round(float(row["Close"]), 6),
                    volume=int(row["Volume"]) if row["Volume"] > 0 else None,
                )
            )
        log.info("Yahoo: %s %d bars (%s)", symbol, len(bars), interval)
        return bars

    @staticmethod
    def _detect_currency(bars: list[PriceBar]) -> str:
        return "USD"  # simplified; real impl reads ticker.info.currency

    @staticmethod
    def _from_cached(symbol: str, data: list[dict]) -> PriceSeries:
        return PriceSeries(
            symbol=symbol,
            currency="USD",
            bars=[PriceBar(d["date"], d["close"], d.get("volume")) for d in data],
        ).sorted()
