"""Tests for validation package: walk-forward, CV, hyperparameter tuning."""

from __future__ import annotations

import numpy as np
import pytest

from packages.validation.walk_forward import walk_forward_backtest, WalkForwardResult
from packages.validation.cv import time_series_cv, CVResult, _purged_kfold_indices
from packages.validation.hyperparameter import hyperparameter_tune, TuneResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def price_data():
    """Synthetic price series (500 days)."""
    np.random.seed(42)
    n = 500
    returns = np.random.normal(0.0005, 0.02, n)
    return (100 * np.exp(np.cumsum(returns))).tolist()


@pytest.fixture
def short_data():
    """Short price series for edge cases."""
    return [100.0, 101.0, 99.5, 102.0, 103.5, 102.0, 104.0, 105.5, 103.0, 106.0]


def simple_strategy(train_data, test_data, **kwargs):
    """Simple trend-following strategy for testing (accepts optional params)."""
    if len(train_data) < 2:
        return [0.0] * len(test_data)
    returns = [b / a - 1 for a, b in zip(train_data, train_data[1:])]
    avg = sum(returns) / len(returns)
    signal = 1.0 if avg > 0 else -1.0
    return [signal] * len(test_data)


# ===========================================================================
# Walk-Forward Tests
# ===========================================================================


class TestWalkForward:
    def test_basic_run(self, price_data):
        result = walk_forward_backtest(price_data, simple_strategy)
        assert isinstance(result, WalkForwardResult)
        assert result.n_folds > 0
        assert result.train_window == 252
        assert result.test_window == 63
        assert result.step == 21

    def test_custom_windows(self, price_data):
        result = walk_forward_backtest(
            price_data,
            simple_strategy,
            train_window=100,
            test_window=50,
            step=25,
        )
        assert result.train_window == 100
        assert result.test_window == 50
        assert result.step == 25
        assert result.n_folds > 0

    def test_summary(self, price_data):
        result = walk_forward_backtest(price_data, simple_strategy)
        summary = result.summary()
        assert "n_folds" in summary
        assert "avg_sharpe" in summary
        assert "oos_sharpe" in summary
        assert len(summary["folds"]) == result.n_folds

    def test_data_too_short(self):
        with pytest.raises(ValueError):
            walk_forward_backtest([1, 2, 3], simple_strategy)

    def test_invalid_windows(self, price_data):
        with pytest.raises(ValueError):
            walk_forward_backtest(price_data, simple_strategy, train_window=0)

    def test_wrong_signal_length(self, price_data):
        def bad_strategy(train, test):
            return [1.0] * (len(test) + 5)

        with pytest.raises(ValueError):
            walk_forward_backtest(price_data, bad_strategy)

    def test_folds_have_metrics(self, price_data):
        result = walk_forward_backtest(price_data, simple_strategy)
        for fold in result.folds:
            assert "sharpe" in fold.metrics
            assert "return" in fold.metrics


# ===========================================================================
# Time-Series CV Tests
# ===========================================================================


class TestTimeSeriesCV:
    def test_basic_run(self, price_data):
        result = time_series_cv(simple_strategy, price_data)
        assert isinstance(result, CVResult)
        assert result.n_splits == 5
        assert result.gap == 21
        assert len(result.folds) == 5

    def test_custom_splits(self, price_data):
        result = time_series_cv(simple_strategy, price_data, n_splits=3, gap=10)
        assert result.n_splits == 3
        assert result.gap == 10

    def test_summary(self, price_data):
        result = time_series_cv(simple_strategy, price_data)
        summary = result.summary()
        assert "n_splits" in summary
        assert "avg" in summary
        assert "std" in summary

    def test_purged_indices(self):
        indices = _purged_kfold_indices(100, 5, gap=5)
        assert len(indices) == 5
        for train_idx, test_idx in indices:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            # no overlap
            assert set(train_idx).isdisjoint(set(test_idx))

    def test_gap_respected(self):
        indices = _purged_kfold_indices(100, 5, gap=5)
        for train_idx, test_idx in indices:
            test_set = set(test_idx)
            for ti in test_idx:
                for g in range(1, 6):
                    # gap before
                    if ti - g >= 0:
                        assert ti - g not in set(train_idx) or ti - g in test_set
                    # gap after
                    if ti + g < 100:
                        assert ti + g not in set(train_idx) or ti + g in test_set

    def test_data_too_small(self):
        with pytest.raises(ValueError):
            time_series_cv(simple_strategy, [1, 2, 3, 4, 5], n_splits=5, gap=2)

    def test_wrong_prediction_length(self, price_data):
        def bad_model(train, test):
            return [1.0] * (len(test) + 3)

        with pytest.raises(ValueError):
            time_series_cv(bad_model, price_data)

    def test_different_metrics(self, price_data):
        for metric in ["sharpe", "return", "volatility"]:
            result = time_series_cv(simple_strategy, price_data, metric=metric)
            assert result.metric_name == metric


# ===========================================================================
# Hyperparameter Tuning Tests
# ===========================================================================


class TestHyperparameterTune:
    def test_basic_run(self, price_data):
        param_grid = {"lookback": [10, 20], "threshold": [0.01, 0.02]}
        result = hyperparameter_tune(
            simple_strategy,
            price_data,
            param_grid,
            n_trials=4,
        )
        assert isinstance(result, TuneResult)
        assert result.n_trials == 4
        assert result.method == "random"
        assert result.seed == 42

    def test_grid_method(self, price_data):
        param_grid = {"a": [1, 2], "b": [3, 4]}
        result = hyperparameter_tune(
            simple_strategy,
            price_data,
            param_grid,
            method="grid",
        )
        assert result.method == "grid"
        assert result.n_trials == 4  # 2x2 grid

    def test_summary(self, price_data):
        param_grid = {"x": [1, 2, 3]}
        result = hyperparameter_tune(simple_strategy, price_data, param_grid)
        summary = result.summary()
        assert "best_params" in summary
        assert "best_metric" in summary
        assert "top_trials" in summary
        assert len(summary["top_trials"]) <= 5

    def test_reproducibility(self, price_data):
        param_grid = {"a": [1, 2, 3], "b": [4, 5, 6]}
        r1 = hyperparameter_tune(simple_strategy, price_data, param_grid, seed=123)
        r2 = hyperparameter_tune(simple_strategy, price_data, param_grid, seed=123)
        assert r1.best_params == r2.best_params
        assert r1.best_metric == r2.best_metric

    def test_empty_grid(self, price_data):
        with pytest.raises(ValueError):
            hyperparameter_tune(simple_strategy, price_data, {})

    def test_data_too_short(self):
        with pytest.raises(ValueError):
            hyperparameter_tune(simple_strategy, [1, 2], {"a": [1]})

    def test_unknown_method(self, price_data):
        with pytest.raises(ValueError):
            hyperparameter_tune(
                simple_strategy,
                price_data,
                {"a": [1]},
                method="bayesian",
            )

    def test_trials_ranked(self, price_data):
        param_grid = {"a": list(range(10))}
        result = hyperparameter_tune(
            simple_strategy,
            price_data,
            param_grid,
            n_trials=10,
        )
        for i, trial in enumerate(result.trials):
            assert trial.rank == i + 1
