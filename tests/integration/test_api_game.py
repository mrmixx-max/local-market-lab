"""Integration tests for the Game API using FastAPI TestClient."""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
import packages.storage.state as state_mod
from packages.storage.workspace import Workspace
from packages.ingest.fixtures import load_demo


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch, tmp_path):
    """Reset global singletons and use a fresh temp DB for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("LML_DB", db_path)

    # Create workspace with thread-safe SQLite (TestClient runs in different thread)
    ws = Workspace(db_path)
    ws.conn = sqlite3.connect(db_path, check_same_thread=False)
    ws.conn.row_factory = sqlite3.Row
    load_demo(ws)

    # Reset singletons
    state_mod._workspace = ws
    state_mod._game_engine = None
    # Force game engine to use this workspace
    from packages.game.engine import TradingGame
    state_mod._game_engine = TradingGame(ws)

    yield
    # Cleanup
    try:
        ws.conn.close()
    except Exception:
        pass
    state_mod._workspace = None
    state_mod._game_engine = None


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "instruments" in data

    def test_health_has_all_fields(self, client):
        """Health response should include all status fields."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        # All expected fields present
        assert "db_connected" in data
        assert "uptime_seconds" in data
        assert "ollama_available" in data
        assert "yahoo_available" in data
        assert "ollama_error" in data or data["ollama_available"]
        assert "yahoo_error" in data or data["yahoo_available"]
        assert data["version"] == "0.9.1"

    def test_health_ollama_status(self, client):
        """Health endpoint should correctly report Ollama availability."""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'{"models": []}'

        with patch("apps.api.main.urllib.request.urlopen", return_value=mock_resp):
            response = client.get("/api/v1/health")
        data = response.json()
        assert data["ollama_available"] is True
        assert data["ollama_error"] is None

    def test_health_ollama_unavailable(self, client):
        """Health endpoint should report Ollama error when unreachable."""
        from unittest.mock import patch
        with patch("apps.api.main.urllib.request.urlopen", side_effect=Exception("connection refused")):
            response = client.get("/api/v1/health")
        data = response.json()
        # When Ollama is unreachable, ollama_available should be False
        assert data["ollama_available"] is False
        assert data["ollama_error"] is not None


class TestGameChallenges:
    def test_challenges_list(self, client):
        response = client.get("/api/v1/game/challenges")
        assert response.status_code == 200
        data = response.json()
        assert "beat_market" in data
        assert "low_volatility" in data
        assert "max_drawdown" in data
        assert "sharpe_master" in data


