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
    volume: float | None = None


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
