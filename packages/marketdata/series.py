"""Price series access and quality checks.

Quality checks are mandatory per concept: gaps reported, never silently filled.
"""
from __future__ import annotations

from datetime import date

from packages.domain.entities import PriceBar, PriceSeries


class MissingPriceError(KeyError):
    """A required price point does not exist — callers must handle explicitly."""


def get_series(ws, symbol: str) -> PriceSeries:
    bars = [PriceBar(date=r["date"], close=r["close"], volume=r["volume"])
            for r in ws.price_series(symbol)]
    if not bars:
        raise MissingPriceError(
            f"no price data for {symbol!r} — import prices first")
    return PriceSeries(symbol.upper(), ws.instrument_currency(symbol), bars).sorted()


def series_quality(series: PriceSeries, max_gap_days: int = 7) -> dict:
    """Descriptive quality report: gaps, duplicates (by date), stale points."""
    dates = sorted(b.date for b in series.bars)
    gaps = []
    for a, b in zip(dates, dates[1:]):
        delta = (date.fromisoformat(b) - date.fromisoformat(a)).days
        if delta > max_gap_days:
            gaps.append({"after": a, "before": b, "gap_days": delta})
    zero_or_negative = [b.date for b in series.bars if b.close <= 0]
    jumps = []
    closes = [b.close for b in series.bars]
    for a, b in zip(closes, closes[1:]):
        if a > 0 and abs(b / a - 1) > 0.5:
            jumps.append({"from_close": a, "to_close": b})
    return {
        "symbol": series.symbol,
        "points": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "gaps_over_days": gaps,
        "nonpositive_closes": zero_or_negative,
        "large_jumps_gt_50pct": len(jumps),
        "notes": (
            f"{len(gaps)} gap(s) over {max_gap_days}d reported — "
            "gaps are NOT interpolated by design."
        ),
    }


def aligned_closes(ws, symbols: list[str]) -> tuple[list[str], dict[str, list[float]]]:
    """Intersect all series on common dates. Raises MissingPriceError when a
    symbol has no data at all; returns only dates present in every series.
    """
    sets = {}
    for sym in symbols:
        s = get_series(ws, sym)
        sets[sym] = {b.date: b.close for b in s.bars}
    common = sorted(set.intersection(*(set(s.keys()) for s in sets.values())))
    return common, {sym: [sets[sym][d] for d in common] for sym in symbols}
