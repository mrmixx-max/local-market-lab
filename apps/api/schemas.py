"""Pydantic response schemas for the Local Market Lab API.

Every response model documents its shape for OpenAPI. All models are
read-only (frozen) and compatible with the dict-based returns they replace.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- health ----------
class HealthResponse(BaseModel):
    """Service health and basic instrumentation count."""

    status: str = "ok"
    instruments: int = Field(..., description="Number of instruments in the database")
    version: str = "0.1.0"
    db_connected: bool = True
    uptime_seconds: float = 0.0
    ollama_available: bool = False
    yahoo_available: bool = False
    ollama_error: str | None = None
    yahoo_error: str | None = None


# ---------- market data ----------
class SymbolSchema(BaseModel):
    """A tradeable instrument."""

    symbol: str
    name: str = ""
    asset_class: str = "etf"
    currency: str = "EUR"


class PriceBarSchema(BaseModel):
    """A single OHLC-style price bar (close-only in this version)."""

    date: str
    close: float
    volume: float | None = None


class PriceSeriesResponse(BaseModel):
    """Price history for a single symbol."""

    symbol: str
    bars: list[PriceBarSchema]


# ---------- portfolio ----------
class PositionSchema(BaseModel):
    """A single valued position within a portfolio."""

    symbol: str
    quantity: float
    avg_cost: float
    last_price: float
    currency: str
    value: float
    cost: float
    pl: float
    pl_pct: float | None = None


class PortfolioValuation(BaseModel):
    """Full portfolio valuation at the latest available close."""

    portfolio: str
    as_of: str | None = None
    reporting_currency: str
    positions: list[PositionSchema]
    total_value: float
    total_cost: float
    unrealized_pl: float
    realized_pl: float
    dividends_received: float
    incomplete_fx: list[dict] = Field(default_factory=list)
    missing_prices: list[str] = Field(default_factory=list)


# ---------- backtest ----------
class BacktestMetrics(BaseModel):
    """Risk/return metrics for a backtest curve."""

    total_return_pct: float
    cagr_pct: float
    volatility_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    calmar: float
    annualization: str = "252 trading days, daily returns"


class BacktestAssumptions(BaseModel):
    """Assumptions used in a backtest run."""

    fees_bps: float
    slippage_bps: float
    rebalance_frequency: str
    start_value: float


class BacktestResult(BaseModel):
    """Full backtest result including curves, metrics, and benchmark."""

    curve: list[float]
    metrics: BacktestMetrics
    benchmark_curve: list[float]
    benchmark_metrics: BacktestMetrics
    assumptions: BacktestAssumptions
    strategy: str
    turnover: float
    trades: int


# ---------- scenario ----------
class ScenarioSummary(BaseModel):
    """Summary statistics from a Monte Carlo or bootstrap scenario."""

    method: str
    runs: int
    horizon_days: int
    seed: int
    p05: float
    p25: float
    median: float
    p75: float
    p95: float
    prob_loss_pct: float
    limitations: list[str] = Field(default_factory=list)


# ---------- game ----------
class PositionOut(BaseModel):
    """Position snapshot within a game state response."""

    quantity: float
    avg_cost: float
    last_price: float
    market_value: float
    unrealized_pl: float


class GameSummary(BaseModel):
    """End-game performance summary with full risk/return stats."""

    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float
    sortino: float
    num_trades: int
    win_rate: float


class GameState(BaseModel):
    """Current state of a paper-trading game session."""

    game_id: str
    player: str
    status: str
    day: str
    date: str | None = None
    cash: float
    positions_value: float
    total_value: float
    return_pct: float
    positions: dict[str, PositionOut]
    pending_orders: int
    filled_orders: int
    challenge: str
    equity_curve: list[float] = Field(default_factory=list)
    summary: GameSummary | None = None


class LeaderboardEntry(BaseModel):
    """A single row in the game leaderboard."""

    player: str
    challenge: str
    score: float
    status: str
    days: int
    summary: GameSummary | None = None


# ---------- lobby ----------
class RoomInfo(BaseModel):
    """Public room listing entry."""

    room_id: str
    host: str
    players: list[str]
    spectators: list[str]
    started: bool
    symbols: list[str]
    days: int
    visibility: str
    has_password: bool


class ChatMessage(BaseModel):
    """A chat message broadcast in a room."""

    type: str
    player: str
    message: str
    timestamp: str


# ---------- stress / crisis ----------
class StressRequest(BaseModel):
    """Request body for stress-test scenarios."""
    scenario: str = Field(..., description="Scenario name (e.g. 2008_financial_crisis, crash_30pct)")
    scenario_type: str | None = Field(default=None,
                                       description="historical or hypothetical — auto-detected if not set")
    positions: dict[str, float] = Field(default_factory=dict,
                                         description="symbol -> weight fraction")
    seed: int = Field(default=42, description="Reproducibility seed")


class StressOut(BaseModel):
    """Stress-test result — unified format with run_id, metrics, timeline."""
    run_id: str = ""
    scenario: str = ""
    seed: int = 42
    data_quality: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    timeline: list[dict] = Field(default_factory=list)
    data_hash: str = ""
    limitations: list[str] = Field(default_factory=list)


class CrisisRequest(BaseModel):
    """Request body for crisis scenario analysis."""
    crisis_type: str = Field(..., description="correlation_break, liquidity_crunch, sector_rotation")
    positions: dict[str, float] = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)


# ---------- rebalancing ----------
class RebalanceRequest(BaseModel):
    """Request body for rebalancing proposals — NEVER executes trades."""
    target_weights: dict[str, float] = Field(default_factory=dict)
    threshold: float = Field(default=0.05, ge=0.001, le=0.5)
    transaction_cost_bps: float = Field(default=10.0, ge=0.0)
    holding_period_days: int = Field(default=30, ge=1, le=365)


# ---------- ollama ----------
class OllamaModelSchema(BaseModel):
    """A model available on the local Ollama daemon."""

    model: str
    size_gb: float
    parameter_size: str
    quantization: str


class OllamaModelsResponse(BaseModel):
    """Response from the Ollama model listing endpoint."""

    models: list[OllamaModelSchema]
    host: str
    error: str | None = None


# ---------- validation ----------
class WalkForwardResponse(BaseModel):
    """Walk-forward backtest result."""

    n_folds: int
    train_window: int
    test_window: int
    step: int
    avg_sharpe: float
    avg_return: float
    oos_sharpe: float
    folds: list[dict]


class CVResponse(BaseModel):
    """Time-series cross-validation result."""

    n_splits: int
    gap: int
    metric: str
    avg: float
    std: float
    folds: list[dict]


class HyperparameterResponse(BaseModel):
    """Hyperparameter tuning result."""

    method: str
    metric: str
    n_trials: int
    seed: int
    best_params: dict
    best_metric: float
    top_trials: list[dict]
