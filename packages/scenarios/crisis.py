"""Crisis scenarios: correlation breaks, liquidity crunches, rotation events.

@experimental — Models non-normal crisis dynamics.
Config: LML_CRISIS_SCENARIOS (default: 2008,2020,2022)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

SECTOR_MAP: dict[str, list[str]] = {
    "TECH": ["AAPL", "MSFT", "GOOGL", "NVDA", "QQQ", "META", "AMD"],
    "HEALTH": ["JNJ", "PFE", "UNH", "ABBV", "MRK"],
    "FINANCE": ["JPM", "BAC", "WFC", "GS", "V", "MA"],
    "ENERGY": ["XOM", "CVX", "COP", "SLB", "OIL"],
    "CONSUMER": ["AMZN", "WMT", "HD", "KO", "PEP"],
    "BONDS": ["AGGH", "IEAG", "BND", "AGG", "TLT"],
    "COMMODITY": ["GLD", "SLV", "DBA", "GSG"],
}


def _sector_for(symbol: str) -> str:
    s = symbol.upper()
    for sector, members in SECTOR_MAP.items():
        if s in members:
            return sector
    return "OTHER"


@dataclass
class CrisisResult:
    scenario_type: str
    portfolio_impact_pct: float
    details: dict
    mitigation: list[str]
    limitations: list[str]


def correlation_break(positions: dict[str, float], normal_correlation: float = 0.3,
                       crisis_correlation: float = 0.85,
                       annual_vol: float = 0.18) -> CrisisResult:
    """Model impact of correlation spiking toward 1 during a crisis. @experimental."""
    n = len(positions)
    if n < 2:
        return CrisisResult("correlation_break", 0.0,
                            {"warning": "need >= 2 positions"},
                            ["Diversify across uncorrelated assets."],
                            ["Single vol assumption."])
    weights = list(positions.values())
    vols = [annual_vol] * n

    def port_var(rho: float) -> float:
        return sum(weights[i] * weights[j] * vols[i] * vols[j] * (1.0 if i == j else rho)
                   for i in range(n) for j in range(n))

    vol_n = math.sqrt(port_var(normal_correlation)) * 100
    vol_c = math.sqrt(port_var(crisis_correlation)) * 100
    delta_var = (vol_c - vol_n) * 1.645
    return CrisisResult(
        "correlation_break", round(-delta_var, 2),
        {"vol_normal_annual_pct": round(vol_n, 2), "vol_crisis_annual_pct": round(vol_c, 2),
         "diversification_lost_pct": round((1 - vol_c / vol_n) * 100, 1) if vol_n > 0 else 0},
        ["Reduce position sizes.", "Add diversifiers: trend-following, long vol.",
         "Use options to cap tail risk."],
        ["Assumes equal pairwise correlation.", "Constant vol across assets."],
    )


def liquidity_crunch(positions: dict[str, float], adv_fraction: float = 0.01,
                      volatility: float = 0.02,
                      participation_cap: float = 0.05) -> CrisisResult:
    """Estimate market impact cost using Almgren-Chriss square-root model. @experimental."""
    total_value = sum(abs(v) for v in positions.values())
    impacts: dict[str, float] = {}
    total_cost = 0.0
    for sym, value in positions.items():
        adv = abs(value) / adv_fraction if adv_fraction > 0 else abs(value)
        participation = abs(value) / adv if adv > 0 else 1.0
        penalty = math.sqrt(participation / participation_cap) if participation > participation_cap else math.sqrt(participation)
        cost_pct = volatility * penalty * 100
        impacts[sym] = round(-cost_pct, 3)
        total_cost += value * cost_pct / 100
    total_cost_pct = (total_cost / total_value * 100) if total_value > 0 else 0
    return CrisisResult(
        "liquidity_crunch", round(-total_cost_pct, 3),
        {"assumed_daily_adv_fraction": adv_fraction, "participation_cap": participation_cap,
         "position_impacts_pct": impacts},
        ["Stagger liquidation over multiple days.", "Prefer liquid instruments.",
         "Maintain cash buffer."],
        ["Square-root model is a simplification.", "ADV may not reflect stressed markets."],
    )


def sector_rotation(positions: dict[str, float],
                     rotation_shift: dict[str, float] | None = None) -> CrisisResult:
    """Model impact of sector rotation (growth -> value). @experimental."""
    if rotation_shift is None:
        rotation_shift = {"TECH": -0.20, "ENERGY": 0.15, "BONDS": 0.05,
                          "CONSUMER": 0.03, "HEALTH": -0.05, "FINANCE": 0.10,
                          "COMMODITY": 0.08, "OTHER": -0.05}
    sector_exp: dict[str, float] = {}
    for sym, w in positions.items():
        sector_exp[_sector_for(sym)] = sector_exp.get(_sector_for(sym), 0.0) + w
    impacts: dict[str, float] = {}
    total = 0.0
    for sector, exposure in sector_exp.items():
        shift = rotation_shift.get(sector, rotation_shift.get("OTHER", -0.05))
        impacts[sector] = round(exposure * shift * 100, 2)
        total += exposure * shift
    return CrisisResult(
        "sector_rotation", round(total * 100, 2),
        {"sector_exposures_pct": {s: round(e * 100, 1) for s, e in sector_exp.items()},
         "impact_by_sector_pct": impacts, "rotation_shifts_applied": rotation_shift},
        ["Reduce concentration in losing sector.", "Tilt toward benefiting sectors."],
        ["Rotation magnitude is an assumption.", "Static sector mapping."],
    )
