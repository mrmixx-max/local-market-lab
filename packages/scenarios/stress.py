"""Stress testing: historical crises, hypothetical scenarios, Monte Carlo fat tails.

@experimental — Sensitivity explorations, not forecasts.
Config: LML_STRESS_MAX_DD_THRESHOLD (default: 0.30)
"""

from __future__ import annotations

import hashlib
import math
import os
import random

from packages.domain.entities import StressTestResult

# Historical crisis shocks: cumulative return multipliers per asset class.
HISTORICAL_CRISES: dict[str, dict[str, float]] = {
    "2008_financial_crisis": {
        "equity": -0.57,
        "bond_gov": 0.12,
        "bond_corp": -0.15,
        "commodity": -0.55,
        "real_estate": -0.40,
        "cash": 0.02,
        "description": "Global Financial Credit Crisis (Lehman collapse)",
    },
    "2020_covid_crash": {
        "equity": -0.34,
        "bond_gov": 0.04,
        "bond_corp": -0.10,
        "commodity": -0.45,
        "real_estate": -0.20,
        "cash": 0.005,
        "description": "COVID-19 Pandemic Crash (Feb-Mar 2020)",
    },
    "2022_inflation_shock": {
        "equity": -0.25,
        "bond_gov": -0.18,
        "bond_corp": -0.16,
        "commodity": 0.20,
        "real_estate": -0.15,
        "cash": 0.015,
        "description": "2022 Inflation / Rate Shock (bonds + equities sold off)",
    },
}

HYPOTHETICAL_SCENARIOS: dict[str, dict[str, float]] = {
    "crash_30pct": {
        "equity": -0.30,
        "bond_gov": 0.05,
        "bond_corp": -0.05,
        "commodity": -0.20,
        "real_estate": -0.15,
        "cash": 0.01,
        "description": "Sudden equity crash -30%, flight to quality",
    },
    "volatility_spike": {
        "equity": -0.15,
        "bond_gov": -0.02,
        "bond_corp": -0.08,
        "commodity": 0.10,
        "real_estate": -0.10,
        "cash": 0.01,
        "description": "Volatility spike: equity -15%, correlation breakdown",
    },
    "rates_300bp": {
        "equity": -0.10,
        "bond_gov": -0.20,
        "bond_corp": -0.15,
        "commodity": 0.05,
        "real_estate": -0.25,
        "cash": 0.03,
        "description": "Sudden +300bp rate shock across the curve",
    },
}


def _asset_class_for(symbol: str) -> str:
    s = symbol.upper()
    if any(b in s for b in ["BOND", "GOV", "AGG", "BND", "IEAG", "AGGH"]):
        return "bond_gov"
    if any(c in s for c in ["CORP", "HYG", "LQD", "CRED"]):
        return "bond_corp"
    if any(r in s for r in ["REIT", "REAL", "IRET"]):
        return "real_estate"
    if any(cm in s for cm in ["GLD", "OIL", "COMM", "GSG", "DBA"]):
        return "commodity"
    return "equity"


def _data_hash(positions: dict) -> str:
    return hashlib.sha256(str(sorted(positions.items())).encode()).hexdigest()[:16]


def _recovery_months(total: float) -> int | None:
    if total >= 0:
        return 0
    return (
        math.ceil(math.log(1 / (1 + total)) / math.log(1.02))
        if (1 + total) > 0
        else None
    )


