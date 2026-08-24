"""Pure metric functions — no side effects, no storage access.

Per concept: every ratio documents its annualization factor (252 trading
days, daily returns assumed).
"""
from __future__ import annotations

from math import sqrt


def total_return(closes: list[float]) -> float:
    if len(closes) < 2 or closes[0] == 0:
        raise ValueError("need >= 2 closes with nonzero start")
    return closes[-1] / closes[0] - 1


def cagr(closes: list[float], periods_per_year: int = 252) -> float:
    n = len(closes)
    if n < 2 or closes[0] <= 0:
        raise ValueError("invalid series for CAGR")
    years = (n - 1) / periods_per_year
    return (closes[-1] / closes[0]) ** (1 / years) - 1


def returns(closes: list[float]) -> list[float]:
    return [b / a - 1 for a, b in zip(closes, closes[1:])]


def volatility(closes: list[float], periods_per_year: int = 252) -> float:
    r = returns(closes)
    if len(r) < 2:
        raise ValueError("need >= 3 closes for volatility")
    m = sum(r) / len(r)
    var = sum((x - m) ** 2 for x in r) / (len(r) - 1)   # sample variance
    return sqrt(var) * sqrt(periods_per_year)


def max_drawdown(closes: list[float]) -> float:
    """Return positive fraction of max peak-to-trough decline (0.25 = -25%)."""
    peak = closes[0]
    mdd = 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = max(mdd, (peak - c) / peak)
    return mdd


def sharpe_ratio(closes: list[float], risk_free_annual: float = 0.0,
                 periods_per_year: int = 252) -> float:
    r = returns(closes)
    if len(r) < 2:
        raise ValueError("need >= 3 closes for Sharpe")
    excess_mean = sum(r) / len(r) - risk_free_annual / periods_per_year
    m = sum(r) / len(r)
    sd = sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
    if sd == 0:
        return 0.0
    # annualized excess return over annualized volatility
    ann_return = excess_mean * periods_per_year
    return ann_return / (sd * sqrt(periods_per_year))


def sortino_ratio(closes: list[float], risk_free_annual: float = 0.0,
                  periods_per_year: int = 252) -> float:
    """Downside-deviation variant of Sharpe; downside measured vs 0 (MAR=0)."""
    r = returns(closes)
    if len(r) < 2:
        raise ValueError("need >= 3 closes for Sortino")
    excess_mean = sum(r) / len(r) - risk_free_annual / periods_per_year
    downside = [min(x, 0) for x in r]
    dd = sqrt(sum(x ** 2 for x in downside) / len(downside))
    if dd == 0:
        return 0.0
    ann_return = excess_mean * periods_per_year
    return ann_return / (dd * sqrt(periods_per_year))


def calmar_ratio(closes: list[float], periods_per_year: int = 252) -> float:
    """CAGR / MaxDrawdown. Returns None-equivalent 0.0 when MDD is zero."""
    mdd = max_drawdown(closes)
    if mdd == 0:
        return 0.0
    return abs(cagr(closes, periods_per_year)) / mdd


def all_metrics(closes: list[float]) -> dict:
    return {
        "total_return_pct": round(total_return(closes) * 100, 2),
        "cagr_pct": round(cagr(closes) * 100, 2),
        "volatility_pct": round(volatility(closes) * 100, 2),
        "max_drawdown_pct": round(max_drawdown(closes) * 100, 2),
        "sharpe": round(sharpe_ratio(closes), 3),
        "sortino": round(sortino_ratio(closes), 3),
        "calmar": round(calmar_ratio(closes), 3),
        "annualization": "252 trading days, daily returns",
    }
