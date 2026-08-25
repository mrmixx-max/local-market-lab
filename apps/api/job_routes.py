"""Additive job endpoints: submit, status, list, cancel, result.

Long-running analysis (monte_carlo, walk_forward, tuning, stress) runs in
the in-process worker; API stays responsive. No trade execution.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from packages.jobs import JobStatus, get_job_system, known_kinds

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class JobSubmit(BaseModel):
    kind: str = Field(..., examples=["monte_carlo"])
    params: dict = Field(default_factory=dict)


def _system(request: Request):
    db = getattr(request.app.state, "jobs_db", "~/.local-market-lab/jobs.db")
    return get_job_system(db)


@router.post("")
def submit_job(body: JobSubmit, request: Request):
    store, worker = _system(request)
    try:
        job = worker.submit(body.kind, body.params)
    except Exception as exc:  # UnknownJobKind etc.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job.id, "status": job.status.value, "known_kinds": known_kinds()}


@router.get("/{job_id}")
def job_status(job_id: str, request: Request):
    store, _ = _system(request)
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
    d = job.to_dict()
    # attach result payload when terminal and available
    if job.status == JobStatus.SUCCEEDED:
        rp = store.db_path.parent / "results" / f"{job.id}.json"
        if rp.exists():
            try:
                d["result"] = json.loads(rp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                d["result_ref"] = str(rp)
    return d


@router.get("")
def list_jobs(request: Request, limit: int = 20):
    store, _ = _system(request)
    return [j.to_dict() for j in store.list(limit=max(1, min(limit, 100)))]


@router.delete("/{job_id}")
def cancel_job(job_id: str, request: Request):
    _, worker = _system(request)
    job = worker.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
    return job.to_dict()
