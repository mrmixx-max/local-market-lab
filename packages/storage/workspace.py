"""SQLite storage — workspace database for instruments, transactions,
corporate actions and price bars. Append-only where it matters.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    asset_class TEXT NOT NULL DEFAULT 'etf',
    currency TEXT NOT NULL DEFAULT 'EUR',
    isin TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio TEXT NOT NULL,
    symbol TEXT NOT NULL REFERENCES instruments(symbol),
    txn_type TEXT NOT NULL,
    date TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fees REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_txn_port_date ON transactions(portfolio, date);

CREATE TABLE IF NOT EXISTS corporate_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL REFERENCES instruments(symbol),
    action TEXT NOT NULL,
    date TEXT NOT NULL,
    ratio REAL,
    amount_per_share REAL,
    currency TEXT NOT NULL DEFAULT 'EUR'
);

CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL REFERENCES instruments(symbol),
    date TEXT NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    source_name TEXT NOT NULL DEFAULT 'user-csv',
    retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
    license_note TEXT NOT NULL DEFAULT 'user data — local only',
    redistribution_allowed INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    manifest_json TEXT NOT NULL
);
"""


class Workspace:
    """The local workspace: one SQLite file under the workspace directory."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get(
            "LML_DB", "./data/marketlab.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ---------- instruments ----------
    def ensure_instrument(self, symbol: str, name: str = "", asset_class: str = "etf",
                          currency: str = "EUR", isin: str | None = None) -> None:
        self.conn.execute(
            """INSERT INTO instruments(symbol,name,asset_class,currency,isin)
               VALUES(?,?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET name=excluded.name""",
            (symbol.upper(), name, asset_class, currency, isin),
        )
        self.conn.commit()

    def has_instrument(self, symbol: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM instruments WHERE symbol=?", (symbol.upper(),)
        ).fetchone() is not None

    def instrument_currency(self, symbol: str) -> str:
        row = self.conn.execute(
            "SELECT currency FROM instruments WHERE symbol=?", (symbol.upper(),)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown instrument {symbol!r}")
        return row["currency"]

    # ---------- transactions ----------
    def add_transaction(self, t: dict) -> int:
        cur = self.conn.execute(
            """INSERT INTO transactions(portfolio,symbol,txn_type,date,quantity,price,fees,currency,note)
               VALUES(:portfolio,:symbol,:txn_type,:date,:quantity,:price,:fees,:currency,:note)""",
            t,
        )
        self.conn.commit()
        return cur.lastrowid

    def transactions_for(self, portfolio: str):
        return self.conn.execute(
            """SELECT * FROM transactions WHERE portfolio=? ORDER BY date, txn_id""",
            (portfolio,),
        ).fetchall()

    def portfolios(self):
        return [r["portfolio"] for r in
                self.conn.execute("SELECT DISTINCT portfolio FROM transactions")]

    # ---------- corporate actions ----------
    def add_corporate_action(self, ca: dict) -> int:
        cur = self.conn.execute(
            """INSERT INTO corporate_actions(symbol,action,date,ratio,amount_per_share,currency)
               VALUES(:symbol,:action,:date,:ratio,:amount_per_share,:currency)""",
            ca,
        )
        self.conn.commit()
        return cur.lastrowid

    def actions_for(self, symbols: list[str] | None = None):
        if symbols:
            qmarks = ",".join("?" * len(symbols))
            rows = self.conn.execute(
                f"SELECT * FROM corporate_actions WHERE symbol IN ({qmarks}) ORDER BY date",
                [s.upper() for s in symbols],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM corporate_actions ORDER BY date").fetchall()
        return rows

    # ---------- prices ----------
    def upsert_price(self, symbol: str, date_iso: str, close: float,
                     volume: float | None = None, source: str = "user-csv",
                     license_note: str = "user data — local only") -> None:
        self.conn.execute(
            """INSERT INTO prices(symbol,date,close,volume,source_name,license_note)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(symbol,date) DO UPDATE SET
                 close=excluded.close, volume=excluded.volume,
                 source_name=excluded.source_name, license_note=excluded.license_note""",
            (symbol.upper(), date_iso, close, volume, source, license_note),
        )

    def commit_prices(self):
        self.conn.commit()

    def price_series(self, symbol: str):
        return self.conn.execute(
            "SELECT date, close, volume FROM prices WHERE symbol=? ORDER BY date",
            (symbol.upper(),),
        ).fetchall()

    def price_count(self, symbol: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) c FROM prices WHERE symbol=?", (symbol.upper(),)
        ).fetchone()["c"]

    # ---------- artifacts ----------
    def save_artifact(self, artifact_id: str, kind: str, manifest: dict) -> None:
        import json
        self.conn.execute(
            "INSERT OR REPLACE INTO artifacts(artifact_id,kind,manifest_json) VALUES(?,?,?)",
            (artifact_id, kind, json.dumps(manifest, sort_keys=True)),
        )
        self.conn.commit()
