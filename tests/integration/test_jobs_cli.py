"""Tests for P1.3 client binding: CLI jobs + shared normalize_job model."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from apps.cli.jobs_client import JobsClient, normalize_job


def _run_cli(*args):
    cmd = [sys.executable, "-m", "apps.cli.main", *args]
    env = dict(os.environ)
    env["LML_API"] = "http://127.0.0.1:8322"
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)


class TestNormalizeModel:
    def test_maps_backend_to_unified(self):
        raw = {
            "id": "abc123",
            "kind": "monte_carlo",
            "status": "running",
            "progress": 0.42,
            "result_ref": None,
            "error": None,
            "created_at": 1.0,
            "started_at": 2.0,
            "finished_at": None,
        }
        n = normalize_job(raw)
        assert n["job_id"] == "abc123"
        assert n["job_type"] == "monte_carlo"
        assert n["status"] == "running"
        assert n["progress"] == 0.42
        assert n["phase"] == "execution"
        assert n["processed"] == 42
        assert n["total"] == 100
        assert n["cancel_requested"] is False

    def test_succeeded_has_artifact(self):
        raw = {
            "id": "x",
            "kind": "stress",
            "status": "succeeded",
            "progress": 1.0,
            "result_ref": "jobs/x/result",
            "error": None,
            "created_at": 0,
            "started_at": 0,
            "finished_at": 1,
        }
        n = normalize_job(raw)
        assert n["artifact_id"] == "jobs/x/result"
        assert n["phase"] == "done"

    def test_failed_sets_error_fields(self):
        raw = {
            "id": "x",
            "kind": "tuning",
            "status": "failed",
            "progress": 0.3,
            "error": "boom",
            "created_at": 0,
            "started_at": 0,
            "finished_at": 1,
        }
        n = normalize_job(raw)
        assert n["error_code"] == "EXECUTION_ERROR"
        assert n["error_message"] == "boom"


class TestCliJobsLive:
    """Requires the API server running. Skips if unreachable."""

    @pytest.fixture(autouse=True)
    def _api(self):
        base = os.environ.get("LML_API", "http://127.0.0.1:8322")
        c = JobsClient(base_url=base)
        health = c._get("/api/v1/health")
        if not isinstance(health, dict) or "error" in health:
            pytest.skip("API server not running — skipping live CLI job tests")
        yield c

    def test_jobs_list_json(self, _api):
        r = _run_cli("jobs", "list", "--json")
        assert r.returncode == 0
        assert isinstance(json.loads(r.stdout), list)

    def test_jobs_submit_status_wait_artifact(self, _api):
        resp = _api.submit("demo_sleep", {"steps": 3, "delay": 0.02})
        assert "job_id" in resp
        jid = resp["job_id"]
        st = _run_cli("jobs", "status", jid, "--json")
        assert st.returncode == 0
        assert json.loads(st.stdout)["job_id"] == jid
        w = _run_cli("jobs", "wait", jid, "--timeout", "15")
        assert w.returncode == 0, w.stderr
        art = _run_cli("jobs", "artifact", jid, "--json")
        assert art.returncode == 0

    def test_jobs_cancel_idempotent(self, _api):
        resp = _api.submit("demo_sleep", {"steps": 100, "delay": 0.05})
        jid = resp["job_id"]
        import time

        time.sleep(0.2)
        c1 = _run_cli("jobs", "cancel", jid)
        assert c1.returncode == 0
        c2 = _run_cli("jobs", "cancel", jid)
        assert c2.returncode == 0

    def test_jobs_artifact_non_succeeded_fails(self, _api):
        resp = _api.submit("demo_sleep", {"steps": 100, "delay": 0.05})
        jid = resp["job_id"]
        _api.cancel(jid)
        art = _run_cli("jobs", "artifact", jid)
        assert art.returncode != 0  # exit 5 (not succeeded)

    def test_cli_timeout_exit_code(self, _api):
        resp = _api.submit("demo_sleep", {"steps": 200, "delay": 0.05})
        jid = resp["job_id"]
        w = _run_cli("jobs", "wait", jid, "--timeout", "0.3")
        assert w.returncode == 2
        _api.cancel(jid)
