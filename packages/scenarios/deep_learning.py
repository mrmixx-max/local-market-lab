"""Pure-numpy LSTM & GRU forecasters for univariate time series.

Functions:
  - lstm_forecast      : full LSTM with forget/input/output gates + BPTT
  - gru_forecast       : GRU with update/reset gates + BPTT
  - train_test_split_ts: chronological split (no shuffling)
"""
from __future__ import annotations
import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


def _xavier(fan_in, fan_out, rng):
    lim = np.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-lim, lim, (fan_out, fan_in))


def _adam_step(params, grads, m, v, t, lr=1e-3, b1=0.9, b2=0.999, eps=1e-8):
    for i in range(len(params)):
        m[i] = b1 * m[i] + (1 - b1) * grads[i]
        v[i] = b2 * v[i] + (1 - b2) * grads[i] ** 2
        mh = m[i] / (1 - b1 ** t)
        vh = v[i] / (1 - b2 ** t)
        params[i] -= lr * mh / (np.sqrt(vh) + eps)


def _clip_grads(grads, max_norm=1.0):
    total = np.sqrt(sum(np.sum(g ** 2) for g in grads))
    if total > max_norm:
        for g in grads:
            g *= max_norm / total


def _normalize(data):
    dmin, dmax = data.min(), data.max()
    scale = dmax - dmin if dmax - dmin > 1e-12 else 1.0
    return (data - dmin) / scale, dmin, scale


def train_test_split_ts(data, test_ratio=0.2):
    """Chronological train/test split — no randomisation."""
    if not 0 < test_ratio < 1:
        raise ValueError("test_ratio must be in (0, 1)")
    n = len(data)
    split = int(n * (1 - test_ratio))
    if split < 2 or n - split < 1:
        raise ValueError("not enough data for the given test_ratio")
    return data[:split], data[split:]


def lstm_forecast(data, horizon=30, hidden_size=32, epochs=100, lr=1e-3, seed=42):
    """LSTM forecaster: forget/input/output gates, BPTT, Adam, Xavier."""
    data = np.asarray(data, dtype=np.float64).ravel()
    if len(data) < 10:
        raise ValueError("need at least 10 data points")
    norm, dmin, scale = _normalize(data)
    H, rng = hidden_size, np.random.default_rng(seed)
    inp = 1 + H
    Wf, Wi, Wc, Wo = (_xavier(inp, H, rng) for _ in range(4))
    bf, bi, bc, bo = (np.zeros(H) for _ in range(4))
    Wo_out, bo_out = _xavier(H, 1, rng).ravel(), np.zeros(1)
    params = [Wf, Wi, Wc, Wo, bf, bi, bc, bo, Wo_out, bo_out]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    seq = len(norm)
    for ep in range(1, epochs + 1):
        h, c = np.zeros(H), np.zeros(H)
        cache = []
        for t in range(seq - 1):
            con = np.concatenate([h, [norm[t]]])
            f = _sigmoid(Wf @ con + bf)
            i = _sigmoid(Wi @ con + bi)
            cc = np.tanh(Wc @ con + bc)
            c = f * c + i * cc
            o = _sigmoid(Wo @ con + bo)
            h = o * np.tanh(c)
            cache.append((con, f, i, cc, c, o, h))
        grads = [np.zeros_like(p) for p in params]
        dh = np.zeros(H)
        dc = np.zeros(H)
        for t in reversed(range(len(cache))):
            con, f, i, cc, c, o, ht = cache[t]
            tgt = np.array([norm[t + 1]])
            pred = Wo_out @ ht + bo_out
            dp = 2.0 * (pred - tgt) / seq
            grads[8] += dp * ht
            grads[9] += dp
            dh += dp * Wo_out
            do = dh * np.tanh(c) * o * (1 - o)
            grads[3] += np.outer(do, con); grads[7] += do
            dc += dh * o * (1 - np.tanh(c) ** 2)
            dcc = dc * i * (1 - cc ** 2)
            grads[2] += np.outer(dcc, con); grads[6] += dcc
            di = dc * cc * i * (1 - i)
            grads[1] += np.outer(di, con); grads[5] += di
            c_prev = cache[t - 1][4] if t > 0 else np.zeros(H)
            df = dc * c_prev * f * (1 - f)
            grads[0] += np.outer(df, con); grads[4] += df
            dcon = Wf.T @ df + Wi.T @ di + Wc.T @ dcc + Wo.T @ do
            dh = dcon[:H]
            dc = dc * f
        _clip_grads(grads)
        _adam_step(params, grads, m, v, ep, lr=lr)
    h, c = np.zeros(H), np.zeros(H)
    for t in range(seq):
        con = np.concatenate([h, [norm[t]]])
        f = _sigmoid(Wf @ con + bf); i = _sigmoid(Wi @ con + bi)
        cc = np.tanh(Wc @ con + bc); c = f * c + i * cc
        o = _sigmoid(Wo @ con + bo); h = o * np.tanh(c)
    lv = norm[-1]
    fc = []
    for _ in range(horizon):
        con = np.concatenate([h, [lv]]); f = _sigmoid(Wf @ con + bf)
        i = _sigmoid(Wi @ con + bi); cc = np.tanh(Wc @ con + bc)
        c = f * c + i * cc; o = _sigmoid(Wo @ con + bo)
        h = o * np.tanh(c); lv = (Wo_out @ h + bo_out)[0]; fc.append(lv)
    fc = np.array(fc) * scale + dmin
    return {"model": "lstm", "forecast": [round(float(x), 4) for x in fc],
            "last": round(float(data[-1]), 4), "horizon": horizon,
            "hidden_size": hidden_size, "epochs": epochs}