class TestGameLifecycle:
    def test_create_game(self, client):
        response = client.post("/api/v1/game/create", json={
            "player": "alice",
            "symbols": ["IWDA", "EIMI"],
            "days": 10,
            "start_capital": 100000,
            "challenge": "beat_market",
            "seed": 42,
        })
        assert response.status_code == 200
        data = response.json()
        assert "game_id" in data
        assert data["status"] == "active"

    def test_create_game_missing_data_400(self, client):
        """Request with insufficient data should return 400."""
        response = client.post("/api/v1/game/create", json={
            "player": "bob",
            "symbols": ["NONEXISTENT_XYZ"],
            "days": 99999,
            "seed": 1,
        })
        assert response.status_code == 400

    def test_get_state(self, client):
        create_resp = client.post("/api/v1/game/create", json={
            "player": "carol",
            "symbols": ["IWDA"],
            "days": 5,
            "seed": 7,
        })
        game_id = create_resp.json()["game_id"]
        state_resp = client.get(f"/api/v1/game/{game_id}")
        assert state_resp.status_code == 200
        state = state_resp.json()
        assert state["player"] == "carol"
        assert state["status"] == "active"
        assert "cash" in state

    def test_get_state_not_found(self, client):
        response = client.get("/api/v1/game/nonexistent_id")
        assert response.status_code == 404

    def test_place_order(self, client):
        create_resp = client.post("/api/v1/game/create", json={
            "player": "dave",
            "symbols": ["IWDA"],
            "days": 5,
            "seed": 3,
        })
        game_id = create_resp.json()["game_id"]
        order_resp = client.post(f"/api/v1/game/{game_id}/order", json={
            "symbol": "IWDA",
            "side": "buy",
            "quantity": 10,
        })
        assert order_resp.status_code == 200
        data = order_resp.json()
        assert "order_id" in data

    def test_place_order_invalid_symbol(self, client):
        create_resp = client.post("/api/v1/game/create", json={
            "player": "eve",
            "symbols": ["IWDA"],
            "days": 5,
            "seed": 4,
        })
        game_id = create_resp.json()["game_id"]
        order_resp = client.post(f"/api/v1/game/{game_id}/order", json={
            "symbol": "INVALID",
            "side": "buy",
            "quantity": 10,
        })
        assert order_resp.status_code == 400

    def test_tick_advances_game(self, client):
        create_resp = client.post("/api/v1/game/create", json={
            "player": "frank",
            "symbols": ["IWDA"],
            "days": 5,
            "seed": 5,
        })
        game_id = create_resp.json()["game_id"]
        # place an order first
        client.post(f"/api/v1/game/{game_id}/order", json={
            "symbol": "IWDA", "side": "buy", "quantity": 10,
        })
        tick_resp = client.post(f"/api/v1/game/{game_id}/tick", params={"days": 1})
        assert tick_resp.status_code == 200
        state = tick_resp.json()
        assert state["day"] == "1/5"

    def test_leaderboard(self, client):
        response = client.get("/api/v1/game/leaderboard")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestMarketEndpoints:
    def test_symbols(self, client):
        response = client.get("/api/v1/market/symbols")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0  # demo data loaded

    def test_prices(self, client):
        response = client.get("/api/v1/market/prices/IWDA")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "IWDA"
        assert "bars" in data


