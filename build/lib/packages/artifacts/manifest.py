"""Artifacts — reproducibility manifests for every analysis run."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from packages.core.hashing import sha256_obj


def new_id(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:8]}"


def build_manifest(kind: str, params: dict, assumptions: dict | None,
                   seed: int | None, data_lineage: dict,
                   app_version: str = "0.1.0") -> dict:
    """Manifest per concept: data hash + parameters + seed + code version +
    disclaimer profile. The manifest IS the reproducibility contract.
    """
    return {
        "artifact_id": new_id(kind[:4].lower()),
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "app_version": app_version,
        "data_snapshot": {
            "hash": data_lineage.get("hash"),
            "sources": data_lineage.get("sources", []),
            "symbols": data_lineage.get("symbols", []),
            "date_range": data_lineage.get("date_range"),
        },
        "parameters": params,
        "assumptions": assumptions or {},
        "seed": seed,
        "reporting_currency": data_lineage.get("reporting_currency", "EUR"),
        "disclaimer_profile": "research-only-v1",
        "input_hash": sha256_obj({"params": params, "seed": seed,
                                  "data": data_lineage}),
    }


def save(ws, manifest: dict) -> str:
    ws.save_artifact(manifest["artifact_id"], manifest["kind"], manifest)
    return manifest["artifact_id"]


def load_json(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True)
