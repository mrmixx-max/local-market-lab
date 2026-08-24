"""Shared job client + unified job-status model.

Used by CLI, Desktop (PyQt6) and Web (fetch). Normalizes the backend
Job dict into the canonical client model so all three surfaces agree:

    job_id, job_type, status, progress, phase, processed, total, message,
    created_at, started_at, finished_at, cancel_requested, run_id,
    artifact_id, error_code, error_message, warnings

The backend stores: id, kind, params, status, progress, result_ref, error,
created_at, started_at, finished_at. Fields not present server-side
(run_id, error_code, warnings) are mapped where sensible and otherwise null.
"""
from __future__ import annotations

import time
from typing import Any


# Canonical status vocabulary across all clients
STATUSES = ("queued", "running", "cancelling", "cancelled", "succeeded", "failed")

# phase is a client-side simplification; the backend does not emit granular
# phases, so we derive one from status + kind.
_PHASE_BY_STATUS = {
    "queued": "queued",
    "running": "execution",
    "cancelling": "cancelling",
    "cancelled": "cancelled",
    "succeeded": "done",
    "failed": "error",
}


def normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a backend Job dict to the unified client model."""
    status = raw.get("status", "queued")
    progress = float(raw.get("progress", 0.0) or 0.0)
    err = raw.get("error")
    artifact = raw.get("result_ref") if status == "succeeded" else None
    # processed/total derived from progress (backend has no granular counts)
    total = 100
    processed = int(round(progress * total))
    message = ""
    if status == "failed" and err:
        message = str(err)
    elif status == "cancelled":
        message = "Job cancelled"
    elif status == "queued":
        message = "Waiting in queue"
    elif status == "running":
        message = f"Running ({progress*100:.0f}%)"

    return {
        "job_id": raw.get("id"),
        "job_type": raw.get("kind"),
        "status": status,
        "progress": progress,
        "phase": raw.get("phase") or _PHASE_BY_STATUS.get(status, "queued"),
        "processed": processed,
        "total": total,
        "message": message,
        "created_at": raw.get("created_at"),
        "started_at": raw.get("started_at"),
        "finished_at": raw.get("finished_at"),
        "cancel_requested": status == "cancelling",
        "run_id": raw.get("run_id"),
        "artifact_id": artifact,
        "error_code": "EXECUTION_ERROR" if status == "failed" else None,
        "error_message": err,
        "warnings": raw.get("warnings", []),
        # passthrough for clients that want the full payload
        "result": raw.get("result"),
    }


def runtime_seconds(raw: dict[str, Any]) -> float | None:
    """Human-readable runtime: started→finished, or started→now if running."""
    import time as _t
    started = raw.get("started_at")
    finished = raw.get("finished_at")
    if not started:
        return None
    end = finished or _t.time()
    return round(end - started, 2)


class JobsClient:
    """Thin REST client for the job endpoints. No broker, no execution."""

    def __init__(self, base_url: str = "http://127.0.0.1:8322", timeout: int = 8):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self._session = None

    def _http(self):
        # lazy import so environments without requests can still import module
        import requests
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _get(self, path: str) -> dict | None:
        try:
            r = self._http().get(f"{self.base}{path}", timeout=self.timeout)
            if r.status_code == 404:
                return {"error": "not_found", "status_code": 404}
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network/timeout/HTTP
            return {"error": str(exc)}

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        try:
            r = self._http().post(f"{self.base}{path}", json=json or {},
                                  timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"error": str(exc)}

    def delete(self, path: str) -> dict | None:
        try:
            r = self._http().delete(f"{self.base}{path}", timeout=self.timeout)
            if r.status_code == 404:
                return {"error": "not_found", "status_code": 404}
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"error": str(exc)}

    # --- high level ---
    def submit(self, kind: str, params: dict) -> dict | None:
        return self._post("/api/v1/jobs", {"kind": kind, "params": params})

    def list(self, limit: int = 20) -> list[dict]:
        data = self._get(f"/api/v1/jobs?limit={limit}")
        if not isinstance(data, list):
            return []
        return [normalize_job(j) for j in data]

    def get(self, job_id: str) -> dict | None:
        raw = self._get(f"/api/v1/jobs/{job_id}")
        if not isinstance(raw, dict) or "error" in raw:
            return raw
        return normalize_job(raw)

    def cancel(self, job_id: str) -> dict | None:
        raw = self.delete(f"/api/v1/jobs/{job_id}")
        if not isinstance(raw, dict) or "error" in raw:
            return raw
        return normalize_job(raw)

    def wait(self, job_id: str, timeout: float = 300.0, poll: float = 1.0) -> dict | None:
        """Block until terminal status or timeout. Returns normalized job or
        {'error': 'timeout'}."""
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = self.get(job_id)
            if isinstance(last, dict) and "error" not in last:
                if last["status"] in ("succeeded", "failed", "cancelled"):
                    return last
            time.sleep(poll)
        return {"error": "timeout", "job_id": job_id}
