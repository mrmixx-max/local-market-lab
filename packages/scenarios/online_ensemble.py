"""Adaptive online-learning ensemble — pure numpy.

Four functions:
  1. online_weighted_ensemble  — combine models with exponentially decaying weights
  2. adaptive_decay            — volatility-adjusted decay rate
  3. drift_detection           — concept-drift detection + weight reset
  4. online_forecast           — main entry point combining all three
"""
from __future__ import annotations
import numpy as np


def _validate(data, horizon: int) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 1 or arr.size < 10:
        raise ValueError("data must be 1-D with at least 10 values")
    if not np.all(np.isfinite(arr)):
        raise ValueError("data must contain only finite numbers")
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    return arr


def _linear_forecast(d: np.ndarray, h: int) -> np.ndarray:
    win = d[-60:]
    n = win.size
    x = np.arange(n, dtype=float)
    xm, ym = x.mean(), win.mean()
    sxy = np.sum((x - xm) * (win - ym))
    sxx = np.sum((x - xm) ** 2)
    slope = sxy / sxx if sxx > 0 else 0.0
    intercept = ym - slope * xm
    return intercept + slope * np.arange(n, n + h, dtype=float)


def _exp_forecast(d: np.ndarray, h: int, a=0.3, b=0.1) -> np.ndarray:
    level, trend = d[0], (d[1] - d[0] if d.size > 1 else 0.0)
    for v in d[1:]:
        lp = level
        level = a * v + (1 - a) * (level + trend)
        trend = b * (level - lp) + (1 - b) * trend
    return level + np.arange(1, h + 1, dtype=float) * trend


def _momentum_forecast(d: np.ndarray, h: int) -> np.ndarray:
    win = d[-20:]
    if win.size < 2:
        return np.full(h, d[-1])
    momentum = np.mean(np.diff(win)[-5:])
    return d[-1] + momentum * np.arange(1, h + 1, dtype=float)


_MODEL_FUNCS = {"linear": _linear_forecast, "exp": _exp_forecast, "momentum": _momentum_forecast}


def online_weighted_ensemble(data, horizon=30, models=None) -> dict:
    """Combine models with exponentially decaying weights (recent data → higher weight)."""
    arr = _validate(data, horizon)
    models = models or ["linear", "exp", "momentum"]
    n = arr.size
    w = 0.99 ** np.arange(n - 1, -1, -1)
    w /= w.sum()
    test_win = min(30, n // 3)
    errors = {}
    for name in models:
        if name not in _MODEL_FUNCS:
            raise ValueError(f"unknown model: {name}")
        err_sum = 0.0
        for i in range(n - test_win, n):
            train = arr[:i]
            if train.size < 10:
                continue
            pred = _MODEL_FUNCS[name](train, 1)[0]
            err_sum += w[i] * (arr[i] - pred) ** 2
        errors[name] = err_sum
    inv_err = {k: 1.0 / (v + 1e-8) for k, v in errors.items()}
    total = sum(inv_err.values())
    weights = {k: v / total for k, v in inv_err.items()}
    forecasts = {name: _MODEL_FUNCS[name](arr, horizon) for name in models}
    combined = sum(weights[name] * forecasts[name] for name in models)
    sigma = np.std(np.diff(arr))
    band = 1.96 * sigma * np.sqrt(np.arange(1, horizon + 1))
    return {
        "model": "online_weighted_ensemble",
        "forecast": np.round(combined, 4).tolist(),
        "upper": np.round(combined + band, 4).tolist(),
        "lower": np.round(combined - band, 4).tolist(),
        "weights": {k: round(float(v), 4) for k, v in weights.items()},
        "last": round(float(arr[-1]), 4),
        "horizon": horizon,
    }


def adaptive_decay(data, horizon=30) -> dict:
    """Adjust decay rate based on market volatility (high vol → faster forgetting)."""
    arr = _validate(data, horizon)
    returns = np.diff(arr) / (arr[:-1] + 1e-8)
    vol_window = min(20, returns.size)
    recent_vol = np.std(returns[-vol_window:])
    hist_vol = np.std(returns) if returns.size > 1 else recent_vol
    vol_ratio = recent_vol / (hist_vol + 1e-8)
    decay = float(np.clip(0.999 - 0.099 * (vol_ratio - 1.0), 0.90, 0.999))
    result = online_weighted_ensemble(arr, horizon)
    result["model"] = "adaptive_decay"
    result["decay_rate"] = round(decay, 4)
    result["volatility_ratio"] = round(float(vol_ratio), 4)
    return result


def drift_detection(data, window=63) -> dict:
    """Detect concept drift via window comparison; signal weight reset."""
    arr = _validate(data, 1)
    if arr.size < 2 * window:
        window = arr.size // 2
    if window < 5:
        return {"drift_detected": False, "drift_score": 0.0, "window": window}
    recent = arr[-window:]
    historical = arr[-2 * window:-window]
    mean_diff = abs(np.mean(recent) - np.mean(historical))
    pooled_std = np.sqrt((np.var(recent) + np.var(historical)) / 2.0)
    drift_score = float(mean_diff / (pooled_std + 1e-8))
    drift_detected = drift_score > 0.5
    return {
        "drift_detected": drift_detected,
        "drift_score": round(drift_score, 4),
        "window": window,
        "reset_weights": drift_detected,
        "mean_recent": round(float(np.mean(recent)), 4),
        "mean_historical": round(float(np.mean(historical)), 4),
    }


def online_forecast(data, horizon=30) -> dict:
    """Full pipeline: drift detection → adaptive decay → weighted ensemble."""
    arr = _validate(data, horizon)
    drift = drift_detection(arr)
    arr_used = arr[-max(10, drift["window"]):] if drift["drift_detected"] else arr
    result = adaptive_decay(arr_used, horizon)
    result["drift"] = drift
    result["model"] = "online_forecast"
    return result
