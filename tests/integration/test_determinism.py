"""Tests for determinism: same seed + same data hash = same results."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from packages.validation.walk_forward import walk_forward_backtest
from packages.validation.cv import time_series_cv
from packages.scenarios.engine import monte_carlo_iid, block_bootstrap
from packages.scenarios.stress import monte_carlo_fat_tail
from packages.scenarios.predict import linear_trend_forecast, ensemble_forecast
from packages.scenarios.deep_learning import lstm_forecast
from packages.core.hashing import sha256_obj

# ---------------------------------------------------------------------------
# Data hash helpers
# ---------------------------------------------------------------------------


def _data_hash(data: list[float]) -> str:
    """Compute a stable hash of a price series."""
    return hashlib.sha256("".join(f"{x:.6f}" for x in data).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Walk-Forward determinism
# ---------------------------------------------------------------------------


class TestWalkForwardDeterminism:
    def test_same_data_same_result(self):
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        def strategy(train, test):
            if len(train) < 2:
                return [0.0] * len(test)
            avg = sum(b / a - 1 for a, b in zip(train, train[1:])) / (len(train) - 1)
            return [1.0 if avg > 0 else -1.0] * len(test)

        r1 = walk_forward_backtest(data, strategy, seed=42)
        r2 = walk_forward_backtest(data, strategy, seed=42)
        assert r1.avg_sharpe == r2.avg_sharpe
        assert r1.avg_return == r2.avg_return
        assert r1.oos_sharpe == r2.oos_sharpe
        assert r1.n_folds == r2.n_folds

    def test_same_seed_different_data_different_result(self):
        np.random.seed(42)
        d1 = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()
        d2 = (100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, 500)))).tolist()

        def strategy(train, test):
            return [1.0] * len(test)

        r1 = walk_forward_backtest(d1, strategy, seed=42)
        r2 = walk_forward_backtest(d2, strategy, seed=42)
        # Different data → different results (unless identical by chance)
        assert r1.avg_return != r2.avg_return or d1 == d2

    def test_deterministic_folds(self):
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 500)))).tolist()

        def strategy(train, test):
            return [1.0] * len(test)

        r = walk_forward_backtest(data, strategy, seed=42)
        folds = r.folds
        # Verify fold boundaries are deterministic
        assert folds[0].train_end == 252
        assert folds[0].test_start == 252
        assert folds[0].test_end == 252 + 63


# ---------------------------------------------------------------------------
# Monte Carlo determinism
# ---------------------------------------------------------------------------


class TestMonteCarloDeterminism:
    def test_same_seed_same_finals(self):
        positions = {"AAPL": 0.6, "MSFT": 0.3, "GLD": 0.1}
        r1 = monte_carlo_fat_tail(positions, runs=200, seed=42)
        r2 = monte_carlo_fat_tail(positions, runs=200, seed=42)
        assert r1["median"] == r2["median"]
        assert r1["p05"] == r2["p05"]
        assert r1["p95"] == r2["p95"]
        assert r1["data_hash"] == r2["data_hash"]

    def test_different_seed_different_result(self):
        positions = {"AAPL": 0.6, "MSFT": 0.3, "GLD": 0.1}
        r1 = monte_carlo_fat_tail(positions, runs=200, seed=1)
        r2 = monte_carlo_fat_tail(positions, runs=200, seed=2)
        assert r1["median"] != r2["median"]

    def test_data_hash_stable(self):
        positions = {"AAPL": 0.5, "MSFT": 0.5}
        r1 = monte_carlo_fat_tail(positions, runs=100, seed=42)
        r2 = monte_carlo_fat_tail(positions, runs=100, seed=42)
        assert r1["data_hash"] == r2["data_hash"]
        assert len(r1["data_hash"]) == 16


# ---------------------------------------------------------------------------
# Forecast determinism
# ---------------------------------------------------------------------------


class TestForecastDeterminism:
    def test_linear_trend_same_data(self):
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 252)))).tolist()
        r1 = linear_trend_forecast(data, 30)
        r2 = linear_trend_forecast(data, 30)
        assert r1["forecast"] == r2["forecast"]

    def test_ensemble_same_data(self):
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 252)))).tolist()
        r1 = ensemble_forecast(data, 30)
        r2 = ensemble_forecast(data, 30)
        assert r1["forecast"] == r2["forecast"]


# ---------------------------------------------------------------------------
# Content hashing determinism
# ---------------------------------------------------------------------------


class TestContentHashing:
    def test_sha256_obj_stable(self):
        obj = {"a": 1, "b": [2, 3], "c": "hello"}
        h1 = sha256_obj(obj)
        h2 = sha256_obj(obj)
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_sha256_obj_order_independent(self):
        """Key order should not matter (sorted keys)."""
        obj1 = {"a": 1, "b": 2}
        obj2 = {"b": 2, "a": 1}
        assert sha256_obj(obj1) == sha256_obj(obj2)

    def test_sha256_obj_different_for_different_data(self):
        assert sha256_obj({"a": 1}) != sha256_obj({"a": 2})

    def test_data_hash_matches(self):
        """Verify data hash is consistent across runs."""
        np.random.seed(42)
        data = (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 252)))).tolist()
        h1 = _data_hash(data)
        h2 = _data_hash(data)
        assert h1 == h2
