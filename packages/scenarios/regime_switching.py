"""Marktregime-basierte Vorhersage — reine numpy-Implementierung.

detect_regime(returns, n_regimes=3)  — EM-GMM für Trend/Seitwärts/Volatil
regime_forecast(data, horizon=30)   — regimespezifische Modelle
regime_probability(data)             — Wahrscheinlichkeiten pro Regime
"""

from __future__ import annotations
import math
import numpy as np


def _as_array(obj, name: str, min_n: int = 10) -> np.ndarray:
    """Validate and convert input to a 1-D float array with >= min_n finite elements."""
    arr = np.asarray(obj, dtype=float)
    if arr.ndim != 1 or arr.size < min_n:
        raise ValueError(f"{name} must be 1-D with >= {min_n} elements")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite numbers")
    return arr


def _gauss(x: np.ndarray, mu: float, s: float) -> np.ndarray:
    """Univariate Gaussian density at x with mean mu and std s."""
    s = max(s, 1e-12)
    z = (x - mu) / s
    return np.exp(-0.5 * z * z) / (s * math.sqrt(2.0 * math.pi))


def _gmm_fit(x: np.ndarray, k: int, max_iter: int = 50, seed: int = 42):
    """EM-Algorithmus für 1-D Gaussian Mixture. Returns (mu, sigma, pi, resp).

    Stabilisiert durch:
    - Min-Sigma-Boden (1e-4) zur Vermeidung degenerierter Cluster
    - K-means++-ähnliche Initialisierung für bessere Konvergenz
    - Vektorisierte E-Step (alle Komponenten gleichzeitig)
    """
    n = x.size
    rng = np.random.default_rng(seed)
    # K-means++-style initialization for means
    centers = [rng.integers(n)]
    for _ in range(1, k):
        dists = np.min([np.abs(x - x[c]) for c in centers], axis=0)
        probs = dists / (dists.sum() + 1e-12)
        centers.append(rng.choice(n, p=probs))
    mu = np.array([float(x[c]) for c in centers])
    sigma = np.array([max(float(np.std(x)), 1e-4)] * k)
    pi = np.ones(k) / k
    min_sigma = 1e-4  # hard floor to prevent degenerate clusters
    resp = np.zeros((n, k))
    sqrt_2pi = math.sqrt(2.0 * math.pi)
    for _ in range(max_iter):
        # E-step: vectorized — compute all components at once
        # Shape: (n, k)
        z = (x[:, None] - mu[None, :]) / sigma[None:]  # (n, k)
        gauss = np.exp(-0.5 * z * z) / (sigma[None, :] * sqrt_2pi)
        resp = pi[None, :] * gauss  # (n, k)
        rs = resp.sum(axis=1, keepdims=True)
        rs = np.where(rs < 1e-30, 1e-30, rs)
        resp /= rs
        # M-step: update parameters
        rk = resp.sum(axis=0)
        rk = np.where(rk < 1e-12, 1e-12, rk)
        for j in range(k):
            mu[j] = float(np.dot(resp[:, j], x) / rk[j])
            var = float(np.dot(resp[:, j], (x - mu[j]) ** 2) / rk[j])
            sigma[j] = math.sqrt(max(var, min_sigma**2))
            pi[j] = rk[j] / n
        # renormalize pi to sum to 1
        pi = pi / pi.sum()
    return mu, sigma, pi, resp


def detect_regime(returns, n_regimes: int = 3) -> dict:
    """Erkennt Marktregime via EM-Algorithmus für Gaussian Mixture."""
    x = _as_array(returns, "returns")
    if not isinstance(n_regimes, int) or n_regimes < 2:
        raise ValueError("n_regimes must be an integer >= 2")
    mu, sigma, pi, resp = _gmm_fit(x, n_regimes)
    labels = np.argmax(resp, axis=1)
    order = np.argsort(mu)[::-1]  # Trend (höchster Mean) → Seitwärts → Volatil
    mapping = {int(old): int(new) for new, old in enumerate(order)}
    labels = np.array([mapping[int(l)] for l in labels], dtype=int)
    mu, sigma, pi = mu[order], sigma[order], pi[order]
    names = (
        ["Trend", "Seitwaerts", "Volatil"]
        + [f"Regime_{i}" for i in range(3, n_regimes)]
    )[:n_regimes]
    return {
        "labels": labels.tolist(),
        "means": [round(float(v), 6) for v in mu],
        "stds": [round(float(v), 6) for v in sigma],
        "weights": [round(float(v), 4) for v in pi],
        "regime_names": names,
        "n_regimes": n_regimes,
    }


