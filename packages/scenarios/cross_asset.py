"""Cross-Asset Lead-Lag prediction — pure numpy."""

from __future__ import annotations
import numpy as np


def _returns(p):
    """Log-returns from a price series: r[t] = log(p[t]/p[t-1])."""
    return np.diff(np.log(p + 1e-12))


def _corr(x, y):
    """Pearson correlation between two arrays. Returns 0.0 if degenerate."""
    if len(x) < 3 or len(y) < 3:
        return 0.0
    sx, sy = x.std(), y.std()
    return 0.0 if sx < 1e-12 or sy < 1e-12 else float(np.corrcoef(x, y)[0, 1])


def _rss(X, y):
    """Ridge-regressed residual sum of squares: ||y - Xw||^2 with w = (X'X + λI)^-1 X'y."""
    b = np.linalg.solve(X.T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ y)
    return float(np.sum((y - X @ b) ** 2))


def lead_lag_correlation(
    asset_data: dict[str, list[float]], target_symbol: str, max_lag: int = 20
) -> dict:
    """Find the asset whose past returns best predict the target's future returns."""
    if target_symbol not in asset_data:
        raise ValueError(f"'{target_symbol}' not in asset_data")
    tgt = _returns(np.asarray(asset_data[target_symbol], dtype=np.float64))
    best: dict = {"symbol": None, "lag": 0, "correlation": 0.0}
    results: list[dict] = []
    for sym, p in asset_data.items():
        if sym == target_symbol:
            continue
        cr = _returns(np.asarray(p, dtype=np.float64))
        ml = min(len(cr), len(tgt))
        if ml < max_lag + 5:
            continue
        cr, tr = cr[-ml:], tgt[-ml:]
        for k in range(1, min(max_lag + 1, ml - 4)):
            r = _corr(cr[:-k], tr[k:])
            results.append({"symbol": sym, "lag": k, "correlation": round(r, 6)})
            if abs(r) > abs(best["correlation"]):
                best = {"symbol": sym, "lag": k, "correlation": round(r, 6)}
    return {
        "best_lead": best,
        "all_results": sorted(results, key=lambda x: -abs(x["correlation"]))[:20],
    }


def granger_causality_proxy(
    asset_data: dict[str, list[float]], target_symbol: str, max_lag: int = 10
) -> dict:
    """Approximate Granger causality via F-test proxy on restricted vs unrestricted AR."""
    if target_symbol not in asset_data:
        raise ValueError(f"'{target_symbol}' not in asset_data")
    tgt = _returns(np.asarray(asset_data[target_symbol], dtype=np.float64))
    n = len(tgt)
    if n < 2 * max_lag + 5:
        raise ValueError("not enough data")
    results = []
    for sym, p in asset_data.items():
        if sym == target_symbol:
            continue
        cr = _returns(np.asarray(p, dtype=np.float64))
        ml = min(n, len(cr))
        if ml < 2 * max_lag + 5:
            continue
        tr, cr = tgt[-ml:], cr[-ml:]
        y = tr[max_lag:]
        xr = [
            tr[max_lag - k : -k] if k else tr[max_lag:] for k in range(1, max_lag + 1)
        ]
        xu = xr + [
            cr[max_lag - k : -k] if k else cr[max_lag:] for k in range(1, max_lag + 1)
        ]
        Xr, Xu = np.column_stack(xr), np.column_stack(xu)
        rss_r, rss_u = _rss(Xr, y), _rss(Xu, y)
        dd = len(y) - 2 * max_lag - 1
        f = (
            ((rss_r - rss_u) / max_lag) / (rss_u / dd)
            if dd > 0 and rss_u > 1e-15
            else 0.0
        )
        results.append(
            {
                "symbol": sym,
                "f_statistic": round(f, 4),
                "improvement_pct": round((1 - rss_u / max(rss_r, 1e-15)) * 100, 2),
            }
        )
    results.sort(key=lambda x: -x["f_statistic"])
    return {"target": target_symbol, "granger_results": results}


