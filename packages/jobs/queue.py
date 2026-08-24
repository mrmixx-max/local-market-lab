"""In-process job queue: persistent status, cooperative cancellation,
artifact result references. No external infrastructure, no broker, no
trade execution — analysis jobs only."""
from __future__ import annotations

import threading
from pathlib import Path

from .errors import InvalidTransition, JobNotFound, UnknownJobKind  # noqa: F401
from .executor import known_kinds, register  # noqa: F401
from .models import Job, JobStatus, can_transition  # noqa: F401
from .store import JobStore
from .worker import Worker

_default: tuple[JobStore, Worker] | None = None
_default_lock = threading.Lock()


def get_job_system(db_path: str | Path = "~/.local-market-lab/jobs.db",
                   autostart: bool = True) -> tuple[JobStore, Worker]:
    """Process-wide singleton (store + started worker)."""
    global _default
    with _default_lock:
        if _default is None:
            store = JobStore(db_path)
            worker = Worker(store)
            if autostart:
                worker.start()
            _default = (store, worker)
        return _default


__all__ = [
    "Job", "JobStatus", "JobStore", "Worker", "can_transition",
    "get_job_system", "known_kinds", "register", "InvalidTransition",
    "JobNotFound", "UnknownJobKind",
]
