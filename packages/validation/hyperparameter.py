"""Hyperparameter Tuning — reproducible grid/random search with seed control.

Supports grid search and randomized search over parameter combinations
with configurable metric optimization and full result tracking.
Results use unified ValidationResult format with data provenance tracking.
"""
from __future__ import annotations

import os
import itertools
import random
from dataclasses import dataclass, field
from math import sqrt
from typing import Any

from packages.domain.decorators import experimental
from packages.metrics.risk import sharpe_ratio


# ---------------------------------------------------------------------------
# Configuration constants (override via .env)
# ---------------------------------------------------------------------------
DEFAULT_SEED = int(os.environ.get("LML_SEED", "42"))


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class TrialResult:
    """Result of a single hyperparameter trial."""
    trial: int
    params: dict[str, Any]
    metric_value: float
    rank: int = 0


@dataclass
class TuneResult:
    """Aggregated hyperparameter tuning result."""
    trials: list[TrialResult]
    best_params: dict[str, Any]
    best_metric: float
    metric: str
    n_trials: int
    seed: int
    method: str

    def summary(self) -> dict:
        """Return summary dictionary with top trials."""
        return {
            "method": self.method,
            "metric": self.metric,
            "n_trials": self.n_trials,
            "seed": self.seed,
            "best_params": self.best_params,
            "best_metric": round(self.best_metric, 4),
            "top_trials": [
                {
                    "trial": t.trial,
                    "params": t.params,
                    "metric": round(t.metric_value, 4),
                    "rank": t.rank,
                }
                for t in self.trials[:5]
            ],
        }


def _sample_params(param_grid: dict[str, list[Any]], rng: random.Random) -> dict[str, Any]:
    """Sample one parameter combination from the grid."""
    return {k: rng.choice(v) for k, v in param_grid.items()}


def _grid_params(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Generate all parameter combinations from the grid."""
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _evaluate_params(
    model_fn, data: list[float], params: dict[str, Any], metric: str,
) -> float:
    """Evaluate a single parameter set by running model_fn on data.

    Uses walk-forward style: train on first 2/3, test on last 1/3.
    """
    split = len(data) * 2 // 3
    train_data = data[:split]
    test_data = data[split:]
    predictions = model_fn(train_data, test_data, **params)
    if len(predictions) != len(test_data):
        predictions = predictions[:len(test_data)]
    test_returns = [
        test_data[j] / test_data[j - 1] - 1 if j > 0 else 0.0
        for j in range(len(test_data))
    ]
    pnl = [predictions[j] * test_returns[j] for j in range(len(test_data))]
    curve = [100.0]
    for r in pnl:
        curve.append(curve[-1] * (1 + r))
    if metric == "sharpe":
        try:
            return sharpe_ratio(curve)
        except ValueError:
            return 0.0
    elif metric == "return":
        if curve[0] == 0:
            return 0.0
        return curve[-1] / curve[0] - 1
    elif metric == "volatility":
        if len(curve) < 3:
            return 0.0
        rets = [b / a - 1 for a, b in zip(curve, curve[1:])]
        m = sum(rets) / len(rets)
        var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
        return sqrt(var) * sqrt(252)
    else:
        raise ValueError(f"unknown metric: {metric}")


@experimental
def hyperparameter_tune(
    model_fn,
    data: list[float],
    param_grid: dict[str, list[Any]],
    metric: str = "sharpe",
    n_trials: int = 50,
    seed: int = DEFAULT_SEED,
    method: str = "random",
) -> TuneResult:
    """Run hyperparameter tuning with reproducible results.

    Supports 'random' search (sample n_trials from grid) and 'grid'
    search (exhaustive, capped at n_trials).

    Args:
        model_fn: Callable(train_data, test_data, **params) -> list[float].
        data: Full price series (chronological).
        param_grid: Dict of param_name -> list of possible values.
        metric: Metric to optimize ('sharpe', 'return', 'volatility').
        n_trials: Number of trials for random search.
        seed: Random seed for reproducibility.
        method: 'random' for random search, 'grid' for exhaustive.

    Returns:
        TuneResult with all trials, best params, and ranking.

    Raises:
        ValueError: If param_grid is empty or data is too short.
    """
    if not param_grid:
        raise ValueError("param_grid must not be empty")
    if len(data) < 10:
        raise ValueError("data too short for tuning")
    rng = random.Random(seed)
    if method == "grid":
        all_combos = _grid_params(param_grid)
        rng.shuffle(all_combos)
        combos = all_combos[:n_trials] if len(all_combos) > n_trials else all_combos
    elif method == "random":
        combos = [_sample_params(param_grid, rng) for _ in range(n_trials)]
    else:
        raise ValueError(f"unknown method: {method} (use 'random' or 'grid')")
    trials: list[TrialResult] = []
    for i, params in enumerate(combos):
        metric_value = _evaluate_params(model_fn, data, params, metric)
        trials.append(TrialResult(trial=i, params=params, metric_value=metric_value))
    sorted_trials = sorted(trials, key=lambda t: t.metric_value, reverse=True)
    for rank, t in enumerate(sorted_trials, 1):
        t.rank = rank
    best = sorted_trials[0]
    return TuneResult(
        trials=sorted_trials, best_params=best.params, best_metric=best.metric_value,
        metric=metric, n_trials=len(trials), seed=seed, method=method,
    )
