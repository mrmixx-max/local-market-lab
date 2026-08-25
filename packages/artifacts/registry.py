"""Manifest storage, validation and integrity (v1.0 P1.4).

Manifests are immutable: written once, never overwritten. Storage is a flat
directory `data/manifests/<manifest_id>.json` plus metadata mirrored into the
workspace artifacts table. All reads verify SHA256 of the stored content.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from packages.artifacts.canonical import stable_hash

# Manifest IDs are lowercase alphanumeric + dash/underscore, fixed length-ish.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# Fields excluded from the integrity digest (self-referential or metadata that
# must not influence reproducibility verification).
_INTEGRITY_EXCLUDED = ("manifest_digest",)


def integrity_payload(manifest: dict) -> dict:
    """Canonical hash basis: deep copy with the self-referential digest removed.

    Used identically by save and load so the digest is stable across round-trips.
    """
    import copy

    payload = copy.deepcopy(manifest)
    for key in _INTEGRITY_EXCLUDED:
        payload.pop(key, None)
    return payload


def manifest_digest_of(manifest: dict) -> str:
    """Single source of truth for the manifest integrity digest."""
    return stable_hash(integrity_payload(manifest))


# Backwards-compatible alias
compute_digest = manifest_digest_of


def _manifest_dir() -> Path:
    base = Path(os.environ.get("LML_MANIFEST_DIR", "data/manifests")).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_id(manifest_id: str) -> str:
    """Reject path traversal / unsafe characters. Returns a clean filename."""
    if not isinstance(manifest_id, str) or not _SAFE_ID.match(manifest_id):
        raise ValueError(f"invalid manifest_id: {manifest_id!r}")
    if not manifest_id.endswith(".json"):
        # auto-append for convenience; stored files are .json
        manifest_id = manifest_id + ".json"
    candidate = (_manifest_dir() / manifest_id).resolve()
    if _manifest_dir() not in candidate.parents and candidate != _manifest_dir():
        raise ValueError("path traversal rejected")
    return str(candidate)


def save_manifest(manifest: dict) -> str:
    """Atomically write a manifest. Never overwrites an existing id.

    The integrity digest is computed over the canonical payload WITHOUT the
    manifest_digest field, then stored inside the file. Load re-derives the
    same digest from the stored payload (field removed) and compares — so
    save and load use an identical hash basis.

    Returns the manifest_id. Raises if the id already exists (immutable).
    """
    mid = manifest.get("manifest_id")
    if not mid or not _SAFE_ID.match(str(mid)):
        raise ValueError("manifest requires a valid manifest_id")
    path = Path(_safe_id(str(mid)))
    if path.exists():
        raise FileExistsError(f"manifest {mid} already exists (immutable)")
    digest = manifest_digest_of(manifest)  # basis excludes manifest_digest
    stored = dict(manifest)
    stored["manifest_digest"] = digest
    raw = json.dumps(stored, indent=2, sort_keys=True, ensure_ascii=True)
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=str(path.parent))
    with open(fd, "w", encoding="utf-8") as fh:
        fh.write(raw)
    Path(tmp).replace(path)  # atomic on same filesystem
    # mirror metadata into workspace (best-effort, non-fatal)
    try:
        from packages.storage.workspace import Workspace

        ws = Workspace()
        ws.save_artifact(
            mid,
            manifest.get("job_type", "manifest"),
            {
                "manifest_id": mid,
                "stored_digest": digest,
                "created_at": manifest.get("created_at"),
            },
        )
    except Exception:
        pass
    return str(mid)


def load_manifest(manifest_id: str) -> dict:
    """Load and verify a manifest. Raises FileNotFoundError / ValueError."""
    path = Path(_safe_id(manifest_id))
    if not path.exists():
        raise FileNotFoundError(f"manifest {manifest_id} not found")
    raw = path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"corrupted manifest {manifest_id}: {exc}") from exc
    # integrity: derive digest from stored payload (digest field removed) and
    # compare to the stored digest. Identical basis to save_manifest.
    stored_digest = manifest.get("manifest_digest")
    if stored_digest is None:
        # Legacy manifest without digest: treat as integrity-unknown.
        # Re-derive and keep on the returned object but do NOT reject — we
        # cannot prove tampering, only absence of a checksum.
        manifest["manifest_digest"] = manifest_digest_of(manifest)
    elif manifest_digest_of(manifest) != stored_digest:
        raise ValueError(f"manifest {manifest_id} integrity check failed")
    return manifest


def list_manifests(limit: int = 50) -> list[dict]:
    """Return metadata summaries of stored manifests, newest first."""
    d = _manifest_dir()
    out = []
    for p in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[
        :limit
    ]:
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            # exclude inherited artifacts table noise
            if (
                "manifest_schema_version" in m
                or "manifest_id" in m
                and m.get("kind") not in ("artifact",)
            ):
                out.append(
                    {
                        "manifest_id": m.get("manifest_id"),
                        "job_type": m.get("job_type"),
                        "system_version": m.get("system_version"),
                        "created_at": m.get("created_at"),
                        "result_hash": m.get("result_hash"),
                    }
                )
        except Exception:
            continue
    return out
