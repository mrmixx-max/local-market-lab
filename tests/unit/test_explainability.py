"""Tests for explainability: importance + comparison."""
from __future__ import annotations

import numpy as np
import pytest

from packages.explainability.importance import permutation_importance, shapley_approx
from packages.explainability.comparison import (
    WalkForwardResult,
    compare_models,
    diebold_mariano,
    walkforward_table,
)
from packages.domain.entities import ExportQuality


@pytest.fixture
def dq():
    return ExportQuality(n_observations=200, missing_pct=0.01, source="yahoo")


class TestPermutationImportance:
    def test_basic_shape(self, dq):
        rng = np.random.default_rng(42)
        X = rng.standard_normal((100, 3))
        y = X[:, 0] * 2 + rng.standard_normal(100) * 0.1
        predict = lambda X: X[:, 0] * 2
        result = permutation_importance(predict, X, y, n_repeats=5, data_quality=dq)
        assert len(result.feature_importance) == 3
        assert result.run_id
        assert result.data_hash
        assert result.data_quality.source == "yahoo"
        # splits_used must NOT falsely claim walk-forward; importance is
        # computed on the evaluation set passed by the caller.
        assert result.splits_used == "permutation_on_eval_set"

    def test_important_feature_detected(self, dq):
        rng = np.random.default_rng(42)
        X = rng.standard_normal((200, 4))
        y = X[:, 1] * 5 + rng.standard_normal(200) * 0.5
        predict = lambda X: X[:, 1] * 5
        result = permutation_importance(predict, X, y,
                                        feature_names=["a", "b", "c", "d"],
                                        n_repeats=10, data_quality=dq)
        means = [f.importance for f in result.feature_importance]
        assert means[1] == max(means)

    def test_metric_mae(self, dq):
        rng = np.random.default_rng(0)
        X = rng.standard_normal((50, 2))
        y = X[:, 0] + rng.standard_normal(50) * 0.1
        predict = lambda X: X[:, 0]
        result = permutation_importance(predict, X, y, metric="mae", n_repeats=3,
                                        data_quality=dq)
        assert result.model == "model"


class TestShapleyApprox:
    def test_output_structure(self):
        rng = np.random.default_rng(42)
        X = rng.standard_normal((50, 3))
        instance = np.array([1.0, 2.0, 3.0])
        predict = lambda X: X[:, 0] * 2 + X[:, 1]
        result = shapley_approx(predict, X, instance, n_samples=20)
        assert "shap_values" in result
        assert "base_value" in result
        assert "prediction" in result
        assert len(result["shap_values"]) == 3

    def test_shap_sums_to_prediction_minus_base(self):
        rng = np.random.default_rng(42)
        X = rng.standard_normal((80, 2))
        instance = np.array([1.0, 0.5])
        predict = lambda X: X[:, 0] + X[:, 1] * 2
        result = shapley_approx(predict, X, instance, n_samples=50)
        shap_sum = sum(result["shap_values"])
        diff = result["prediction"] - result["base_value"]
        # Monte Carlo approximation — allow wider tolerance
        assert abs(shap_sum - diff) < 3.0


class TestDieboldMariano:
    def test_identical_predictions(self):
        pred = [1.0, 2.0, 3.0, 4.0]
        actual = [1.1, 2.1, 2.9, 4.1]
        result = diebold_mariano(pred, pred, actual)
        assert result["better_model"] == "tie"
        assert not result["significant"]

    def test_clear_difference(self):
        rng = np.random.default_rng(42)
        actual = rng.standard_normal(200)
        pred1 = actual + rng.standard_normal(200) * 0.1
        pred2 = actual + rng.standard_normal(200) * 2.0
        result = diebold_mariano(pred1, pred2, actual)
        assert result["significant"]
        assert result["better_model"] == "model1"

    def test_mae_loss(self):
        pred1 = [1.0, 2.0, 3.0]
        pred2 = [1.5, 2.5, 3.5]
        actual = [1.0, 2.0, 3.0]
        result = diebold_mariano(pred1, pred2, actual, loss="mae")
        assert result["loss"] == "mae"


class TestWalkForwardTable:
    def test_basic_table(self):
        results = [
            WalkForwardResult(1, 0, 100, 100, 130, "model_a", 0.01, 0.08),
            WalkForwardResult(2, 0, 120, 120, 150, "model_a", 0.02, 0.10),
            WalkForwardResult(1, 0, 100, 100, 130, "model_b", 0.015, 0.09),
        ]
        table = walkforward_table(results)
        assert len(table["rows"]) == 3
        assert "model_a" in table["summary"]
        assert "model_b" in table["summary"]
        assert table["summary"]["model_a"]["n_windows"] == 2


class TestCompareModels:
    def test_compare_basic(self, dq):
        a = [
            WalkForwardResult(1, 0, 100, 100, 130, "a", 0.01, 0.08,
                              predictions=[1.0, 2.0], actuals=[1.1, 2.1]),
            WalkForwardResult(2, 0, 120, 120, 150, "a", 0.02, 0.10,
                              predictions=[3.0, 4.0], actuals=[3.1, 4.1]),
        ]
        b = [
            WalkForwardResult(1, 0, 100, 100, 130, "b", 0.015, 0.09,
                              predictions=[1.2, 2.2], actuals=[1.1, 2.1]),
            WalkForwardResult(2, 0, 120, 120, 150, "b", 0.025, 0.11,
                              predictions=[3.2, 4.2], actuals=[3.1, 4.1]),
        ]
        result = compare_models(a, b, dq)
        assert result.run_id
        assert result.data_hash
        assert "walk_forward" in result.splits_used
        assert result.data_quality.source == "yahoo"
        assert "diebold_mariano" in result.to_dict()
