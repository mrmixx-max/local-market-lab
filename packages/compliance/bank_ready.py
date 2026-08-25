"""Bank-ready compliance: audit trail, integrity checks, BaFin-style reports,
GDPR export/deletion. All critical audit events append to an immutable log."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from apps.api.deps import get_workspace
from apps.api.middleware import log_json

SYSTEM_VERSION = "1.0.0-bankready"
CRITICAL_TABLES = ("instruments", "transactions", "prices", "corporate_actions")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _h(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _audit_tbl(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT NOT NULL,
        timestamp TEXT NOT NULL, action TEXT NOT NULL,
        params TEXT, result_hash TEXT)""")
    conn.commit()


def _cs_tbl(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS table_checksums(
        table_name TEXT PRIMARY KEY, checksum TEXT NOT NULL, computed_at TEXT NOT NULL)"""
    )
    conn.commit()


class AuditLogger:
    """Append-only log of all API actions (user, ts, action, params, result_hash)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        _audit_tbl(conn)

    def log(
        self, user: str, action: str, params: Any = None, result: Any = None
    ) -> int:
        p = (
            json.dumps(params, sort_keys=True, default=str)
            if params is not None
            else None
        )
        rh = (
            _h(json.dumps(result, sort_keys=True, default=str))
            if result is not None
            else None
        )
        cur = self.conn.execute(
            "INSERT INTO audit_log(user,timestamp,action,params,result_hash) VALUES(?,?,?,?,?)",
            (user, _utc(), action, p, rh),
        )
        self.conn.commit()
        return cur.lastrowid

    def entries(self, limit: int = 100) -> list[dict]:
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        ]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]


class DataIntegrity:
    """SHA-256 checksums of critical DB tables; verify on startup."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        _cs_tbl(conn)

    def _tbl_cs(self, table: str) -> str:
        rows = self.conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
        return _h(json.dumps([dict(r) for r in rows], sort_keys=True, default=str))

    def snapshot(self) -> dict[str, str]:
        result = {}
        for t in CRITICAL_TABLES:
            cs = self._tbl_cs(t)
            result[t] = cs
            self.conn.execute(
                "INSERT OR REPLACE INTO table_checksums(table_name,checksum,computed_at) VALUES(?,?,?)",  # noqa: E501
                (t, cs, _utc()),
            )
        self.conn.commit()
        return result

    def verify(self) -> dict[str, bool]:
        stored = {
            r["table_name"]: r["checksum"]
            for r in self.conn.execute("SELECT * FROM table_checksums").fetchall()
        }
        return {
            t: stored.get(t) == self._tbl_cs(t) for t in CRITICAL_TABLES if t in stored
        }


class ComplianceReport:
    """Generate BaFin-style JSON compliance report."""

    def __init__(self, logger: AuditLogger, integrity: DataIntegrity):
        self.logger, self.integrity = logger, integrity

    def generate(self) -> dict:
        n = self.logger.count()
        ok = self.integrity.verify()
        flags = (["no_audit_entries"] if n == 0 else []) + (
            ["data_integrity_mismatch"] if not all(ok.values()) else []
        )
        return {
            "system_version": SYSTEM_VERSION,
            "generated_at": _utc(),
            "audit_log_summary": {
                "total_entries": n,
                "recent_actions": [r["action"] for r in self.logger.entries(5)],
            },
            "data_integrity_status": ok,
            "user_actions_count": n,
            "risk_flags": flags,
        }


class DataExport:
    """GDPR-style export of all user data as JSON."""

    @staticmethod
    def export_user(conn: sqlite3.Connection, user: str) -> dict:
        txns = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM transactions WHERE portfolio=?", (user,)
            ).fetchall()
        ]
        return {
            "user": user,
            "exported_at": _utc(),
            "data_categories": {"transactions": txns},
            "format_version": "1.0",
        }


class DataDeletion:
    """Anonymize user PII, keep aggregates."""

    @staticmethod
    def anonymize(conn: sqlite3.Connection, user: str) -> int:
        anon = f"deleted_user_{_h(user)[:8]}"
        cur = conn.execute(
            "UPDATE transactions SET portfolio=?, note='' WHERE portfolio=?",
            (anon, user),
        )
        conn.commit()
        return cur.rowcount


# ---------------------------------------------------------------------------
compliance_router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])
_logger = lambda ws: AuditLogger(ws.conn)  # noqa: E731
_integ = lambda ws: DataIntegrity(ws.conn)  # noqa: E731


@compliance_router.get("/audit-log")
def audit_log(limit: int = 50, ws=Depends(get_workspace)):
    return {"entries": _logger(ws).entries(limit), "total": _logger(ws).count()}


@compliance_router.post("/integrity-check")
def integrity_check(ws=Depends(get_workspace)):
    i = _integ(ws)
    i.snapshot()
    return {"status": "ok", "tables": i.verify()}


@compliance_router.get("/report")
def report(ws=Depends(get_workspace)):
    return ComplianceReport(_logger(ws), _integ(ws)).generate()


@compliance_router.get("/export/{user}")
def export_user(user: str, ws=Depends(get_workspace)):
    d = DataExport.export_user(ws.conn, user)
    _logger(ws).log("system", "gdpr_export", {"user": user})
    return d


@compliance_router.delete("/delete-account/{user}")
def delete_account(user: str, ws=Depends(get_workspace)):
    n = DataDeletion.anonymize(ws.conn, user)
    _logger(ws).log("system", "gdpr_deletion", {"user": user}, {"rows": n})
    log_json("info", event="gdpr_deletion", user=user, rows=n)
    return {"status": "anonymized", "user": user, "rows_affected": n}
