"""In-process job queue: persistent status (SQLite/WAL), progress,
cooperative cancellation, artifact result references. Additive to the
synchronous endpoints — analysis jobs only, no trade execution."""

from .errors import InvalidTransition, JobNotFound, UnknownJobKind
from .executor import known_kinds
from .models import Job, JobStatus, can_transition
from .queue import get_job_system

__all__ = [
    "Job",
    "JobStatus",
    "JobStore",
    "Worker",
    "can_transition",
    "get_job_system",
    "known_kinds",
    "InvalidTransition",
    "JobNotFound",
    "UnknownJobKind",
]

# keep store/worker importable from package root
from .store import JobStore  # noqa: E402,F401
from .worker import Worker  # noqa: E402,F401
