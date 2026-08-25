"""Multiplayer Lobby WebSocket + REST routes.

Prefix: /api/v1/lobby
WebSocket: /ws/lobby/{room_id}
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from packages.storage.state import get_game_engine
from packages.game.lobby import MultiplayerLobby

lobby_router = APIRouter(prefix="/api/v1/lobby", tags=["lobby"])

_lobby: MultiplayerLobby | None = None


def get_lobby() -> MultiplayerLobby:
    global _lobby
    if _lobby is None:
        _lobby = MultiplayerLobby(get_game_engine())
    return _lobby


# ---------- list / create rooms ----------
@lobby_router.get("/rooms")
async def list_rooms():
    return get_lobby().list_rooms()


@lobby_router.post("/rooms")
async def create_room(payload: dict):
    lobby = get_lobby()
    room = lobby.create_room(
        host=payload.get("host", "anonymous"),
        visibility=payload.get("visibility", "public"),
        password=payload.get("password"),
    )
    return {
        "room_id": room.room_id,
        "host": room.host,
        "visibility": room.visibility,
    }


@lobby_router.get("/rooms/{room_id}")
async def room_info(room_id: str):
    rooms = [
        r
        for r in get_lobby().list_rooms(include_private=True)
        if r["room_id"] == room_id
    ]
    if rooms:
        return rooms[0]
    raise HTTPException(404, "room not found")


@lobby_router.get("/rooms/{room_id}/chat")
async def chat_history(room_id: str):
    return {"room_id": room_id, "messages": get_lobby().get_chat_history(room_id)}


# ---------- WebSocket: lobby room ----------
@lobby_router.websocket("/ws/{room_id}")
async def lobby_ws(ws: WebSocket, room_id: str):
    """Real-time lobby WebSocket.

    Client first sends: {"action": "join", "player": "alice", "role": "player"}
    Then: {"action": "start", "symbols": [...], "days": 63, "seed": 42}
        or: {"action": "order", "symbol": "IWDA", "side": "buy", "quantity": 10}
        or: {"action": "tick"}
        or: {"action": "chat", "message": "hello"}
        or: {"action": "leave"}
    """
    lobby = get_lobby()
    await ws.accept()
    player: str | None = None
    try:
        # first message must be a join
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("action") != "join":
            await ws.close(code=4001, reason="first action must be 'join'")
            return
        player = msg.get("player", "anon")
        role = msg.get("role", "player")
        password = msg.get("password")
        room = lobby.join_room(room_id, player, ws, role=role, password=password)
        if room is None:
            await ws.close(
                code=4002, reason="room not found, already started, or wrong password"
            )
            return
        await ws.send_json(
            {"type": "joined", "room": room_id, "player": player, "role": role}
        )
        await lobby.broadcast_state(room_id, "player_joined", player=player, role=role)

        # message loop
        while True:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "start":
                ok = await lobby.start_game(room_id)
                await lobby.broadcast_state(room_id, "game_started", success=ok)

            elif action == "order":
                result = await lobby.place_order(
                    player,
                    msg.get("symbol", ""),
                    msg.get("side", "buy"),
                    float(msg.get("quantity", 0)),
                )
                if result:
                    await lobby.broadcast_state(
                        room_id, "order_filled", player=player, data=result
                    )

            elif action == "tick":
                await lobby.tick_room(room_id)
                await lobby.broadcast_state(room_id, "tick")

            elif action == "chat":
                message = msg.get("message", "")
                if message:
                    await lobby.broadcast_chat(room_id, player, message)

            elif action == "leave":
                lobby.leave_room(player)
                await lobby.broadcast_state(room_id, "player_left", player=player)
                break

    except asyncio.TimeoutError:
        # heartbeat — continue loop
        pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if player:
            lobby.leave_room(player)
