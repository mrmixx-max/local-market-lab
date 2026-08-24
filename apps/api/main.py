"""Local Market Lab — FastAPI backend.

Serves:
  - REST: /api/v1/portfolio, /api/v1/backtest, /api/v1/scenario, /api/v1/health
  - WebSocket: /ws/market  (live tick feed into the terminal UI)
  - REST: /api/v1/game/*  (trading game)
  - REST: /api/v1/ollama/*  (local LLM bridge)
  - REST: /api/v1/market/indicators/{symbol}  (technical indicators)
  - REST: /api/v1/system/info  (runtime metadata)
  - Static:  /            (the Bloomberg-style terminal web UI)
"""
from __future__ import annotations

import asyncio
import atexit
import json
import os
import random
import signal
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.deps import get_game, get_workspace
from apps.api.middleware import (
    ExceptionHandlerMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    log_json,
)
from apps.api.schemas import (
    BacktestResult,
    CrisisRequest,
    CVResponse,
    HealthResponse,
    HyperparameterResponse,
    PortfolioValuation,
    PriceSeriesResponse,
    RebalanceRequest,
    ScenarioSummary,
    StressOut,
    StressRequest,
    SymbolSchema,
    WalkForwardResponse,
)

# ---------------------------------------------------------------------------
# App + lifecycle
# ---------------------------------------------------------------------------
app = FastAPI(title="Local Market Lab", version="0.1.0")
_start_time = time.monotonic()
_shutdown_done = False


def _shutdown() -> None:
    """Close the SQLite connection pool on process exit."""
    global _shutdown_done
    if _shutdown_done:
        return
    _shutdown_done = True
    try:
        from packages.storage.state import _workspace
        if _workspace is not None:
            _workspace.conn.close()
            log_json("info", event="shutdown", msg="database connection closed")
    except Exception as exc:  # noqa: BLE001
        log_json("error", event="shutdown_error", msg=str(exc))


# PyInstaller SIGTERM/SIGINT handler — needed because PyInstaller's bootloader
# does not forward signals by default in windowed mode.
def _signal_handler(signum, frame):
    _shutdown()
    raise SystemExit(0)


try:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
except (ValueError, OSError):
    # May fail on non-main threads or restricted environments.
    pass

atexit.register(_shutdown)


# ---------------------------------------------------------------------------
# Middleware  (order: outermost → innermost)
# ---------------------------------------------------------------------------
cors_origins = os.environ.get("LML_CORS_ORIGINS", "*")
app.add_middleware(CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins.split(",") if o.strip()] or ["*"],
    allow_methods=["*"], allow_headers=["*"])
app.add_middleware(ExceptionHandlerMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)


# ---------- health ----------
@app.get("/api/v1/health", response_model=HealthResponse, summary="Service health check")
async def health(ws=Depends(get_workspace)):
    """Return service status, DB connectivity, instrument count, uptime, and upstream status."""
    db_ok = True
    try:
        ws.conn.execute("SELECT 1")
    except Exception:
        db_ok = False
    n = ws.conn.execute("SELECT COUNT(*) c FROM instruments").fetchone()["c"] if db_ok else 0
    uptime_seconds = round(time.monotonic() - _start_time, 1)

    # Check Ollama availability
    ollama_available = False
    ollama_error = None
    try:
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        if not ollama_host.startswith("http"):
            ollama_host = f"http://{ollama_host}"
        if ":" not in ollama_host.split("://", 1)[-1]:
            ollama_host = f"{ollama_host}:11434"
        req = urllib.request.Request(f"{ollama_host}/api/tags", headers={"User-Agent": "LocalMarketLab/0.1"})
        with urllib.request.urlopen(req, timeout=3) as r:
            json.load(r)
        ollama_available = True
    except Exception as exc:
        ollama_error = str(exc)

    # Check Yahoo Finance availability
    yahoo_available = False
    yahoo_error = None
    try:
        yahoo_url = "https://query1.finance.yahoo.com/v8/finance/chart/^GDAXI?range=1d&interval=1d"
        req = urllib.request.Request(yahoo_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=5) as r:
            json.load(r)
        yahoo_available = True
    except Exception as exc:
        yahoo_error = str(exc)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        instruments=n,
        version="0.1.0",
        db_connected=db_ok,
        uptime_seconds=uptime_seconds,
        ollama_available=ollama_available,
        yahoo_available=yahoo_available,
        ollama_error=ollama_error,
        yahoo_error=yahoo_error,
    )


