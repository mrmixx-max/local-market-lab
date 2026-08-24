"""Trading Game engine tests."""
import pytest

from packages.game.engine import (CHALLENGES, TradingGame, GameStatus)
from packages.ingest.fixtures import load_demo
from packages.storage.workspace import Workspace


@pytest.fixture
def ws(tmp_path):
    w = Workspace(str(tmp_path / "test.db"))
    load_demo(w)
    return w


@pytest.fixture
def engine(ws):
    return TradingGame(ws)


class TestChallenges:
    def test_all_present(self):
        assert "beat_market" in CHALLENGES
        assert "low_volatility" in CHALLENGES
        assert "max_drawdown" in CHALLENGES
        assert "sharpe_master" in CHALLENGES


class TestGameLifecycle:
    def test_create_game(self, engine):
        g = engine.create_game("alice", ["IWDA", "EIMI"], days=10, seed=1)
        assert g.status == GameStatus.ACTIVE
        assert g.start_capital == 100_000.0
        assert g.day_index == 0

    def test_buy_order_fills_and_consumes_cash(self, engine):
        g = engine.create_game("bob", ["IWDA"], days=5, seed=2)
        engine.place_order(g.game_id, "IWDA", "buy", 100)
        state = engine.tick(g.game_id)
        assert state["status"] == "active"
        assert state["filled_orders"] == 1
        assert state["cash"] < 100_000.0
        assert "IWDA" in state["positions"]

    def test_sell_order(self, engine):
        g = engine.create_game("c", ["IWDA"], days=5, seed=3)
        engine.place_order(g.game_id, "IWDA", "buy", 50)
        engine.tick(g.game_id)
        pre_sell_pos = engine.get_state(g.game_id)["positions"]["IWDA"]["quantity"]
        engine.place_order(g.game_id, "IWDA", "sell", 20)
        engine.tick(g.game_id)
        post_sell_pos = engine.get_state(g.game_id)["positions"]["IWDA"]["quantity"]
        assert abs(post_sell_pos - (pre_sell_pos - 20)) < 1e-9

    def test_insufficient_funds_no_crash(self, engine):
        g = engine.create_game("d", ["IWDA"], days=5, seed=4)
        engine.place_order(g.game_id, "IWDA", "buy", 1_000_000)  # way too many
        state = engine.tick(g.game_id)
        assert state["status"] == "active"

    def test_game_completes_after_total_days(self, engine):
        g = engine.create_game("e", ["IWDA"], days=2, seed=5)
        engine.place_order(g.game_id, "IWDA", "buy", 10)
        for _ in range(4):
            state = engine.tick(g.game_id)
            if state["status"] != "active":
                break
        assert state["status"] in ("won", "lost")

    def test_determinism_same_seed(self, engine):
        g1 = engine.create_game("f", ["IWDA", "EIMI"], days=5, seed=99)
        g2 = engine.create_game("g", ["IWDA", "EIMI"], days=5, seed=99)
        # same starting window, same starting date
        assert g1.history[0]["date"] == g2.history[0]["date"]
        assert g1.history[0]["prices"] == g2.history[0]["prices"]


class TestLeaderboard:
    def test_empty_on_fresh_engine(self, engine):
        assert engine.leaderboard() == []

    def test_leaderboard_populates_on_game_end(self, engine):
        g = engine.create_game("h", ["IWDA"], days=2, seed=6)
        engine.place_order(g.game_id, "IWDA", "buy", 10)
        for _ in range(4):
            state = engine.tick(g.game_id)
            if state["status"] != "active":
                break
        lb = engine.leaderboard()
        assert len(lb) == 1
        assert lb[0]["player"] == "h"