def cross_asset_forecast(
    asset_data: dict[str, list[float]], target_symbol: str, horizon: int = 30
) -> dict:
    """Forecast target using top leading assets as exogenous regressors."""
    if target_symbol not in asset_data:
        raise ValueError(f"'{target_symbol}' not in asset_data")
    target = np.asarray(asset_data[target_symbol], dtype=np.float64)
    tgt = _returns(target)
    n = len(tgt)
    if n < 30:
        raise ValueError("need >= 30 data points")
    ll = lead_lag_correlation(asset_data, target_symbol, max_lag=10)
    top, seen = [], set()
    for r in ll["all_results"]:
        if r["symbol"] not in seen and len(top) < 3:
            top.append(r)
            seen.add(r["symbol"])
    if not top:
        phi = np.clip(np.corrcoef(tgt[:-1], tgt[1:])[0, 1], -0.99, 0.99)
        mu, last, fc = tgt.mean(), tgt[-1], []
        for _ in range(horizon):
            last = mu + phi * (last - mu)
            fc.append(last)
        pfc = [target[-1]]
        for r in fc:
            pfc.append(pfc[-1] * np.exp(r))
        return {
            "model": "cross_asset_forecast",
            "forecast": [round(v, 4) for v in pfc[1:]],
            "leading_assets": [],
            "last": round(target[-1], 4),
        }
    ol, el = 5, max(r["lag"] for r in top)
    tot = max(ol, el)
    y = tgt[tot:]
    xp = [np.ones(len(y))]
    for k in range(1, ol + 1):
        xp.append(tgt[tot - k : -k] if k else tgt[tot:])
    li = []
    for r in top:
        cr = _returns(np.asarray(asset_data[r["symbol"]], dtype=np.float64))
        lag, ml = r["lag"], min(n, len(cr))
        cr = cr[-ml:]
        tgt[-ml:]
        al = tot + lag
        if al > len(cr):
            continue
        ls = cr[al - tot : -tot] if tot else cr[al:]
        if len(ls) > len(y):
            ls = ls[-len(y) :]
        elif len(ls) < len(y):
            y = y[-len(ls) :]
            xp = [p[-len(ls) :] for p in xp]
        xp.append(ls)
        li.append({"symbol": r["symbol"], "lag": lag, "correlation": r["correlation"]})
    X = np.column_stack(xp)
    try:
        beta = np.linalg.solve(X.T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ y)
    except np.linalg.LinAlgError:
        beta = np.zeros(X.shape[1])
    hist = list(tgt)
    fc = []
    for _ in range(horizon):
        row = [1.0] + [hist[-k] for k in range(1, ol + 1)]
        for i in li:
            cr = _returns(np.asarray(asset_data[i["symbol"]], dtype=np.float64))
            idx = len(hist) - 1 - i["lag"]
            row.append(cr[idx] if 0 <= idx < len(cr) else 0.0)
        pred = float(np.dot(beta, row))
        fc.append(pred)
        hist.append(pred)
    pfc = [target[-1]]
    for r in fc:
        pfc.append(pfc[-1] * np.exp(r))
    return {
        "model": "cross_asset_forecast",
        "forecast": [round(v, 4) for v in pfc[1:]],
        "leading_assets": li,
        "last": round(target[-1], 4),
    }


def correlation_regime(
    asset_data: dict[str, list[float]],
    target_symbol: str,
    window: int = 60,
    threshold: float = 0.5,
) -> dict:
    """Detect when cross-asset correlations break down via rolling window analysis."""
    if target_symbol not in asset_data:
        raise ValueError(f"'{target_symbol}' not in asset_data")
    tgt = _returns(np.asarray(asset_data[target_symbol], dtype=np.float64))
    n = len(tgt)
    if n < window + 10:
        raise ValueError(f"need >= {window + 10} data points")
    regimes = []
    for sym, p in asset_data.items():
        if sym == target_symbol:
            continue
        cr = _returns(np.asarray(p, dtype=np.float64))
        ml = min(n, len(cr))
        if ml < window + 10:
            continue
        tr, cr = tgt[-ml:], cr[-ml:]
        rc = [
            _corr(tr[i : i + window], cr[i : i + window])
            for i in range(ml - window + 1)
        ]
        if not rc:
            continue
        recent, havg = rc[-1], np.mean(rc[:-1])
        z = (recent - havg) / max(np.std(rc[:-1]) if len(rc) > 1 else 1e-8, 1e-8)
        regimes.append(
            {
                "symbol": sym,
                "current_correlation": round(recent, 4),
                "historical_avg": round(float(havg), 4),
                "z_score": round(float(z), 4),
                "regime_broken": bool(abs(recent) < threshold or abs(z) > 2.0),
                "rolling_correlations": [round(v, 4) for v in rc],
            }
        )
    return {
        "target": target_symbol,
        "window": window,
        "threshold": threshold,
        "any_regime_broken": any(r["regime_broken"] for r in regimes),
        "asset_regimes": sorted(regimes, key=lambda x: abs(x["z_score"]), reverse=True),
    }