# ---------- system info ----------
@app.get("/api/v1/system/info", summary="Runtime metadata")
async def system_info(ws=Depends(get_workspace)):
    """Return version, uptime, DB path, and DB file size."""
    from packages.storage.state import get_ws
    ws = get_ws()
    db_path = ws.db_path
    try:
        db_size = Path(db_path).stat().st_size
    except OSError:
        db_size = 0
    return {
        "version": "0.1.0",
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "db_path": db_path,
        "db_size_bytes": db_size,
        "python_version": os.sys.version.split()[0],
    }


# ---------- market data ----------
@app.get("/api/v1/market/symbols", response_model=list[SymbolSchema], summary="List all tradeable instruments")
async def symbols(ws=Depends(get_workspace)):
    """Return all instruments sorted by symbol."""
    rows = ws.conn.execute(
        "SELECT symbol, name, asset_class, currency FROM instruments ORDER BY symbol"
    ).fetchall()
    return [SymbolSchema(**dict(r)) for r in rows]


@app.get("/api/v1/market/prices/{symbol}", response_model=PriceSeriesResponse, summary="Get price history for a symbol")
async def prices(symbol: str, limit: int | None = None, ws=Depends(get_workspace)):
    """Return historical close prices for a given instrument."""
    q = "SELECT date, close, volume FROM prices WHERE symbol=? ORDER BY date"
    params: list = [symbol.upper()]
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    rows = ws.conn.execute(q, params).fetchall()
    return PriceSeriesResponse(symbol=symbol.upper(), bars=[dict(r) for r in rows])


@app.get("/api/v1/market/yahoo/{symbol}", summary="Yahoo Finance Fallback")
async def yahoo_fallback(symbol: str):
    """Fallback to Yahoo Finance for real-time prices (crypto, stocks not in local DB).

    Tries query1.finance.yahoo.com first, then query2 as fallback.
    Uses a realistic browser User-Agent to avoid Yahoo blocks.
    Configurable timeout via LML_YAHOO_TIMEOUT env var (default: 10s).
    """
    timeout = int(os.environ.get("LML_YAHOO_TIMEOUT", "10"))
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    endpoints = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1m",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1m",
    ]
    last_err: str | None = None
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            result = data.get("chart", {}).get("result", [])
            if not result:
                last_err = "no data in Yahoo response"
                continue
            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("chartPreviousClose", price)
            return {
                "symbol": symbol,
                "price": price,
                "prev_close": prev,
                "currency": meta.get("currency", "USD"),
                "source": url.split("/")[2],
            }
        except Exception as exc:
            last_err = str(exc)
            continue
    return {"error": last_err or "all Yahoo endpoints failed"}


# ---------- technical indicators ----------
@app.post("/api/v1/market/indicators/{symbol}", summary="Compute technical indicators for a symbol")
async def indicators(symbol: str, payload: dict, ws=Depends(get_workspace)):
    """Compute SMA, EMA, RSI, MACD, or Bollinger indicators for a symbol."""
    from packages.marketdata.indicators import bollinger, ema, macd, rsi, sma

    ind = payload.get("indicator", "sma").lower()
    period = int(payload.get("period", 20 if ind == "bollinger" else 14 if ind == "rsi" else 12))
    rows = ws.conn.execute("SELECT close FROM prices WHERE symbol=? ORDER BY date", (symbol.upper(),)).fetchall()
    if not rows:
        raise HTTPException(404, f"no prices for {symbol.upper()}")
    data = [r["close"] for r in rows]
    try:
        if ind == "sma": return sma(data, period)
        elif ind == "ema": return ema(data, period)
        elif ind == "rsi": return rsi(data, payload.get("period", 14))
        elif ind == "macd": return macd(data, fast=int(payload.get("fast", 12)), slow=int(payload.get("slow", 26)), signal=int(payload.get("signal", 9)))
        elif ind == "bollinger": return bollinger(data, period, float(payload.get("std", 2.0)))
        else: raise ValueError(f"unknown indicator: {ind}")
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
                "SELECT close FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1", (sym,),
            ).fetchone()
            lasts[sym] = row["close"] if row else 100.0
        while True:
            out = {}
            for sym in subbed:
                lasts[sym] *= 1 + rng.gauss(0, 0.0008)
                out[sym] = {"close": round(lasts[sym], 4), "ts": datetime.now(timezone.utc).isoformat()}
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
async def portfolio(name: str, benchmark: str | None = None,
                    include_analytics: bool = True,
                    ws=Depends(get_workspace)):
    """Value a portfolio. Optional: benchmark symbol, allocation + risk analytics."""
    from packages.portfolio.engine import (allocation_breakdown, benchmark_comparison, portfolio_returns, risk_contribution, value_portfolio)
    from packages.marketdata.fx import FxPolicy

    fx = FxPolicy()
    for k, v in os.environ.items():
        if k.startswith("LML_FX_"):
            fx.set_rate(k[8:], float(v))
    result = value_portfolio(ws, name, fx)
    if include_analytics:
        result["allocation"] = allocation_breakdown(ws, result)
        if benchmark:
            port_rets = portfolio_returns(ws, result, fx)
            result["benchmark"] = benchmark_comparison(ws, port_rets, benchmark.upper())
        result["risk_contribution"] = risk_contribution(ws, result, fx)
    else:
        result["allocation"] = []
        result["benchmark"] = None
        result["risk_contribution"] = []
    return PortfolioValuation(**result)


