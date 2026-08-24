"""Domain entities — pure dataclasses, no framework deps.

Instrument, Transaction, CorporateAction, PriceSeries.
Money is Decimal-based (packages.core.money); float is forbidden for amounts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    CRYPTO = "crypto"
    FUND = "fund"
    CASH = "cash"
    BOND = "bond"


class TxnType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    SPLIT = "split"


@dataclass(frozen=True)
class Instrument:
    symbol: str                      # canonical short id, e.g. 'IWDA'
    name: str = ""
    asset_class: AssetClass = AssetClass.ETF
    currency: str = "EUR"
    isin: str | None = None

    def __post_init__(self):
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError(f"symbol must be uppercase non-empty: {self.symbol!r}")


@dataclass(frozen=True)
class Transaction:
    """Append-only ledger entry. Corrections create new rows, never mutations."""
    txn_id: str | None               # assigned by storage
    portfolio: str
    symbol: str
    txn_type: TxnType
    date: str                        # ISO yyyy-mm-dd
    quantity: float                  # signed by type semantics (buy:+ sell:- handled in engine)
    price: float                     # per unit, transaction currency
    fees: float = 0.0
    currency: str = "EUR"
    note: str = ""

    def __post_init__(self):
        if self.quantity < 0 or self.price < 0 or self.fees < 0:
            raise ValueError("quantity, price and fees must be non-negative")


@dataclass(frozen=True)
class CorporateAction:
    """Split / reverse split / cash dividend with effective date."""
    symbol: str
    action: str                      # 'split' | 'cash_dividend'
    date: str
    # split: new shares per old share (2.0 = 2:1 split; 0.5 = reverse 1:2)
    ratio: float | None = None
    amount_per_share: float | None = None   # dividend
    currency: str = "EUR"

    def __post_init__(self):
        if self.action == "split" and (self.ratio is None or self.ratio <= 0):
            raise ValueError("split requires positive ratio")
        if self.action == "cash_dividend" and self.amount_per_share is None:
            raise ValueError("cash_dividend requires amount_per_share")


@dataclass
class PriceBar:
    date: str
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    currency: str = "USD"

    def to_ohlcv(self) -> dict:
        """Return unified OHLCV format with currency."""
        return {
            "date": self.date,
            "open": self.open if self.open is not None else self.close,
            "high": self.high if self.high is not None else self.close,
            "low": self.low if self.low is not None else self.close,
            "close": self.close,
            "volume": self.volume if self.volume is not None else 0.0,
            "currency": self.currency,
        }


@dataclass
class PriceSeries:
    symbol: str
    currency: str
    bars: list[PriceBar] = field(default_factory=list)

    def sorted(self) -> "PriceSeries":
        return PriceSeries(self.symbol, self.currency,
                           sorted(self.bars, key=lambda b: b.date))

    def closes(self) -> list[float]:
        return [b.close for b in sorted(self.bars, key=lambda b: b.date)]

    def dates(self) -> list[str]:
        return [b.date for b in sorted(self.bars, key=lambda b: b.date)]


# ---------- export entities ----------
@dataclass
class ExportQuality:
    """Data quality report for exports."""
    n_observations: int
    missing_pct: float
    source: str
    start_date: str = ""
    end_date: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_observations": self.n_observations,
            "missing_pct": self.missing_pct,
            "source": self.source,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "warnings": self.warnings,
        }


@dataclass
class ExportResult:
    """Result of an export operation."""
    run_id: str
    format: str  # pdf | excel | csv
    data_quality: ExportQuality
    data_hash: str
    file_path: str = ""
    file_bytes: bytes = b""
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "format": self.format,
            "data_quality": self.data_quality.to_dict(),
            "data_hash": self.data_hash,
            "file_path": self.file_path,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ---------- explainability entities ----------
@dataclass
class FeatureImportanceItem:
    """Single feature importance entry."""
    feature: str
    importance: float
    std: float = 0.0


@dataclass
class ExplainabilityResult:
    """Result of a feature importance analysis."""
    run_id: str
    model: str
    feature_importance: list[FeatureImportanceItem]
    data_quality: ExportQuality
    splits_used: str = "walk_forward_252_63_21"
    data_hash: str = ""
    shap_values: dict | None = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "model": self.model,
            "feature_importance": [
                {"feature": f.feature, "importance": f.importance, "std": f.std}
                for f in self.feature_importance
            ],
            "data_quality": self.data_quality.to_dict(),
            "splits_used": self.splits_used,
            "data_hash": self.data_hash,
            "shap_values": self.shap_values,
        }


@dataclass
class ModelComparison:
    """Result of comparing two or more models."""
    run_id: str
    models: list[str]
    walk_forward_results: list[dict]
    diebold_mariano: dict
    data_quality: ExportQuality
    splits_used: str = "walk_forward_252_63_21"
    data_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "models": self.models,
            "walk_forward_results": self.walk_forward_results,
            "diebold_mariano": self.diebold_mariano,
            "data_quality": self.data_quality.to_dict(),
            "splits_used": self.splits_used,
            "data_hash": self.data_hash,
        }


@dataclass
class QualityReport:
    """Unified data quality report embedded in every market data response."""
    symbol: str
    status: str = "valid"          # valid | warning | invalid
    missing_values: int = 0
    duplicate_timestamps: int = 0
    stale_data: bool = False
    source: str = "unknown"
    data_hash: str = ""
    timestamp: str = ""
    score: float = 1.0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "data_quality": {
                "status": self.status,
                "missing_values": self.missing_values,
                "duplicate_timestamps": self.duplicate_timestamps,
                "stale_data": self.stale_data,
                "source": self.source,
                "data_hash": self.data_hash,
                "timestamp": self.timestamp,
            },
            "score": round(self.score, 3),
            "issues": self.issues,
        }


# ---------- Stress & Rebalancing domain entities ----------

@dataclass
class StressTestResult:
    """Result of a stress-test scenario run."""
    run_id: str = ""
    scenario: str = ""
    seed: int = 42
    data_quality: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    timeline: list[dict] = field(default_factory=list)
    data_hash: str = ""
    limitations: list[str] = field(default_factory=list)


@dataclass
class CrisisScenario:
    """A crisis scenario definition."""
    name: str = ""
    description: str = ""
    scenario_type: str = ""  # correlation_break, liquidity_crunch, sector_rotation
    shocks: dict = field(default_factory=dict)
    mitigation: list[str] = field(default_factory=list)


@dataclass
class RebalancingProposal:
    """A single rebalancing suggestion — NEVER executes trades."""
    symbol: str = ""
    current_weight: float = 0.0
    target_weight: float = 0.0
    drift: float = 0.0
    action: str = ""  # "buy" or "sell"
    estimated_cost: float = 0.0  # in reporting currency
    tax_impact: float = 0.0  # estimated tax impact


# ---------------------------------------------------------------------------
# Validation domain models — unified result format for all validation runs
# ---------------------------------------------------------------------------

@dataclass
class DataQuality:
    """Data quality report for validation inputs."""
    status: str = "valid"
    missing: int = 0
    duplicates: int = 0
    stale: bool = False
    gaps: list[dict] = field(default_factory=list)


@dataclass
class SplitDoc:
    """Documentation of a single train/test split."""
    fold: int
    train_start: int
    train_end: int
    train_size: int
    test_start: int
    test_end: int
    test_size: int


@dataclass
class ValidationResult:
    """Unified result format for all validation runs."""
    run_id: str = ""
    seed: int = 42
    timestamp: str = ""
    data_hash: str = ""
    data_quality: DataQuality = field(default_factory=DataQuality)
    metrics: dict = field(default_factory=dict)
    splits: list[SplitDoc] = field(default_factory=list)
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "timestamp": self.timestamp,
            "data_hash": self.data_hash,
            "data_quality": {
                "status": self.data_quality.status,
                "missing": self.data_quality.missing,
                "duplicates": self.data_quality.duplicates,
                "stale": self.data_quality.stale,
            },
            "metrics": self.metrics,
            "splits": [
                {
                    "fold": s.fold,
                    "train": {"start": s.train_start, "end": s.train_end, "size": s.train_size},
                    "test": {"start": s.test_start, "end": s.test_end, "size": s.test_size},
                }
                for s in self.splits
            ],
            "config": self.config,
        }


@dataclass
class WalkForwardResult:
    """Walk-forward validation result with unified format."""
    validation: ValidationResult = field(default_factory=ValidationResult)
    n_folds: int = 0
    train_window: int = 252
    test_window: int = 63
    step: int = 21
    avg_sharpe: float = 0.0
    avg_return: float = 0.0
    oos_sharpe: float = 0.0
    folds: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        """Return summary dictionary."""
        base = self.validation.to_dict()
        base.update({
            "n_folds": self.n_folds,
            "train_window": self.train_window,
            "test_window": self.test_window,
            "step": self.step,
            "avg_sharpe": round(self.avg_sharpe, 4),
            "avg_return": round(self.avg_return, 4),
            "oos_sharpe": round(self.oos_sharpe, 4),
            "folds": self.folds,
        })
        return base


@dataclass
class CVResult:
    """Time-series cross-validation result with unified format."""
    validation: ValidationResult = field(default_factory=ValidationResult)
    n_splits: int = 5
    gap: int = 21
    avg_metric: float = 0.0
    std_metric: float = 0.0
    metric_name: str = "sharpe"
    folds: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        """Return summary dictionary."""
        base = self.validation.to_dict()
        base.update({
            "n_splits": self.n_splits,
            "gap": self.gap,
            "metric": self.metric_name,
            "avg": round(self.avg_metric, 4),
            "std": round(self.std_metric, 4),
            "folds": self.folds,
        })
        return base


@dataclass
class HyperparameterResult:
    """Hyperparameter tuning result with unified format."""
    validation: ValidationResult = field(default_factory=ValidationResult)
    best_params: dict = field(default_factory=dict)
    best_metric: float = 0.0
    metric: str = "sharpe"
    n_trials: int = 0
    seed: int = 42
    method: str = "random"
    top_trials: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        """Return summary dictionary."""
        base = self.validation.to_dict()
        base.update({
            "method": self.method,
            "metric": self.metric,
            "n_trials": self.n_trials,
            "best_params": self.best_params,
            "best_metric": round(self.best_metric, 4),
            "top_trials": self.top_trials,
        })
        return base
