"""Shared helpers for explainability modules."""

from __future__ import annotations

import hashlib

import numpy as np

from packages.domain.constants import (
    WALK_FORWARD_STEP,
    WALK_FORWARD_TEST_WINDOW,
    WALK_FORWARD_TRAIN_WINDOW,
)


def _data_hash(arr: np.ndarray) -> str:
    """Compute SHA-256 hash of a numpy array for provenance tracking."""
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _splits_str() -> str:
    """Return walk-forward split identifier string."""
    return (
        f"walk_forward_{WALK_FORWARD_TRAIN_WINDOW}_"
        f"{WALK_FORWARD_TEST_WINDOW}_{WALK_FORWARD_STEP}"
    )
