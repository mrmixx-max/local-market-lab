"""Encoder-only Transformer for time series forecasting — pure numpy."""
from __future__ import annotations

import math

import numpy as np


def causal_attention_mask(seq_len: int) -> np.ndarray:
    """Upper-triangular mask (True = masked) to prevent future attention."""
    return np.triu(np.ones((seq_len, seq_len), dtype=bool), k=1)


def positional_encoding(seq_len: int, d_model: int = 32) -> np.ndarray:
    """Sinus / cosine positional encoding, shape (seq_len, d_model)."""
    pe = np.zeros((seq_len, d_model))
    pos = np.arange(seq_len)[:, None]
    div = np.exp(np.arange(0, d_model, 2) * -(math.log(10000.0) / d_model))
    pe[:, 0::2] = np.sin(pos * div)
    pe[:, 1::2] = np.cos(pos * div)
    return pe


def _layer_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps)


def _feed_forward(x: np.ndarray, d_ff: int = 64) -> np.ndarray:
    d_model = x.shape[-1]
    rng = np.random.RandomState(0)
    w1 = rng.randn(d_model, d_ff).astype(float) * 0.1
    w2 = rng.randn(d_ff, d_model).astype(float) * 0.1
    return np.maximum(0, x @ w1) @ w2


def multi_head_attention(Q, K, V, n_heads=4, mask=None):
    """Scaled dot-product attention with n_heads parallel heads."""
    seq_len, d_model = Q.shape
    assert d_model % n_heads == 0, "d_model must be divisible by n_heads"
    d_head = d_model // n_heads
    rng = np.random.RandomState(42)
    w_q = rng.randn(d_model, d_model).astype(float) * 0.1
    w_k = rng.randn(d_model, d_model).astype(float) * 0.1
    w_v = rng.randn(d_model, d_model).astype(float) * 0.1
    w_o = rng.randn(d_model, d_model).astype(float) * 0.1
    Q, K, V = Q @ w_q, K @ w_k, V @ w_v
    Q = Q.reshape(seq_len, n_heads, d_head).transpose(1, 0, 2)
    K = K.reshape(seq_len, n_heads, d_head).transpose(1, 0, 2)
    V = V.reshape(seq_len, n_heads, d_head).transpose(1, 0, 2)
    scale = math.sqrt(d_head)
    scores = Q @ K.transpose(0, 2, 1) / scale
    if mask is not None:
        scores[:, mask] = -1e9
    scores -= scores.max(axis=-1, keepdims=True)
    attn = np.exp(scores)
    attn /= attn.sum(axis=-1, keepdims=True)
    out = attn @ V
    out = out.transpose(1, 0, 2).reshape(seq_len, d_model)
    return out @ w_o


def _encoder_layer(x, n_heads=4, mask=None):
    """MHA → Add&Norm → FFN → Add&Norm."""
    attn_out = multi_head_attention(x, x, x, n_heads=n_heads, mask=mask)
    x = _layer_norm(x + attn_out)
    ff_out = _feed_forward(x)
    return _layer_norm(x + ff_out)


def transformer_forecast(data, horizon=30, d_model=32, n_heads=4, n_layers=2):
    """Encoder-only Transformer forecast for univariate time series.

    Uses sinusoidal positional encoding, causal multi-head self-attention,
    and feed-forward layers. No training — uses fixed random projections
    (acts as a random feature extractor suitable for short-term patterns).

    Args:
        data: 1-D array-like of float values (min 2 points).
        horizon: Number of steps to forecast (>=1).
        d_model: Embedding dimension (must be divisible by n_heads).
        n_heads: Number of attention heads.
        n_layers: Number of encoder layers.

    Returns:
        dict with: forecast, ci_68_lower/upper, ci_95_lower/upper,
                   d_model, n_heads, n_layers.
    """
    if len(data) < 2:
        raise ValueError("data must contain at least 2 points")
    if horizon < 1:
        raise ValueError("horizon must be positive")
    if d_model % n_heads != 0:
        raise ValueError("d_model must be divisible by n_heads")
    y = np.array(data, dtype=float)
    n = len(y)
    mu, sigma = y.mean(), y.std() + 1e-8
    y_norm = (y - mu) / sigma
    rng = np.random.RandomState(7)
    proj_in = rng.randn(1, d_model).astype(float) * 0.1
    seq = y_norm[:, None] @ proj_in
    seq += positional_encoding(n, d_model)
    mask = causal_attention_mask(n)
    for _ in range(n_layers):
        seq = _encoder_layer(seq, n_heads=n_heads, mask=mask)
    proj_out = rng.randn(d_model, 1).astype(float) * 0.1
    preds = (seq @ proj_out).ravel()
    last_state = seq[-1:]
    future_norm = []
    for _ in range(horizon):
        next_val = (last_state @ proj_out).ravel()[0]
        future_norm.append(next_val)
        new_step = np.array([[next_val]]) @ proj_in
        new_step += positional_encoding(1, d_model)
        step_mask = causal_attention_mask(1)
        for _ in range(n_layers):
            new_step = _encoder_layer(new_step, n_heads=n_heads, mask=step_mask)
        last_state = new_step
    future_norm = np.array(future_norm)
    forecast = future_norm * sigma + mu
    resid = y - (preds * sigma + mu)
    sigma_resid = np.std(resid) + 1e-8
    ci_68 = 1.0 * sigma_resid * np.sqrt(np.arange(1, horizon + 1))
    ci_95 = 1.96 * sigma_resid * np.sqrt(np.arange(1, horizon + 1))
    return {
        "forecast": forecast.tolist(),
        "ci_68_lower": (forecast - ci_68).tolist(),
        "ci_68_upper": (forecast + ci_68).tolist(),
        "ci_95_lower": (forecast - ci_95).tolist(),
        "ci_95_upper": (forecast + ci_95).tolist(),
        "d_model": d_model,
        "n_heads": n_heads,
        "n_layers": n_layers,
    }


def walk_forward_validate(model_fn, data, min_train=60, step=20, horizon=5, **kw):
    """Chronological walk-forward validation for Transformer forecast.

    Args:
        model_fn: Callable(data, horizon, **kw) -> dict with 'forecast' key.
        data: Full 1-D time series.
        min_train: Minimum training size (default 60 for Transformer).
        step: Step size for rolling window.
        horizon: Forecast horizon per fold.
        **kw: Passed through to model_fn.

    Returns:
        dict with: predictions, actuals, rmse, mae, n_folds, fold_starts.
    """
    data = np.asarray(data, dtype=float)
    predictions, actuals, fold_starts = [], [], []
    for start in range(min_train, len(data) - horizon, step):
        train = data[:start]
        test = data[start:start + horizon]
        try:
            result = model_fn(train, horizon, **kw)
            predictions.extend(result["forecast"])
            actuals.extend(test)
            fold_starts.append(start)
        except Exception:
            continue
    if not predictions:
        return {"predictions": [], "actuals": [], "rmse": float("nan"),
                "mae": float("nan"), "n_folds": 0, "fold_starts": []}
    p, a = np.array(predictions), np.array(actuals)
    return {"predictions": p.tolist(), "actuals": a.tolist(),
            "rmse": float(np.sqrt(np.mean((p - a) ** 2))),
            "mae": float(np.mean(np.abs(p - a))),
            "n_folds": len(fold_starts), "fold_starts": fold_starts}