# ---------- backtest ----------
@app.post(
    "/api/v1/backtest",
    response_model=BacktestResult,
    summary="Run a portfolio backtest",
)
async def backtest(payload: dict, ws=Depends(get_workspace)):
    """Run a backtest with the given symbols, strategy, and assumptions."""
    from packages.backtest.engine import (Assumptions, BuyAndHold, PeriodicRebalance, run_backtest)
    from packages.marketdata.series import aligned_closes

    strat_name = payload.get("strategy", "buy-and-hold")
    strat = BuyAndHold() if strat_name == "buy-and-hold" else PeriodicRebalance(63)
    _, prices = aligned_closes(ws, payload.get("symbols", ["IWDA", "EIMI", "AGGH"]))
    result = run_backtest(prices, strat, Assumptions(fees_bps=payload.get("fees_bps", 10), slippage_bps=payload.get("slippage_bps", 5)))
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
    runs = payload.get("runs", 2000)
    seed = payload.get("seed", 42)
    horizon = payload.get("horizon_days", 252)
    if payload.get("kind", "bootstrap") == "mc":
        res = monte_carlo_iid(ws, symbol, horizon, runs, seed)
    else:
        res = block_bootstrap(ws, symbol, horizon, runs, seed)
    return ScenarioSummary(**res.summary())


# ---------- advanced metrics ----------
@app.post("/api/v1/metrics/advanced", summary="Advanced risk metrics")
async def metrics_advanced(payload: dict, ws=Depends(get_workspace)):
    """VaR, CVaR, correlation matrix, rolling Sharpe, drawdown, performance attribution."""
    from packages.marketdata.series import aligned_closes
    from packages.metrics.risk import (correlation_matrix, drawdown_series, performance_attribution, rolling_sharpe, var_cvar, returns)

    syms = payload.get("symbols", ["IWDA", "EIMI", "AGGH"])
    conf = float(payload.get("confidence", 0.95))
    win = int(payload.get("window", 63))
    _, prices = aligned_closes(ws, syms)
    rets = {s: returns(p) for s, p in prices.items()}
    port = [sum(rets[s][i] for s in rets) / len(rets) for i in range(min(len(r) for r in rets.values()))]
    eq = [1.0]
    for r in port:
        eq.append(eq[-1] * (1 + r))
    w = {s: float(payload.get("weights", {}).get(s, 1.0 / len(syms))) for s in syms}
    return {
        "var_cvar": var_cvar(port, conf),
        "correlation": correlation_matrix(rets),
        "rolling_sharpe": rolling_sharpe(port, win),
        "drawdown": drawdown_series(eq),
        "attribution": performance_attribution(w, prices),
    }


# ---------- stress test ----------
@app.post("/api/v1/scenario/stress", response_model=StressOut,
          summary="Run a stress-test scenario")
async def stress_test(payload: StressRequest):
    """Apply a historical or hypothetical stress scenario to a portfolio.

    @experimental — Returns StressTestResult format with run_id, metrics,
    timeline, and data_hash. Sensitivity exploration, not a forecast.
    """
    from packages.scenarios.stress import (
        HISTORICAL_CRISES, HYPOTHETICAL_SCENARIOS,
        run_historical_stress, run_hypothetical_stress,
    )

    if not payload.positions:
        raise HTTPException(400, "positions required (symbol -> weight fraction)")

    if payload.scenario_type == "historical":
        if payload.scenario not in HISTORICAL_CRISES:
            raise HTTPException(404, f"unknown crisis: {payload.scenario}. "
                                     f"available: {list(HISTORICAL_CRISES)}")
        res = run_historical_stress(payload.scenario, payload.positions,
                                     payload.seed)
    else:
        if payload.scenario not in HYPOTHETICAL_SCENARIOS:
            raise HTTPException(404, f"unknown scenario: {payload.scenario}. "
                                     f"available: {list(HYPOTHETICAL_SCENARIOS)}")
        res = run_hypothetical_stress(payload.scenario, payload.positions,
                                       payload.seed)
    return StressOut(
        run_id=res.run_id, scenario=res.scenario, seed=res.seed,
        data_quality=res.data_quality, metrics=res.metrics,
        timeline=res.timeline, data_hash=res.data_hash,
        limitations=res.limitations,
    )


