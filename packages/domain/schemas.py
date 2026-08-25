"""Shared domain schemas for validation results.

Provides ValidationSchema as a single source of truth for all
validation result formats across walk-forward, CV, and hyperparameter tuning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import uuid

from packages.domain.entities import (
    DataQuality,
    SplitDoc,
    ValidationResult,
    WalkForwardResult,
    CVResult,
    HyperparameterResult,
)


def _compute_data_hash(data: list[float]) -> str:
    """Compute SHA-256 hash of price data for provenance tracking."""
    content = ",".join(f"{x:.6f}" for x in data)
    return sha256(content.encode()).hexdigest()[:16]


def _assess_quality(data: list[float]) -> DataQuality:
    """Assess data quality: missing, duplicates, stale."""
    missing = sum(1 for x in data if x != x)  # NaN check
    # check for stale (zero returns)
    stale = any(data[i] == data[i - 1] for i in range(1, min(10, len(data))))
    return DataQuality(
        status="valid" if missing == 0 and not stale else "degraded",
        missing=missing,
        duplicates=0,
        stale=stale,
    )


def make_validation_result(
    data: list[float], seed: int, config: dict
) -> ValidationResult:
    """Create a ValidationResult with run metadata and data quality."""
    return ValidationResult(
        run_id=str(uuid.uuid4())[:8],
        seed=seed,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data_hash=_compute_data_hash(data),
        data_quality=_assess_quality(data),
        config=config,
    )


def make_walk_forward_result(
    data: list[float],
    seed: int,
    train_window: int,
    test_window: int,
    step: int,
    n_folds: int,
    avg_sharpe: float,
    avg_return: float,
    oos_sharpe: float,
    fold_docs: list[dict],
) -> WalkForwardResult:
    """Create a WalkForwardResult with unified validation metadata."""
    splits = [
        SplitDoc(
            fold=d["fold"],
            train_start=d["train"][0],
            train_end=d["train"][1],
            train_size=d["train"][1] - d["train"][0],
            test_start=d["test"][0],
            test_end=d["test"][1],
            test_size=d["test"][1] - d["test"][0],
        )
        for d in fold_docs
    ]
    return WalkForwardResult(
        validation=make_validation_result(
            data,
            seed,
            {"train_window": train_window, "test_window": test_window, "step": step},
        ),
        n_folds=n_folds,
        train_window=train_window,
        test_window=test_window,
        step=step,
        avg_sharpe=avg_sharpe,
        avg_return=avg_return,
        oos_sharpe=oos_sharpe,
        folds=fold_docs,
        splits=splits,
    )


def make_cv_result(
    data: list[float],
    seed: int,
    n_splits: int,
    gap: int,
    metric_name: str,
    avg_metric: float,
    std_metric: float,
    fold_docs: list[dict],
) -> CVResult:
    """Create a CVResult with unified validation metadata."""
    splits = [
        SplitDoc(
            fold=d["fold"],
            train_start=0,
            train_end=0,
            train_size=d["train_size"],
            test_start=0,
            test_end=0,
            test_size=d["test_size"],
        )
        for d in fold_docs
    ]
    return CVResult(
        validation=make_validation_result(
            data, seed, {"n_splits": n_splits, "gap": gap}
        ),
        n_splits=n_splits,
        gap=gap,
        avg_metric=avg_metric,
        std_metric=std_metric,
        metric_name=metric_name,
        folds=fold_docs,
        splits=splits,
    )


def make_hyperparameter_result(
    data: list[float],
    seed: int,
    method: str,
    metric: str,
    n_trials: int,
    best_params: dict,
    best_metric: float,
    top_trials: list[dict],
) -> HyperparameterResult:
    """Create a HyperparameterResult with unified validation metadata."""
    return HyperparameterResult(
        validation=make_validation_result(
            data, seed, {"method": method, "metric": metric}
        ),
        best_params=best_params,
        best_metric=best_metric,
        metric=metric,
        n_trials=n_trials,
        seed=seed,
        method=method,
        top_trials=top_trials,
    )
