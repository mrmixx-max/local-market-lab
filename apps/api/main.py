"""Local Market Lab — FastAPI backend.

Serves:
  - REST: /api/v1/portfolio, /api/v1/backtest, /api/v1/scenario, /api/v1/health
  - WebSocket: /ws/market  (live tick feed into the terminal UI)
  - REST: /api/v1/game/*  (trading game)
  - REST: /api/v1/ollama/*  (local LLM bridge)
  - Static:  /            (the Bloomberg-style terminal web UI)
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from packages.storage.state import get_ws


app = FastAPI(title="Local Market Lab", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------- health ----------
@app.get("/api/v1/health")
async def health():
    ws = get_ws()
    n = ws.conn.execute("SELECT COUNT(*) c FROM instruments").fetchone()["c"]
    return {"status": "ok", "instruments": n, "version": "0.1.0"}


# ---------- market data ----------
@app.get("/api/v1/market/symbols")
async def symbols():
    ws = get_ws()
    rows = ws.conn.execute(
        "SELECT symbol, name, asset_class, currency FROM instruments ORDER BY symbol"
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/market/prices/{symbol}")
async def prices(symbol: str, limit: int | None = None):
    ws = get_ws()
    q = "SELECT date, close, volume FROM prices WHERE symbol=? ORDER BY date"
    params: list = [symbol.upper()]
    if limit:
        q += " LIMIT ?"; params.append(limit)
    rows = ws.conn.execute(q, params).fetchall()
    return {"symbol": symbol.upper(), "bars": [dict(r) for r in rows]}


# ---------- WebSocket: live market feed ----------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await ws.accept()
    subbed: list[str] = []
    try:
        msg = await ws.receive_text()
        data = json.loads(msg)
        if data.get("action") == "subscribe":
            subbed = [s.upper() for s in data.get("symbols", [])]
        rng = random.Random(17)
        lasts: dict[str, float] = {}
        for sym in subbed:
            row = get_ws().conn.execute(
                "SELECT close FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1",
                (sym,)
            ).fetchone()
            lasts[sym] = row["close"] if row else 100.0
        while True:
            out = {}
            for sym in subbed:
                lasts[sym] *= 1 + rng.gauss(0, 0.0008)
                out[sym] = {"close": round(lasts[sym], 4),
                            "ts": datetime.now(timezone.utc).isoformat()}
            await ws.send_text(json.dumps(out))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ---------- portfolio valuation ----------
@app.get("/api/v1/portfolio/{name}")
async def portfolio(name: str):
    from packages.portfolio.engine import value_portfolio
    from packages.marketdata.fx import FxPolicy
    fx = FxPolicy()
    for k, v in os.environ.items():
        if k.startswith("LML_FX_"):
            fx.set_rate(k[8:], float(v))
    return value_portfolio(get_ws(), name, fx)


# ---------- backtest ----------
@app.post("/api/v1/backtest")
async def backtest(payload: dict):
    from packages.backtest.engine import (Assumptions, BuyAndHold,
                                           PeriodicRebalance, run_backtest)
    from packages.marketdata.series import aligned_closes
    symbols = payload.get("symbols", ["IWDA", "EIMI", "AGGH"])
    strat_name = payload.get("strategy", "buy-and-hold")
    strat = BuyAndHold() if strat_name == "buy-and-hold" else PeriodicRebalance(63)
    dates, prices = aligned_closes(get_ws(), symbols)
    return run_backtest(prices, strat, Assumptions(
        fees_bps=payload.get("fees_bps", 10),
        slippage_bps=payload.get("slippage_bps", 5)))


# ---------- scenario ----------
@app.post("/api/v1/scenario")
async def scenario(payload: dict):
    from packages.scenarios.engine import (block_bootstrap, monte_carlo_iid)
    symbol = payload.get("symbol", "IWDA")
    kind = payload.get("kind", "bootstrap")
    runs = payload.get("runs", 2000)
    seed = payload.get("seed", 42)
    horizon = payload.get("horizon_days", 252)
    if kind == "mc":
        res = monte_carlo_iid(get_ws(), symbol, horizon, runs, seed)
    else:
        res = block_bootstrap(get_ws(), symbol, horizon, runs, seed)
    return res.summary()


# ---------- trading game ----------
from apps.api.game_routes import game_router
app.include_router(game_router)


# ---------- ollama ----------
from apps.api.ollama_routes import ollama_router
app.include_router(ollama_router)


# ---------- multiplayer lobby ----------
from apps.api.lobby_routes import lobby_router
app.include_router(lobby_router)


# ---------- static web UI ----------
WEB_DIR = Path(__file__).parent.parent / "web"


@app.get("/")
async def root():
    return FileResponse(str(WEB_DIR / "index.html"))


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
