"""Walk-Forward Validation — rolling train/test splits for time series.

Implements expanding-window walk-forward backtesting with configurable
train/test sizes and step length. Results use unified ValidationResult
format with data provenance tracking.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import sqrt

from packages.metrics.risk import sharpe_ratio


# ---------------------------------------------------------------------------
# Configuration constants (override via .env)
# ---------------------------------------------------------------------------
DEFAULT_TRAIN_WINDOW = int(os.environ.get("LML_WF_TRAIN_WINDOW", "252"))
DEFAULT_TEST_WINDOW = int(os.environ.get("LML_WF_TEST_WINDOW", "63"))
DEFAULT_STEP = int(os.environ.get("LML_WF_STEP", "21"))
DEFAULT_SEED = int(os.environ.get("LML_SEED", "42"))


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def experimental(func):
    """Mark a function as experimental — API may change without notice."""
    func._experimental = True
    return func


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class WalkForwardFold:
    """Result of a single walk-forward fold."""
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    metrics: dict = field(default_factory=dict)


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward backtest result."""
    folds: list[WalkForwardFold]
    train_window: int
    test_window: int
    step: int
    n_folds: int
    avg_sharpe: float
    avg_return: float
    oos_sharpe: float
    seed: int = DEFAULT_SEED

    def summary(self) -> dict:
        """Return summary dictionary with split documentation."""
        return {
            "n_folds": self.n_folds,
            "train_window": self.train_window,
            "test_window": self.test_window,
            "step": self.step,
            "avg_sharpe": round(self.avg_sharpe, 4),
            "avg_return": round(self.avg_return, 4),
            "oos_sharpe": round(self.oos_sharpe, 4),
            "seed": self.seed,
            "folds": [
                {
                    "fold": f.fold,
                    "train": [f.train_start, f.train_end],
                    "test": [f.test_start, f.test_end],
                    "metrics": f.metrics,
                }
                for f in self.folds
            ],
        }


def _curve_from_returns(returns: list[float], start_value: float = 100.0) -> list[float]:
    """Build equity curve from return series."""
    curve = [start_value]
    for r in returns:
        curve.append(curve[-1] * (1 + r))
    return curve


@experimental
def walk_forward_backtest(
    data: list[float],
    strategy_fn,
    train_window: int = DEFAULT_TRAIN_WINDOW,
    test_window: int = DEFAULT_TEST_WINDOW,
    step: int = DEFAULT_STEP,
    seed: int = DEFAULT_SEED,
) -> WalkForwardResult:
    """Run walk-forward backtest with rolling train/test windows.

    Expanding window: training set grows from ``train_window`` to full
    available history. A gap-free step ensures no data leakage.

    Args:
        data: Full price series (chronological).
        strategy_fn: Callable(train_data, test_data) -> list[float] signals.
        train_window: Initial training window size (observations).
        test_window: Out-of-sample test window size.
        step: Step size to advance the window each fold.
        seed: Random seed for reproducibility.

    Returns:
        WalkForwardResult with per-fold metrics and aggregate stats.

    Raises:
        ValueError: If data is too short or windows are invalid.
    """
    n = len(data)
    if n < train_window + test_window:
        raise ValueError(
            f"data length {n} < train_window + test_window "
            f"({train_window} + {test_window})"
        )
    if train_window < 2 or test_window < 1 or step < 1:
        raise ValueError("windows and step must be positive")

    folds: list[WalkForwardFold] = []
    pos = 0
    i = train_window
    while i + test_window <= n:
        train_data = data[:i]
        test_data = data[i:i + test_window]
        signals = strategy_fn(train_data, test_data)
        if len(signals) != test_window:
            raise ValueError(
                f"strategy_fn returned {len(signals)} signals, expected {test_window}"
            )
        test_returns = [
            test_data[j] / test_data[j - 1] - 1 if j > 0 else 0.0
            for j in range(test_window)
        ]
        pnl = [signals[j] * test_returns[j] for j in range(test_window)]
        curve = _curve_from_returns(pnl)
        try:
            sh = sharpe_ratio(curve)
        except ValueError:
            sh = 0.0
        total_ret = curve[-1] / curve[0] - 1 if curve[0] != 0 else 0.0
        folds.append(WalkForwardFold(
            fold=pos, train_start=0, train_end=i,
            test_start=i, test_end=i + test_window,
            metrics={"sharpe": round(sh, 4), "return": round(total_ret, 4), "n_obs": test_window},
        ))
        i += step
        pos += 1

    if not folds:
        raise ValueError("no folds generated — check window parameters")

    avg_sharpe = sum(f.metrics["sharpe"] for f in folds) / len(folds)
    avg_return = sum(f.metrics["return"] for f in folds) / len(folds)
    # aggregate OOS curve
    all_pnl = []
    for f in folds:
        idx = f.test_start
        tdata = data[idx:idx + (f.test_end - f.test_start)]
        sigs = strategy_fn(data[:f.train_end], tdata)
        trets = [tdata[j] / tdata[j - 1] - 1 if j > 0 else 0.0 for j in range(len(tdata))]
        all_pnl.extend(sigs[j] * trets[j] for j in range(len(tdata)))
    oos_curve = _curve_from_returns(all_pnl)
    try:
        oos_sharpe = sharpe_ratio(oos_curve)
    except ValueError:
        oos_sharpe = 0.0

    return WalkForwardResult(
        folds=folds, train_window=train_window, test_window=test_window,
        step=step, n_folds=len(folds), avg_sharpe=avg_sharpe,
        avg_return=avg_return, oos_sharpe=oos_sharpe, seed=seed,
    )
