"""Feature importance: Permutation Importance + SHAP-like for LSTM/Transformer.

Pure numpy implementation. Results include run_id, data_hash, and splits_used
to align with walk-forward validation (packages/domain/constants.py).
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Callable

import numpy as np

from packages.domain.constants import (
    WALK_FORWARD_STEP,
    WALK_FORWARD_TEST_WINDOW,
    WALK_FORWARD_TRAIN_WINDOW,
)
from packages.domain.entities import ExportQuality, ExplainabilityResult, FeatureImportanceItem


def _data_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _splits_str() -> str:
    return (f"walk_forward_{WALK_FORWARD_TRAIN_WINDOW}_"
            f"{WALK_FORWARD_TEST_WINDOW}_{WALK_FORWARD_STEP}")


def permutation_importance(
    predict: Callable[[np.ndarray], np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str] | None = None,
    n_repeats: int = 10,
    seed: int = 42,
    metric: str = "mse",
    model_name: str = "model",
    data_quality: ExportQuality | None = None,
) -> ExplainabilityResult:
    """Compute permutation importance. Returns ExplainabilityResult with metadata."""
    rng = np.random.default_rng(seed)
    n_samples, n_features = X.shape
    if feature_names is None:
        feature_names = [f"f{i}" for i in range(n_features)]
    baseline = predict(X)
    base_err = _error(baseline, y, metric)
    imp = np.zeros((n_repeats, n_features))
    for r in range(n_repeats):
        for f in range(n_features):
            X_perm = X.copy()
            X_perm[:, f] = rng.permutation(X_perm[:, f])
            perm_err = _error(predict(X_perm), y, metric)
            imp[r, f] = perm_err - base_err
    means = imp.mean(axis=0)
    stds = imp.std(axis=0)
    items = [FeatureImportanceItem(feature_names[i], float(means[i]), float(stds[i]))
             for i in range(n_features)]
    return ExplainabilityResult(
        run_id=str(uuid.uuid4())[:12],
        model=model_name,
        feature_importance=items,
        data_quality=data_quality or ExportQuality(n_samples, 0.0, "unknown"),
        splits_used=_splits_str(),
        data_hash=_data_hash(X),
    )


def _error(pred: np.ndarray, y: np.ndarray, metric: str) -> float:
    """Compute error between prediction and target."""
    if metric == "mse":
        return float(np.mean((pred - y) ** 2))
    if metric == "mae":
        return float(np.mean(np.abs(pred - y)))
    if metric == "rmse":
        return float(np.sqrt(np.mean((pred - y) ** 2)))
    raise ValueError(f"unknown metric: {metric}")


def shapley_approx(
    predict: Callable[[np.ndarray], np.ndarray],
    X: np.ndarray,
    instance: np.ndarray,
    n_samples: int = 100,
    seed: int = 42,
) -> dict:
    """Approximate SHAP values for a single instance via marginal contributions."""
    rng = np.random.default_rng(seed)
    n_features = X.shape[1]
    background = X[rng.choice(len(X), min(50, len(X)), replace=False)]
    base_val = float(np.mean(predict(background)))
    shap_vals = np.zeros(n_features)
    for f in range(n_features):
        contributions = []
        for _ in range(n_samples):
            subset = set(i for i in range(n_features) if rng.random() > 0.5)
            subset.discard(f)
            z0 = _build_instance(instance, background, subset, exclude=f)
            z1 = _build_instance(instance, background, subset | {f}, exclude=f)
            p0 = float(np.mean(predict(z0)))
            p1 = float(np.mean(predict(z1)))
            contributions.append(p1 - p0)
        shap_vals[f] = np.mean(contributions)
    return {
        "feature_names": [f"f{i}" for i in range(n_features)],
        "shap_values": shap_vals.tolist(),
        "base_value": base_val,
        "prediction": float(np.mean(predict(instance.reshape(1, -1)))),
    }


def _build_instance(instance: np.ndarray, background: np.ndarray,
                    include: np.ndarray | set[int], exclude: int) -> np.ndarray:
    """Build blended instance: features in `include` from `instance`, others from background."""
    n_bg = len(background)
    n = len(instance)
    if isinstance(include, set):
        mask = np.array([i in include for i in range(n)])
    else:
        mask = include.astype(bool)
    mask[exclude] = True
    bg_idx = np.random.randint(0, n_bg, size=n)
    out = np.where(mask, instance, background[bg_idx, np.arange(n)])
    return out.reshape(1, -1)
