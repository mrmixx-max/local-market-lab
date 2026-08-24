"""Trading Game — paper-trading training engine.

A game session gives the player virtual capital. They place orders against
real (or synthetic) price data. The engine tracks positions, P&L, enforces
rules, and scores performance. Designed for learning — NOT for live trading.

Game loop:
  1. create_game(start_capital, symbols, days, seed, challenge_type)
  2. place_order(game_id, symbol, side, quantity, order_type)
  3. tick(game_id)  — advance one day, fill orders, update P&L
  4. get_state(game_id)  — current positions, cash, score
  5. end_game(game_id)  — final scoring + leaderboard entry
"""
from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from packages.storage.workspace import Workspace
from packages.marketdata.series import get_series


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class GameStatus(str, Enum):
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"
    ABANDONED = "abandoned"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    limit_price: float | None = None
    filled: bool = False
    fill_price: float | None = None
    fill_date: str | None = None


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pl(self, price: float) -> float:
        return self.quantity * (price - self.avg_cost)


@dataclass
class GameState:
    game_id: str
    player: str
    status: GameStatus
    start_capital: float
    cash: float
    day_index: int
    total_days: int
    symbols: list[str]
    challenge: str
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    score: float = 0.0
    seed: int = 42


# ---------- challenge definitions ----------
CHALLENGES = {
    "beat_market": {
        "name": "Beat the Market",
        "description": "Outperform an equal-weight buy-and-hold index over the game period.",
        "scoring": "total_return_vs_benchmark",
        "target": 0.0,  # beat by any amount
    },
    "low_volatility": {
        "name": "Steady Hand",
        "description": "Max annualized volatility under 8% while staying positive.",
        "scoring": "volatility_capped_return",
        "target": 0.08,
    },
    "max_drawdown": {
        "name": "Drawdown Control",
        "description": "Keep max drawdown under 5% over the full period.",
        "scoring": "drawdown_capped_return",
        "target": 0.05,
    },
    "sharpe_master": {
        "name": "Sharpe Master",
        "description": "Achieve the highest Sharpe ratio among all players.",
        "scoring": "sharpe_ratio",
        "target": 1.0,
    },
}


