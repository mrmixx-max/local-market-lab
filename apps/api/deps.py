"""FastAPI dependency injection for the API layer.

Provides injectable dependencies so routes can declare what they need
instead of calling factory functions directly. Keeps the singleton
behavior from packages.storage.state but exposes it via Depends().
"""
from __future__ import annotations

from fastapi import Depends

from packages.storage.state import get_ws, get_game_engine
from packages.storage.workspace import Workspace
from packages.game.engine import TradingGame


def get_workspace() -> Workspace:
    """Inject the shared Workspace (SQLite) singleton."""
    return get_ws()


def get_game() -> TradingGame:
    """Inject the shared TradingGame engine singleton."""
    return get_game_engine()


# Type aliases for cleaner route signatures
WorkspaceDep = Depends(get_workspace)
GameEngineDep = Depends(get_game)