def _momentum(data: np.ndarray, h: int) -> list[float]:
    """Momentum model: extrapolates drift from the last 20-point window."""
    w = data[-min(20, len(data)) :]
    drift = float(np.mean(np.diff(w))) if len(w) > 1 else 0.0
    return [round(float(data[-1]) + drift * (i + 1), 4) for i in range(h)]


def _mean_reversion(data: np.ndarray, h: int) -> list[float]:
    """Mean-reversion model: pulls toward the long-term mean with rate 0.15."""
    target = float(np.mean(data))
    v = float(data[-1])
    fc = []
    for _ in range(h):
        v += 0.15 * (target - v)
        fc.append(round(v, 4))
    return fc


def _garch_like(data: np.ndarray, h: int) -> list[float]:
    """GARCH(1,1)-like: volatility extrapolation via Monte Carlo simulation."""
    rets = np.diff(data)
    omega, alpha, beta = 1e-5, 0.1, 0.85
    var = float(np.var(rets))
    for r in rets:
        var = omega + alpha * r * r + beta * var
    rng = np.random.default_rng(123)
    paths = np.zeros((500, h))
    for s in range(500):
        v, lv = float(data[-1]), var
        for i in range(h):
            shock = float(rng.normal(0, math.sqrt(max(lv, 1e-12))))
            v += shock
            paths[s, i] = v
            lv = omega + alpha * shock * shock + beta * lv
    return [round(float(np.mean(paths[:, i])), 4) for i in range(h)]


def regime_forecast(data, horizon: int = 30) -> dict:
    """Regimespezifische Modelle, kombiniert nach aktuellem Regime."""
    arr = _as_array(data, "data")
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    rets = np.diff(arr)
    reg = detect_regime(rets)
    cur = int(reg["labels"][-1])
    names = reg["regime_names"]
    models = (
        [_momentum, _mean_reversion, _garch_like]
        if reg["n_regimes"] == 3
        else [_momentum] * reg["n_regimes"]
    )
    forecast = models[cur](arr, horizon)
    sigma = float(np.std(rets[-min(20, rets.size) :]))
    band = [1.96 * sigma * math.sqrt(i + 1) for i in range(horizon)]
    return {
        "model": "regime_switching",
        "current_regime": names[cur],
        "current_regime_id": cur,
        "forecast": forecast,
        "upper": [round(forecast[i] + band[i], 4) for i in range(horizon)],
        "lower": [round(forecast[i] - band[i], 4) for i in range(horizon)],
        "regime_names": names,
        "regime_means": reg["means"],
        "regime_stds": reg["stds"],
        "regime_weights": reg["weights"],
        "last": round(float(arr[-1]), 4),
        "horizon": horizon,
    }


def regime_probability(data) -> dict:
    """Gibt Wahrscheinlichkeiten für jedes Regime zurück."""
    arr = _as_array(data, "data")
    rets = np.diff(arr)
    reg = detect_regime(rets)
    mu, sigma, pi_w = (
        np.array(reg["means"]),
        np.array(reg["stds"]),
        np.array(reg["weights"]),
    )
    k = reg["n_regimes"]
    names = reg["regime_names"]
    inst = np.array(
        [
            pi_w[j] * _gauss(np.array([float(rets[-1])]), mu[j], sigma[j])[0]
            for j in range(k)
        ]
    )
    inst = inst / inst.sum() if inst.sum() > 0 else np.ones(k) / k
    labels = np.array(reg["labels"])
    window = labels[-min(20, labels.size) :]
    smoothed = [round(float(np.mean(window == j)), 4) for j in range(k)]
    return {
        "model": "regime_probability",
        "probabilities": {names[j]: round(float(inst[j]), 4) for j in range(k)},
        "smoothed_probabilities": {names[j]: smoothed[j] for j in range(k)},
        "current_regime": names[int(labels[-1])],
        "regime_names": names,
        "n_regimes": k,
    }
