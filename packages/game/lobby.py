"""Multiplayer Lobby — shared game rooms with real-time WebSocket sync.

A lobby lets multiple players join a room. All game state changes are
broadcast to every connected player in real-time. Each player runs their
own paper-trading portfolio within the shared game window.

Protocol (JSON over WS):
  Client → Server:
    {"action": "join", "room": "abc", "player": "alice"}
    {"action": "start", "symbols": ["IWDA","EIMI"], "days": 63, "seed": 42}
    {"action": "order", "symbol": "IWDA", "side": "buy", "quantity": 10}
    {"action": "tick"}
    {"action": "leave"}

  Server → Client (broadcast):
    {"type": "state", "room": "...", "players": [...], "game": {...}}
    {"type": "event", "event": "player_joined", "player": "..."}
    {"type": "event", "event": "order_filled", "player": "...", "data": {...}}
    {"type": "event", "event": "game_over", "winner": "...", "scores": {...}}
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum

from packages.game.engine import TradingGame, GameStatus


class LobbyEventType(str, Enum):
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    ORDER_FILLED = "order_filled"
    GAME_STARTED = "game_started"
    GAME_OVER = "game_over"
    TICK = "tick"
    STATE = "state"


@dataclass
class PlayerSession:
    player: str
    ws: object  # WebSocket
    game_id: str | None = None
    cash: float = 100_000.0
    positions: dict = field(default_factory=dict)
    score: float = 0.0
    ready: bool = False


@dataclass
class Room:
    room_id: str
    host: str
    players: dict[str, PlayerSession] = field(default_factory=dict)
    game_id: str | None = None
    symbols: list[str] = field(default_factory=list)
    days: int = 63
    seed: int = 42
    started: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class MultiplayerLobby:
    """In-memory lobby manager. One instance serves all rooms."""

    def __init__(self, game_engine: TradingGame):
        self.engine = game_engine
        self.rooms: dict[str, Room] = {}
        self._player_room: dict[str, str] = {}  # player → room_id

    def list_rooms(self) -> list[dict]:
        return [
            {
                "room_id": r.room_id,
                "host": r.host,
                "players": list(r.players.keys()),
                "started": r.started,
                "symbols": r.symbols,
                "days": r.days,
            }
            for r in self.rooms.values()
        ]

    def create_room(self, host: str) -> Room:
        room_id = f"room_{uuid.uuid4().hex[:6]}"
        room = Room(room_id=room_id, host=host)
        self.rooms[room_id] = room
        return room

    def join_room(self, room_id: str, player: str, ws) -> Room | None:
        room = self.rooms.get(room_id)
        if room is None or room.started:
            return None
        if player in room.players:
            # update ws on reconnect
            room.players[player].ws = ws
        else:
            room.players[player] = PlayerSession(player=player, ws=ws)
        self._player_room[player] = room_id
        return room

    def leave_room(self, player: str) -> Room | None:
        room_id = self._player_room.pop(player, None)
        if room_id is None:
            return None
        room = self.rooms.get(room_id)
        if room and player in room.players:
            del room.players[player]
            if not room.players:
                del self.rooms[room_id]
            elif room.host == player:
                room.host = next(iter(room.players))
        return room

    async def start_game(self, room_id: str) -> bool:
        async with self._get_room_lock(room_id) as room:
            if room is None or room.started or not room.players:
                return False
            room.started = True
            game = self.engine.create_game(
                player=room.host,
                symbols=room.symbols or ["IWDA", "EIMI", "AGGH"],
                days=room.days,
                start_capital=100_000.0,
                seed=room.seed,
            )
            room.game_id = game.game_id
            # give each player their own sub-game (same window, tracked separately)
            for pname, ps in room.players.items():
                pg = self.engine.create_game(
                    player=pname,
                    symbols=game.symbols,
                    days=room.days,
                    start_capital=100_000.0,
                    seed=room.seed,
                )
                ps.game_id = pg.game_id
            return True

    def _get_room_lock(self, room_id: str):
        room = self.rooms.get(room_id)
        if room is None:
            raise KeyError(f"room {room_id!r} not found")
        return room.lock

    async def place_order(self, player: str, symbol: str, side: str, quantity: float) -> dict | None:
        room_id = self._player_room.get(player)
        if room_id is None:
            return None
        room = self.rooms.get(room_id)
        if room is None or not room.started:
            return None
        ps = room.players.get(player)
        if ps is None or ps.game_id is None:
            return None
        try:
            order = self.engine.place_order(ps.game_id, symbol, side, quantity)
            return {"order_id": order.order_id, "filled": order.filled}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    async def tick_room(self, room_id: str) -> dict | None:
        """Advance all games in the room by one day."""
        room = self.rooms.get(room_id)
        if room is None or not room.started:
            return None
        results = {}
        for pname, ps in room.players.items():
            if ps.game_id:
                results[pname] = self.engine.tick(ps.game_id)
        return results

    async def broadcast_state(self, room_id: str, event_type: str, **extra):
        """Push current room state to all connected WebSocket clients."""
        room = self.rooms.get(room_id)
        if room is None:
            return
        # build per-player state
        players_out = {}
        for pname, ps in room.players.items():
            if ps.game_id:
                gs = self.engine.get_state(ps.game_id)
                players_out[pname] = {
                    "cash": gs["cash"],
                    "total_value": gs["total_value"],
                    "return_pct": gs["return_pct"],
                    "positions": gs["positions"],
                    "filled_orders": gs["filled_orders"],
                    "status": gs["status"],
                }
            else:
                players_out[pname] = {"status": "waiting"}
        payload = {
            "type": event_type,
            "room": room_id,
            "players": players_out,
            "game_id": room.game_id,
            **extra,
        }
        disconnected = []
        for pname, ps in room.players.items():
            try:
                await ps.ws.send_json(payload)
            except Exception:
                disconnected.append(pname)
        for pname in disconnected:
            self.leave_room(pname)

    def get_player_room(self, player: str) -> Room | None:
        room_id = self._player_room.get(player)
        return self.rooms.get(room_id) if room_id else None