# ---------- crisis scenario ----------
@app.post("/api/v1/scenario/crisis", summary="Run a crisis scenario analysis")
async def crisis_scenario(payload: CrisisRequest):
    """Analyze correlation break, liquidity crunch, or sector rotation."""
    from packages.scenarios.crisis import correlation_break, liquidity_crunch, sector_rotation

    if not payload.positions:
        raise HTTPException(400, "positions required (symbol -> weight fraction)")

    p = payload.params
    if payload.crisis_type == "correlation_break":
        res = correlation_break(payload.positions, **p)
    elif payload.crisis_type == "liquidity_crunch":
        res = liquidity_crunch(payload.positions, **p)
    elif payload.crisis_type == "sector_rotation":
        res = sector_rotation(payload.positions, **p)
    else:
        raise HTTPException(400, f"unknown crisis_type: {payload.crisis_type}")
    return {
        "scenario_type": res.scenario_type,
        "portfolio_impact_pct": res.portfolio_impact_pct,
        "details": res.details,
        "mitigation": res.mitigation,
        "limitations": res.limitations,
    }


# ---------- rebalancing assistant ----------
@app.get("/api/v1/portfolio/{name}/rebalancing",
         summary="Get rebalancing analysis for a portfolio")
async def rebalancing_analysis(
    name: str,
    threshold: float = 0.05,
    ws=Depends(get_workspace),
):
    """Analyze drift and suggest rebalancing proposals for a live portfolio.

    @experimental — NEVER executes trades. Only returns RebalancingProposal
    suggestions with cost estimates and tax-loss harvesting indicators.
    """
    from packages.portfolio.engine import value_portfolio
    from packages.portfolio.rebalancing import rebalance_from_valuation
    from packages.marketdata.fx import FxPolicy

    fx = FxPolicy()
    for k, v in os.environ.items():
        if k.startswith("LML_FX_"):
            fx.set_rate(k[8:], float(v))
    valued = value_portfolio(ws, name, fx)
    n = len(valued["positions"])
    if n == 0:
        return {"needs_rebalance": False, "summary": "No positions in portfolio."}
    target = {p["symbol"]: 1.0 / n for p in valued["positions"]}
    result = rebalance_from_valuation(valued, target, threshold)
    return {
        "needs_rebalance": result.needs_rebalance,
        "drift_threshold": result.drift_threshold,
        "drift_analysis": [d.__dict__ for d in result.drift_analysis],
        "proposals": [p.__dict__ for p in result.proposals],
        "total_estimated_cost": result.total_estimated_cost,
        "tax_loss_opportunities": result.tax_loss_opportunities,
        "summary": result.summary,
        "disclaimer": "Suggestions only — no trades executed.",
    }


@app.post("/api/v1/portfolio/{name}/rebalance",
             summary="Generate rebalancing proposals for target weights")
async def rebalance_portfolio(name: str, payload: RebalanceRequest,
                               ws=Depends(get_workspace)):
    """Generate rebalancing proposals for a portfolio given target weights.

    @experimental — NEVER executes trades. Only returns RebalancingProposal
    suggestions with drift analysis and cost-benefit estimates.
    """
    from packages.portfolio.engine import value_portfolio
    from packages.portfolio.rebalancing import rebalance_from_valuation
    from packages.marketdata.fx import FxPolicy

    if not payload.target_weights:
        raise HTTPException(400, "target_weights required")

    fx = FxPolicy()
    for k, v in os.environ.items():
        if k.startswith("LML_FX_"):
            fx.set_rate(k[8:], float(v))
    valued = value_portfolio(ws, name, fx)
    result = rebalance_from_valuation(
        valued, payload.target_weights, payload.threshold,
        payload.transaction_cost_bps,
    )
    return {
        "needs_rebalance": result.needs_rebalance,
        "drift_threshold": result.drift_threshold,
        "proposals": [p.__dict__ for p in result.proposals],
        "total_estimated_cost": result.total_estimated_cost,
        "tax_loss_opportunities": result.tax_loss_opportunities,
        "summary": result.summary,
        "disclaimer": "Suggestions only — no trades executed.",
    }


