"""Content hashing — data lineage for artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_obj(obj) -> str:
    """Stable hash of a JSON-serializable object (sorted keys)."""
    payload = json.dumps(obj, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()
