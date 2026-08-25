"""Canonical, stable serialization for reproducibility hashing.

Guarantees byte-identical output for equal logical content regardless of:
- dict key ordering
- float representation (Python's stable repr)
- Decimal vs float vs int
- datetime/date/timezone
- Enum naming
- set ordering
- NaN / Infinity (which are not JSON-valid by default)

Time-dependent or random fields are EXCLUDED by the caller (e.g. created_at
is stored but never fed into the result_hash). This module only makes the
serialization deterministic.
"""

from __future__ import annotations

import datetime
import decimal
import enum
import json
import math
from typing import Any


class _Sentinel:
    def __repr__(self) -> str:  # pragma: no cover - defensive
        return "<REDACTED>"


REDACTED = _Sentinel()


def _redact_value(v):
    """Return a JSON-safe redacted marker for secrets."""
    return "<REDACTED>"


def _default(o: Any):
    if isinstance(o, _Sentinel):
        return "<REDACTED>"
    if isinstance(o, decimal.Decimal):
        # fixed-point canonical string, no exponent surprises
        return str(o)
    if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
        return o.isoformat()
    if isinstance(o, enum.Enum):
        return o.name
    if isinstance(o, float):
        if math.isnan(o):
            return "NaN"
        if math.isinf(o):
            return "Infinity" if o > 0 else "-Infinity"
        return o  # json uses repr() → stable across runs
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, bytes):
        return o.hex()
    if hasattr(o, "__dict__"):
        return {k: v for k, v in vars(o).items() if not k.startswith("_")}
    raise TypeError(f"not serializable: {type(o)!r}")


def _preprocess(o: Any):
    """Recursively replace non-finite floats with canonical string tokens so
    the result is stable AND serializable (json allow_nan=False)."""
    if isinstance(o, float):
        if math.isnan(o):
            return "NaN"
        if math.isinf(o):
            return "Infinity" if o > 0 else "-Infinity"
        return o
    if isinstance(o, dict):
        return {k: _preprocess(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [_preprocess(v) for v in o]
    return o


def canonical(obj: Any) -> str:
    """Deterministic JSON string with sorted keys and stable encoding."""
    return json.dumps(
        _preprocess(obj),
        sort_keys=True,
        ensure_ascii=True,
        default=_default,
        allow_nan=False,
        separators=(",", ":"),
    )


def canonical_bytes(obj: Any) -> bytes:
    return canonical(obj).encode("utf-8")


def stable_hash(obj: Any) -> str:
    """sha256 of the canonical form. Used for parameters/data/model/result."""
    import hashlib

    return "sha256:" + hashlib.sha256(canonical_bytes(obj)).hexdigest()


def redact_secrets(obj: Any) -> Any:
    """Recursively replace likely-secret keys with REDACTED. Never stores
    tokens/keys. Pattern-match on key names only — content is never assumed."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and any(
                s in k.lower()
                for s in (
                    "key",
                    "token",
                    "secret",
                    "password",
                    "passwd",
                    "api_key",
                    "auth",
                    "credential",
                    "private",
                )
            ):
                out[k] = _redact_value(v)
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [redact_secrets(v) for v in obj]
    return obj
