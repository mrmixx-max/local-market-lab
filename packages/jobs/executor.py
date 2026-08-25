"""Built-in job executors — thin wrappers around existing package APIs."""

from __future__ import annotations

import random
from typing import Any, Callable

ProgressFn = Callable[[float], None]
ExecFn = Callable[[dict[str, Any], ProgressFn], dict[str, Any]]

REGISTRY: dict[str, ExecFn] = {}


def register(kind: str):
    def deco(fn: ExecFn) -> ExecFn:
        REGISTRY[kind] = fn
        return fn

    return deco


def get_executor(kind: str) -> ExecFn | None:
    return REGISTRY.get(kind)


def known_kinds() -> list[str]:
    return sorted(REGISTRY)


# --------------------------------------------------------------------------
# monte_carlo — wraps packages.scenarios.stress.monte_carlo_fat_tail
# --------------------------------------------------------------------------


@register("monte_carlo")
def run_monte_carlo(params: dict, progress: ProgressFn) -> dict:
    from packages.scenarios.stress import monte_carlo_fat_tail

    weights = params["weights"]
    runs = int(params.get("runs", 1000))
    seed = int(params.get("seed", 42))
    progress(0.05)
    res = monte_carlo_fat_tail(
        weights, runs=runs, seed=seed, horizon_days=int(params.get("horizon_days", 252))
    )
    progress(1.0)
    return {
        "metrics": {"p01": res["p01"], "p05": res.get("p05"), "p50": res.get("p50")},
        "runs": runs,
        "seed": seed,
    }


# --------------------------------------------------------------------------
# walk_forward — wraps packages.validation.walk_forward.walk_forward_backtest
# --------------------------------------------------------------------------


@register("walk_forward")
def run_walk_forward(params: dict, progress: ProgressFn) -> dict:
    from packages.validation.walk_forward import walk_forward_backtest

    prices = params["prices"]
    predict = params.get("predict") or (lambda tr, te: [1.0] * len(te))
    seed = int(params.get("seed", 42))
    progress(0.05)
    r = walk_forward_backtest(
        prices,
        predict,
        train_window=params.get("train_window", 200),
        test_window=params.get("test_window", 50),
        step=params.get("step", 25),
        seed=seed,
    )
    s = r.summary()
    progress(1.0)
    return {
        "summary": {
            k: s[k] for k in ("n_folds", "oos_sharpe", "oos_mae", "seed") if k in s
        }
    }


# --------------------------------------------------------------------------
# tuning — wraps packages.validation.hyperparameter.hyperparameter_tune
# --------------------------------------------------------------------------


@register("tuning")
def run_tuning(params: dict, progress: ProgressFn) -> dict:
    from packages.validation.hyperparameter import hyperparameter_tune

    grid = params["grid"]
    total = max(1, len(grid))
    done = {"n": 0}

    def cb():
        done["n"] += 1
        progress(min(0.95, done["n"] / total))

    r = hyperparameter_tune(
        lambda tr, te, **p: [p.get("w", 1.0)] * len(te),
        params["prices"],
        grid,
        n_trials=int(params.get("n_trials", len(grid))),
        seed=int(params.get("seed", 42)),
        method=params.get("method", "grid"),
        on_trial=cb if _supports_callback(hyperparameter_tune) else None,
    )
    progress(1.0)
    return {
        "best_params": r.best_params,
        "best_metric": r.best_metric,
        "n_trials": r.n_trials,
    }


def _supports_callback(fn) -> bool:
    import inspect

    return "on_trial" in inspect.signature(fn).parameters


# --------------------------------------------------------------------------
# stress — historical + hypothetical scenarios
# --------------------------------------------------------------------------


@register("stress")
def run_stress(params: dict, progress: ProgressFn) -> dict:
    from packages.scenarios.stress import HISTORICAL_CRISES, run_historical_stress

    weights = params["weights"]
    seed = int(params.get("seed", 42))
    out = {}
    for i, name in enumerate(HISTORICAL_CRISES):
        m = run_historical_stress(name, weights, seed=seed).metrics
        out[name] = {"max_drawdown": m["max_drawdown"]}
        progress((i + 1) / (len(HISTORICAL_CRISES) + 1))
    progress(1.0)
    return {"scenarios": out, "seed": seed}


# --------------------------------------------------------------------------
# demo/sleep — for tests and UI development only; deterministic
# --------------------------------------------------------------------------


@register("demo_sleep")
def run_demo_sleep(params: dict, progress: ProgressFn) -> dict:
    steps = int(params.get("steps", 10))
    delay = float(params.get("delay", 0.05))
    rng = random.Random(int(params.get("seed", 42)))
    acc = 0.0
    for i in range(steps):
        import time as _t

        _t.sleep(delay)
        acc += rng.random()
        progress((i + 1) / steps)
    return {"sum": round(acc, 6), "steps": steps}


@register("rerun")
def run_rerun(params: dict, progress: ProgressFn) -> dict:
    """Re-execute a stored manifest via the rerun engine (P1.4).

    params: {manifest_id, allow_data_drift, allow_environment_drift}
    New run_id; original manifest untouched; comparison stored immutably.
    """
    from packages.artifacts.rerun import rerun_manifest, DriftError
    from packages.artifacts.run_manifest import _env_hash, _system_version
    from apps.cli.rerun_cli_helpers import get_executor

    progress(0.05)
    manifest_id = params["manifest_id"]
    executor = get_executor()
    cur_ver = _system_version()
    cur_env, _ = _env_hash()
    try:
        report = rerun_manifest(
            manifest_id,
            executor,
            cur_ver,
            cur_env,
            allow_data_drift=params.get("allow_data_drift", False),
            allow_environment_drift=params.get("allow_environment_drift", False),
        )
    except FileNotFoundError:
        raise ValueError(f"manifest {manifest_id} not found")
    except DriftError as exc:
        raise ValueError(f"drift abort: {exc}")
    progress(1.0)
    return report.to_dict()
