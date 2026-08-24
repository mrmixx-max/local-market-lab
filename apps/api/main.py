"""Local Market Lab — FastAPI backend.

Serves:
  - REST: /api/v1/portfolio, /api/v1/backtest, /api/v1/scenario, /api/v1/health
  - WebSocket: /ws/market  (live tick feed into the terminal UI)
  - REST: /api/v1/game/*  (trading game)
  - REST: /api/v1/ollama/*  (local LLM bridge)
  - REST: /api/v1/market/indicators/{symbol}  (technical indicators)
  - Static:  /            (the Bloomberg-style terminal web UI)
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import random
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.deps import get_game, get_workspace
from apps.api.schemas import (
    BacktestResult,
    HealthResponse,
    PortfolioValuation,
    PriceSeriesResponse,
    ScenarioSummary,
    SymbolSchema,
)

app = FastAPI(title="Local Market Lab", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------- health ----------
@app.get("/api/v1/health", response_model=HealthResponse, summary="Service health check")
async def health(ws=Depends(get_workspace)):
    """Return service status and the number of instruments in the database."""
    n = ws.conn.execute("SELECT COUNT(*) c FROM instruments").fetchone()["c"]
    return HealthResponse(status="ok", instruments=n, version="0.1.0")


# ---------- market data ----------
@app.get(
    "/api/v1/market/symbols",
    response_model=list[SymbolSchema],
    summary="List all tradeable instruments",
)
async def symbols(ws=Depends(get_workspace)):
    """Return all instruments sorted by symbol."""
    rows = ws.conn.execute(
        "SELECT symbol, name, asset_class, currency FROM instruments ORDER BY symbol"
    ).fetchall()
    return [SymbolSchema(**dict(r)) for r in rows]


@app.get(
    "/api/v1/market/prices/{symbol}",
    response_model=PriceSeriesResponse,
    summary="Get price history for a symbol",
)
async def prices(symbol: str, limit: int | None = None, ws=Depends(get_workspace)):
    """Return historical close prices for a given instrument."""
    q = "SELECT date, close, volume FROM prices WHERE symbol=? ORDER BY date"
    params: list = [symbol.upper()]
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    rows = ws.conn.execute(q, params).fetchall()
    bars = [dict(r) for r in rows]
    return PriceSeriesResponse(symbol=symbol.upper(), bars=bars)


# ---------- technical indicators ----------
@app.post(
    "/api/v1/market/indicators/{symbol}",
    summary="Compute technical indicators for a symbol",
)
async def indicators(symbol: str, payload: dict, ws=Depends(get_workspace)):
    """Compute SMA, EMA, RSI, MACD, or Bollinger indicators for a symbol."""
    from packages.marketdata.indicators import bollinger, ema, macd, rsi, sma

    ind = payload.get("indicator", "sma").lower()
    period = int(
        payload.get(
            "period", 20 if ind == "bollinger" else 14 if ind == "rsi" else 12
        )
    )
    rows = ws.conn.execute(
        "SELECT close FROM prices WHERE symbol=? ORDER BY date", (symbol.upper(),)
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"no prices for {symbol.upper()}")
    data = [r["close"] for r in rows]
    try:
        if ind == "sma":
            return sma(data, period)
        elif ind == "ema":
            return ema(data, period)
        elif ind == "rsi":
            return rsi(data, payload.get("period", 14))
        elif ind == "macd":
            return macd(
                data,
                fast=int(payload.get("fast", 12)),
                slow=int(payload.get("slow", 26)),
                signal=int(payload.get("signal", 9)),
            )
        elif ind == "bollinger":
            return bollinger(data, period, float(payload.get("std", 2.0)))
        else:
            raise ValueError(f"unknown indicator: {ind}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---------- WebSocket: live market feed ----------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    """Live market data feed — subscribe to symbols and receive ticks."""
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
            row = get_workspace().conn.execute(
                "SELECT close FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1",
                (sym,),
            ).fetchone()
            lasts[sym] = row["close"] if row else 100.0
        while True:
            out = {}
            for sym in subbed:
                lasts[sym] *= 1 + rng.gauss(0, 0.0008)
                out[sym] = {
                    "close": round(lasts[sym], 4),
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            await ws.send_text(json.dumps(out))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ---------- portfolio valuation ----------
@app.get(
    "/api/v1/portfolio/{name}",
    response_model=PortfolioValuation,
    summary="Value a portfolio at latest close",
)
async def portfolio(name: str, ws=Depends(get_workspace)):
    """Compute the current value of all positions in a named portfolio."""
    from packages.portfolio.engine import value_portfolio
    from packages.marketdata.fx import FxPolicy

    fx = FxPolicy()
    for k, v in os.environ.items():
        if k.startswith("LML_FX_"):
            fx.set_rate(k[8:], float(v))
    result = value_portfolio(ws, name, fx)
    return PortfolioValuation(**result)


# ---------- backtest ----------
@app.post(
    "/api/v1/backtest",
    response_model=BacktestResult,
    summary="Run a portfolio backtest",
)
async def backtest(payload: dict, ws=Depends(get_workspace)):
    """Run a backtest with the given symbols, strategy, and assumptions."""
    from packages.backtest.engine import (
        Assumptions,
        BuyAndHold,
        PeriodicRebalance,
        run_backtest,
    )
    from packages.marketdata.series import aligned_closes

    symbols = payload.get("symbols", ["IWDA", "EIMI", "AGGH"])
    strat_name = payload.get("strategy", "buy-and-hold")
    strat = BuyAndHold() if strat_name == "buy-and-hold" else PeriodicRebalance(63)
    dates, prices = aligned_closes(ws, symbols)
    result = run_backtest(
        prices,
        strat,
        Assumptions(
            fees_bps=payload.get("fees_bps", 10),
            slippage_bps=payload.get("slippage_bps", 5),
        ),
    )
    return BacktestResult(**result)


# ---------- scenario ----------
@app.post(
    "/api/v1/scenario",
    response_model=ScenarioSummary,
    summary="Run a Monte Carlo or bootstrap scenario",
)
async def scenario(payload: dict, ws=Depends(get_workspace)):
    """Run a scenario simulation and return summary statistics."""
    from packages.scenarios.engine import block_bootstrap, monte_carlo_iid

    symbol = payload.get("symbol", "IWDA")
    kind = payload.get("kind", "bootstrap")
    runs = payload.get("runs", 2000)
    seed = payload.get("seed", 42)
    horizon = payload.get("horizon_days", 252)
    if kind == "mc":
        res = monte_carlo_iid(ws, symbol, horizon, runs, seed)
    else:
        res = block_bootstrap(ws, symbol, horizon, runs, seed)
    return ScenarioSummary(**res.summary())


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


@app.get("/", summary="Serve the web UI entry point")
async def root():
    """Return the main web UI HTML page."""
    return FileResponse(str(WEB_DIR / "index.html"))


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
