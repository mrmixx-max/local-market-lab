"""Core package tests."""

from decimal import Decimal

import pytest

from packages.core.money import Money
from packages.core.dates import parse_date


class TestMoney:
    def test_basic_arithmetic(self):
        a = Money(100, "EUR")
        b = Money(50, "EUR")
        assert a + b == Money(150, "EUR")
        assert a - b == Money(50, "EUR")

    def test_mismatch_raises(self):
        with pytest.raises(ValueError):
            Money(10, "EUR") + Money(10, "USD")

    def test_float_forbidden(self):
        with pytest.raises(TypeError):
            Money(10, "EUR") * 0.5

    def test_decimal_scaling(self):
        assert Money(100, "EUR").scaled(Decimal("0.5")) == Money(50, "EUR")

    def test_quantization(self):
        assert str(Money("100.555", "EUR")) == "100.56 EUR"

    def test_minor_units_roundtrip(self):
        assert Money.from_minor_units(1999, "EUR") == Money("19.99", "EUR")
        assert Money("19.99", "EUR").as_minor_units() == 1999


class TestDates:
    def test_iso(self):
        assert parse_date("2026-03-15") == "2026-03-15"

    def test_de(self):
        assert parse_date("15.03.2026") == "2026-03-15"

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_date("not a date")