class TestYahooEndpoint:
    def test_yahoo_returns_json(self, client):
        """Yahoo endpoint should return a JSON response (may be error if offline)."""
        response = client.get("/api/v1/market/yahoo/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Either we got data, or we got an error dict
        assert "symbol" in data or "error" in data

    def test_yahoo_query2_fallback(self, client):
        """Yahoo endpoint should fall back to query2 when query1 fails."""
        from unittest.mock import patch, MagicMock
        import json as _json

        # Mock query1 to fail, query2 to succeed
        def mock_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, 'full_url') else str(req)
            if "query1" in url:
                raise Exception("query1 blocked")
            # query2 succeeds
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock.read.return_value = _json.dumps({
                "chart": {"result": [{"meta": {"regularMarketPrice": 150.0, "chartPreviousClose": 145.0, "currency": "USD"}}]}
            }).encode()
            return mock

        with patch("apps.api.main.urllib.request.urlopen", side_effect=mock_urlopen):
            response = client.get("/api/v1/market/yahoo/TEST")

        assert response.status_code == 200
        data = response.json()
        assert data.get("symbol") == "TEST"
        assert data.get("price") == 150.0
        assert "query2" in data.get("source", "")

    def test_yahoo_user_agent_header(self, client):
        """Yahoo endpoint should send a realistic browser User-Agent."""
        from unittest.mock import patch, MagicMock
        import json as _json

        captured_req = {}
        def mock_urlopen(req, timeout=None):
            captured_req['headers'] = dict(req.headers) if hasattr(req, 'headers') else {}
            captured_req['url'] = req.full_url if hasattr(req, 'full_url') else str(req)
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock.read.return_value = _json.dumps({
                "chart": {"result": [{"meta": {"regularMarketPrice": 100.0}}]}
            }).encode()
            return mock

        with patch("apps.api.main.urllib.request.urlopen", side_effect=mock_urlopen):
            client.get("/api/v1/market/yahoo/AAPL")

        # Check that a browser-like User-Agent was sent
        headers = captured_req.get('headers', {})
        ua = headers.get('User-agent', headers.get('User-Agent', ''))
        assert "Mozilla" in ua or "Chrome" in ua or "Browser" in ua

    def test_yahoo_timeout_configurable(self, client):
        """Yahoo endpoint should respect LML_YAHOO_TIMEOUT env var."""
        from unittest.mock import patch, MagicMock
        import os

        with patch.dict(os.environ, {"LML_YAHOO_TIMEOUT": "3"}):
            with patch("apps.api.main.urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.__enter__ = MagicMock(return_value=mock_resp)
                mock_resp.__exit__ = MagicMock(return_value=False)
                mock_resp.read.return_value = b'{"chart": {"result": [{"meta": {"regularMarketPrice": 100.0}}]}}'
                mock_urlopen.return_value = mock_resp

                response = client.get("/api/v1/market/yahoo/AAPL")
                assert response.status_code == 200
                # Verify timeout was passed
                call_kwargs = mock_urlopen.call_args
                assert call_kwargs[1].get("timeout") == 3 or (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == 3)


class TestOllamaEndpoints:
    """Tests for Ollama bridge routes using mocked HTTP."""

    def test_ollama_chat_returns_content(self, client):
        """Chat route should return content when Ollama responds."""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'{"message": {"content": "Hello there!"}}'

        with patch("apps.api.ollama_routes.urllib.request.urlopen", return_value=mock_resp):
            response = client.post("/api/v1/ollama/chat", json={
                "model": "llama3.1",
                "messages": [{"role": "user", "content": "Hi"}],
            })

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Hello there!"
        assert data["model"] == "llama3.1"

    def test_ollama_chat_response_has_content_not_response(self, client):
        """Chat route must return 'content' field, NOT 'response' field."""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'{"message": {"content": "Test answer"}}'

        with patch("apps.api.ollama_routes.urllib.request.urlopen", return_value=mock_resp):
            response = client.post("/api/v1/ollama/chat", json={
                "model": "llama3.1",
                "messages": [{"role": "user", "content": "Hi"}],
            })

        data = response.json()
        # Must have 'content'
        assert "content" in data
        assert data["content"] == "Test answer"
        # Must NOT have 'response' (old incorrect field name)
        assert "response" not in data

    def test_ollama_chat_with_system_prompt(self, client):
        """Chat route should prepend system message when provided."""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'{"message": {"content": "System acknowledged"}}'

        with patch("apps.api.ollama_routes.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            response = client.post("/api/v1/ollama/chat", json={
                "model": "llama3.1",
                "messages": [{"role": "user", "content": "Hi"}],
                "system": "You are a trading coach.",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "System acknowledged"
        # Verify system message was sent in request body
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        import json
        body = json.loads(req.data)
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "You are a trading coach."

    def test_ollama_chat_missing_model_400(self, client):
        response = client.post("/api/v1/ollama/chat", json={
            "messages": [{"role": "user", "content": "Hi"}],
        })
        assert response.status_code == 400

    def test_ollama_chat_missing_messages_400(self, client):
        response = client.post("/api/v1/ollama/chat", json={
            "model": "llama3.1",
        })
        assert response.status_code == 400

    def test_ollama_chat_error_response(self, client):
        """Chat route should return error content when Ollama is unreachable."""
        from unittest.mock import patch
        with patch("apps.api.ollama_routes.urllib.request.urlopen", side_effect=Exception("connection refused")):
            response = client.post("/api/v1/ollama/chat", json={
                "model": "llama3.1",
                "messages": [{"role": "user", "content": "Hi"}],
            })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data["content"].lower()
        assert data["model"] == "llama3.1"

    def test_ollama_chat_returns_tokens_and_duration(self, client):
        """Chat route should return duration_ms and tokens fields."""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'{"message": {"content": "Hi"}, "total_duration": 5000000000, "eval_count": 42}'

        with patch("apps.api.ollama_routes.urllib.request.urlopen", return_value=mock_resp):
            response = client.post("/api/v1/ollama/chat", json={
                "model": "llama3.1",
                "messages": [{"role": "user", "content": "Hi"}],
            })

        data = response.json()
        assert data["duration_ms"] == 5000  # 5s in ns -> ms
        assert data["tokens"] == 42
