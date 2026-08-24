"""Data quality checks for market price series.

Checks: missing data, splits, FX consistency, timestamps, outliers.
Returns structured reports — never silently fixes issues.

Configuration via environment variables:
  LML_QUALITY_MISSING_THRESHOLD (default 0.05) — >5% missing → warning
  LML_QUALITY_STALE_HOURS (default 24) — data age threshold
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timedelta, timezone

import numpy as np

from packages.domain.entities import PriceSeries, QualityReport


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


MISSING_THRESHOLD = _env_float("LML_QUALITY_MISSING_THRESHOLD", 0.05)
STALE_HOURS = _env_int("LML_QUALITY_STALE_HOURS", 24)


def check_missing_data(series: PriceSeries, max_gap_days: int = 5) -> tuple[int, list[str]]:
    """Detect business-day gaps exceeding threshold."""
    dates = sorted(date.fromisoformat(b.date) for b in series.bars)
    if len(dates) < 2:
        return 0, []
    missing = []
    for a, b in zip(dates, dates[1:]):
        gap = (b - a).days
        weekdays = sum(1 for i in range(1, gap) if (a + timedelta(days=i)).weekday() < 5)
        if weekdays > max_gap_days:
            missing.append(b.isoformat())
    return len(missing), missing


def check_splits(series: PriceSeries, threshold: float = 0.4) -> tuple[bool, list[dict]]:
    """Detect potential splits/reverse splits via daily return jumps."""
    bars = sorted(series.bars, key=lambda b: b.date)
    candidates = []
    for prev, curr in zip(bars, bars[1:]):
        if prev.close <= 0:
            continue
        change = (curr.close - prev.close) / prev.close
        if abs(change) > threshold:
            candidates.append({
                "date": curr.date,
                "prev_close": prev.close,
                "curr_close": curr.close,
                "change_pct": round(change * 100, 1),
            })
    return len(candidates) > 0, candidates


def check_fx_consistency(series: PriceSeries, expected_ccy: str = "USD") -> tuple[bool, list[str]]:
    """Flag if series currency mismatches expected."""
    issues = []
    if series.currency and series.currency != expected_ccy:
        issues.append(f"currency mismatch: series={series.currency}, expected={expected_ccy}")
    return len(issues) > 0, issues


def check_timestamps(series: PriceSeries) -> tuple[list[str], int]:
    """Validate date format, ordering, duplicates, and future dates."""
    issues = []
    today = date.today()
    seen = set()
    dupes = 0
    prev = None
    for bar in series.bars:
        try:
            d = date.fromisoformat(bar.date)
        except ValueError:
            issues.append(f"invalid date format: {bar.date!r}")
            continue
        if bar.date in seen:
            dupes += 1
        seen.add(bar.date)
        if d > today:
            issues.append(f"future date: {bar.date}")
        if prev and d <= prev and dupes == 0:
            issues.append(f"non-monotonic: {prev.isoformat()} -> {bar.date}")
        prev = d
    return issues, dupes


def check_stale(series: PriceSeries, max_hours: int = STALE_HOURS) -> bool:
    """Check if the most recent bar is older than max_hours."""
    bars = sorted(series.bars, key=lambda b: b.date)
    if not bars:
        return True
    last = date.fromisoformat(bars[-1].date)
    return (datetime.now(timezone.utc).date() - last).days * 24 > max_hours


def detect_outliers(series: PriceSeries, z_threshold: float = 4.0) -> tuple[int, list[dict]]:
    """Detect price outliers using z-score of log returns."""
    bars = sorted(series.bars, key=lambda b: b.date)
    closes = np.array([b.close for b in bars], dtype=float)
    if len(closes) < 3:
        return 0, []
    log_rets = np.diff(np.log(closes))
    mu, sigma = float(np.mean(log_rets)), float(np.std(log_rets))
    if sigma == 0:
        return 0, []
    outliers = []
    for i, r in enumerate(log_rets):
        z = abs((r - mu) / sigma)
        if z > z_threshold:
            outliers.append({
                "date": bars[i + 1].date,
                "close": bars[i + 1].close,
                "log_return": round(float(r), 5),
                "z_score": round(float(z), 2),
            })
    return len(outliers), outliers


def run_quality_check(
    series: PriceSeries,
    expected_ccy: str = "USD",
    max_gap_days: int = 5,
    split_threshold: float = 0.4,
    z_threshold: float = 4.0,
    source: str = "unknown",
) -> QualityReport:
    """Run all quality checks and return a unified domain QualityReport."""
    n = len(series.bars)
    missing_count, _ = check_missing_data(series, max_gap_days)
    split_detected, split_cands = check_splits(series, split_threshold)
    fx_mismatch, fx_issues = check_fx_consistency(series, expected_ccy)
    ts_issues, dupes = check_timestamps(series)
    stale = check_stale(series)
    outlier_count, _ = detect_outliers(series, z_threshold)
    # Build issues list and status
    issues = []
    status = "valid"
    if missing_count / max(n, 1) > MISSING_THRESHOLD:
        issues.append(f"missing data: {missing_count} bars exceed {MISSING_THRESHOLD*100:.0f}%")
        status = "warning"
    if dupes > 0:
        issues.append(f"{dupes} duplicate timestamps")
        status = "invalid"
    if stale:
        issues.append(f"stale data: last bar >{STALE_HOURS}h old")
        status = "warning" if status == "valid" else status
    if split_detected:
        issues.append(f"{len(split_cands)} potential split(s)")
    if fx_mismatch:
        issues.extend(fx_issues)
    if ts_issues:
        issues.extend(ts_issues[:5])
        status = "invalid"
    if outlier_count > 0:
        issues.append(f"{outlier_count} price outlier(s)")
    missing_ratio = missing_count / max(n, 1)
    penalties = [
        min(missing_ratio * 2, 0.3), 0.2 if split_detected else 0.0,
        0.15 if fx_mismatch else 0.0, min(len(ts_issues) * 0.05, 0.3),
        0.3 if dupes > 0 else 0.0, 0.1 if stale else 0.0,
        min(outlier_count * 0.03, 0.25),
    ]
    score = max(0.0, 1.0 - sum(penalties))
    data_hash = hashlib.sha256("".join(b.date + str(b.close) for b in series.bars).encode()).hexdigest()[:16]
    return QualityReport(
        symbol=series.symbol, status=status, missing_values=missing_count,
        duplicate_timestamps=dupes, stale_data=stale, source=source,
        data_hash=data_hash, timestamp=datetime.now(timezone.utc).isoformat(),
        score=score, issues=issues,
    )
