"""Trading Game REST + WebSocket routes.

Prefix: /api/v1/game
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from apps.api.deps import get_game
from apps.api.schemas import GameState, LeaderboardEntry
from packages.game.engine import CHALLENGES

game_router = APIRouter(prefix="/api/v1/game", tags=["game"])


# ---------- challenges catalog ----------
@game_router.get("/challenges", summary="List available game challenges")
async def challenges():
    """Return all challenge definitions."""
    return CHALLENGES


# ---------- create a game ----------
@game_router.post("/create", summary="Create a paper-trading game session")
async def create_game(payload: dict, game=Depends(get_game)):
    """Create a new paper-trading game session with the given parameters."""
    try:
        g = game.create_game(
            player=payload.get("player", "anonymous"),
            symbols=payload.get("symbols", ["IWDA", "EIMI", "AGGH"]),
            days=payload.get("days", 63),
            start_capital=payload.get("start_capital", 100_000.0),
            challenge=payload.get("challenge", "beat_market"),
            seed=payload.get("seed", 42),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"game_id": g.game_id, "status": g.status.value}


# ---------- leaderboard (must come BEFORE /{game_id}) ----------
@game_router.get(
    "/leaderboard",
    response_model=list[LeaderboardEntry],
    summary="Get the game leaderboard",
)
async def leaderboard(game=Depends(get_game)):
    """Return the sorted leaderboard of completed games."""
    rows = game.leaderboard()
    return [LeaderboardEntry(**r) for r in rows]


# ---------- place order ----------
@game_router.post("/{game_id}/order", summary="Place a buy/sell order")
async def place_order(game_id: str, payload: dict, game=Depends(get_game)):
    """Place a buy or sell order in an active game."""
    try:
        order = game.place_order(
            game_id,
            symbol=payload["symbol"],
            side=payload["side"],
            quantity=float(payload["quantity"]),
            order_type=payload.get("order_type", "market"),
            limit_price=payload.get("limit_price"),
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))
    return {
        "order_id": order.order_id,
        "filled": order.filled,
        "fill_price": order.fill_price,
    }


# ---------- advance game by N days ----------
@game_router.post("/{game_id}/tick", summary="Advance the game by N days")
async def tick(game_id: str, days: int = 1, game=Depends(get_game)):
    """Advance the game by one or more trading days."""
    state = {}
    for _ in range(days):
        state = game.tick(game_id)
        if state["status"] != "active":
            break
    return state


# ---------- current state ----------
@game_router.get(
    "/{game_id}",
    response_model=GameState,
    summary="Get current game state",
)
async def state(game_id: str, game=Depends(get_game)):
    """Return the current state of a game session."""
    try:
        return GameState(**game.get_state(game_id))
    except KeyError:
        raise HTTPException(404, "game not found")


# ---------- game summary (end-game stats) ----------
@game_router.get(
    "/{game_id}/summary",
    summary="Get end-game summary with full stats",
)
async def game_summary(game_id: str, game=Depends(get_game)):
    """Return the end-game summary (total_return, cagr, max_drawdown, sharpe, sortino, num_trades, win_rate)."""
    try:
        s = game.get_state(game_id)
    except KeyError:
        raise HTTPException(404, "game not found")
    if not s.get("summary"):
        raise HTTPException(400, "game is still active — no summary yet")
    return s["summary"]


# ---------- equity curve (replay) ----------
@game_router.get(
    "/{game_id}/equity",
    summary="Get the full equity curve for replay",
)
async def equity_curve(game_id: str, game=Depends(get_game)):
    """Return the full equity curve (list of daily portfolio values) for replay."""
    try:
        s = game.get_state(game_id)
    except KeyError:
        raise HTTPException(404, "game not found")
    return {"game_id": game_id, "equity_curve": s.get("equity_curve", [])}


# ---------- websocket live feed ----------
@game_router.websocket("/ws/{game_id}")
async def game_ws(ws: WebSocket, game_id: str):
    """Live game state feed — sends state every 500ms while active."""
    game = get_game()
    await ws.accept()
    try:
        while True:
            state = game.get_state(game_id)
            await ws.send_json(state)
            if state["status"] != "active":
                break
            # non-blocking: try to receive an order (timeout 100ms)
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
                data = json.loads(msg)
                if data.get("action") == "order":
                    game.place_order(
                        game_id,
                        data["symbol"],
                        data["side"],
                        float(data["quantity"]),
                    )
                    # immediately tick once after order
                    game.tick(game_id)
            except (asyncio.TimeoutError, Exception):
                pass
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
