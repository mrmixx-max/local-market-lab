"""Money value object — Decimal-based, per project non-negotiable.

float is forbidden for money in domain and ledger logic.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Union

getcontext().prec = 28

Number = Union[int, str, Decimal]


class Money:
    """Immutable amount + currency. Arithmetic requires matching currency."""

    __slots__ = ("amount", "currency")

    def __init__(self, amount: Number, currency: str):
        self.amount = Decimal(str(amount))
        self.currency = currency.upper()

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(0, currency)

    def quantized(self, places: int = 2) -> "Money":
        q = Decimal(1).scaleb(-places)
        return Money(self.amount.quantize(q, rounding=ROUND_HALF_EVEN), self.currency)

    def _check(self, other: "Money") -> None:
        if not isinstance(other, Money) or other.currency != self.currency:
            raise ValueError(
                f"currency mismatch: {self.currency} vs {getattr(other,'currency',other)}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Union[int, Decimal]) -> "Money":
        if isinstance(factor, float):
            raise TypeError(
                "float multiplication on Money is forbidden; use Decimal or int"
            )
        return Money(self.amount * Decimal(factor), self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def scaled(self, factor: Decimal) -> "Money":
        """Decimal-safe scaling (the only sanctioned non-integer multiply)."""
        if isinstance(factor, float):
            raise TypeError("use Decimal, not float")
        return Money(self.amount * factor, self.currency)

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Money)
            and self.amount == other.amount
            and self.currency == other.currency
        )

    def __lt__(self, other: "Money") -> bool:
        self._check(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._check(other)
        return self.amount <= other.amount

    def __hash__(self):
        return hash((self.amount, self.currency))

    def as_minor_units(self) -> int:
        return int((self.amount * 100).to_integral_value(rounding=ROUND_HALF_EVEN))

    @classmethod
    def from_minor_units(cls, units: int, currency: str) -> "Money":
        return cls(Decimal(units) / 100, currency)

    def __repr__(self):
        return f"Money({self.amount}, {self.currency!r})"

    def __str__(self):
        return f"{self.amount.quantize(Decimal('0.01'))} {self.currency}"
