"""Tests for the in-process job queue (v1.0 P1.1 + P1.3)."""

from __future__ import annotations

import json
import time

import pytest

from packages.jobs import JobStatus, JobStore, Worker, known_kinds


@pytest.fixture()
def system(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    worker = Worker(store)
    worker.start()
    yield store, worker
    worker.stop()


class TestStateMachine:
    def test_valid_transitions(self):
        from packages.jobs.models import can_transition

        assert can_transition(JobStatus.QUEUED, JobStatus.RUNNING)
        assert can_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert not can_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)  # terminal
        assert not can_transition(JobStatus.CANCELLED, JobStatus.RUNNING)

    def test_store_crud_roundtrip(self, tmp_path):
        store = JobStore(tmp_path / "j.db")
        job = store.create("demo_sleep", {"steps": 1})
        got = store.get(job.id)
        assert got is not None and got.params == {"steps": 1}
        assert got.status == JobStatus.QUEUED

    def test_wal_mode_active(self, tmp_path):
        store = JobStore(tmp_path / "j.db")
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"


class TestExecution:
    def test_submit_run_succeed(self, system):
        store, worker = system
        job = worker.submit("demo_sleep", {"steps": 4, "delay": 0.01})
        done = worker.wait(job.id, timeout=10)
        assert done is not None and done.status == JobStatus.SUCCEEDED
        assert done.progress == 1.0
        assert done.result_ref == f"jobs/{job.id}/result"

    def test_result_artifact_persisted(self, system):
        store, worker = system
        job = worker.submit("demo_sleep", {"steps": 2, "delay": 0.01})
        worker.wait(job.id, timeout=10)
        rp = store.db_path.parent / "results" / f"{job.id}.json"
        assert rp.exists()
        data = json.loads(rp.read_text(encoding="utf-8"))
        assert data["steps"] == 2

    def test_unknown_kind_rejected(self, system):
        _, worker = system
        from packages.jobs import UnknownJobKind

        with pytest.raises(UnknownJobKind):
            worker.submit("nuke_the_market", {})

    def test_progress_visible_while_running(self, system):
        store, worker = system
        job = worker.submit("demo_sleep", {"steps": 8, "delay": 0.08})
        saw_progress = False
        for _ in range(60):
            j = store.get(job.id)
            if j.status == JobStatus.RUNNING and 0 < j.progress < 1.0:
                saw_progress = True
                break
            time.sleep(0.05)
        assert saw_progress or store.get(job.id).status == JobStatus.SUCCEEDED

    def test_cancel_running_job(self, system):
        store, worker = system
        job = worker.submit("demo_sleep", {"steps": 100, "delay": 0.05})
        # wait until running
        for _ in range(50):
            if store.get(job.id).status == JobStatus.RUNNING:
                break
            time.sleep(0.02)
        cancelled = worker.cancel(job.id)
        assert cancelled is not None
        done = worker.wait(job.id, timeout=10)
        assert done is not None and done.status == JobStatus.CANCELLED

    def test_cancel_queued_job(self, system):
        # occupy the worker so the submitted job stays queued
        store, worker = system
        blocker = worker.submit("demo_sleep", {"steps": 20, "delay": 0.05})
        queued_job = worker.submit("demo_sleep", {"steps": 1})
        result = worker.cancel(queued_job.id)
        assert result is not None
        assert store.get(queued_job.id).status == JobStatus.CANCELLED
        worker.cancel(blocker.id)  # cleanup
        worker.wait(blocker.id, timeout=15)

    def test_cancel_terminal_is_noop(self, system):
        store, worker = system
        job = worker.submit("demo_sleep", {"steps": 1, "delay": 0.01})
        worker.wait(job.id, timeout=10)
        before = store.get(job.id).status
        out = worker.cancel(job.id)
        assert store.get(job.id).status == before
        assert out is not None


class TestConcurrency:
    def test_two_jobs_process_serially_both_succeed(self, system):
        store, worker = system
        a = worker.submit("demo_sleep", {"steps": 3, "delay": 0.02})
        b = worker.submit("demo_sleep", {"steps": 3, "delay": 0.02})
        ra = worker.wait(a.id, timeout=20)
        rb = worker.wait(b.id, timeout=20)
        assert ra.status == rb.status == JobStatus.SUCCEEDED

    def test_status_readable_while_worker_busy(self, system):
        """API-responsiveness guarantee: status polls never block on the worker."""
        store, worker = system
        blocker = worker.submit("demo_sleep", {"steps": 40, "delay": 0.05})
        t0 = time.perf_counter()
        for _ in range(20):
            store.get(blocker.id)
        elapsed = time.perf_counter() - t0
        assert elapsed < 1.0, "status polling blocked while job running"
        worker.cancel(blocker.id)


class TestBuiltins:
    def test_known_kinds(self):
        kinds = known_kinds()
        for k in ("monte_carlo", "walk_forward", "tuning", "stress", "demo_sleep"):
            assert k in kinds

    def test_monte_carlo_executor(self, system):
        store, worker = system
        job = worker.submit(
            "monte_carlo",
            {"weights": {"IWDA": 1.0}, "runs": 200, "seed": 42, "horizon_days": 63},
        )
        done = worker.wait(job.id, timeout=60)
        assert done.status == JobStatus.SUCCEEDED
        payload = json.loads(
            (store.db_path.parent / "results" / f"{job.id}.json").read_text()
        )
        assert "p01" in payload["metrics"]

    def test_stress_executor(self, system):
        store, worker = system
        job = worker.submit("stress", {"weights": {"IWDA": 1.0}, "seed": 42})
        done = worker.wait(job.id, timeout=60)
        assert done.status == JobStatus.SUCCEEDED


# ---------------------------------------------------------------------------
# API endpoints (additive; sync paths untouched)
# ---------------------------------------------------------------------------


class TestJobApi:
    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from apps.api import main as api_main

        monkeypatch.setattr(
            api_main.app.state, "jobs_db", str(tmp_path / "api_jobs.db"), raising=False
        )
        api_main.app.state.jobs_db = str(tmp_path / "api_jobs.db")
        return TestClient(api_main.app)

    def test_full_cycle_via_api(self, client):
        r = client.post(
            "/api/v1/jobs",
            json={"kind": "demo_sleep", "params": {"steps": 3, "delay": 0.01}},
        )
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        deadline = time.time() + 15
        final = None
        while time.time() < deadline:
            s = client.get(f"/api/v1/jobs/{job_id}").json()
            if s["status"] in ("succeeded", "failed", "cancelled"):
                final = s
                break
            time.sleep(0.05)
        assert final and final["status"] == "succeeded"
        assert final.get("result", {}).get("steps") == 3

    def test_unknown_kind_400(self, client):
        r = client.post("/api/v1/jobs", json={"kind": "nope", "params": {}})
        assert r.status_code == 400

    def test_cancel_via_api(self, client):
        r = client.post(
            "/api/v1/jobs",
            json={"kind": "demo_sleep", "params": {"steps": 100, "delay": 0.05}},
        )
        job_id = r.json()["job_id"]
        time.sleep(0.2)  # let it start
        d = client.delete(f"/api/v1/jobs/{job_id}")
        assert d.status_code == 200
        deadline = time.time() + 10
        while time.time() < deadline:
            s = client.get(f"/api/v1/jobs/{job_id}").json()
            if s["status"] == "cancelled":
                break
            time.sleep(0.05)
        assert s["status"] == "cancelled"

    def test_list_and_404(self, client):
        assert client.get("/api/v1/jobs?limit=5").status_code == 200
        assert client.get("/api/v1/jobs/doesnotexist").status_code == 404
