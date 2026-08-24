"""Trading Game REST + WebSocket routes.

Prefix: /api/v1/game
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from packages.storage.state import get_ws, get_game_engine
from packages.game.engine import CHALLENGES

game_router = APIRouter(prefix="/api/v1/game", tags=["game"])


# ---------- challenges catalog ----------
@game_router.get("/challenges")
async def challenges():
    return CHALLENGES


# ---------- create a game ----------
@game_router.post("/create")
async def create_game(payload: dict):
    """Create a paper-trading game session.

    Body: {
      "player": "alice",
      "symbols": ["IWDA","EIMI"],
      "days": 63,
      "start_capital": 100000,
      "challenge": "beat_market",
      "seed": 42
    }
    """
    try:
        g = get_game_engine().create_game(
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
@game_router.get("/leaderboard")
async def leaderboard():
    return get_game_engine().leaderboard()


# ---------- place order ----------
@game_router.post("/{game_id}/order")
async def place_order(game_id: str, payload: dict):
    """Place an order: {symbol, side, quantity, order_type?, limit_price?}"""
    try:
        order = get_game_engine().place_order(
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
@game_router.post("/{game_id}/tick")
async def tick(game_id: str, days: int = 1):
    for _ in range(days):
        state = get_game_engine().tick(game_id)
        if state["status"] != "active":
            break
    return state


# ---------- current state ----------
@game_router.get("/{game_id}")
async def state(game_id: str):
    try:
        return get_game_engine().get_state(game_id)
    except KeyError:
        raise HTTPException(404, "game not found")


# ---------- websocket live feed ----------
@game_router.websocket("/ws/{game_id}")
async def game_ws(ws: WebSocket, game_id: str):
    """Pushes game state every 500ms while the game is active.

    The client can send orders as JSON while the game ticks:
      {"action": "order", "symbol": "IWDA", "side": "buy", "quantity": 10}
    """
    await ws.accept()
    try:
        while True:
            state = get_game_engine().get_state(game_id)
            await ws.send_json(state)
            if state["status"] != "active":
                break
            # non-blocking: try to receive an order (timeout 100ms)
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
                data = json.loads(msg)
                if data.get("action") == "order":
                    get_game_engine().place_order(
                        game_id,
                        data["symbol"],
                        data["side"],
                        float(data["quantity"]),
                    )
                    # immediately tick once after order
                    get_game_engine().tick(game_id)
            except (asyncio.TimeoutError, Exception):
                pass
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
