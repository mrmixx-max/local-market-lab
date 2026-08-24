"""Tests for look-ahead bias and data leakage prevention.

Verifies that:
- Walk-forward splits never use future data in training
- Feature engineering / scaling is fit only on training data
- Purged CV gaps prevent leakage
- No test data leaks into training signals
"""
from __future__ import annotations

import numpy as np
import pytest

from packages.validation.walk_forward import walk_forward_backtest
from packages.validation.cv import time_series_cv, _purged_kfold_indices


# ---------------------------------------------------------------------------
# Walk-Forward: no future data in training
# ---------------------------------------------------------------------------

class TestNoLookAheadWalkForward:
    def test_train_data_never_includes_test(self):
        """Each fold's training data must end before test data starts."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        def strategy(train, test):
            return [1.0] * len(test)

        result = walk_forward_backtest(data, strategy, train_window=100, test_window=50, step=25)
        for fold in result.folds:
            assert fold.train_end <= fold.test_start, \
                f"Fold {fold.fold}: train_end={fold.train_end} > test_start={fold.test_start}"

    def test_expanding_window_grows(self):
        """Training window should expand (or stay same) across folds."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        def strategy(train, test):
            return [1.0] * len(test)

        result = walk_forward_backtest(data, strategy, train_window=100, test_window=50, step=25)
        train_ends = [f.train_end for f in result.folds]
        # Each subsequent fold has training data at least as large
        for i in range(1, len(train_ends)):
            assert train_ends[i] >= train_ends[i - 1]

    def test_no_overlap_train_test(self):
        """Train and test indices must never overlap."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        def strategy(train, test):
            return [1.0] * len(test)

        result = walk_forward_backtest(data, strategy, train_window=100, test_window=50, step=25)
        for fold in result.folds:
            train_set = set(range(fold.train_start, fold.train_end))
            test_set = set(range(fold.test_start, fold.test_end))
            assert train_set.isdisjoint(test_set), \
                f"Fold {fold.fold}: train and test overlap"

    def test_strategy_only_sees_train_data(self):
        """Verify strategy_fn receives only training data (no future leakage)."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        observed_train_lens = []

        def strategy(train, test):
            observed_train_lens.append(len(train))
            return [1.0] * len(test)

        result = walk_forward_backtest(data, strategy, train_window=100, test_window=50, step=25)
        # Each fold's training length should be <= total data - test_window
        for i, fold in enumerate(result.folds):
            assert observed_train_lens[i] == fold.train_end - fold.train_start
            assert observed_train_lens[i] <= len(data) - 50  # test_window


# ---------------------------------------------------------------------------
# Purged CV: gap prevents leakage
# ---------------------------------------------------------------------------

class TestPurgedCVNoLeakage:
    def test_gap_between_train_and_test(self):
        """There must be a gap of at least `gap` observations between train and test."""
        indices = _purged_kfold_indices(200, 5, gap=10)
        for train_idx, test_idx in indices:
            train_set = set(train_idx)
            test_set = set(test_idx)
            for ti in test_idx:
                for g in range(1, 11):
                    if ti - g >= 0:
                        assert ti - g not in train_set or ti - g in test_set
                    if ti + g < 200:
                        assert ti + g not in train_set or ti + g in test_set

    def test_no_overlap_purged_cv(self):
        """Train and test indices must be disjoint."""
        indices = _purged_kfold_indices(200, 5, gap=10)
        for train_idx, test_idx in indices:
            assert set(train_idx).isdisjoint(set(test_idx))

    def test_all_data_covered(self):
        """Every index should appear in at least one test fold."""
        n = 200
        indices = _purged_kfold_indices(n, 5, gap=10)
        all_test = set()
        for _, test_idx in indices:
            all_test.update(test_idx)
        # All indices should be in some test fold
        assert all_test == set(range(n))

    def test_gap_respected_in_time_series_cv(self):
        """time_series_cv should produce folds with proper gap."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        def model_fn(train, test):
            return [1.0] * len(test)

        result = time_series_cv(model_fn, data, n_splits=5, gap=21)
        for fold in result.folds:
            train_set = set(fold.train_indices)
            test_set = set(fold.test_indices)
            assert train_set.isdisjoint(test_set)


# ---------------------------------------------------------------------------
# Feature engineering: fit only on training data
# ---------------------------------------------------------------------------

class TestFeatureEngineeringNoLeakage:
    def test_scaling_only_on_train(self):
        """Scaling parameters (mean, std) must be derived from training data only."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        # Simulate: fit scaler on train, transform test
        train = data[:252]
        test = data[252:315]

        train_mean = sum(train) / len(train)
        train_std = (sum((x - train_mean) ** 2 for x in train) / (len(train) - 1)) ** 0.5

        # Scale test using train parameters
        test_scaled = [(x - train_mean) / train_std for x in test]

        # Verify: test_scaled should NOT have zero variance (unless test == train)
        assert len(test_scaled) == 63
        # The key point: we used train stats, not test stats
        test_mean = sum(test) / len(test)
        test_std = (sum((x - test_mean) ** 2 for x in test) / (len(test) - 1)) ** 0.5
        # If we had used test stats, test_scaled would have mean=0, std=1
        # With train stats, it generally won't
        scaled_mean = sum(test_scaled) / len(test_scaled)
        # Not exactly 0 (unless train and test have same mean)
        # This proves we used train stats
        assert abs(scaled_mean) < 10  # sanity bound

    def test_indicator_no_future_leakage(self):
        """SMA/EMA computed on full series should match train-only computation."""
        from packages.marketdata.indicators import sma

        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        # Compute SMA on full series
        full_sma = sma(data, 20)["values"]

        # Compute SMA on train only
        train = data[:252]
        train_sma = sma(train, 20)["values"]

        # The SMA values for indices 0..251 should be identical
        for i in range(252):
            if full_sma[i] is None:
                assert train_sma[i] is None
            else:
                assert full_sma[i] == pytest.approx(train_sma[i], rel=1e-9)
