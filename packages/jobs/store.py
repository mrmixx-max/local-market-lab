"""Persistent job state in SQLite (WAL mode)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .models import Job, JobStatus, can_transition


class JobStore:
    """Thread-safe persistent job store. WAL allows concurrent readers while
    the writer commits — API status polls never block the worker."""

    def __init__(self, db_path: str | Path = "~/.local-market-lab/jobs.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    # one connection per thread; WAL + busy_timeout keeps writers/reader apart
    @property
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=10000")
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        with self._tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    result_ref TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL
                )""")

    from contextlib import contextmanager

    @contextmanager
    def _tx(self):
        c = self._conn
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise

    # ---------- CRUD ----------

    def create(self, kind: str, params: dict) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            params=params,
            created_at=time.time(),
        )
        with self._tx() as c:
            c.execute(
                "INSERT INTO jobs(id,kind,params_json,status,progress,created_at)"
                " VALUES (?,?,?,?,0,?)",
                (job.id, kind, json.dumps(params), job.status.value, job.created_at),
            )
        return job

    def get(self, job_id: str) -> Job | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list(self, limit: int = 50) -> list[Job]:
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def update(self, job: Job, *, expect_status: JobStatus | None = None) -> bool:
        """Persist job fields. When expect_status is given, the write only
        happens if the stored status still matches (optimistic guard for
        cancel races); returns False otherwise."""
        sets = [
            "status=?",
            "progress=?",
            "result_ref=?",
            "error=?",
            "started_at=?",
            "finished_at=?",
        ]
        vals = [
            job.status.value,
            job.progress,
            job.result_ref,
            job.error,
            job.started_at,
            job.finished_at,
        ]
        if expect_status is not None:
            with self._tx() as c:
                cur = c.execute(
                    f"UPDATE jobs SET {', '.join(sets)} WHERE id=? AND status=?",
                    (*vals, job.id, expect_status.value),
                )
                return cur.rowcount > 0
        with self._tx() as c:
            c.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", (*vals, job.id))
        return True

    # ---------- helpers ----------

    def transition(
        self, job_id: str, new_status: JobStatus, expect: JobStatus | None = None
    ) -> Job | None:
        """Apply a guarded state transition; returns updated Job or None."""
        job = self.get(job_id)
        if job is None or not can_transition(job.status, new_status):
            return None
        if new_status == JobStatus.RUNNING and job.started_at is None:
            job.started_at = time.time()
        if new_status in (JobStatus.CANCELLED, JobStatus.SUCCEEDED, JobStatus.FAILED):
            job.finished_at = time.time()
        job.status = new_status
        ok = self.update(job, expect_status=expect or job_status_of(job, new_status))
        return job if ok else None

    @staticmethod
    def _row_to_job(r) -> Job:
        return Job(
            id=r["id"],
            kind=r["kind"],
            params=json.loads(r["params_json"]),
            status=JobStatus(r["status"]),
            progress=r["progress"],
            result_ref=r["result_ref"],
            error=r["error"],
            created_at=r["created_at"],
            started_at=r["started_at"],
            finished_at=r["finished_at"],
        )


def job_status_of(job: Job, new_status: JobStatus) -> JobStatus:
    """The DB status expected when applying `new_status` to this in-memory job."""
    return job.status if job.status != new_status else None or new_status