class TradingGame:
    """In-memory game engine. One instance manages all active games."""

    def __init__(self, ws: Workspace):
        self.ws = ws
        self.games: dict[str, GameState] = {}
        # pre-load price series for fast ticking
        self._price_cache: dict[str, list[tuple[str, float]]] = {}

    def _prices(self, symbol: str) -> list[tuple[str, float]]:
        if symbol not in self._price_cache:
            try:
                s = get_series(self.ws, symbol)
                self._price_cache[symbol] = [(b.date, b.close) for b in s.bars]
            except KeyError:
                self._price_cache[symbol] = []
        return self._price_cache[symbol]

    def create_game(
        self,
        player: str,
        symbols: list[str],
        days: int = 63,
        start_capital: float = 100_000.0,
        challenge: str = "beat_market",
        seed: int = 42,
    ) -> GameState:
        game_id = f"game_{uuid.uuid4().hex[:8]}"
        # slice a contiguous window from available prices
        # find common date range across all symbols
        common_dates = None
        for sym in symbols:
            dates = [d for d, _ in self._prices(sym)]
            common_dates = set(dates) if common_dates is None else common_dates & set(dates)
        common_dates = sorted(common_dates or [])
        if len(common_dates) < days + 1:
            raise ValueError(
                f"not enough common price data: {len(common_dates)} dates, need {days + 1}")
        rng = random.Random(seed)
        start_idx = rng.randint(0, len(common_dates) - days - 1)
        window = common_dates[start_idx:start_idx + days + 1]

        # store window in game state via history seed
        game = GameState(
            game_id=game_id,
            player=player,
            status=GameStatus.ACTIVE,
            start_capital=start_capital,
            cash=start_capital,
            day_index=0,
            total_days=days,
            symbols=symbols,
            challenge=challenge,
            seed=seed,
        )
        # record the window dates for ticking
        game.history = [
            {"date": d, "prices": {sym: self._price_for(sym, d) for sym in symbols}}
            for d in window
        ]
        self.games[game_id] = game
        return game

    def _price_for(self, symbol: str, date_iso: str) -> float:
        for d, p in self._prices(symbol):
            if d == date_iso:
                return p
        raise KeyError(f"no price for {symbol} on {date_iso}")

    def place_order(self, game_id: str, symbol: str, side: str,
                    quantity: float, order_type: str = "market",
                    limit_price: float | None = None) -> Order:
        game = self.games[game_id]
        if game.status != GameStatus.ACTIVE:
            raise ValueError("game is not active")
        if symbol not in game.symbols:
            raise ValueError(f"symbol {symbol!r} not in this game")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:6]}",
            symbol=symbol.upper(),
            side=OrderSide(side),
            quantity=quantity,
            order_type=OrderType(order_type),
            limit_price=limit_price,
        )
        game.orders.append(order)
        return order

    def tick(self, game_id: str) -> dict:
        """Advance one trading day. Fill orders, update positions, record snapshot."""
        game = self.games[game_id]
        if game.status != GameStatus.ACTIVE:
            return self.get_state(game_id)
        if game.day_index >= game.total_days:
            self._finalize(game_id)
            return self.get_state(game_id)

        snap = game.history[game.day_index]
        today = snap["date"]
        prices = snap["prices"]

        # fill pending orders at today's close (simplified: market = immediate, limit = check)
        for order in game.orders:
            if order.filled:
                continue
            px = prices[order.symbol]
            if order.order_type == OrderType.MARKET:
                self._fill(game, order, px, today)
            elif order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and px <= (order.limit_price or float("inf")):
                    self._fill(game, order, px, today)
                elif order.side == OrderSide.SELL and px >= (order.limit_price or 0):
                    self._fill(game, order, px, today)

        # compute portfolio value
        position_value = sum(
            pos.market_value(prices[sym])
            for sym, pos in game.positions.items()
        )
        total_value = game.cash + position_value
        snap["portfolio_value"] = round(total_value, 2)
        snap["cash"] = round(game.cash, 2)
        game.day_index += 1
        return self.get_state(game_id)

    def _fill(self, game: GameState, order: Order, price: float, date_iso: str):
        cost = order.quantity * price
        pos = game.positions.setdefault(order.symbol, Position(symbol=order.symbol))
        if order.side == OrderSide.BUY:
            if cost > game.cash:
                return  # insufficient funds — order stays pending (or could reject)
            game.cash -= cost
            # update avg cost
            total_qty = pos.quantity + order.quantity
            pos.avg_cost = (pos.avg_cost * pos.quantity + price * order.quantity) / total_qty
            pos.quantity = total_qty
        else:  # SELL
            if order.quantity > pos.quantity:
                return  # insufficient position
            game.cash += cost
            pos.quantity -= order.quantity
            if pos.quantity <= 1e-9:
                pos.avg_cost = 0.0
        order.filled = True
        order.fill_price = price
        order.fill_date = date_iso

    def get_state(self, game_id: str) -> dict:
        game = self.games[game_id]
        if game.day_index == 0:
            current_prices = game.history[0]["prices"] if game.history else {}
            today = game.history[0]["date"] if game.history else None
        else:
            snap = game.history[game.day_index - 1]
            current_prices = snap["prices"]
            today = snap["date"]

        positions_out = {}
        total_pos_value = 0.0
        for sym, pos in game.positions.items():
            px = current_prices.get(sym, 0)
            mv = pos.market_value(px)
            total_pos_value += mv
            positions_out[sym] = {
                "quantity": round(pos.quantity, 6),
                "avg_cost": round(pos.avg_cost, 4),
                "last_price": px,
                "market_value": round(mv, 2),
                "unrealized_pl": round(pos.unrealized_pl(px), 2),
            }
        total_value = game.cash + total_pos_value
        pending = [o for o in game.orders if not o.filled]
        return {
            "game_id": game.game_id,
            "player": game.player,
            "status": game.status.value,
            "day": f"{game.day_index}/{game.total_days}",
            "date": today,
            "cash": round(game.cash, 2),
            "positions_value": round(total_pos_value, 2),
            "total_value": round(total_value, 2),
            "return_pct": round((total_value / game.start_capital - 1) * 100, 2),
            "positions": positions_out,
            "pending_orders": len(pending),
            "filled_orders": len(game.orders) - len(pending),
            "challenge": game.challenge,
        }

    def _finalize(self, game_id: str):
        game = self.games[game_id]
        game.status = GameStatus.WON if self._score(game) > 0 else GameStatus.LOST
        game.score = self._score(game)

    def _score(self, game: GameState) -> float:
        """Compute final score based on challenge type."""
        if not game.history:
            return 0.0
        values = [h.get("portfolio_value", game.start_capital) for h in game.history]
        if len(values) < 2:
            return 0.0
        rets = [b / a - 1 for a, b in zip(values, values[1:])]
        total_ret = values[-1] / values[0] - 1
        vol = (sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / max(1, len(rets) - 1)) ** 0.5 * (252 ** 0.5)
        peak = values[0]
        mdd = 0.0
        for v in values:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak)
        sharpe = (sum(rets) / len(rets) * 252) / (vol or 1.0)

        bench = self._benchmark_return(game)
        challenge = game.challenge
        if challenge == "beat_market":
            return round((total_ret - bench) * 100, 2)
        elif challenge == "low_volatility":
            return round(total_ret * 100, 2) if vol <= CHALLENGES["low_volatility"]["target"] else round(total_ret * 50, 2)
        elif challenge == "max_drawdown":
            return round(total_ret * 100, 2) if mdd <= CHALLENGES["max_drawdown"]["target"] else round(total_ret * 50, 2)
        elif challenge == "sharpe_master":
            return round(sharpe, 3)
        return round(total_ret * 100, 2)

    def _benchmark_return(self, game: GameState) -> float:
        """Equal-weight buy-and-hold return over the game window."""
        if not game.history:
            return 0.0
        first = game.history[0]["prices"]
        last = game.history[min(game.day_index, len(game.history) - 1)]["prices"] if game.day_index > 0 else first
        bench_ret = sum(last[s] / first[s] - 1 for s in game.symbols) / len(game.symbols)
        return bench_ret

    def leaderboard(self) -> list[dict]:
        rows = []
        for g in self.games.values():
            if g.status in (GameStatus.WON, GameStatus.LOST):
                rows.append({
                    "player": g.player,
                    "challenge": g.challenge,
                    "score": g.score,
                    "status": g.status.value,
                    "days": g.total_days,
                })
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows
