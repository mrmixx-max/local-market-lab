"""Integration tests for OllamaClient with mocked urllib.request.urlopen."""

import json
from unittest.mock import MagicMock, patch


from packages.ollama.client import OllamaClient


def _mock_response(data: dict):
    """Create a mock HTTP response that behaves like urlopen's return."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = json.dumps(data).encode()
    return mock


class TestOllamaModels:
    def test_models_returns_list_on_success(self):
        payload = {
            "models": [
                {
                    "model": "llama3.1:8b",
                    "size": 4700000000,
                    "details": {"parameter_size": "8.0B"},
                },
            ]
        }
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
            client = OllamaClient("http://localhost:11434")
            models = client.models()
        assert len(models) == 1
        assert models[0].name == "llama3.1:8b"
        assert models[0].size == 4700000000

    def test_models_empty_on_error(self):
        with patch(
            "urllib.request.urlopen", side_effect=Exception("connection refused")
        ):
            client = OllamaClient("http://localhost:11434")
            assert client.models() == []

    def test_models_handles_alternative_name_key(self):
        payload = {"models": [{"name": "qwen2:7b", "size": 1000}]}
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
            client = OllamaClient("http://localhost:11434")
            models = client.models()
        assert models[0].name == "qwen2:7b"


class TestOllamaChat:
    def test_chat_returns_assistant_message(self):
        payload = {"message": {"role": "assistant", "content": "Hello!"}}
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
            client = OllamaClient("http://localhost:11434")
            result = client.chat("llama3.1", [{"role": "user", "content": "Hi"}])
        assert result["role"] == "assistant"
        assert result["content"] == "Hello!"

    def test_chat_with_system_prompt(self):
        payload = {"message": {"role": "assistant", "content": "Sure!"}}
        with patch(
            "urllib.request.urlopen", return_value=_mock_response(payload)
        ) as mock_urlopen:
            client = OllamaClient("http://localhost:11434")
            client.chat(
                "llama3.1",
                [{"role": "user", "content": "Hi"}],
                system="You are helpful.",
            )
        # verify the request was made with system message
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data)
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "You are helpful."

    def test_chat_error_returns_error_role(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            client = OllamaClient("http://localhost:11434")
            result = client.chat("llama3.1", [{"role": "user", "content": "Hi"}])
        assert result["role"] == "error"
        assert "Ollama error" in result["content"]


class TestOllamaChatStream:
    def test_chat_stream_yields_tokens(self):
        lines = [
            json.dumps({"message": {"content": "Hello"}, "done": False}),
            json.dumps({"message": {"content": " world"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        mock.__iter__ = MagicMock(
            return_value=iter([f"data: {line}\n".encode() for line in lines])
        )
        with patch("urllib.request.urlopen", return_value=mock):
            client = OllamaClient("http://localhost:11434")
            tokens = list(
                client.chat_stream("llama3.1", [{"role": "user", "content": "Hi"}])
            )
        assert tokens == ["Hello", " world"]

    def test_chat_stream_handles_connection_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("refused")):
            client = OllamaClient("http://localhost:11434")
            tokens = list(
                client.chat_stream("llama3.1", [{"role": "user", "content": "Hi"}])
            )
        assert len(tokens) == 1
        assert "Ollama error" in tokens[0]


class TestOllamaClientInit:
    def test_default_base_url(self):
        client = OllamaClient("http://test-host:11434")
        assert client.base == "http://test-host:11434"

    def test_custom_base_url(self):
        client = OllamaClient("http://custom:8080")
        assert client.base == "http://custom:8080"

    def test_trailing_slash_stripped(self):
        client = OllamaClient("http://host:11434/")
        assert client.base == "http://host:11434"
