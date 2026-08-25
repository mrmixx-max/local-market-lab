"""Market data adapters — pluggable sources with explicit license tracking.

Built-in adapters:
  - SyntheticAdapter: seeded random walk (default, no external calls)
  - YahooAdapter: Yahoo Finance via yfinance (optional dep)
  - AlphaVantageAdapter: Alpha Vantage API (requires API key)

Each adapter returns PriceSeries with full provenance metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta

from packages.domain.entities import PriceBar, PriceSeries


@dataclass
class DataSource:
    name: str
    url: str | None = None
    license: str = "unknown"
    attribution: str = ""
    rate_limit: str = "unknown"
    requires_key: bool = False
    notes: str = ""


@dataclass
class FetchResult:
    series: PriceSeries
    source: DataSource
    raw_path: str | None = None


class SyntheticAdapter:
    """Seeded geometric random walk. The default — no network needed."""

    SOURCE = DataSource(
        name="synthetic-seeded",
        license="public-domain",
        notes="Deterministic random walk — for testing and demos only.",
    )

    def __init__(self, seed: int = 42):
        self.seed = seed

    def fetch(
        self,
        symbol: str,
        days: int = 504,
        start_price: float = 100.0,
        vol: float = 0.01,
    ) -> FetchResult:
        rng = self._rng(symbol)
        px = start_price
        d0 = date.today() - timedelta(days=days)
        bars = []
        for i in range(days):
            d = d0 + timedelta(days=i)
            if d.weekday() < 5:
                px *= 1 + rng.gauss(0.0003, vol)
                bars.append(PriceBar(date=d.isoformat(), close=round(px, 4)))
        series = PriceSeries(symbol.upper(), "EUR", bars).sorted()
        return FetchResult(series=series, source=self.SOURCE)

    def _rng(self, symbol: str):
        import random

        return random.Random(hash(symbol) % 2**31 + self.seed)


class YahooAdapter:
    """Yahoo Finance via yfinance. Requires: pip install yfinance"""

    SOURCE = DataSource(
        name="yahoo-finance",
        url="https://finance.yahoo.com",
        license="Yahoo Terms of Service — non-commercial, no redistribution",
        attribution="Data © Yahoo Finance",
        rate_limit="~2000 requests/hour (unauthenticated)",
        notes="For personal/research use. Check Yahoo's ToS before any redistribution.",
    )

    def fetch(self, symbol: str, days: int = 504) -> FetchResult:
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yahoo adapter requires: pip install yfinance")

        end = date.today()
        start = end - timedelta(days=int(days * 1.5))  # buffer for weekends
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=True
        )
        if hist.empty:
            raise ValueError(f"no data returned for {symbol!r}")

        bars = []
        for idx, row in hist.iterrows():
            d = (
                idx.date()
                if hasattr(idx, "date")
                else date.fromisoformat(str(idx)[:10])
            )
            bars.append(PriceBar(date=d.isoformat(), close=float(row["Close"])))

        series = PriceSeries(symbol.upper(), "EUR", bars).sorted()
        return FetchResult(series=series, source=self.SOURCE)


class AlphaVantageAdapter:
    """Alpha Vantage daily prices. Requires ALPHAVANTAGE_KEY env var."""

    SOURCE = DataSource(
        name="alpha-vantage",
        url="https://www.alphavantage.co",
        license="Alpha Vantage Terms — free tier: 25 req/day",
        attribution="Data © Alpha Vantage",
        rate_limit="25 requests/day (free), 75 (premium)",
        requires_key=True,
        notes="Requires ALPHAVANTAGE_KEY environment variable.",
    )

    def fetch(self, symbol: str) -> FetchResult:
        import urllib.request

        api_key = os.environ.get("ALPHAVANTAGE_KEY")
        if not api_key:
            raise ValueError("ALPHAVANTAGE_KEY not set")

        url = (
            f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED"
            f"&symbol={symbol.upper()}&apikey={api_key}&outputsize=full&datatype=json"
        )
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)

        key = "Time Series (Daily)"
        if key not in data:
            raise ValueError(f"unexpected response: {list(data.keys())}")

        bars = []
        for d, row in data[key].items():
            bars.append(PriceBar(date=d, close=float(row["5. adjusted close"])))

        series = PriceSeries(symbol.upper(), "EUR", bars).sorted()
        return FetchResult(series=series, source=self.SOURCE)


# ---------- adapter registry ----------
ADAPTERS: dict[str, type] = {
    "synthetic": SyntheticAdapter,
    "yahoo": YahooAdapter,
    "alphavantage": AlphaVantageAdapter,
}


def get_adapter(
    name: str = "synthetic", **kwargs
) -> SyntheticAdapter | YahooAdapter | AlphaVantageAdapter:
    cls = ADAPTERS.get(name)
    if cls is None:
        raise ValueError(
            f"unknown adapter {name!r}. available: {list(ADAPTERS.keys())}"
        )
    return cls(**kwargs)


def import_prices_to_ws(ws, symbol: str, adapter: str = "synthetic", **kwargs) -> dict:
    """Fetch prices via adapter and upsert into the workspace."""
    a = get_adapter(adapter, **kwargs)
    result = a.fetch(symbol, **kwargs)
    for bar in result.series.bars:
        ws.upsert_price(symbol.upper(), bar.date, bar.close, source=result.source.name)
    ws.commit_prices()
    return {
        "symbol": symbol.upper(),
        "source": result.source.name,
        "license": result.source.license,
        "points": len(result.series.bars),
        "first": result.series.bars[0].date if result.series.bars else None,
        "last": result.series.bars[-1].date if result.series.bars else None,
    }


import json  # for AlphaVantage
