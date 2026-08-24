"""Trading Game — paper-trading engine. Players get virtual capital, place orders
against real price data, and are scored on performance. For learning only.
Game loop: create_game → place_order → tick → get_state → end_game."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
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
    order_id: str; symbol: str; side: OrderSide; quantity: float
    order_type: OrderType; limit_price: float | None = None
    filled: bool = False; fill_price: float | None = None; fill_date: str | None = None


@dataclass
class Position:
    symbol: str; quantity: float = 0.0; avg_cost: float = 0.0

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pl(self, price: float) -> float:
        return self.quantity * (price - self.avg_cost)


@dataclass
class GameState:
    game_id: str; player: str; status: GameStatus; start_capital: float
    cash: float; day_index: int; total_days: int; symbols: list[str]; challenge: str
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    score: float = 0.0; seed: int = 42


CHALLENGES = {
    "beat_market": {"name": "Beat the Market", "description": "Outperform an equal-weight buy-and-hold index.",
                    "scoring": "total_return_vs_benchmark", "target": 0.0},
    "low_volatility": {"name": "Steady Hand", "description": "Max annualized volatility under 8% while staying positive.",
                       "scoring": "volatility_capped_return", "target": 0.08},
    "max_drawdown": {"name": "Drawdown Control", "description": "Keep max drawdown under 5% over the full period.",
                     "scoring": "drawdown_capped_return", "target": 0.05},
    "sharpe_master": {"name": "Sharpe Master", "description": "Achieve the highest Sharpe ratio among all players.",
                      "scoring": "sharpe_ratio", "target": 1.0},
    "max_sharpe": {"name": "Max Sharpe", "description": "Maximize your Sharpe ratio.",
                   "scoring": "sharpe_ratio", "target": 1.5},
    "min_volatility": {"name": "Min Volatility", "description": "Lowest annualized volatility while breaking even.",
                       "scoring": "min_volatility", "target": 0.05},
    "beat_benchmark_by_5pct": {"name": "Beat by 5%",
                                "description": "Outperform the benchmark by at least 5 percentage points.",
                                "scoring": "beat_benchmark_by_5pct", "target": 0.05},
}


class TradingGame:
    """In-memory game engine. One instance manages all active games."""

    def __init__(self, ws: Workspace):
        self.ws = ws
        self.games: dict[str, GameState] = {}
        self._price_cache: dict[str, list[tuple[str, float]]] = {}

    def _prices(self, symbol: str) -> list[tuple[str, float]]:
        if symbol not in self._price_cache:
            try:
                s = get_series(self.ws, symbol)
                self._price_cache[symbol] = [(b.date, b.close) for b in s.bars]
            except KeyError:
                self._price_cache[symbol] = []
        return self._price_cache[symbol]

    def create_game(self, player: str, symbols: list[str], days: int = 63,
                    start_capital: float = 100_000.0, challenge: str = "beat_market",
                    seed: int = 42) -> GameState:
        game_id = f"game_{uuid.uuid4().hex[:8]}"
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
        game = GameState(
            game_id=game_id, player=player, status=GameStatus.ACTIVE,
            start_capital=start_capital, cash=start_capital, day_index=0,
            total_days=days, symbols=symbols, challenge=challenge, seed=seed)
        game.history = [
            {"date": d, "prices": {sym: self._price_for(sym, d) for sym in symbols}}
            for d in window]
        game.equity_curve = [start_capital]
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
        if game.day_index >= game.total_days:
            raise ValueError("game has ended — no more trading days")
        if symbol not in game.symbols:
            raise ValueError(f"symbol {symbol!r} not in this game")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:6]}", symbol=symbol.upper(),
            side=OrderSide(side), quantity=quantity,
            order_type=OrderType(order_type), limit_price=limit_price)
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
        position_value = sum(
            pos.market_value(prices[sym]) for sym, pos in game.positions.items())
        total_value = game.cash + position_value
        snap["portfolio_value"] = round(total_value, 2)
        snap["cash"] = round(game.cash, 2)
        game.equity_curve.append(round(total_value, 2))
        game.day_index += 1
        return self.get_state(game_id)

    def _fill(self, game: GameState, order: Order, price: float, date_iso: str):
        cost = order.quantity * price
        pos = game.positions.setdefault(order.symbol, Position(symbol=order.symbol))
        if order.side == OrderSide.BUY:
            if cost > game.cash:
                return
            game.cash -= cost
            total_qty = pos.quantity + order.quantity
            pos.avg_cost = (pos.avg_cost * pos.quantity + price * order.quantity) / total_qty
            pos.quantity = total_qty
        else:
            if order.quantity > pos.quantity:
                return
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
            cur = game.history[0]["prices"] if game.history else {}
            today = game.history[0]["date"] if game.history else None
        else:
            snap = game.history[game.day_index - 1]
            cur, today = snap["prices"], snap["date"]
        positions_out = {}
        total_pos_value = 0.0
        for sym, pos in game.positions.items():
            px = cur.get(sym, 0)
            mv = pos.market_value(px)
            total_pos_value += mv
            positions_out[sym] = {
                "quantity": round(pos.quantity, 6), "avg_cost": round(pos.avg_cost, 4),
                "last_price": px, "market_value": round(mv, 2),
                "unrealized_pl": round(pos.unrealized_pl(px), 2)}
        total_value = game.cash + total_pos_value
        pending = [o for o in game.orders if not o.filled]
        return {
            "game_id": game.game_id, "player": game.player,
            "status": game.status.value, "day": f"{game.day_index}/{game.total_days}",
            "date": today, "cash": round(game.cash, 2),
            "positions_value": round(total_pos_value, 2),
            "total_value": round(total_value, 2),
            "return_pct": round((total_value / game.start_capital - 1) * 100, 2),
            "positions": positions_out, "pending_orders": len(pending),
            "filled_orders": len(game.orders) - len(pending),
            "challenge": game.challenge, "equity_curve": game.equity_curve,
            "summary": game.summary if game.summary else None}

    def _finalize(self, game_id: str):
        game = self.games[game_id]
        game.score = self._score(game)
        game.status = GameStatus.WON if game.score > 0 else GameStatus.LOST
        game.summary = self._compute_summary(game)

    def _equity(self, game: GameState) -> list[float]:
        return game.equity_curve if len(game.equity_curve) > 1 else (
            [game.start_capital] + [h.get("portfolio_value", game.start_capital)
                                    for h in game.history])

    def _stats(self, game: GameState) -> tuple:
        """Return (total_ret, vol, mdd, sharpe, bench)."""
        values = self._equity(game)
        if len(values) < 2:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        rets = [b / a - 1 for a, b in zip(values, values[1:])]
        total_ret = values[-1] / values[0] - 1
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / max(1, len(rets) - 1)
        vol = var ** 0.5 * (252 ** 0.5)
        peak, mdd = values[0], 0.0
        for v in values:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak)
        sharpe = (mean_r * 252) / (vol or 1.0)
        bench = self._benchmark_return(game)
        return total_ret, vol, mdd, sharpe, bench

    def _compute_summary(self, game: GameState) -> dict:
        """Produce end-game summary: {total_return, cagr, max_drawdown, sharpe, sortino, num_trades, win_rate}."""
        values = self._equity(game)
        if len(values) < 2:
            return {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
                    "sharpe": 0.0, "sortino": 0.0, "num_trades": 0, "win_rate": 0.0}
        rets = [b / a - 1 for a, b in zip(values, values[1:])]
        n = len(rets)
        total_ret = values[-1] / values[0] - 1
        years = n / 252.0
        cagr = ((values[-1] / values[0]) ** (1 / years) - 1) if years > 0 else 0.0
        mean_r = sum(rets) / n
        var = sum((r - mean_r) ** 2 for r in rets) / max(1, n - 1)
        vol = var ** 0.5 * (252 ** 0.5)
        neg = [r for r in rets if r < 0]
        down_vol = (sum(r ** 2 for r in neg) / max(1, n - 1)) ** 0.5 * (252 ** 0.5)
        sharpe = (mean_r * 252) / (vol or 1.0)
        sortino = (mean_r * 252) / (down_vol or 1.0)
        peak, mdd = values[0], 0.0
        for v in values:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak)
        filled = [o for o in game.orders if o.filled]
        num_trades = len(filled)
        wins = [o for o in filled if o.side == OrderSide.SELL and o.fill_price]
        win_rate = len(wins) / num_trades if num_trades > 0 else 0.0
        return {
            "total_return": round(total_ret * 100, 2), "cagr": round(cagr * 100, 2),
            "max_drawdown": round(mdd * 100, 2), "sharpe": round(sharpe, 3),
            "sortino": round(sortino, 3), "num_trades": num_trades,
            "win_rate": round(win_rate * 100, 2)}

    def _score(self, game: GameState) -> float:
        """Compute final score based on challenge type."""
        if not game.history:
            return 0.0
        total_ret, vol, mdd, sharpe, bench = self._stats(game)
        ch = game.challenge
        if ch == "beat_market":
            return round((total_ret - bench) * 100, 2)
        elif ch == "low_volatility":
            return round(total_ret * 100, 2) if vol <= CHALLENGES["low_volatility"]["target"] else round(total_ret * 50, 2)
        elif ch == "max_drawdown":
            return round(total_ret * 100, 2) if mdd <= CHALLENGES["max_drawdown"]["target"] else round(total_ret * 50, 2)
        elif ch in ("sharpe_master", "max_sharpe"):
            return round(sharpe, 3)
        elif ch == "min_volatility":
            return round((1.0 / (vol or 1.0)) * 100, 2) if total_ret >= 0 else round(total_ret * 100, 2)
        elif ch == "beat_benchmark_by_5pct":
            return round((total_ret - bench - CHALLENGES["beat_benchmark_by_5pct"]["target"]) * 100, 2)
        return round(total_ret * 100, 2)

    def _benchmark_return(self, game: GameState) -> float:
        """Equal-weight buy-and-hold return over the game window."""
        if not game.history:
            return 0.0
        first = game.history[0]["prices"]
        last_idx = min(game.day_index, len(game.history) - 1)
        last = game.history[last_idx]["prices"] if game.day_index > 0 else first
        return sum(last[s] / first[s] - 1 for s in game.symbols) / len(game.symbols)

    def leaderboard(self) -> list[dict]:
        rows = []
        for g in self.games.values():
            if g.status in (GameStatus.WON, GameStatus.LOST):
                rows.append({
                    "player": g.player, "challenge": g.challenge,
                    "score": g.score, "status": g.status.value,
                    "days": g.total_days, "summary": g.summary})
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows
