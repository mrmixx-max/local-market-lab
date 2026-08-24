"""Comprehensive tests for all 15+ AI prediction modules in packages/scenarios/.

Covers:
  1. Smoke tests (import + basic call) for all modules
  2. Walk-Forward-Validation for LSTM/Transformer
  3. EM-GMM convergence stability (regime_switching)
  4. Drift detection (online_ensemble) — mean + variance
  5. NSGA-II multi-objective optimization
  6. Performance benchmarks (numpy vectorization)
  7. Input validation and edge cases
"""
from __future__ import annotations

import math
import time

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def price_data():
    """252 days of synthetic price data."""
    np.random.seed(42)
    n = 252
    returns = np.random.normal(0.0005, 0.02, n)
    return (100 * np.exp(np.cumsum(returns))).tolist()


@pytest.fixture
def asset_data():
    """Multi-asset price data for cross-asset tests."""
    np.random.seed(42)
    n = 252
    return {
        "AAPL": (100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))).tolist(),
        "MSFT": (100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, n)))).tolist(),
        "GLD": (150 * np.exp(np.cumsum(np.random.normal(0.0001, 0.01, n)))).tolist(),
    }


@pytest.fixture
def regression_data():
    """Feature matrix + target for GA tests."""
    rng = np.random.RandomState(42)
    X = rng.randn(100, 5)
    y = X @ np.array([1.0, -0.5, 0.3, 0.0, 0.0]) + rng.randn(100) * 0.1
    return X, y


# ===========================================================================
# 1. predict.py — Pure-Python forecasting
# ===========================================================================

class TestPredict:
    def test_linear_trend(self, price_data):
        from packages.scenarios.predict import linear_trend_forecast
        r = linear_trend_forecast(price_data, 30)
        assert r["model"] == "linear_trend"
        assert len(r["forecast"]) == 30
        assert len(r["upper"]) == 30
        assert len(r["lower"]) == 30
        assert all(r["upper"][i] >= r["lower"][i] for i in range(30))
        assert r["last"] == round(price_data[-1], 4)

    def test_exp_smooth(self, price_data):
        from packages.scenarios.predict import exp_smooth_forecast
        r = exp_smooth_forecast(price_data, 30, alpha=0.3, beta=0.1)
        assert r["model"] == "exp_smooth"
        assert len(r["forecast"]) == 30
        assert r["level"] != 0

    def test_exp_smooth_invalid_params(self, price_data):
        from packages.scenarios.predict import exp_smooth_forecast
        with pytest.raises(ValueError):
            exp_smooth_forecast(price_data, 30, alpha=0.0, beta=0.1)
        with pytest.raises(ValueError):
            exp_smooth_forecast(price_data, 30, alpha=0.3, beta=1.5)

    def test_arima_like(self, price_data):
        from packages.scenarios.predict import arima_like_forecast
        r = arima_like_forecast(price_data, 30, order=(5, 1, 0))
        assert r["model"] == "arima_like"
        assert len(r["forecast"]) == 30
        assert abs(r["phi"]) < 1.0  # stationarity

    def test_ensemble(self, price_data):
        from packages.scenarios.predict import ensemble_forecast
        r = ensemble_forecast(price_data, 30)
        assert r["model"] == "ensemble"
        assert len(r["forecast"]) == 30
        assert "components" in r
        assert set(r["components"].keys()) == {"linear_trend", "exp_smooth", "arima_like"}

    def test_validation(self):
        from packages.scenarios.predict import linear_trend_forecast
        with pytest.raises(ValueError):
            linear_trend_forecast([1, 2, 3], 30)  # too short
        with pytest.raises(ValueError):
            linear_trend_forecast([1, 2, 3, 4, 5], -1)  # bad horizon
        with pytest.raises(ValueError):
            linear_trend_forecast([1, 2, float("inf"), 4, 5], 30)  # non-finite


# ===========================================================================
# 2. regime_switching.py — EM-GMM
# ===========================================================================

class TestRegimeSwitching:
    def test_detect_regime(self, price_data):
        from packages.scenarios.regime_switching import detect_regime
        rets = np.diff(np.array(price_data))
        r = detect_regime(rets, n_regimes=3)
        assert r["n_regimes"] == 3
        assert len(r["means"]) == 3
        assert len(r["stds"]) == 3
        assert len(r["weights"]) == 3
        assert all(s > 0 for s in r["stds"])  # no degenerate clusters
        assert abs(sum(r["weights"]) - 1.0) < 0.01

    def test_detect_regime_bimodal(self):
        from packages.scenarios.regime_switching import detect_regime
        rng = np.random.RandomState(0)
        rets = np.concatenate([rng.normal(-2, 0.3, 100), rng.normal(2, 0.3, 100)])
        r = detect_regime(rets, n_regimes=2)
        assert all(s > 0 for s in r["stds"])  # no sigma=0

    def test_detect_regime_near_identical(self):
        from packages.scenarios.regime_switching import detect_regime
        rets = np.ones(200) + np.random.normal(0, 0.001, 200)
        r = detect_regime(rets, n_regimes=3)
        assert all(s > 0 for s in r["stds"])

    def test_regime_forecast(self, price_data):
        from packages.scenarios.regime_switching import regime_forecast
        r = regime_forecast(price_data, 30)
        assert r["model"] == "regime_switching"
        assert len(r["forecast"]) == 30
        assert r["current_regime"] in {"Trend", "Seitwaerts", "Volatil"}

    def test_regime_probability(self, price_data):
        from packages.scenarios.regime_switching import regime_probability
        r = regime_probability(price_data)
        assert "probabilities" in r
        assert abs(sum(r["probabilities"].values()) - 1.0) < 0.01

    def test_gmm_fit_stability(self):
        from packages.scenarios.regime_switching import _gmm_fit
        # Trimodal — hardest case
        rng = np.random.RandomState(42)
        x = np.concatenate([rng.normal(-3, 0.2, 67), rng.normal(0, 0.2, 67), rng.normal(3, 0.2, 66)])
        mu, sigma, pi, resp = _gmm_fit(x, 3, max_iter=100)
        assert all(s > 1e-4 for s in sigma)  # no degenerate
        assert abs(pi.sum() - 1.0) < 1e-6
        assert resp.shape == (200, 3)


# ===========================================================================
# 3. bayesian_forecast.py
# ===========================================================================

class TestBayesian:
    def test_trend(self, price_data):
        from packages.scenarios.bayesian_forecast import bayesian_trend_forecast
        r = bayesian_trend_forecast(price_data, 30)
        assert len(r["forecast"]) == 30
        assert len(r["ci_95_lower"]) == 30
        assert all(r["ci_95_lower"][i] <= r["ci_95_upper"][i] for i in range(30))

    def test_seasonal(self, price_data):
        from packages.scenarios.bayesian_forecast import bayesian_seasonal_forecast
        r = bayesian_seasonal_forecast(price_data, 30, season_period=60)
        assert len(r["forecast"]) == 30
        assert r["n_harmonics"] > 0

    def test_combine(self, price_data):
        from packages.scenarios.bayesian_forecast import bayesian_combine
        r = bayesian_combine(price_data, 30)
        assert len(r["forecast"]) == 30
        assert "trend_component" in r
        assert "seasonal_component" in r


# ===========================================================================
# 4. online_ensemble.py — drift detection
# ===========================================================================

class TestOnlineEnsemble:
    def test_weighted_ensemble(self, price_data):
        from packages.scenarios.online_ensemble import online_weighted_ensemble
        r = online_weighted_ensemble(price_data, 30)
        assert r["model"] == "online_weighted_ensemble"
        assert len(r["forecast"]) == 30
        assert abs(sum(r["weights"].values()) - 1.0) < 0.01

    def test_adaptive_decay(self, price_data):
        from packages.scenarios.online_ensemble import adaptive_decay
        r = adaptive_decay(price_data, 30)
        assert "decay_rate" in r
        assert 0.90 <= r["decay_rate"] <= 0.999

    def test_drift_no_drift(self):
        from packages.scenarios.online_ensemble import drift_detection
        data = np.random.normal(100, 1, 200).tolist()
        r = drift_detection(data)
        assert not r["drift_detected"]

    def test_drift_mean_shift(self):
        from packages.scenarios.online_ensemble import drift_detection
        data = np.concatenate([np.random.normal(100, 1, 100), np.random.normal(110, 1, 100)]).tolist()
        r = drift_detection(data)
        assert r["drift_detected"]
        assert r["mean_score"] > 0.5

    def test_drift_volatility_shift(self):
        from packages.scenarios.online_ensemble import drift_detection
        rng = np.random.RandomState(0)
        data = np.concatenate([rng.normal(100, 0.5, 100), rng.normal(100, 3, 100)]).tolist()
        r = drift_detection(data)
        assert r["drift_detected"]
        assert r["var_score"] > 0.3

    def test_drift_small_data(self):
        from packages.scenarios.online_ensemble import drift_detection
        data = np.random.normal(100, 1, 15).tolist()
        r = drift_detection(data)
        assert "drift_detected" in r  # should not crash

    def test_online_forecast(self, price_data):
        from packages.scenarios.online_ensemble import online_forecast
        r = online_forecast(price_data, 30)
        assert r["model"] == "online_forecast"
        assert "drift" in r


