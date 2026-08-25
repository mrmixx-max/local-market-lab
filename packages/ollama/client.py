"""Local-first Ollama bridge — single HTTP client, no framework deps.

Reads OLLAMA_HOST from env (default: http://localhost:11434).
Streams chat completions via the /api/chat endpoint (Ollama ≥ 0.1.17).
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


@dataclass
class OllamaModel:
    name: str
    size: int
    parameter_size: str


class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self.base = (base_url or OLLAMA_HOST).rstrip("/")

    def models(self) -> list[OllamaModel]:
        try:
            with urllib.request.urlopen(f"{self.base}/api/tags", timeout=3) as r:
                data = json.load(r)
        except Exception:
            return []
        return [
            OllamaModel(
                name=m.get("model") or m.get("name", "?"),
                size=m.get("size", 0),
                parameter_size=m.get("details", {}).get("parameter_size", "?"),
            )
            for m in data.get("models", [])
        ]

    def chat(
        self,
        model: str,
        messages: list[dict],
        system: str | None = None,
        temperature: float = 0.4,
        stream: bool = False,
    ):
        """Single-shot chat. Returns the message dict."""
        payload = {
            "model": model,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + messages,
            "stream": stream,
            "options": {"temperature": temperature, "num_ctx": 8192},
        }
        req = urllib.request.Request(
            f"{self.base}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.load(r)
                return {
                    "role": "assistant",
                    "content": resp.get("message", {}).get("content", ""),
                }
        except Exception as exc:
            return {"role": "error", "content": f"Ollama error: {exc}"}

    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        system: str | None = None,
        temperature: float = 0.4,
    ):
        """Generator yielding partial tokens as strings."""
        payload = {
            "model": model,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": 8192},
        }
        req = urllib.request.Request(
            f"{self.base}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                for raw in r:
                    if not raw:
                        continue
                    line = raw.decode().strip()
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        return
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        return
                    token = obj.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if obj.get("done"):
                        return
        except Exception as exc:
            yield f"\n[Ollama error: {exc}]"
