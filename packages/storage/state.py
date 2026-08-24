"""Shared workspace + game engine singletons for the API layer."""
from __future__ import annotations

import os

from packages.storage.workspace import Workspace
from packages.ingest.fixtures import load_demo

_workspace: Workspace | None = None
_game_engine = None


def get_ws() -> Workspace:
    global _workspace
    if _workspace is None:
        db_path = os.environ.get("LML_DB", "./data/marketlab.db")
        _workspace = Workspace(db_path)
        cur = _workspace.conn.execute("SELECT COUNT(*) c FROM instruments")
        if cur.fetchone()["c"] == 0:
            load_demo(_workspace)
    return _workspace


def get_game_engine():
    """Shared TradingGame instance bound to the workspace singleton."""
    global _game_engine
    if _game_engine is None:
        from packages.game.engine import TradingGame
        _game_engine = TradingGame(get_ws())
    return _game_engine
