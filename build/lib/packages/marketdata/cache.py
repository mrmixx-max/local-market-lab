"""SQLite-based cache for market data with TTL and offline fallback.

Configuration via environment variables:
  LML_CACHE_TTL_HOURS (default 24) — cache entry lifetime
  LML_CACHE_DB_PATH (default ~/.local-market-lab/cache/market.db)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)


def _default_ttl() -> int:
    try:
        return int(os.environ.get("LML_CACHE_TTL_HOURS", "24")) * 3600
    except ValueError:
        return 86400


def _default_db_path() -> str:
    return os.environ.get(
        "LML_CACHE_DB_PATH",
        str(Path.home() / ".local-market-lab" / "cache" / "market.db"),
    )


class MarketDataCache:
    """SQLite cache for OHLCV bars. TTL-based expiry, offline fallback."""

    def __init__(self, db_path: str | Path | None = None, ttl: int | None = None):
        self.db_path = str(db_path or _default_db_path())
        self.ttl = ttl or _default_ttl()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    quality_status TEXT DEFAULT 'unknown'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_ts ON cache(created_at)")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _make_key(self, symbol: str, interval: str, source: str) -> str:
        return f"{source}:{symbol.upper()}:{interval}"

    def get(self, symbol: str, interval: str, source: str) -> list[dict] | None:
        """Return cached bars if present and fresh, else None."""
        key = self._make_key(symbol, interval, source)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data, created_at FROM cache WHERE key=?", (key,)
            ).fetchone()
            if row is None:
                return None
            age = time.time() - row["created_at"]
            if age > self.ttl:
                return None
            return json.loads(row["data"])

    def put(self, symbol: str, interval: str, source: str,
            bars: list[dict], quality_status: str = "unknown") -> None:
        """Store bars in cache with quality status."""
        key = self._make_key(symbol, interval, source)
        payload = json.dumps(bars)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, data, created_at, quality_status)"
                " VALUES (?,?,?,?)",
                (key, payload, time.time(), quality_status),
            )

    def get_offline(self, symbol: str, interval: str, source: str) -> list[dict] | None:
        """Return cached bars regardless of TTL (offline fallback)."""
        key = self._make_key(symbol, interval, source)
        with self._conn() as conn:
            row = conn.execute("SELECT data FROM cache WHERE key=?", (key,)).fetchone()
            return json.loads(row["data"]) if row else None

    # ---------- versioned entries (schema-aware) ----------

    def put_versioned(self, key: str, bars: list[dict],
                      quality_status: str = "unchecked") -> None:
        """Store bars under a fully versioned composite key."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, data, created_at, quality_status)"
                " VALUES (?,?,?,?)",
                (key, json.dumps(bars), time.time(), quality_status),
            )

    def get_versioned(self, key: str, respect_ttl: bool = True) -> list[dict] | None:
        """Return cached bars only when the exact versioned key exists and is
        fresh. A schema change changes the key itself — old entries are never
        silently returned; they simply miss."""
        with self._conn() as conn:
            try:
                row = conn.execute(
                    "SELECT data, created_at FROM cache WHERE key=?", (key,)
                ).fetchone()
            except sqlite3.OperationalError:
                return None
            if row is None:
                return None
            if respect_ttl:
                age = time.time() - row["created_at"]
                if age > self.ttl:
                    return None
            try:
                return json.loads(row["data"])
            except (json.JSONDecodeError, TypeError):
                log.error("corrupt cache entry for key %.60s... — invalidated", key)
                conn.execute("DELETE FROM cache WHERE key=?", (key,))
                return None

    def purge_old_schema(self, schema_version: str = "") -> int:
        """Delete all entries whose key does not carry the current schema tag.
        Called on demand after a CACHE_SCHEMA_VERSION bump; not automatic."""
        with self._conn() as conn:
            cur = conn.execute("SELECT key FROM cache")
            stale = [r["key"] for r in cur if f"schema={schema_version}|" not in r["key"]]
            for k in stale:
                conn.execute("DELETE FROM cache WHERE key=?", (k,))
            return len(stale)

    def invalidate(self, symbol: str | None = None) -> int:
        """Invalidate cache entries. If symbol is None, clear all."""
        with self._conn() as conn:
            if symbol is None:
                cur = conn.execute("DELETE FROM cache")
            else:
                pattern = f"%:{symbol.upper()}:%"
                cur = conn.execute("DELETE FROM cache WHERE key LIKE ?", (pattern,))
            return cur.rowcount or 0

    def invalidate_on_quality_error(self, symbol: str, source: str, interval: str) -> None:
        """Invalidate cache when quality check fails (forces re-fetch)."""
        key = self._make_key(symbol, interval, source)
        with self._conn() as conn:
            conn.execute("DELETE FROM cache WHERE key=?", (key,))

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM cache").fetchone()["c"]
            oldest = conn.execute("SELECT MIN(created_at) t FROM cache").fetchone()["t"]
            newest = conn.execute("SELECT MAX(created_at) t FROM cache").fetchone()["t"]
        now = time.time()
        return {
            "entries": total,
            "ttl_seconds": self.ttl,
            "oldest_age_seconds": round(now - oldest, 1) if oldest else None,
            "newest_age_seconds": round(now - newest, 1) if newest else None,
        }
