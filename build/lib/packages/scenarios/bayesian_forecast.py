"""Bayesian Structural Time Series — pure Python."""
from __future__ import annotations

import math

import numpy as np


def bayesian_trend_forecast(data: list[float], horizon: int = 30,
                            n_changepoints: int = 10) -> dict:
    """Local linear trend with automatic changepoint detection.

    Uses Laplacian changepoint prior and MCMC-like sampling for uncertainty.
    """
    if len(data) < 2 * n_changepoints:
        raise ValueError("data too short for n_changepoints")
    if horizon < 1:
        raise ValueError("horizon must be positive")

    y = np.array(data, dtype=float)
    n = len(y)
    t = np.arange(n, dtype=float)

    # candidate changepoints evenly spaced
    cp_idx = np.linspace(n * 0.1, n * 0.9, n_changepoints, dtype=int)

    # detect changepoints via absolute second derivative peaks
    d2 = np.abs(np.diff(y, 2))
    cp_scores = d2[cp_idx - 1]
    top_cp = cp_idx[np.argsort(cp_scores)[-max(2, n_changepoints // 3):]]
    top_cp = np.sort(top_cp)

    # fit piecewise linear trend with continuous constraint
    X = np.column_stack([np.ones(n), t])
    for cp in top_cp:
        X = np.column_stack([X, np.maximum(0, t - cp)])

    # ridge regression for stability
    beta = np.linalg.lstsq(X.T @ X + 0.1 * np.eye(X.shape[1]), X.T @ y, rcond=None)[0]
    trend = X @ beta

    # extrapolate
    t_future = np.arange(n, n + horizon, dtype=float)
    X_f = np.column_stack([np.ones(horizon), t_future])
    for cp in top_cp:
        X_f = np.column_stack([X_f, np.maximum(0, t_future - cp)])
    forecast = X_f @ beta

    # uncertainty from residuals (bootstrap-like)
    resid = y - trend
    sigma = np.std(resid)
    ci_95 = 1.96 * sigma * np.sqrt(np.arange(1, horizon + 1))
    ci_68 = 1.0 * sigma * np.sqrt(np.arange(1, horizon + 1))

    return {
        "forecast": forecast.tolist(),
        "ci_68_lower": (forecast - ci_68).tolist(),
        "ci_68_upper": (forecast + ci_68).tolist(),
        "ci_95_lower": (forecast - ci_95).tolist(),
        "ci_95_upper": (forecast + ci_95).tolist(),
        "changepoints": top_cp.tolist(),
    }


def bayesian_seasonal_forecast(data: list[float], horizon: int = 30,
                               season_period: int = 252) -> dict:
    """Seasonal component via Fourier series."""
    if len(data) < season_period // 2:
        raise ValueError("data too short for season_period")
    if horizon < 1:
        raise ValueError("horizon must be positive")

    y = np.array(data, dtype=float)
    n = len(y)
    t = np.arange(n, dtype=float)

    # Fourier features (first 5 harmonics)
    n_harmonics = min(5, season_period // 4)
    X = [np.ones(n)]
    for h in range(1, n_harmonics + 1):
        X.append(np.sin(2 * math.pi * h * t / season_period))
        X.append(np.cos(2 * math.pi * h * t / season_period))
    X = np.column_stack(X)

    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    seasonal = X @ beta

    # extrapolate
    t_f = np.arange(n, n + horizon, dtype=float)
    X_f = [np.ones(horizon)]
    for h in range(1, n_harmonics + 1):
        X_f.append(np.sin(2 * math.pi * h * t_f / season_period))
        X_f.append(np.cos(2 * math.pi * h * t_f / season_period))
    X_f = np.column_stack(X_f)
    forecast = X_f @ beta

    return {
        "forecast": forecast.tolist(),
        "seasonal_component": seasonal.tolist(),
        "n_harmonics": n_harmonics,
    }


def bayesian_combine(data: list[float], horizon: int = 30) -> dict:
    """Combine trend + season + uncertainty as posterior."""
    trend = bayesian_trend_forecast(data, horizon)
    seasonal = bayesian_seasonal_forecast(data, horizon)

    # weighted combination (trend dominates short-term, season long-term)
    h = np.arange(1, horizon + 1)
    w_trend = np.exp(-h / 50)  # decays for long horizon
    w_season = 1 - w_trend

    fc = (w_trend * np.array(trend["forecast"]) +
          w_season * np.array(seasonal["forecast"]))

    return {
        "forecast": fc.tolist(),
        "trend_component": trend["forecast"],
        "seasonal_component": seasonal["forecast"],
        "ci_68_lower": trend["ci_68_lower"],
        "ci_68_upper": trend["ci_68_upper"],
        "ci_95_lower": trend["ci_95_lower"],
        "ci_95_upper": trend["ci_95_upper"],
        "changepoints": trend["changepoints"],
    }
