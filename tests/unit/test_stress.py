"""Tests for stress scenarios: historical crises, hypothetical, Monte Carlo fat-tail.

Covers domain entity StressTestResult format, scenario names, and fat-tail
Monte Carlo with data_hash and timeline.
"""
from __future__ import annotations

import pytest

from packages.scenarios.stress import (
    HISTORICAL_CRISES,
    HYPOTHETICAL_SCENARIOS,
    available_scenarios,
    monte_carlo_fat_tail,
    run_historical_stress,
    run_hypothetical_stress,
)

POSITIONS = {"IWDA": 0.6, "AGGH": 0.3, "GLD": 0.1}


class TestHistoricalStress:
    def test_gfc_2008(self):
        r = run_historical_stress("2008_financial_crisis", POSITIONS)
        assert r.scenario == "2008_financial_crisis"
        assert r.metrics["max_drawdown"] < 0
        assert r.metrics["recovery_days"] is not None
        assert r.metrics["recovery_days"] > 0
        assert r.run_id  # UUID assigned
        assert r.data_hash  # deterministic hash

    def test_covid_2020(self):
        r = run_historical_stress("2020_covid_crash", POSITIONS)
        assert r.metrics["max_drawdown"] < 0
        assert "COVID" in HISTORICAL_CRISES["2020_covid_crash"]["description"]
        assert len(r.timeline) >= 2

    def test_inflation_2022(self):
        r = run_historical_stress("2022_inflation_shock", POSITIONS)
        assert r.metrics["max_drawdown"] < 0
        assert len(r.limitations) > 0

    def test_timeline_structure(self):
        r = run_historical_stress("2008_financial_crisis", POSITIONS)
        assert r.timeline[0]["event"] == "pre-shock"
        assert r.timeline[0]["portfolio_value_pct"] == 100.0
        assert r.timeline[1]["event"] == "shock_applied"

    def test_data_quality_field(self):
        r = run_historical_stress("2020_covid_crash", POSITIONS)
        assert r.data_quality["positions_count"] == 3

    def test_unknown_crisis_raises(self):
        with pytest.raises(ValueError, match="unknown crisis"):
            run_historical_stress("no-such-scenario", POSITIONS)


class TestHypotheticalStress:
    def test_crash_30pct(self):
        r = run_hypothetical_stress("crash_30pct", POSITIONS)
        assert r.metrics["max_drawdown"] < 0
        assert "crash" in r.scenario.lower() or "Crash" in r.scenario

    def test_volatility_spike(self):
        r = run_hypothetical_stress("volatility_spike", POSITIONS)
        assert r.metrics["max_drawdown"] < 0
        assert r.metrics["recovery_days"] is not None

    def test_rates_300bp(self):
        r = run_hypothetical_stress("rates_300bp", POSITIONS)
        assert r.metrics["max_drawdown"] < 0

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError, match="unknown scenario"):
            run_hypothetical_stress("nuclear-war", POSITIONS)


class TestMonteCarloFatTail:
    def test_basic_run(self):
        r = monte_carlo_fat_tail(POSITIONS, runs=500, seed=42, df=5)
        assert r["method"] == "monte-carlo-fat-tail"
        assert r["runs"] == 500
        assert r["p05"] <= r["median"] <= r["p95"]
        assert 0 <= r["prob_loss_pct"] <= 100

    def test_var_cvar(self):
        r = monte_carlo_fat_tail(POSITIONS, runs=500, seed=42)
        assert "var_95_pct" in r
        assert "cvar_95_pct" in r
        assert r["cvar_95_pct"] >= r["var_95_pct"]

    def test_lower_df_fatter_tails(self):
        """Lower df should produce wider tails (lower p05)."""
        r5 = monte_carlo_fat_tail(POSITIONS, runs=500, seed=42, df=3)
        r30 = monte_carlo_fat_tail(POSITIONS, runs=500, seed=42, df=30)
        assert r5["p05"] <= r30["p05"]

    def test_seed_reproducible(self):
        r1 = monte_carlo_fat_tail(POSITIONS, runs=200, seed=123)
        r2 = monte_carlo_fat_tail(POSITIONS, runs=200, seed=123)
        assert r1["median"] == r2["median"]
        assert r1["data_hash"] == r2["data_hash"]

    def test_data_hash_present(self):
        r = monte_carlo_fat_tail(POSITIONS, runs=100, seed=1)
        assert "data_hash" in r
        assert len(r["data_hash"]) == 16


class TestAvailableScenarios:
    def test_structure(self):
        s = available_scenarios()
        assert "historical" in s
        assert "hypothetical" in s
        assert "2008_financial_crisis" in s["historical"]
        assert "crash_30pct" in s["hypothetical"]
