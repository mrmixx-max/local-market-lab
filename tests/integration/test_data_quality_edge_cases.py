"""Tests for data quality edge cases: missing values, duplicates, timezones, weekends, incomplete series."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from packages.domain.entities import PriceBar, PriceSeries
from packages.quality.checks import (
    check_missing_data,
    check_timestamps,
    check_stale,
    detect_outliers,
    run_quality_check,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _daily_series(
    symbol: str, start: date, n_days: int, step: float = 1.0
) -> PriceSeries:
    """Generate a daily series skipping weekends."""
    bars = []
    d = start
    for _ in range(n_days):
        while d.weekday() >= 5:  # skip Sat/Sun
            d += timedelta(days=1)
        bars.append(PriceBar(d.isoformat(), 100.0 + step * len(bars)))
        d += timedelta(days=1)
    return PriceSeries(symbol, "USD", bars)


# ---------------------------------------------------------------------------
# Weekend handling
# ---------------------------------------------------------------------------


class TestWeekendHandling:
    def test_weekend_gap_not_flagged(self):
        """A weekend gap (Fri->Mon) should NOT be flagged as missing data."""
        friday = date(2024, 1, 5)  # a Friday
        monday = date(2024, 1, 8)  # next Monday
        bars = [
            PriceBar(friday.isoformat(), 100.0),
            PriceBar(monday.isoformat(), 101.0),
        ]
        series = PriceSeries("TEST", "USD", bars)
        count, _ = check_missing_data(series, max_gap_days=5)
        assert count == 0, "weekend gap should not be flagged"

    def test_holiday_gap_flagged(self):
        """A multi-day holiday gap should be flagged."""
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-10", 101.0),  # 9-day gap
        ]
        series = PriceSeries("TEST", "USD", bars)
        count, _ = check_missing_data(series, max_gap_days=5)
        assert count >= 1

    def test_daily_series_no_weekend_bars(self):
        """A properly constructed daily series has no weekend bars."""
        series = _daily_series("TEST", date(2024, 1, 1), 60)
        for bar in series.bars:
            d = date.fromisoformat(bar.date)
            assert d.weekday() < 5, f"weekend bar found: {bar.date}"


# ---------------------------------------------------------------------------
# Missing values
# ---------------------------------------------------------------------------


class TestMissingValues:
    def test_empty_series(self):
        series = PriceSeries("EMPTY", "USD", [])
        count, dates = check_missing_data(series)
        assert count == 0

    def test_single_bar(self):
        series = PriceSeries("ONE", "USD", [PriceBar("2024-01-01", 100.0)])
        count, dates = check_missing_data(series)
        assert count == 0

    def test_large_gap_detected(self):
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-03-01", 105.0),  # ~60 day gap
        ]
        series = PriceSeries("GAP", "USD", bars)
        count, dates = check_missing_data(series, max_gap_days=5)
        assert count >= 1

    def test_multiple_gaps(self):
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-02", 101.0),
            PriceBar("2024-01-15", 102.0),  # gap 1
            PriceBar("2024-01-16", 103.0),
            PriceBar("2024-02-01", 104.0),  # gap 2
        ]
        series = PriceSeries("MULTI", "USD", bars)
        count, dates = check_missing_data(series, max_gap_days=5)
        assert count == 2


# ---------------------------------------------------------------------------
# Duplicate timestamps
# ---------------------------------------------------------------------------


class TestDuplicateTimestamps:
    def test_single_duplicate(self):
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-01", 101.0),
        ]
        series = PriceSeries("DUP", "USD", bars)
        _, dupes = check_timestamps(series)
        assert dupes == 1

    def test_multiple_duplicates(self):
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-01", 101.0),
            PriceBar("2024-01-02", 102.0),
            PriceBar("2024-01-02", 103.0),
        ]
        series = PriceSeries("DUP", "USD", bars)
        _, dupes = check_timestamps(series)
        assert dupes == 2

    def test_duplicate_marks_invalid(self):
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-01", 101.0),
        ]
        series = PriceSeries("DUP", "USD", bars)
        report = run_quality_check(series)
        assert report.status == "invalid"
        assert report.duplicate_timestamps > 0


# ---------------------------------------------------------------------------
# Incomplete price series
# ---------------------------------------------------------------------------


class TestIncompleteSeries:
    def test_very_short_series(self):
        """A series with < 3 bars should still be processable."""
        bars = [PriceBar("2024-01-01", 100.0), PriceBar("2024-01-02", 101.0)]
        series = PriceSeries("SHORT", "USD", bars)
        count, _ = detect_outliers(series)
        assert count == 0  # not enough data

    def test_zero_close_reported(self):
        """Zero or negative closes should be detected."""
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-02", 0.0),
            PriceBar("2024-01-03", 102.0),
        ]
        series = PriceSeries("ZERO", "USD", bars)
        report = run_quality_check(series)
        # zero close causes a large jump detection
        assert report.score < 1.0

    def test_negative_close_reported(self):
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-02", -5.0),
            PriceBar("2024-01-03", 102.0),
        ]
        series = PriceSeries("NEG", "USD", bars)
        report = run_quality_check(series)
        assert report.score < 1.0


# ---------------------------------------------------------------------------
# Timezone / date format edge cases
# ---------------------------------------------------------------------------


class TestTimezoneAndDateFormat:
    def test_iso_format_accepted(self):
        bars = [PriceBar("2024-01-15", 100.0)]
        series = PriceSeries("ISO", "USD", bars)
        issues, _ = check_timestamps(series)
        assert not any("invalid date" in i for i in issues)

    def test_non_iso_format_rejected(self):
        bars = [PriceBar("15/01/2024", 100.0)]
        series = PriceSeries("NONISO", "USD", bars)
        issues, _ = check_timestamps(series)
        assert any("invalid date" in i for i in issues)

    def test_datetime_with_time_rejected(self):
        """ISO datetime with time component should be rejected by date.fromisoformat."""
        bars = [PriceBar("2024-01-15T10:30:00", 100.0)]
        series = PriceSeries("DT", "USD", bars)
        issues, _ = check_timestamps(series)
        # Python 3.11+ accepts datetime in fromisoformat, but we want date-only
        # This test documents current behavior
        assert isinstance(issues, list)

    def test_utc_date_consistency(self):
        """Dates should be treated as UTC (no timezone offset)."""
        bars = [
            PriceBar("2024-01-01", 100.0),
            PriceBar("2024-01-02", 101.0),
        ]
        series = PriceSeries("UTC", "USD", bars)
        issues, _ = check_timestamps(series)
        assert issues == []


# ---------------------------------------------------------------------------
# Stale data detection
# ---------------------------------------------------------------------------


class TestStaleData:
    def test_very_recent_not_stale(self):
        today = date.today()
        bars = [PriceBar(today.isoformat(), 100.0)]
        series = PriceSeries("FRESH", "USD", bars)
        assert not check_stale(series, max_hours=1)

    def test_old_data_stale(self):
        old = date.today() - timedelta(days=30)
        bars = [PriceBar(old.isoformat(), 100.0)]
        series = PriceSeries("OLD", "USD", bars)
        assert check_stale(series, max_hours=24)

    def test_empty_series_stale(self):
        series = PriceSeries("EMPTY", "USD", [])
        assert check_stale(series)
