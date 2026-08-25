"""In-process worker: pulls queued jobs, runs executors, honors cancellation."""

from __future__ import annotations

import logging
import threading
from typing import Any

from .executor import get_executor
from .models import Job, JobStatus
from .store import JobStore

log = logging.getLogger(__name__)


class Worker:
    """Single background thread processing queued jobs FIFO."""

    def __init__(self, store: JobStore, poll_interval: float = 0.05):
        self.store = store
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_id: str | None = None
        self._cancel_requested: set[str] = set()
        self._lock = threading.Lock()

    # ---------- lifecycle ----------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="lml-job-worker", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Graceful shutdown: finish current poll cycle; running job's thread
        is daemon so process exit never hangs."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    # ---------- queue ops ----------

    def submit(self, kind: str, params: dict[str, Any]) -> Job:
        if get_executor(kind) is None:
            from .errors import UnknownJobKind

            raise UnknownJobKind(
                f"unknown job kind {kind!r}; known: monte_carlo, walk_forward,"
                " tuning, stress, demo_sleep"
            )
        job = self.store.create(kind, params)
        log.info("job submitted %s kind=%s", job.id, kind)
        return job

    def cancel(self, job_id: str) -> Job | None:
        """Request cancellation. queued -> cancelled directly;
        running -> cancelling (worker observes cooperative flag)."""
        job = self.store.get(job_id)
        if job is None:
            return None
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLING
            if self.store.update(job, expect_status=JobStatus.QUEUED):
                job.status = JobStatus.CANCELLED
                job.finished_at = _now()
                self.store.update(job)
                return job
            return self.store.get(job_id)
        if job.status == JobStatus.RUNNING:
            with self._lock:
                self._cancel_requested.add(job_id)
            job.status = JobStatus.CANCELLING
            self.store.update(job, expect_status=JobStatus.RUNNING)
            return job
        return job  # terminal state — no-op

    def wait(self, job_id: str, timeout: float = 60.0, poll: float = 0.1) -> Job | None:
        """Block until job reaches a terminal status or timeout."""
        import time as _t

        deadline = _t.time() + timeout
        while _t.time() < deadline:
            job = self.store.get(job_id)
            if job and job.status in (
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                return job
            _t.sleep(poll)
        return self.store.get(job_id)

    # ---------- internals ----------

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            job = self._next_queued()
            if job is None:
                self._stop.wait(self.poll_interval)
                continue
            self._execute(job)

    def _next_queued(self) -> Job | None:
        for job in reversed(self.store.list(limit=100)):  # oldest first
            if job.status == JobStatus.QUEUED:
                t = self.store.transition(
                    job.id, JobStatus.RUNNING, expect=JobStatus.QUEUED
                )
                return t
        return None

    def _execute(self, job: Job) -> None:
        self._current_id = job.id
        fn = get_executor(job.kind)

        def progress(frac: float) -> None:
            frac = max(0.0, min(1.0, float(frac)))
            with self._lock:
                cancelled = job.id in self._cancel_requested
            fresh = self.store.get(job.id)
            if cancelled and fresh and fresh.status == JobStatus.CANCELLING:
                raise _JobCancelled()

        try:
            result = fn(job.params, progress)
            fresh = self.store.get(job.id)
            if fresh and fresh.status == JobStatus.CANCELLING:
                raise _JobCancelled()
            job.result_ref = f"jobs/{job.id}/result"
            job.progress = 1.0
            job.status = JobStatus.SUCCEEDED
            job.result_payload = result  # type: ignore[attr-defined]
            self.store.update(job, expect_status=JobStatus.RUNNING)
            self._persist_result(job.id, result)
            log.info("job %s succeeded", job.id)
        except _JobCancelled:
            job.status = JobStatus.CANCELLED
            job.finished_at = _now()
            self.store.update(job)
            with self._lock:
                self._cancel_requested.discard(job.id)
            log.info("job %s cancelled", job.id)
        except Exception as exc:  # noqa: BLE001 — jobs must never kill worker
            job.status = JobStatus.FAILED
            job.error = repr(exc)[:500]
            job.finished_at = _now()
            self.store.update(job)
            log.exception("job %s failed", job.id)
        finally:
            self._current_id = None

    def _persist_result(self, job_id: str, result: dict) -> None:
        """Store full result JSON next to the status DB (artifact reference)."""
        import json

        path = self.store.db_path.parent / "results"
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{job_id}.json").write_text(
            json.dumps(result, indent=1), encoding="utf-8"
        )


def _now() -> float:
    import time

    return time.time()


class _JobCancelled(BaseException):
    """Internal control-flow signal (BaseException so generic except in user
    code inside executors doesn't swallow it)."""