# ---------- routers ----------
@app.post("/api/v1/scenario/forecast/{symbol}", summary="Generate ML forecast for a symbol")
async def forecast(symbol: str, payload: dict, ws=Depends(get_workspace)):
    """Generate a pure-Python forecast (linear + Holt + ARIMA-like + ensemble)."""
    from packages.scenarios.predict import ensemble_forecast

    rows = ws.conn.execute(
        "SELECT close FROM prices WHERE symbol=? ORDER BY date", (symbol.upper(),)
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"no prices for {symbol.upper()}")
    data = [r["close"] for r in rows]
    horizon = payload.get("horizon", 30)
    try:
        result = ensemble_forecast(data, horizon)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    result["symbol"] = symbol.upper()
    return result


# ---------- validation ----------
def _default_strategy(train_data, test_data):
    """Default mean-reversion strategy for validation endpoints."""
    if len(train_data) < 2:
        return [0.0] * len(test_data)
    returns = [b / a - 1 for a, b in zip(train_data, train_data[1:])]
    avg_return = sum(returns) / len(returns)
    # simple signal: positive if recent trend is positive
    signal = 1.0 if avg_return > 0 else -1.0
    return [signal] * len(test_data)


@app.post("/api/v1/validation/walk-forward", response_model=WalkForwardResponse, summary="Walk-forward backtest")
async def validation_walk_forward(payload: dict, ws=Depends(get_workspace)):
    """Run walk-forward validation on a price series."""
    from packages.validation.walk_forward import walk_forward_backtest

    symbol = payload.get("symbol", "IWDA")
    rows = ws.conn.execute(
        "SELECT close FROM prices WHERE symbol=? ORDER BY date", (symbol.upper(),)
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"no prices for {symbol.upper()}")
    data = [r["close"] for r in rows]

    result = walk_forward_backtest(
        data=data,
        strategy_fn=_default_strategy,
        train_window=payload.get("train_window", 252),
        test_window=payload.get("test_window", 63),
        step=payload.get("step", 21),
    )
    return WalkForwardResponse(**result.summary())


@app.post("/api/v1/validation/cv", response_model=CVResponse, summary="Time-series cross-validation")
async def validation_cv(payload: dict, ws=Depends(get_workspace)):
    """Run purged K-Fold cross-validation on a price series."""
    from packages.validation.cv import time_series_cv

    symbol = payload.get("symbol", "IWDA")
    rows = ws.conn.execute(
        "SELECT close FROM prices WHERE symbol=? ORDER BY date", (symbol.upper(),)
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"no prices for {symbol.upper()}")
    data = [r["close"] for r in rows]

    result = time_series_cv(
        model_fn=_default_strategy,
        data=data,
        n_splits=payload.get("n_splits", 5),
        gap=payload.get("gap", 21),
        metric=payload.get("metric", "sharpe"),
    )
    return CVResponse(**result.summary())


@app.post("/api/v1/validation/hyperparameter", response_model=HyperparameterResponse, summary="Hyperparameter tuning")
async def validation_hyperparameter(payload: dict, ws=Depends(get_workspace)):
    """Run hyperparameter tuning on a price series."""
    from packages.validation.hyperparameter import hyperparameter_tune

    symbol = payload.get("symbol", "IWDA")
    rows = ws.conn.execute(
        "SELECT close FROM prices WHERE symbol=? ORDER BY date", (symbol.upper(),)
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"no prices for {symbol.upper()}")
    data = [r["close"] for r in rows]

    param_grid = payload.get("param_grid")
    if not param_grid:
        param_grid = {"lookback": [10, 20, 50], "threshold": [0.01, 0.02, 0.05]}

    result = hyperparameter_tune(
        model_fn=_default_strategy,
        data=data,
        param_grid=param_grid,
        metric=payload.get("metric", "sharpe"),
        n_trials=payload.get("n_trials", 20),
        seed=payload.get("seed", 42),
        method=payload.get("method", "random"),
    )
    return HyperparameterResponse(**result.summary())


# ---------- routers ----------
from apps.api.game_routes import game_router
from apps.api.ollama_routes import ollama_router
from apps.api.lobby_routes import lobby_router
from apps.api.market_data_routes import market_data_router
from apps.api.export_routes import export_router, explain_router
from packages.compliance.bank_ready import compliance_router

app.include_router(game_router)
app.include_router(ollama_router)
app.include_router(lobby_router)
app.include_router(market_data_router)
app.include_router(compliance_router)
app.include_router(export_router)
app.include_router(explain_router)


# ---------- static web UI ----------
WEB_DIR = Path(__file__).parent.parent / "web"


@app.get("/", summary="Serve the web UI entry point")
async def root():
    """Return the main web UI HTML page."""
    return FileResponse(str(WEB_DIR / "index.html"))


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
