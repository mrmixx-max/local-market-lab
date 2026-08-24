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


# --- Risk analytics: VaR, CVaR, correlation, rolling Sharpe, drawdown, attribution ---

def var_cvar(returns: list[float], confidence: float = 0.95) -> dict:
    """Historical VaR + Expected Shortfall (CVaR)."""
    if len(returns) < 2: raise ValueError("need >= 2 returns")
    s = sorted(returns)
    idx = int((1 - confidence) * len(s))
    var, cvar = -s[idx], -sum(s[:idx+1]) / (idx+1) if idx > 0 else -s[idx]
    return {"var_pct": round(var*100,3), "cvar_pct": round(cvar*100,3), "confidence": confidence}


def correlation_matrix(returns_dict: dict[str, list[float]]) -> dict:
    """Pearson correlation between position return series."""
    syms = list(returns_dict.keys())
    n = min(len(v) for v in returns_dict.values())
    d = {k: v[-n:] for k, v in returns_dict.items()}
    mu = {k: sum(v)/n for k, v in d.items()}
    out = {}
    for a in syms:
        for b in syms:
            da, db, ma, mb = d[a], d[b], mu[a], mu[b]
            cov = sum((da[i]-ma)*(db[i]-mb) for i in range(n))/(n-1)
            sa = sqrt(sum((x-ma)**2 for x in da)/(n-1))
            sb = sqrt(sum((x-mb)**2 for x in db)/(n-1))
            out[f"{a}__{b}"] = round(cov/(sa*sb),3) if sa and sb else 0.0
    return {"symbols": syms, "matrix": out}


def rolling_sharpe(returns: list[float], window: int = 63) -> list[float]:
    """Rolling annualized Sharpe ratio series."""
    if len(returns) < window: return []
    out = []
    for i in range(window, len(returns)+1):
        w = returns[i-window:i]
        m = sum(w)/len(w)
        sd = sqrt(sum((x-m)**2 for x in w)/(len(w)-1))
        out.append(round((m*252)/(sd*sqrt(252)),3) if sd > 0 else 0.0)
    return out


def drawdown_series(equity_curve: list[float]) -> list[float]:
    """Drawdown as percentage series (0=peak, negative=decline)."""
    peak = equity_curve[0]
    out = []
    for v in equity_curve:
        peak = max(peak, v)
        out.append(round((v/peak-1)*100, 3))
    return out


def performance_attribution(positions: dict, prices: dict) -> dict:
    """Each position's contribution to total return."""
    ts = sum(q*prices[s][0] for s,q in positions.items() if s in prices and len(prices[s])>=2)
    te = sum(q*prices[s][-1] for s,q in positions.items() if s in prices and len(prices[s])>=2)
    if ts == 0: return {"total_return_pct": 0, "positions": {}}
    attrs = {}
    for sym, qty in positions.items():
        if sym not in prices or len(prices[sym]) < 2: continue
        sv = qty*prices[sym][0]; ev = qty*prices[sym][-1]
        attrs[sym] = {"weight_pct": round(sv/ts*100,2),
                      "return_pct": round((prices[sym][-1]/prices[sym][0]-1)*100,2),
                      "contribution_pct": round((ev-sv)/ts*100,2)}
    return {"total_return_pct": round((te/ts-1)*100,2), "positions": attrs}