# ===========================================================================
# 5. cross_asset.py
# ===========================================================================

class TestCrossAsset:
    def test_lead_lag(self, asset_data):
        from packages.scenarios.cross_asset import lead_lag_correlation
        r = lead_lag_correlation(asset_data, "AAPL", max_lag=10)
        assert "best_lead" in r
        assert "all_results" in r

    def test_granger_proxy(self, asset_data):
        from packages.scenarios.cross_asset import granger_causality_proxy
        r = granger_causality_proxy(asset_data, "AAPL", max_lag=5)
        assert "granger_results" in r

    def test_cross_asset_forecast(self, asset_data):
        from packages.scenarios.cross_asset import cross_asset_forecast
        r = cross_asset_forecast(asset_data, "AAPL", 30)
        assert r["model"] == "cross_asset_forecast"
        assert len(r["forecast"]) == 30

    def test_correlation_regime(self, asset_data):
        from packages.scenarios.cross_asset import correlation_regime
        r = correlation_regime(asset_data, "AAPL", window=40)
        assert "asset_regimes" in r


# ===========================================================================
# 6. deep_learning.py — LSTM/GRU + Walk-Forward
# ===========================================================================

class TestDeepLearning:
    def test_lstm(self, price_data):
        from packages.scenarios.deep_learning import lstm_forecast
        r = lstm_forecast(price_data, 10, hidden_size=16, epochs=5, seed=42)
        assert r["model"] == "lstm"
        assert len(r["forecast"]) == 10

    def test_gru(self, price_data):
        from packages.scenarios.deep_learning import gru_forecast
        r = gru_forecast(price_data, 10, hidden_size=16, epochs=5, seed=42)
        assert r["model"] == "gru"
        assert len(r["forecast"]) == 10

    def test_train_test_split(self, price_data):
        from packages.scenarios.deep_learning import train_test_split_ts
        arr = np.array(price_data)
        tr, te = train_test_split_ts(arr, test_ratio=0.2)
        assert len(tr) + len(te) == len(arr)
        assert len(tr) < len(arr)

    def test_walk_forward_lstm(self, price_data):
        from packages.scenarios.deep_learning import lstm_forecast, walk_forward_validate
        r = walk_forward_validate(lstm_forecast, price_data, min_train=100, step=30, horizon=5,
                                  hidden_size=16, epochs=5, seed=42)
        assert r["n_folds"] > 0
        assert r["rmse"] > 0
        assert not math.isnan(r["rmse"])

    def test_walk_forward_gru(self, price_data):
        from packages.scenarios.deep_learning import gru_forecast, walk_forward_validate
        r = walk_forward_validate(gru_forecast, price_data, min_train=100, step=30, horizon=5,
                                  hidden_size=16, epochs=5, seed=42)
        assert r["n_folds"] > 0
        assert r["rmse"] > 0


# ===========================================================================
# 7. transformer_forecast.py + Walk-Forward
# ===========================================================================

class TestTransformer:
    def test_transformer(self, price_data):
        from packages.scenarios.transformer_forecast import transformer_forecast
        r = transformer_forecast(price_data[:80], 10, d_model=16, n_heads=2, n_layers=1)
        assert len(r["forecast"]) == 10
        assert "ci_95_lower" in r

    def test_walk_forward_transformer(self, price_data):
        from packages.scenarios.transformer_forecast import transformer_forecast, walk_forward_validate
        r = walk_forward_validate(transformer_forecast, price_data, min_train=80, step=30, horizon=5,
                                  d_model=16, n_heads=2, n_layers=1)
        assert r["n_folds"] > 0
        assert r["rmse"] > 0

    def test_positional_encoding(self):
        from packages.scenarios.transformer_forecast import positional_encoding
        pe = positional_encoding(50, 32)
        assert pe.shape == (50, 32)

    def test_causal_mask(self):
        from packages.scenarios.transformer_forecast import causal_attention_mask
        mask = causal_attention_mask(5)
        assert mask.shape == (5, 5)
        # upper triangular
        assert mask[0, 0] == False
        assert mask[0, 1] == True
        assert mask[1, 0] == False


# ===========================================================================
# 8. rl_trading.py
# ===========================================================================