def _apply_shocks(
    scenario_name: str,
    shocks: dict,
    positions: dict,
    scenario_type: str,
    seed: int = 42,
) -> StressTestResult:
    """Core: apply shock map to positions, build StressTestResult."""
    impacts: dict[str, float] = {}
    total = 0.0
    for sym, w in positions.items():
        ac = _asset_class_for(sym)
        shock = shocks.get(ac, shocks.get("equity", -0.2))
        impacts[sym] = round(w * shock * 100, 2)
        total += w * shock
    months = _recovery_months(total)
    timeline = [
        {"day": 0, "portfolio_value_pct": 100.0, "event": "pre-shock"},
        {
            "day": 1,
            "portfolio_value_pct": round(100 * (1 + total), 2),
            "event": "shock_applied",
        },
    ]
    if months:
        for m in [months // 4, months // 2, months]:
            if m > 0:
                timeline.append(
                    {
                        "day": m * 30,
                        "portfolio_value_pct": round(100 * (1 + total) * (1.02**m), 2),
                        "event": f"recovery_{m}m",
                    }
                )
    dd_threshold = float(os.environ.get("LML_STRESS_MAX_DD_THRESHOLD", "0.30"))
    return StressTestResult(
        run_id=f"stress-{scenario_name}-{seed}",
        scenario=scenario_name,
        seed=seed,
        data_quality={
            "positions_count": len(positions),
            "asset_classes": list(set(_asset_class_for(s) for s in positions)),
        },
        metrics={
            "max_drawdown": round(total, 4),
            "recovery_days": (months * 30 if months else None),
            "var_95": round(total * 1.2, 4),
            "breaches_threshold": abs(total) > dd_threshold,
        },
        timeline=timeline,
        data_hash=_data_hash(positions),
        limitations=[
            f"{scenario_type.capitalize()} scenario — approximate shocks.",
            "Recovery estimate assumes 2% monthly compounding from trough.",
        ],
    )


def run_historical_stress(
    scenario_name: str, positions: dict[str, float], seed: int = 42
) -> StressTestResult:
    """Apply a historical crisis shock. @experimental."""
    if scenario_name not in HISTORICAL_CRISES:
        raise ValueError(f"unknown crisis: {scenario_name}")
    return _apply_shocks(
        scenario_name, HISTORICAL_CRISES[scenario_name], positions, "historical", seed
    )


def run_hypothetical_stress(
    scenario_name: str, positions: dict[str, float], seed: int = 42
) -> StressTestResult:
    """Apply a hypothetical scenario shock. @experimental."""
    if scenario_name not in HYPOTHETICAL_SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario_name}")
    return _apply_shocks(
        scenario_name,
        HYPOTHETICAL_SCENARIOS[scenario_name],
        positions,
        "hypothetical",
        seed,
    )


def monte_carlo_fat_tail(
    positions: dict[str, float],
    annual_vol: float = 0.18,
    annual_drift: float = 0.06,
    horizon_days: int = 252,
    runs: int = 5000,
    seed: int = 42,
    df: int = 5,
) -> dict:
    """Monte Carlo with Student-t innovations (fat tails). @experimental.

    Student-t innovations are standardized to unit variance so that
    ``daily_vol`` is the true per-day standard deviation of the innovation
    (t-distribution variance = df/(df-2) for df > 2).
    """
    if df <= 2:
        raise ValueError("Student-t degrees of freedom must be > 2 for finite variance")
    rng = random.Random(seed)
    weights = list(positions.values())
    daily_drift = annual_drift / 252
    daily_vol = annual_vol / math.sqrt(252)
    # Standardize t-innovations to unit variance: t / sqrt(df/(df-2))
    t_norm = math.sqrt((df - 2) / df)
    finals: list[float] = []
    for _ in range(runs):
        port_ret = 0.0
        for _day in range(horizon_days):
            z = rng.gauss(0, 1)
            chi2 = sum(rng.gauss(0, 1) ** 2 for _ in range(df))
            t = z / math.sqrt(chi2 / df) * t_norm if chi2 > 0 else 0.0
            port_ret += sum(w * (daily_drift + daily_vol * t) for w in weights)
        finals.append(1 + port_ret)
    s = sorted(finals)
    n = len(s)
    cvar_idx = int(0.05 * n)
    return {
        "method": "monte-carlo-fat-tail",
        "runs": runs,
        "horizon_days": horizon_days,
        "df": df,
        "seed": seed,
        "p01": round(s[int(0.01 * n)], 4),
        "p05": round(s[int(0.05 * n)], 4),
        "p25": round(s[int(0.25 * n)], 4),
        "median": round(s[int(0.50 * n)], 4),
        "p75": round(s[int(0.75 * n)], 4),
        "p95": round(s[int(0.95 * n)], 4),
        "prob_loss_pct": round(sum(1 for x in s if x < 1) / n * 100, 1),
        "var_95_pct": round((-s[cvar_idx] + 1) * 100, 2),
        "cvar_95_pct": round((-sum(s[:cvar_idx]) / cvar_idx + 1) * 100, 2),
        "data_hash": _data_hash(positions),
        "limitations": [
            "Student-t fat tails; constant vol/drift assumed.",
            "Single-factor model: all positions share one innovation stream.",
            "Weights are treated as fixed fractions; no rebalancing modeled.",
        ],
    }


def available_scenarios() -> dict:
    return {
        "historical": {k: v["description"] for k, v in HISTORICAL_CRISES.items()},
        "hypothetical": {
            k: v["description"] for k, v in HYPOTHETICAL_SCENARIOS.items()
        },
    }
