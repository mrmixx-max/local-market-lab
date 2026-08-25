"""Pure-Python forecasting — no statsmodels / numpy required.

Four models, all pure functions:
  1. linear_trend_forecast  — OLS on recent window + confidence bands
  2. exp_smooth_forecast    — Holt's linear trend (level + slope)
  3. arima_like_forecast    — AR(1) on differenced data
  4. ensemble_forecast      — average of the three + confidence intervals
"""

from __future__ import annotations

import math


def _validate(data: list[float], horizon: int) -> None:
    if not isinstance(data, list) or len(data) < 5:
        raise ValueError("data must be a list of at least 5 numeric values")
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in data):
        raise ValueError("data must contain only finite numbers")
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")


def _ols(x: list[float], y: list[float]) -> tuple[float, float]:
    """Ordinary least squares: returns (slope, intercept).

    Uses pure-Python math (no numpy dependency for this module).
    """
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return 0.0, my
    b = sxy / sxx
    return b, my - b * mx


def linear_trend_forecast(data: list[float], horizon: int = 30) -> dict:
    """OLS on the last 60 points + 95% confidence band.

    Args:
        data: List of at least 5 finite numeric values.
        horizon: Number of steps to forecast (>=1).

    Returns:
        dict with keys: model, forecast, upper, lower, slope, last.
    """
    _validate(data, horizon)
    win = data[-60:]
    x = list(range(len(win)))
    b, a = _ols(x, win)
    n = len(win)
    resid = sum((win[i] - (a + b * i)) ** 2 for i in range(n))
    se = math.sqrt(resid / max(1, n - 2))
    forecast = [a + b * (n + h) for h in range(1, horizon + 1)]
    band = [1.96 * se * math.sqrt(1 + 1.0 / n + h / n) for h in range(1, horizon + 1)]
    return {
        "model": "linear_trend",
        "forecast": [round(v, 4) for v in forecast],
        "upper": [round(forecast[i] + band[i], 4) for i in range(horizon)],
        "lower": [round(forecast[i] - band[i], 4) for i in range(horizon)],
        "slope": round(b, 6),
        "last": round(data[-1], 4),
    }


def exp_smooth_forecast(
    data: list[float], horizon: int = 30, alpha: float = 0.3, beta: float = 0.1
) -> dict:
    """Holt's linear trend (double exponential smoothing).

    Args:
        data: List of at least 5 finite numeric values.
        horizon: Number of steps to forecast (>=1).
        alpha: Level smoothing factor in (0, 1].
        beta: Trend smoothing factor in (0, 1].

    Returns:
        dict with keys: model, forecast, upper, lower, level, trend, last.
    """
    _validate(data, horizon)
    if not (0 < alpha <= 1) or not (0 < beta <= 1):
        raise ValueError("alpha and beta must be in (0, 1]")
    level, trend = data[0], (data[1] - data[0] if len(data) > 1 else 0.0)
    l_pre = level
    for v in data[1:]:
        l_pre = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - l_pre) + (1 - beta) * trend
    forecast = [level + (h + 1) * trend for h in range(horizon)]
    # historical smoothing error for band
    level, t = data[0], (data[1] - data[0] if len(data) > 1 else 0.0)
    errs = []
    for v in data[1:]:
        errs.append(v - (level + t))
        lp = level
        level = alpha * v + (1 - alpha) * (level + t)
        t = beta * (level - lp) + (1 - beta) * t
    sigma = math.sqrt(sum(e * e for e in errs) / max(1, len(errs))) if errs else 1.0
    return {
        "model": "exp_smooth",
        "forecast": [round(v, 4) for v in forecast],
        "upper": [
            round(forecast[h] + 1.96 * sigma * math.sqrt(h + 1), 4)
            for h in range(horizon)
        ],
        "lower": [
            round(forecast[h] - 1.96 * sigma * math.sqrt(h + 1), 4)
            for h in range(horizon)
        ],
        "level": round(level, 4),
        "trend": round(trend, 6),
        "last": round(data[-1], 4),
    }


def arima_like_forecast(
    data: list[float], horizon: int = 30, order: tuple[int, int, int] = (5, 1, 0)
) -> dict:
    """AR(p) on differenced data — no statsmodels needed.

    Args:
        data: List of at least 5 finite numeric values.
        horizon: Number of steps to forecast (>=1).
        order: (p, d, q) — AR order, differencing degree, MA order (q unused).

    Returns:
        dict with keys: model, forecast, upper, lower, phi, d, last.
    """
    _validate(data, horizon)
    p, d, _ = order
    if d < 0 or p < 1:
        raise ValueError("order must be (p>=1, d>=0, q)")
    series = list(data)
    for _ in range(d):
        series = [series[i] - series[i - 1] for i in range(1, len(series))]
    if len(series) < p + 1:
        raise ValueError("not enough data after differencing for AR order")
    y = series[p:]
    x1 = [series[i] for i in range(len(series) - p)]
    phi, mu = _ols(x1, y)
    phi = max(-0.99, min(0.99, phi))
    last = series[-p:]
    fcd = []
    for _ in range(horizon):
        nxt = mu + phi * last[-1]
        fcd.append(nxt)
        last = (last + [nxt])[-p:]
    acc = data[-1]
    forecast = []
    for v in fcd:
        acc += v
        forecast.append(acc)
    sigma = (
        math.sqrt(
            sum((y[i] - (mu + phi * x1[i])) ** 2 for i in range(len(y)))
            / max(1, len(y) - 1)
        )
        if len(y) > 1
        else 1.0
    )
    return {
        "model": "arima_like",
        "forecast": [round(v, 4) for v in forecast],
        "upper": [
            round(forecast[h] + 1.96 * sigma * math.sqrt(h + 1), 4)
            for h in range(horizon)
        ],
        "lower": [
            round(forecast[h] - 1.96 * sigma * math.sqrt(h + 1), 4)
            for h in range(horizon)
        ],
        "phi": round(phi, 4),
        "d": d,
        "last": round(data[-1], 4),
    }


def ensemble_forecast(data: list[float], horizon: int = 30) -> dict:
    """Average of all three models + combined confidence intervals.

    Combines linear_trend, exp_smooth, and arima_like forecasts with
    equal weights. Upper/lower bands are the envelope of all three models.

    Args:
        data: List of at least 5 finite numeric values.
        horizon: Number of steps to forecast (>=1).

    Returns:
        dict with keys: model, forecast, upper, lower, components, last, horizon.
    """
    _validate(data, horizon)
    lin = linear_trend_forecast(data, horizon)
    exp = exp_smooth_forecast(data, horizon)
    ar = arima_like_forecast(data, horizon)
    n = horizon
    fc = [
        (lin["forecast"][i] + exp["forecast"][i] + ar["forecast"][i]) / 3
        for i in range(n)
    ]
    up = [max(lin["upper"][i], exp["upper"][i], ar["upper"][i]) for i in range(n)]
    lo = [min(lin["lower"][i], exp["lower"][i], ar["lower"][i]) for i in range(n)]
    return {
        "model": "ensemble",
        "forecast": [round(v, 4) for v in fc],
        "upper": [round(v, 4) for v in up],
        "lower": [round(v, 4) for v in lo],
        "components": {"linear_trend": lin, "exp_smooth": exp, "arima_like": ar},
        "last": round(data[-1], 4),
        "horizon": horizon,
    }