class TestRLTrading:
    def test_q_learning(self, price_data):
        from packages.scenarios.rl_trading import q_learning_trading
        r = q_learning_trading(price_data, episodes=20)
        assert r["algorithm"] == "q_learning"
        assert "forecast" in r

    def test_rl_forecast(self, price_data):
        from packages.scenarios.rl_trading import rl_forecast
        r = rl_forecast(data=price_data, horizon=10)
        assert "actions" in r
        assert "equity_curve" in r
        assert len(r["actions"]) == 10

    def test_disc_bounds(self):
        from packages.scenarios.rl_trading import _disc
        # Edge cases
        assert _disc(0.0) == 2  # middle bin
        assert _disc(0.03) == 4  # max clip -> last bin (n-1)
        assert _disc(-0.03) == 0  # min clip -> first bin
        assert _disc(10.0) == 4  # way above clip
        assert _disc(-10.0) == 0  # way below clip

    def test_extreme_returns(self):
        """Ensure no index error with extreme price jumps."""
        from packages.scenarios.rl_trading import q_learning_trading
        data = list(np.random.normal(100, 1, 100))
        data[50] = data[49] * 1.05  # 5% jump
        r = q_learning_trading(data, episodes=10)
        assert "forecast" in r


# ===========================================================================
# 9. genetic_optimization.py — NSGA-II
# ===========================================================================

class TestGeneticOptimization:
    def test_feature_selection(self, regression_data):
        from packages.scenarios.genetic_optimization import genetic_feature_selection
        X, y = regression_data
        r = genetic_feature_selection(X, y, pop_size=20, generations=10, seed=42)
        assert r["n_features"] > 0
        assert r["rmse"] < float("inf")

    def test_differential_evolution(self, regression_data):
        from packages.scenarios.genetic_optimization import differential_evolution
        X, y = regression_data

        def model_fn(X_tr, y_tr, X_va, y_va, alpha=0.01):
            A = X_tr.T @ X_tr + alpha * np.eye(X_tr.shape[1])
            w = np.linalg.solve(A, X_tr.T @ y_tr)
            return float(np.sqrt(np.mean((y_va - X_va @ w) ** 2)))

        r = differential_evolution(X, y, model_fn, {"alpha": [0.001, 10.0]},
                                    pop_size=15, generations=10, seed=42)
        assert "best_params" in r
        assert r["rmse"] < float("inf")

    def test_nsga2(self, regression_data):
        from packages.scenarios.genetic_optimization import nsga2_multi_objective
        X, y = regression_data

        def model_fn(X_tr, y_tr, X_va, y_va, alpha=0.01, l1_ratio=0.5):
            A = X_tr.T @ X_tr + alpha * np.eye(X_tr.shape[1])
            w = np.linalg.solve(A, X_tr.T @ y_tr)
            rmse = float(np.sqrt(np.mean((y_va - X_va @ w) ** 2)))
            complexity = int(np.sum(np.abs(w) > 0.01))
            return rmse, complexity

        r = nsga2_multi_objective(X, y, model_fn,
                                   {"alpha": [0.001, 10.0], "l1_ratio": [0.0, 1.0]},
                                   pop_size=20, generations=15, seed=42)
        assert r["n_solutions"] > 0
        assert all("rmse" in sol and "complexity" in sol for sol in r["pareto_front"])


# ===========================================================================
# 10. Performance benchmarks
# ===========================================================================

class TestPerformance:
    def test_ensemble_speed(self, price_data):
        from packages.scenarios.predict import ensemble_forecast
        t0 = time.time()
        for _ in range(100):
            ensemble_forecast(price_data, 30)
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"100 ensemble forecasts took {elapsed:.2f}s"

    def test_regime_speed(self, price_data):
        from packages.scenarios.regime_switching import regime_forecast
        t0 = time.time()
        for _ in range(50):
            regime_forecast(price_data, 30)
        elapsed = time.time() - t0
        assert elapsed < 10.0, f"50 regime forecasts took {elapsed:.2f}s"

    def test_online_ensemble_speed(self, price_data):
        from packages.scenarios.online_ensemble import online_forecast
        t0 = time.time()
        for _ in range(100):
            online_forecast(price_data, 30)
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"100 online forecasts took {elapsed:.2f}s"

    def test_transformer_speed(self, price_data):
        from packages.scenarios.transformer_forecast import transformer_forecast
        t0 = time.time()
        for _ in range(50):
            transformer_forecast(price_data[:80], 10, d_model=16, n_heads=2, n_layers=1)
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"50 transformer forecasts took {elapsed:.2f}s"