def gru_forecast(data, horizon=30, hidden_size=32, epochs=100, lr=1e-3, seed=42):
    """GRU forecaster: update/reset gates, BPTT, Adam, Xavier.

    Args:
        data: 1-D array-like of float prices/values (min 10 points).
        horizon: Number of steps to forecast (>=1).
        hidden_size: Number of GRU hidden units.
        epochs: Training iterations over the full sequence.
        lr: Adam learning rate.
        seed: RNG seed for reproducibility.

    Returns:
        dict with keys: model, forecast, last, horizon, hidden_size, epochs.
    """
    data = np.asarray(data, dtype=np.float64).ravel()
    if len(data) < 10:
        raise ValueError("need at least 10 data points")
    norm, dmin, scale = _normalize(data)
    H, rng = hidden_size, np.random.default_rng(seed)
    inp = 1 + H
    Wz, Wr, Wh = (_xavier(inp, H, rng) for _ in range(3))
    bz, br, bh = (np.zeros(H) for _ in range(3))
    Wo_out, bo_out = _xavier(H, 1, rng).ravel(), np.zeros(1)
    params = [Wz, Wr, Wh, bz, br, bh, Wo_out, bo_out]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    seq = len(norm)
    for ep in range(1, epochs + 1):
        h = np.zeros(H)
        cache = []
        for t in range(seq - 1):
            con = np.concatenate([h, [norm[t]]])
            z = _sigmoid(Wz @ con + bz)
            r = _sigmoid(Wr @ con + br)
            con_r = np.concatenate([r * h, [norm[t]]])
            hc = np.tanh(Wh @ con_r + bh)
            h = (1 - z) * h + z * hc
            cache.append((con, con_r, z, r, hc, h))
        grads = [np.zeros_like(p) for p in params]
        dh = np.zeros(H)
        for t in reversed(range(len(cache))):
            con, con_r, z, r, hc, ht = cache[t]
            hp = cache[t - 1][5] if t > 0 else np.zeros(H)
            tgt = np.array([norm[t + 1]])
            pred = Wo_out @ ht + bo_out
            dp = 2.0 * (pred - tgt) / seq
            grads[6] += dp * ht; grads[7] += dp
            dh += dp * Wo_out
            dz = dh * (hc - hp) * z * (1 - z)
            grads[0] += np.outer(dz, con); grads[3] += dz
            dhc = dh * z * (1 - hc ** 2)
            grads[2] += np.outer(dhc, con_r); grads[5] += dhc
            dcr = Wh.T @ dhc
            dr = dcr[:H] * hp * r * (1 - r)
            grads[1] += np.outer(dr, con); grads[4] += dr
            dcon = Wz.T @ dz + Wr.T @ dr
            dh = dcon[:H] + dh * (1 - z) + dcr[:H] * r
        _clip_grads(grads)
        _adam_step(params, grads, m, v, ep, lr=lr)
    h = np.zeros(H)
    for t in range(seq):
        con = np.concatenate([h, [norm[t]]])
        z = _sigmoid(Wz @ con + bz); r = _sigmoid(Wr @ con + br)
        con_r = np.concatenate([r * h, [norm[t]]])
        hc = np.tanh(Wh @ con_r + bh); h = (1 - z) * h + z * hc
    lv = norm[-1]; fc = []
    for _ in range(horizon):
        con = np.concatenate([h, [lv]]); z = _sigmoid(Wz @ con + bz)
        r = _sigmoid(Wr @ con + br); con_r = np.concatenate([r * h, [lv]])
        hc = np.tanh(Wh @ con_r + bh); h = (1 - z) * h + z * hc
        lv = (Wo_out @ h + bo_out)[0]; fc.append(lv)
    fc = np.array(fc) * scale + dmin
    return {"model": "gru", "forecast": [round(float(x), 4) for x in fc],
            "last": round(float(data[-1]), 4), "horizon": horizon,
            "hidden_size": hidden_size, "epochs": epochs}


def walk_forward_validate(model_fn, data, min_train=100, step=20, horizon=5, **kw):
    """Chronological walk-forward validation for any forecast model.

    For each window start position, trains on data[:start] and tests on
    data[start:start+horizon]. Predictions and actuals are concatenated.

    Args:
        model_fn: Callable(data_array, horizon, **kw) -> dict with 'forecast' key.
        data: Full 1-D time series.
        min_train: Minimum training size before first prediction.
        step: Step size for rolling the window.
        horizon: Forecast horizon per fold.
        **kw: Passed through to model_fn.

    Returns:
        dict with: predictions, actuals, rmse, mae, n_folds, fold_starts.
    """
    data = np.asarray(data, dtype=np.float64).ravel()
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
