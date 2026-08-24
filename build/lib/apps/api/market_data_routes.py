"""Market data API endpoints — real adapter integration.

@experimental — external API calls, rate limits apply.

GET /api/v1/market/data/{symbol}?source=yahoo|alphavantage
GET /api/v1/quality/report/{symbol}
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from packages.domain.entities import PriceSeries
from packages.marketdata.cache import MarketDataCache
from packages.marketdata.yahoo_adapter import YahooAdapter
from packages.marketdata.alpha_vantage_adapter import AlphaVantageAdapter
from packages.quality.checks import run_quality_check

market_data_router = APIRouter(prefix="/api/v1/market", tags=["market-data"])

DEFAULT_CACHE = Path.home() / ".local-market-lab" / "cache" / "market.db"

# Symbol validation: only allow safe ticker characters (prevents path/URL injection)
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-^=]{1,20}$")


def _validate_symbol(symbol: str) -> str:
    """Validate and normalize a ticker symbol. Raises HTTPException if invalid."""
    if not symbol or not _SYMBOL_RE.match(symbol):
        raise HTTPException(400, f"invalid symbol format: {symbol!r}")
    return symbol.upper()


def _build_response(series: PriceSeries, source: str, interval: str, run_id: str) -> dict:
    """Build unified response with embedded QualityReport."""
    report = run_quality_check(series, source=source)
    if report.status == "invalid":
        # Invalidate cache on quality errors to force re-fetch next time
        cache = MarketDataCache(DEFAULT_CACHE)
        cache.invalidate_on_quality_error(series.symbol, source, interval)
    return {
        "run_id": run_id,
        "symbol": series.symbol,
        "currency": series.currency,
        "source": source,
        "interval": interval,
        "bars": [b.to_ohlcv() for b in series.bars],
        "count": len(series.bars),
        "first": series.bars[0].date if series.bars else None,
        "last": series.bars[-1].date if series.bars else None,
        **report.to_dict(),
    }


@market_data_router.get("/data/{symbol}", summary="Fetch market data from external source")
async def market_data(
    symbol: str,
    source: str = Query("yahoo", pattern="^(yahoo|alphavantage)$"),
    interval: str = Query("1d", pattern="^(1d|1h)$"),
    years: int = Query(5, ge=1, le=20),
    offline: bool = False,
):
    """Fetch OHLCV bars from Yahoo Finance or Alpha Vantage with caching.

    - **source**: 'yahoo' (default, no API key needed) or 'alphavantage' (needs ALPHAVANTAGE_KEY)
    - **interval**: '1d' (5y history) or '1h' (60d history, Yahoo-only)
    - **years**: number of years for daily data (1-20)
    - **offline**: return cached data only, no network calls

    Returns unified OHLCV format with embedded data_quality report.
    """
    # Validate symbol to prevent URL/path injection
    symbol = _validate_symbol(symbol)
    
    run_id = str(uuid.uuid4())[:8]
    cache = MarketDataCache(DEFAULT_CACHE)
    try:
        if source == "yahoo":
            adapter = YahooAdapter(cache=cache)
            series = adapter.fetch(symbol, interval=interval, years=years, offline=offline)
        elif source == "alphavantage":
            if interval != "1d":
                raise HTTPException(400, "alphavantage only supports daily interval")
            adapter = AlphaVantageAdapter(cache=cache)
            series = adapter.fetch(symbol, offline=offline)
        else:
            raise HTTPException(400, f"unknown source: {source}")
    except ImportError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return _build_response(series, source, interval, run_id)


@market_data_router.get("/quality/report/{symbol}", summary="Run data quality checks on cached or fetched data")
async def quality_report(
    symbol: str,
    source: str = Query("yahoo", pattern="^(yahoo|alphavantage)$"),
    interval: str = "1d",
    expected_ccy: str | None = None,
):
    """Run quality checks (missing data, splits, FX, timestamps, outliers) on a symbol.

    Fetches data if not already cached, then runs the full quality suite.
    Returns unified QualityReport with status, issues, and score.
    """
    # Validate symbol to prevent URL/path injection
    symbol = _validate_symbol(symbol)
    
    run_id = str(uuid.uuid4())[:8]
    cache = MarketDataCache(DEFAULT_CACHE)
    try:
        if source == "yahoo":
            adapter = YahooAdapter(cache=cache)
            series = adapter.fetch(symbol, interval=interval, years=5)
        else:
            adapter = AlphaVantageAdapter(cache=cache)
            series = adapter.fetch(symbol)
    except ImportError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    ccy = expected_ccy or series.currency or ("USD" if source == "alphavantage" else "USD")
    report = run_quality_check(series, expected_ccy=ccy, source=source)
    return {"run_id": run_id, "symbol": symbol.upper(), **report.to_dict()}


@market_data_router.get("/cache/stats", summary="Cache statistics")
async def cache_stats():
    """Return cache entry count, TTL, and age statistics."""
    cache = MarketDataCache(DEFAULT_CACHE)
    return cache.stats()


@market_data_router.delete("/cache", summary="Invalidate cache entries")
async def cache_invalidate(symbol: str | None = None):
    """Invalidate cache for a symbol or all entries."""
    if symbol:
        # Validate symbol to prevent URL/path injection
        symbol = _validate_symbol(symbol)
    cache = MarketDataCache(DEFAULT_CACHE)
    n = cache.invalidate(symbol)
    return {"invalidated": n}
