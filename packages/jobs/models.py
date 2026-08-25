"""Job models and status state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


#: Allowed transitions. Anything not listed is rejected.
TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLING},
    JobStatus.RUNNING: {JobStatus.CANCELLING, JobStatus.SUCCEEDED, JobStatus.FAILED},
    JobStatus.CANCELLING: {JobStatus.CANCELLED},
}


def can_transition(old: JobStatus, new: JobStatus) -> bool:
    return new in TRANSITIONS.get(old, set())


@dataclass
class Job:
    id: str
    kind: str
    params: dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0  # 0.0 .. 1.0
    result_ref: str | None = None  # artifact manifest id / path reference
    error: str | None = None
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "params": self.params,
            "status": self.status.value,
            "progress": round(self.progress, 4),
            "result_ref": self.result_ref,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
