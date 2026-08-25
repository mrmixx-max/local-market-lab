"""Time-Series Cross-Validation — Purged K-Fold for sequential data.

Implements purged cross-validation where a gap is enforced between
train and test folds to prevent information leakage in time series.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import sqrt

from packages.domain.decorators import experimental
from packages.metrics.risk import sharpe_ratio

# Configuration constants (override via .env)
DEFAULT_N_SPLITS = int(os.environ.get("LML_CV_SPLITS", "5"))
DEFAULT_GAP = int(os.environ.get("LML_CV_GAP", "21"))
DEFAULT_SEED = int(os.environ.get("LML_SEED", "42"))


@dataclass
class CVFold:
    """Result of a single CV fold."""

    fold: int
    train_indices: list[int]
    test_indices: list[int]
    metrics: dict = field(default_factory=dict)


@dataclass
class CVResult:
    """Aggregated cross-validation result."""

    folds: list[CVFold]
    n_splits: int
    gap: int
    avg_metric: float
    std_metric: float
    metric_name: str
    seed: int = DEFAULT_SEED

    def summary(self) -> dict:
        """Return summary dictionary with split documentation."""
        return {
            "n_splits": self.n_splits,
            "gap": self.gap,
            "metric": self.metric_name,
            "avg": round(self.avg_metric, 4),
            "std": round(self.std_metric, 4),
            "seed": self.seed,
            "folds": [
                {
                    "fold": f.fold,
                    "train_size": len(f.train_indices),
                    "test_size": len(f.test_indices),
                    "metric": round(f.metrics.get(self.metric_name, 0), 4),
                }
                for f in self.folds
            ],
        }


def _purged_kfold_indices(
    n: int, n_splits: int, gap: int
) -> list[tuple[list[int], list[int]]]:
    """Generate purged K-Fold train/test index pairs. Gap prevents leakage."""
    fold_size = n // n_splits
    if fold_size <= gap:
        raise ValueError(f"fold_size {fold_size} must be > gap {gap}")
    indices = []
    for k in range(n_splits):
        test_start = k * fold_size
        test_end = min(test_start + fold_size, n)
        test_idx = list(range(test_start, test_end))
        train_idx = []
        for i in range(n):
            if test_start <= i < test_end:
                continue
            if test_start - gap <= i < test_start:
                continue
            if test_end <= i < test_end + gap:
                continue
            train_idx.append(i)
        if not train_idx:
            raise ValueError(f"fold {k}: empty training set")
        indices.append((train_idx, test_idx))
    return indices


def _compute_metric(data: list[float], metric: str) -> float:
    """Compute a performance metric on a price series."""
    if metric == "sharpe":
        try:
            return sharpe_ratio(data)
        except ValueError:
            return 0.0
    elif metric == "return":
        if len(data) < 2 or data[0] == 0:
            return 0.0
        return data[-1] / data[0] - 1
    elif metric == "volatility":
        if len(data) < 3:
            return 0.0
        rets = [b / a - 1 for a, b in zip(data, data[1:])]
        m = sum(rets) / len(rets)
        var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
        return sqrt(var) * sqrt(252)
    else:
        raise ValueError(f"unknown metric: {metric}")


@experimental
def time_series_cv(
    model_fn,
    data: list[float],
    n_splits: int = DEFAULT_N_SPLITS,
    gap: int = DEFAULT_GAP,
    metric: str = "sharpe",
    seed: int = DEFAULT_SEED,
) -> CVResult:
    """Run purged K-Fold cross-validation on time series data.

    A gap of ``gap`` observations is enforced between train and test
    to prevent information leakage from autocorrelated features.

    Args:
        model_fn: Callable(train_data, test_data) -> list[float] predictions.
        data: Full price series (chronological).
        n_splits: Number of CV folds.
        gap: Number of observations to purge between train and test.
        metric: Metric to track ('sharpe', 'return', 'volatility').
        seed: Random seed for reproducibility.

    Returns:
        CVResult with per-fold metrics and aggregate statistics.

    Raises:
        ValueError: If data is too short or windows are invalid.
    """
    n = len(data)
    if n < n_splits * (gap + 2):
        raise ValueError(
            f"data length {n} too small for {n_splits} splits with gap {gap}"
        )
    fold_indices = _purged_kfold_indices(n, n_splits, gap)
    folds: list[CVFold] = []
    for k, (train_idx, test_idx) in enumerate(fold_indices):
        train_data = [data[i] for i in train_idx]
        test_data = [data[i] for i in test_idx]
        predictions = model_fn(train_data, test_data)
        if len(predictions) != len(test_data):
            raise ValueError(
                f"model_fn returned {len(predictions)} predictions, expected {len(test_data)}"
            )
        test_returns = [
            test_data[j] / test_data[j - 1] - 1 if j > 0 else 0.0
            for j in range(len(test_data))
        ]
        pnl = [predictions[j] * test_returns[j] for j in range(len(test_data))]
        curve = [100.0]
        for r in pnl:
            curve.append(curve[-1] * (1 + r))
        fold_metric = _compute_metric(curve, metric)
        folds.append(
            CVFold(
                fold=k,
                train_indices=train_idx,
                test_indices=test_idx,
                metrics={metric: fold_metric},
            )
        )
    metrics_list = [f.metrics[metric] for f in folds]
    avg_m = sum(metrics_list) / len(metrics_list)
    std_m = (
        sqrt(
            sum((m - avg_m) ** 2 for m in metrics_list) / max(1, len(metrics_list) - 1)
        )
        if len(metrics_list) > 1
        else 0.0
    )
    return CVResult(
        folds=folds,
        n_splits=n_splits,
        gap=gap,
        avg_metric=avg_m,
        std_metric=std_m,
        metric_name=metric,
        seed=seed,
    )
