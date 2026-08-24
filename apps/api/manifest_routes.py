"""Manifest API endpoints (v1.0 P1.4) — additive."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException, Query

from packages.artifacts.registry import list_manifests, load_manifest
from packages.artifacts.rerun import rerun_manifest, DriftError
from packages.artifacts.run_manifest import _env_hash, _system_version
from apps.cli.rerun_cli_helpers import get_executor

router = APIRouter(prefix="/api/v1/manifests", tags=["manifests"])


@router.get("", summary="List stored run manifests")
def api_list_manifests(limit: int = Query(50, ge=1, le=500)):
    return list_manifests(limit=limit)


@router.get("/{manifest_id}", summary="Get a single manifest")
def api_get_manifest(manifest_id: str):
    try:
        return load_manifest(manifest_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{manifest_id}/compare", summary="Compare original vs rerun record")
def api_compare_manifest(manifest_id: str):
    try:
        m = load_manifest(manifest_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "manifest_id": manifest_id,
        "result_hash": m.get("result_hash"),
        "parameters_hash": m.get("parameters_hash"),
        "environment_hash": m.get("environment_hash"),
        "system_version": m.get("system_version"),
    }


@router.post("/{manifest_id}/rerun", summary="Re-execute a stored manifest")
def api_rerun_manifest(
    manifest_id: str,
    allow_data_drift: bool = Query(False),
    allow_environment_drift: bool = Query(False),
    background: bool = Query(False, description="run via job queue"),
):
    if background:
        # delegate to the job queue (async)
        from apps.api.job_routes import _queue
        try:
            job = _queue.submit("rerun", {
                "manifest_id": manifest_id,
                "allow_data_drift": allow_data_drift,
                "allow_environment_drift": allow_environment_drift,
            })
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"job_id": job.job_id, "status": job.status.value,
                "rerun_submitted": True}

    cur_ver = _system_version()
    cur_env, _ = _env_hash()
    try:
        report = rerun_manifest(manifest_id, get_executor(), cur_ver, cur_env,
                                allow_data_drift=allow_data_drift,
                                allow_environment_drift=allow_environment_drift)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest not found")
    except DriftError as exc:
        raise HTTPException(status_code=409, detail=f"drift abort: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return report.to_dict()
