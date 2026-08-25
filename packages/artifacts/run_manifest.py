"""Versioned run manifest builder (v1.0 P1.4).

Extends the legacy build_manifest with a full, versioned schema: manifest_id,
separate hashes (parameters / data / model / environment / result / artifact),
and environment capture. No secrets are ever included (redacted on build).

Reproducibility-relevant fields (fed into result_hash):
    parameters, parameters_hash, data[*].data_hash, model.*, seed,
    features.*, job_type, system_version
Non-reproducibility-relevant (excluded from result_hash): created_at, run_id,
manifest_id, stored paths.
"""

from __future__ import annotations

import datetime
import importlib.metadata
import os
import platform
import sys
import uuid
from typing import Any

from packages.artifacts.canonical import stable_hash, redact_secrets
from packages.artifacts.registry import manifest_digest_of

MANIFEST_SCHEMA_VERSION = 1
DISCLAIMER = "Keine Finanzberatung. Keine Kauf- oder Verkaufsempfehlung."

# keys that must NOT influence the business result_hash
_NON_RESULT_KEYS = (
    "manifest_id",
    "run_id",
    "created_at",
    "stored_at",
    "manifest_digest",
    "artifacts",
    "warnings",
    "limitations",
    "disclaimer",
    "reproducibility_status",
)


def _system_version() -> str:
    try:
        return importlib.metadata.version("local-market-lab")
    except Exception:
        return os.environ.get("LML_VERSION", "unknown")


def _git_commit() -> str:
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()[:12]
    except Exception:
        pass
    return "unknown"


def _env_hash() -> tuple[str, list[str]]:
    """Hash of the runtime environment relevant to reproducibility."""
    py = sys.version.split()[0]
    plat = platform.platform()
    # package lock: installed versions of top-level deps
    deps = []
    try:
        import importlib.metadata as md

        for dist in sorted(md.distributions(), key=lambda d: d.name):
            deps.append(f"{dist.name}=={dist.version}")
    except Exception:
        pass
    lock_hash = stable_hash(deps)
    env = {"python_version": py, "platform": plat, "package_lock_hash": lock_hash}
    return stable_hash(env), deps


def build_run_manifest(
    job_type: str,
    parameters: dict,
    data: list[dict] | None = None,
    model: dict | None = None,
    features: dict | None = None,
    seed: int | None = None,
    result: Any = None,
    assumptions: dict | None = None,
    known_kinds: list[str] | None = None,
) -> dict:
    """Build a full v1 run manifest with all hashes populated.

    No value is invented: missing info is marked 'unknown' / 'not_available' /
    'incomplete'.
    """
    params = redact_secrets(parameters or {})
    params_hash = stable_hash(params)

    data_list = []
    if data:
        for d in data:
            data_list.append(
                {
                    "source": d.get("source", "unknown"),
                    "provider_version": d.get("provider_version", "unknown"),
                    "symbol": d.get("symbol", "unknown"),
                    "currency": d.get("currency", "unknown"),
                    "timezone": d.get("timezone", "unknown"),
                    "interval": d.get("interval", "unknown"),
                    "start_date": d.get("start_date", "unknown"),
                    "end_date": d.get("end_date", "unknown"),
                    "data_hash": d.get("data_hash", "incomplete"),
                    "cache_schema_version": d.get("cache_schema_version", "unknown"),
                    "adjusted_prices": d.get("adjusted_prices", "unknown"),
                }
            )

    model_block = None
    if model:
        model_block = {
            "name": model.get("name", "unknown"),
            "version": model.get("version", "unknown"),
            "parameters": redact_secrets(model.get("parameters", {})),
            "implementation_hash": model.get("implementation_hash", "not_available"),
        }
    feat_block = None
    if features:
        feat_block = {
            "feature_set_version": features.get("feature_set_version", "unknown"),
            "feature_parameters": redact_secrets(
                features.get("feature_parameters", {})
            ),
            "feature_hash": features.get("feature_hash", "not_available"),
        }

    env_hash, deps = _env_hash()
    mid = f"man_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"  # noqa: E501
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": mid,
        "run_id": run_id,
        "system_version": _system_version(),
        "git_commit": _git_commit(),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "job_type": job_type,
        "seed": seed,
        "parameters": params,
        "parameters_hash": params_hash,
        "data": data_list,
        "features": feat_block or "not_available",
        "model": model_block or "not_available",
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "package_lock_hash": env_hash,
            "dependencies": deps[:200],  # cap to keep manifest readable
        },
        "environment_hash": env_hash,
        "known_kinds": known_kinds or [],
        "assumptions": assumptions or {},
        "artifacts": [],
        "result_hash": stable_hash(result) if result is not None else "pending",
        "warnings": [],
        "limitations": [],
        "disclaimer": DISCLAIMER,
    }
    manifest["manifest_digest"] = manifest_digest_of(manifest)
    return manifest


def result_hash_of(result: Any) -> str:
    """Canonical result hash — independent of storage metadata."""
    return stable_hash(result)


def manifest_result_hash(manifest: dict) -> str:
    """Extract the reproducibility-relevant business result hash.

    Excludes created_at/run_id/manifest_id so they cannot break reproducibility.
    """
    relevant = {k: v for k, v in manifest.items() if k not in _NON_RESULT_KEYS}
    return stable_hash(relevant)
