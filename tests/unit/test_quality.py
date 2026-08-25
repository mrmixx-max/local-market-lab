"""Tests for the data quality checks layer."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from packages.domain.entities import PriceBar, PriceSeries
from packages.quality.checks import (
    check_fx_consistency,
    check_missing_data,
    check_splits,
    check_timestamps,
    check_stale,
    detect_outliers,
    run_quality_check,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def make_series(symbol: str, closes: list[float], ccy: str = "USD") -> PriceSeries:
    d = date.today() - timedelta(days=len(closes))
    bars = []
    for i, c in enumerate(closes):
        bars.append(PriceBar((d + timedelta(days=i)).isoformat(), c, 1000))
    return PriceSeries(symbol, ccy, bars)


@pytest.fixture
def clean_series():
    return make_series("TEST", [100.0, 101.0, 102.0, 103.0, 104.0, 105.0])


@pytest.fixture
def series_with_gap():
    bars = [
        PriceBar("2024-01-01", 100.0),
        PriceBar("2024-01-02", 101.0),
        PriceBar("2024-01-15", 102.0),  # 13-day gap
        PriceBar("2024-01-16", 103.0),
    ]
    return PriceSeries("GAP", "USD", bars)


@pytest.fixture
def series_with_split():
    return make_series("SPLIT", [100.0, 101.0, 50.0, 51.0, 52.0])


@pytest.fixture
def series_with_outlier():
    base = [100.0 + i for i in range(10)]
    base.append(500.0)  # extreme spike
    return make_series("OUT", base)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
class TestMissingData:
    def test_no_gaps(self, clean_series):
        count, dates = check_missing_data(clean_series, max_gap_days=5)
        assert count == 0
        assert dates == []

    def test_detects_gap(self, series_with_gap):
        count, dates = check_missing_data(series_with_gap, max_gap_days=5)
        assert count == 1
        assert "2024-01-15" in dates


class TestSplitDetection:
    def test_no_split(self, clean_series):
        detected, cands = check_splits(clean_series)
        assert not detected
        assert cands == []

    def test_detects_split(self, series_with_split):
        detected, cands = check_splits(series_with_split)
        assert detected
        assert any(c["change_pct"] < -40 for c in cands)


class TestFXConsistency:
    def test_matching_currency(self, clean_series):
        mismatch, issues = check_fx_consistency(clean_series, "USD")
        assert not mismatch
        assert issues == []

    def test_mismatched_currency(self, clean_series):
        mismatch, issues = check_fx_consistency(clean_series, "EUR")
        assert mismatch
        assert any("currency mismatch" in i for i in issues)


class TestTimestamps:
    def test_valid_order(self, clean_series):
        issues, dupes = check_timestamps(clean_series)
        assert issues == []
        assert dupes == 0

    def test_future_date(self):
        bars = [PriceBar("2099-01-01", 100.0)]
        series = PriceSeries("FUT", "USD", bars)
        issues, _ = check_timestamps(series)
        assert any("future date" in i for i in issues)

    def test_invalid_format(self):
        bars = [PriceBar("not-a-date", 100.0)]
        series = PriceSeries("INV", "USD", bars)
        issues, _ = check_timestamps(series)
        assert any("invalid date" in i for i in issues)

    def test_duplicates(self):
        bars = [PriceBar("2024-01-01", 100.0), PriceBar("2024-01-01", 101.0)]
        series = PriceSeries("DUP", "USD", bars)
        _, dupes = check_timestamps(series)
        assert dupes == 1


class TestStale:
    def test_recent_not_stale(self, clean_series):
        assert not check_stale(clean_series, max_hours=24 * 365)

    def test_old_is_stale(self):
        old_bars = [PriceBar("2020-01-01", 100.0)]
        old_series = PriceSeries("OLD", "USD", old_bars)
        assert check_stale(old_series, max_hours=1)


class TestOutlierDetection:
    def test_no_outliers(self, clean_series):
        count, _ = detect_outliers(clean_series)
        assert count == 0

    def test_detects_outlier(self, series_with_outlier):
        count, outliers = detect_outliers(series_with_outlier, z_threshold=2.5)
        assert count >= 1
        assert any(o["z_score"] > 2.5 for o in outliers)


# ---------------------------------------------------------------------------
# Composite report (unified domain QualityReport)
# ---------------------------------------------------------------------------
class TestQualityReport:
    def test_clean_series_passes(self, clean_series):
        report = run_quality_check(clean_series, source="test")
        assert report.status == "valid"
        assert report.score >= 0.9

    def test_report_to_dict(self, clean_series):
        report = run_quality_check(clean_series, source="test")
        d = report.to_dict()
        assert "data_quality" in d
        assert d["data_quality"]["status"] == "valid"
        assert d["data_quality"]["source"] == "test"

    def test_split_lowers_score(self, clean_series, series_with_split):
        clean_report = run_quality_check(clean_series)
        split_report = run_quality_check(series_with_split)
        assert split_report.score < clean_report.score
        assert any("split" in i.lower() for i in split_report.issues)

    def test_missing_data_warning(self, series_with_gap):
        report = run_quality_check(series_with_gap)
        assert report.missing_values > 0

    def test_fx_mismatch_warning(self, clean_series):
        ok_report = run_quality_check(clean_series, expected_ccy="USD")
        bad_report = run_quality_check(clean_series, expected_ccy="EUR")
        assert bad_report.score < ok_report.score
        assert any("mismatch" in i.lower() for i in bad_report.issues)

    def test_invalid_on_timestamp_issues(self):
        bars = [PriceBar("2099-01-01", 100.0)]
        series = PriceSeries("INV", "USD", bars)
        report = run_quality_check(series)
        assert report.status == "invalid"

    def test_embedded_format(self, clean_series):
        report = run_quality_check(clean_series, source="yahoo")
        d = report.to_dict()
        assert "data_quality" in d
        dq = d["data_quality"]
        assert "status" in dq
        assert "missing_values" in dq
        assert "duplicate_timestamps" in dq
        assert "stale_data" in dq
        assert "source" in dq
        assert "timestamp" in dq
