"""Validation package — walk-forward, cross-validation, hyperparameter tuning."""

from packages.validation.walk_forward import (
    walk_forward_backtest,
    WalkForwardResult,
    WalkForwardFold,
    experimental,
)
from packages.validation.cv import (
    time_series_cv,
    CVResult,
    CVFold,
)
from packages.validation.hyperparameter import (
    hyperparameter_tune,
    TuneResult,
    TrialResult,
)
from packages.domain.entities import (
    ValidationResult,
    DataQuality,
    SplitDoc,
)
from packages.domain.schemas import (
    make_validation_result,
    make_walk_forward_result,
    make_cv_result,
    make_hyperparameter_result,
)

__all__ = [
    "walk_forward_backtest",
    "WalkForwardResult",
    "WalkForwardFold",
    "time_series_cv",
    "CVResult",
    "CVFold",
    "hyperparameter_tune",
    "TuneResult",
    "TrialResult",
    "experimental",
    "ValidationResult",
    "DataQuality",
    "SplitDoc",
    "make_validation_result",
    "make_walk_forward_result",
    "make_cv_result",
    "make_hyperparameter_result",
]
