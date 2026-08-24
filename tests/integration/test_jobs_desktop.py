"""Tests for the PyQt6 Jobs-panel logic (no real GUI — mock ApiClient)."""
from __future__ import annotations

import json
import types

import pytest

# PyQt6 may not be importable in headless CI; skip module if absent
qt_available = False
try:
    from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
    qt_available = True
except Exception:
    qt_available = False

pytestmark = pytest.mark.skipif(not qt_available, reason="PyQt6 not available")

from windows.src.main_window import MainWindow  # noqa: E402


class _FakeApi:
    """Records calls; returns canned job lists/statuses."""
    def __init__(self, jobs=None):
        self.jobs = jobs or []
        self.calls = []
        self.cancel_calls = []

    def get(self, path):
        self.calls.append(path)
        if path.startswith("/api/v1/jobs?") or path == "/api/v1/jobs":
            return self.jobs
        if path.startswith("/api/v1/jobs/"):
            jid = path.split("/")[-1]
            for j in self.jobs:
                if j["id"] == jid:
                    return j
        return None

    def post(self, path, json=None):
        self.calls.append((path, json))
        return {"job_id": "new1", "status": "queued", "known_kinds": []}

    def delete(self, path):
        self.cancel_calls.append(path)
        jid = path.split("/")[-1]
        for j in self.jobs:
            if j["id"] == jid:
                j["status"] = "cancelled"
        return {"id": jid, "status": "cancelled"}


def _make_window(monkeypatch, jobs):
    app = QApplication.instance() or QApplication([])
    w = MainWindow.__new__(MainWindow)  # bypass __init__ (GUI building)
    w.api = _FakeApi(jobs)
    w.jobs_table = QTableWidget(0, 7)
    w.jobs_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows)
    w.jobs_msg = types.SimpleNamespace(setText=lambda x: None)
    w._jobs_cache = {}
    return w, app


class TestDesktopJobs:
    def test_refresh_populates_table(self, monkeypatch):
        jobs = [{"id": "a1", "kind": "monte_carlo", "status": "running",
                 "progress": 0.5, "created_at": 1.0, "started_at": 2.0,
                 "finished_at": None},
                {"id": "b2", "kind": "stress", "status": "succeeded",
                 "progress": 1.0, "created_at": 0, "started_at": 0,
                 "finished_at": 1, "result_ref": "jobs/b2/result"}]
        w, app = _make_window(monkeypatch, jobs)
        w._jobs_refresh()
        assert w.jobs_table.rowCount() == 2
        # first row is newest (reversed) -> b2 succeeded
        assert w.jobs_table.item(0, 0).text() == "b2"
        assert w.jobs_table.item(0, 2).text() == "succeeded"

    def test_refresh_shows_api_down(self, monkeypatch):
        w, app = _make_window(monkeypatch, [])
        w.api.get = lambda p: None  # network down
        captured = {}
        w.jobs_msg.setText = lambda x: captured.update(msg=x)
        w._jobs_refresh()
        assert "unreachable" in captured["msg"]

    def test_cancel_uses_real_endpoint(self, monkeypatch):
        jobs = [{"id": "c3", "kind": "tuning", "status": "running",
                 "progress": 0.1, "created_at": 0, "started_at": 0,
                 "finished_at": None}]
        w, app = _make_window(monkeypatch, jobs)
        w.jobs_table.setRowCount(1)
        w.jobs_table.setItem(0, 0, QTableWidgetItem("c3"))
        w.jobs_table.selectRow(0)
        w._jobs_cancel_selected()
        assert w.api.cancel_calls == ["/api/v1/jobs/c3"]
        # after cancel, status flips to cancelled in the fake
        assert w.api.jobs[0]["status"] == "cancelled"

    def test_artifact_only_when_succeeded(self, monkeypatch):
        # terminal state: not succeeded -> no artifact fetch
        w, app = _make_window(monkeypatch, [])
        w.jobs_table.setRowCount(1)
        w.jobs_table.setItem(0, 0, QTableWidgetItem("d4"))
        w.jobs_table.setItem(0, 2, QTableWidgetItem("queued"))
        captured = {}
        w.jobs_msg = types.SimpleNamespace(setText=lambda x: captured.update(m=x))
        w.jobs_table.currentRow = lambda: 0
        w._jobs_open_artifact()
        assert "no artifact" in captured["m"]

    def test_no_blocking_on_submit(self, monkeypatch):
        w, app = _make_window(monkeypatch, [])
        w.jobs_kind = types.SimpleNamespace(currentText=lambda: "monte_carlo")
        w._jobs_submit()  # should return immediately, not block
        assert w.api.calls and any(
            c[0] == "/api/v1/jobs" for c in w.api.calls if isinstance(c, tuple))
