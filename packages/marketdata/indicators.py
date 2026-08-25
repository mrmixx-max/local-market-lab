"""Pure technical indicator functions — no state, no side effects.

Each function takes a list of floats and returns a dict with 'values'
plus metadata about the indicator and its parameters.
"""

from __future__ import annotations

import math


def _validate_series(data: list[float], min_len: int, name: str) -> None:
    if not isinstance(data, list) or len(data) < min_len:
        raise ValueError(f"{name}: need list with >= {min_len} elements")
    if any(
        not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x) for x in data
    ):
        raise ValueError(f"{name}: all elements must be finite numbers")
    if min_len < 1:
        raise ValueError(f"{name}: min_len must be >= 1")


def sma(data: list[float], period: int) -> dict:
    """Simple Moving Average. Returns NaN for indices < period-1."""
    if not isinstance(period, int) or period < 1:
        raise ValueError("sma: period must be a positive integer")
    _validate_series(data, period, "sma")
    values = [None] * (period - 1)
    window_sum = sum(data[:period])
    values.append(window_sum / period)
    for i in range(period, len(data)):
        window_sum += data[i] - data[i - period]
        values.append(window_sum / period)
    return {"values": values, "indicator": "sma", "period": period}


def ema(data: list[float], period: int) -> dict:
    """Exponential Moving Average. First value seeds from SMA of first `period` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError("ema: period must be a positive integer")
    _validate_series(data, period, "ema")
    mult = 2.0 / (period + 1)
    values: list[float | None] = [None] * (period - 1)
    seed = sum(data[:period]) / period
    values.append(seed)
    prev = seed
    for x in data[period:]:
        prev = (x - prev) * mult + prev
        values.append(prev)
    return {"values": values, "indicator": "ema", "period": period}


def rsi(data: list[float], period: int = 14) -> dict:
    """Relative Strength Index (Wilder smoothing). First `period` values are None."""
    if not isinstance(period, int) or period < 1:
        raise ValueError("rsi: period must be a positive integer")
    _validate_series(data, period + 1, "rsi")
    gains, losses = [], []
    for i in range(1, len(data)):
        delta = data[i] - data[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    values: list[float | None] = [None] * period
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        values.append(100.0)
    else:
        values.append(100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            values.append(100.0)
        else:
            values.append(100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    return {"values": values, "indicator": "rsi", "period": period}


def macd(data: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD line, signal line, and histogram."""
    if not all(isinstance(p, int) and p > 0 for p in (fast, slow, signal)):
        raise ValueError("macd: fast, slow, signal must be positive integers")
    if fast >= slow:
        raise ValueError("macd: fast must be < slow")
    _validate_series(data, slow + signal, "macd")
    ema_fast = ema(data, fast)["values"]
    ema_slow = ema(data, slow)["values"]
    macd_line: list[float | None] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)
    valid = [v for v in macd_line if v is not None]
    sig = ema(valid, signal)["values"]
    macd_padded = macd_line[: len(macd_line) - len(valid)] + [
        v for v in macd_line if v is not None
    ]
    sig_padded: list[float | None] = [None] * (len(macd_padded) - len(sig)) + sig
    hist: list[float | None] = [
        m - s if m is not None and s is not None else None
        for m, s in zip(macd_padded, sig_padded)
    ]
    return {
        "values": {"macd": macd_padded, "signal": sig_padded, "histogram": hist},
        "indicator": "macd",
        "fast": fast,
        "slow": slow,
        "signal": signal,
    }


def bollinger(data: list[float], period: int = 20, std_dev: float = 2.0) -> dict:
    """Bollinger Bands: middle (SMA), upper, lower."""
    if not isinstance(period, int) or period < 2:
        raise ValueError("bollinger: period must be an integer >= 2")
    if not isinstance(std_dev, (int, float)) or std_dev <= 0:
        raise ValueError("bollinger: std_dev must be a positive number")
    _validate_series(data, period, "bollinger")
    mid = sma(data, period)["values"]
    upper, lower = [], []
    for i, m in enumerate(mid):
        if m is None:
            upper.append(None)
            lower.append(None)
        else:
            window = data[i - period + 1 : i + 1]
            variance = sum((x - m) ** 2 for x in window) / period
            sd = math.sqrt(variance) * std_dev
            upper.append(m + sd)
            lower.append(m - sd)
    return {
        "values": {"middle": mid, "upper": upper, "lower": lower},
        "indicator": "bollinger",
        "period": period,
        "std_dev": std_dev,
    }
