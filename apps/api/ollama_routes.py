"""Ollama bridge REST routes.

Prefix: /api/v1/ollama
"""

from __future__ import annotations

import json
import os
import urllib.request

import requests
from fastapi import APIRouter, HTTPException

ollama_router = APIRouter(prefix="/api/v1/ollama", tags=["ollama"])


def _ollama_host() -> str:
    import os

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    if not host.startswith("http"):
        host = f"http://{host}"
    if ":" not in host.split("://", 1)[-1]:
        host = f"{host}:11434"
    return host


@ollama_router.get("/models")
async def list_models():
    """List models available on the local Ollama daemon."""
    try:
        r = requests.get(f"{_ollama_host()}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        models = []
        for m in data.get("models", []):
            models.append(
                {
                    "model": m.get("model") or m.get("name"),
                    "size_gb": round(m.get("size", 0) / 1e9, 1),
                    "parameter_size": m.get("details", {}).get("parameter_size", "?"),
                    "quantization": m.get("details", {}).get("quantization_level", "?"),
                }
            )
        return {"models": models, "host": _ollama_host()}
    except Exception as exc:
        return {"models": [], "host": _ollama_host(), "error": str(exc)}


@ollama_router.post("/chat")
async def chat(payload: dict):
    """Proxy a chat completion to the local Ollama daemon.

    Body: {model, messages, system?, temperature?, num_ctx?}
    Returns: {content, model, duration_ms, tokens}
    """
    model = payload.get("model")
    if not model:
        raise HTTPException(400, "model required")
    if not payload.get("messages"):
        raise HTTPException(400, "messages required")

    timeout = int(os.environ.get("OLLAMA_TIMEOUT", "180"))
    msgs = payload["messages"]
    if payload.get("system"):
        msgs = [{"role": "system", "content": payload["system"]}] + msgs

    body = {
        "model": model,
        "messages": msgs,
        "stream": False,
        "options": {
            "temperature": payload.get("temperature", 0.4),
            "num_ctx": payload.get("num_ctx", 8192),
        },
    }
    try:
        req = urllib.request.Request(
            f"{_ollama_host()}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.load(r)
        return {
            "content": resp.get("message", {}).get("content", ""),
            "model": model,
            "duration_ms": resp.get("total_duration", 0) // 1_000_000,
            "tokens": resp.get("eval_count", 0),
        }
    except Exception as exc:
        return {"content": f"[Ollama error: {exc}]", "model": model, "error": str(exc)}


@ollama_router.post("/optimize_prompt")
async def optimize_prompt(payload: dict):
    """Trading prompt optimizer — returns a tuned system prompt.

    Body: {goal?, audience?, risk_temperature?, style?}
    """
    goal = payload.get("goal", "paper-trading coach")
    audience = payload.get("audience", "retail trader")
    temp = payload.get("risk_temperature", "moderate")
    style = payload.get("style", "concise")

    templates = {
        "paper-trading coach": f"""You are an AI trading coach for a paper-trading simulator. Your role:
- Analyze portfolio positions, risk metrics, and trade history the user provides.
- Explain concepts like Sharpe ratio, max drawdown, position sizing, and diversification in plain language.
- When the user describes a trade idea, evaluate it on risk/reward, position size relative to portfolio, and correlation with existing holdings — NOT on whether you think the price will go up or down.
- If the user asks "will X go up?", answer: "I don't predict prices. Instead, let's look at the risk if you're wrong."
- Be {style}. Use bullet points. Keep responses under 200 words unless asked for depth.
- Remind the user that paper-trading results do not guarantee live-trading outcomes.""",
        "strategy explainer": f"""You are a quantitative strategy explainer. Your role:
- Given a strategy description, break it into: (1) signal logic, (2) execution rules, (3) risk controls, (4) known failure modes.
- Always stress-test the strategy against: high-volatility regimes, low-liquidity environments, and black-swan events.
- If a strategy lacks an explicit stop-loss or position limit, call that out immediately.
- Use precise language. {style} delivery.
- You do NOT predict whether a strategy will be profitable in the future.""",
        "risk auditor": f"""You are a portfolio risk auditor. Your role:
- Given a portfolio composition (list of positions with weights), identify: concentration risk, sector/currency exposure, tail-risk contributions.
- Flag any single position above 10% of total, any sector above 30%, any currency exposure above 20%.
- Suggest specific rebalancing moves (e.g., "reduce X from 15% to 8%, redistribute to Y and Z").
- Tone: factual, direct, {style}.
- You do not provide buy/sell recommendations — only risk observations and rebalancing mechanics.""",
    }

    prompt = templates.get(goal, templates["paper-trading coach"])
    return {
        "optimized_prompt": prompt,
        "goal": goal,
        "audience": audience,
        "risk_temperature": temp,
        "char_count": len(prompt),
        "tips": [
            "Keep system prompt under 1000 chars for faster CPU inference.",
            "Use temperature 0.3-0.5 for analysis, 0.6-0.8 for creative strategy brainstorming.",
            "If the model goes off-topic, add: 'Stay strictly on the topic of risk management and execution.'",
            "For Ollama models: include a one-shot example in the system prompt for better format adherence.",
            "If using a small model (<7B), keep prompts under 500 chars and ask for shorter outputs.",
        ],
    }
