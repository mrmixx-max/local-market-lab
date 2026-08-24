"""FX policy — explicit conversion, no silent 1:1.

Per addendum II: missing FX rates produce an 'incomplete' state, never a
silent 1.0 conversion.
"""
from __future__ import annotations


class FxPolicy:
    """Holds explicit FX rates (quote currency -> reporting currency)."""

    def __init__(self, reporting_currency: str = "EUR",
                 rates: dict[str, float] | None = None):
        self.reporting = reporting_currency.upper()
        # rate: 1 unit of currency -> reporting currency
        self.rates = {self.reporting: 1.0}
        for cur, rate in (rates or {}).items():
            self.set_rate(cur, rate)

    def set_rate(self, currency: str, rate: float) -> None:
        if rate <= 0:
            raise ValueError("fx rate must be positive")
        self.rates[currency.upper()] = rate

    def known(self, currency: str) -> bool:
        return currency.upper() in self.rates

    def convert(self, amount: float, from_currency: str,
                date_iso: str | None = None) -> float | None:
        """Convert to reporting currency.

        Returns None when the rate is unknown — callers must treat the result
        as INCOMPLETE and report it, never default to 1:1.
        """
        cur = from_currency.upper()
        if cur == self.reporting:
            return amount
        rate = self.rates.get(cur)
        if rate is None:
            return None
        return amount * rate

    def require(self, amount: float, from_currency: str) -> float:
        out = self.convert(amount, from_currency)
        if out is None:
            raise KeyError(
                f"missing FX rate {from_currency}->{self.reporting}; "
                "result would be incomplete")
        return out
