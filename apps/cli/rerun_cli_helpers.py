"""Executor registry for reruns (v1.0 P1.4).

Maps a manifest's job_type to a deterministic re-execution function that takes
the stored manifest (parameters, seed, data refs) and returns the business
result. Each executor must be deterministic given the same manifest.

If the original data cannot be rehydrated, the executor raises — it must NOT
silently substitute different data.
"""
from __future__ import annotations

import importlib
from typing import Callable


# registry: job_type -> (module, function_name)
_EXECUTORS = {
    "backtest": ("packages.backtest.engine", "backtest_from_manifest"),
    "scenario": ("packages.scenarios.engine", "scenario_from_manifest"),
    "validation": ("packages.validation.walk_forward", "wf_from_manifest"),
    "tuning": ("packages.tuning.engine", "tune_from_manifest"),
    "stress": ("packages.scenarios.stress", "stress_from_manifest"),
    "rebalancing": ("packages.portfolio.rebalancing", "rebalance_from_manifest"),
}


def get_executor() -> Callable[[dict], object]:
    """Return a generic executor that dispatches on manifest job_type."""
    def executor(manifest: dict) -> object:
        job_type = manifest.get("job_type")
        spec = _EXECUTORS.get(job_type)
        if not spec:
            raise ValueError(f"no rerun executor for job_type={job_type!r}")
        module = importlib.import_module(spec[0])
        func = getattr(module, spec[1])
        return func(manifest)
    return executor


def register_executor(job_type: str, module: str, func_name: str) -> None:
    _EXECUTORS[job_type] = (module, func_name)
