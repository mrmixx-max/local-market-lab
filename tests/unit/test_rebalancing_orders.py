"""Tests for v1.0 P1.2 — minimum order sizes & realistic rebalancing."""
from __future__ import annotations

import pytest

from packages.portfolio.rebalancing import (
    OrderProposal,
    RebalanceOrdersResult,
    suggest_rebalance_orders,
)


def _positions(spec):
    """spec: symbol -> (quantity, price)"""
    return {s: {"quantity": q, "price": p} for s, (q, p) in spec.items()}


class TestMinOrderSize:
    def test_below_minimum_marked(self):
        # A and B at 0.5 each (10000 total). Target 0.51/0.49 -> A trade 100
        # -> below 150 min -> below minimum
        pos = _positions({"A": (50, 100.0), "B": (50, 100.0)})  # 10000 total
        res = suggest_rebalance_orders(
            pos, {"A": 0.51, "B": 0.49}, cash=0, threshold=0.001,
            default_min_order_value=150.0)
        assert res.orders_skipped_below_minimum >= 1
        assert any(p.below_minimum for p in res.proposals)

    def test_above_minimum_normal(self):
        pos = _positions({"A": (0, 1.0)})  # buy needed
        # total value = 0 + nothing; use cash to create weight
        res = suggest_rebalance_orders(
            _positions({"A": (0, 10.0), "B": (0, 10.0)}),
            {"A": 0.5, "B": 0.5}, cash=1000, threshold=0.001,
            default_min_order_value=50.0)
        a = next(p for p in res.proposals if p.symbol == "A")
        assert not a.below_minimum
        assert a.adjusted_order_quantity > 0

    def test_invalid_negative_min_raises(self):
        with pytest.raises(ValueError):
            suggest_rebalance_orders(_positions({"A": (10, 10.0)}), {"A": 1.0},
                                     cash=0, default_min_order_value=-5.0)

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError):
            suggest_rebalance_orders(_positions({"A": (10, 10.0)}), {"A": 1.0},
                                     cash=0, min_order_strategy="explode")


class TestRounding:
    def test_integer_rounding_residual_note(self):
        # drift implies 10.4 fractional shares at price 10 -> 104 value
        # raw_qty 10.4 -> round to 10, residual 0.4*10 = 4.0
        pos = _positions({"A": (0, 10.0)})
        # craft so target weight shift yields ~10.4 shares: keep simple via override
        res = suggest_rebalance_orders(
            _positions({"A": (0, 10.0), "B": (0, 10.0)}),
            {"A": 0.52, "B": 0.48}, cash=1000, threshold=0.001,
            allow_fractional=False, default_min_order_value=0.0)
        a = next(p for p in res.proposals if p.symbol == "A")
        assert a.adjusted_order_quantity == int(a.adjusted_order_quantity)
        # residual note present when rounding occurred
        if a.raw_order_quantity != a.adjusted_order_quantity:
            assert a.rounding_note is not None

    def test_fractional_mode_allows_float(self):
        pos = _positions({"A": (0, 13.37), "B": (0, 13.37)})
        res = suggest_rebalance_orders(
            pos, {"A": 0.5, "B": 0.5}, cash=1000, threshold=0.001,
            allow_fractional=True, default_min_order_value=0.0)
        a = next(p for p in res.proposals if p.symbol == "A")
        assert a.adjusted_order_quantity != int(a.adjusted_order_quantity)


class TestCosts:
    def test_fees_in_result(self):
        res = suggest_rebalance_orders(
            _positions({"A": (0, 10.0), "B": (0, 10.0)}),
            {"A": 0.5, "B": 0.5}, cash=2000, threshold=0.001,
            fee_bps=10.0, min_fee=1.0, default_min_order_value=0.0)
        assert res.total_fees_estimate > 0
        for p in res.proposals:
            assert p.fees_estimate >= 1.0  # min fee enforced

    def test_cost_benefit_status_present(self):
        res = suggest_rebalance_orders(
            _positions({"A": (0, 10.0), "B": (0, 10.0)}),
            {"A": 0.5, "B": 0.5}, cash=5000, threshold=0.001,
            default_min_order_value=0.0)
        assert res.cost_benefit_status in ("worthwhile", "marginal", "not_worthwhile")


class TestCash:
    def test_cash_after_never_negative(self):
        # tiny cash, big drift buy -> capped, cash stays >= 0
        res = suggest_rebalance_orders(
            _positions({"A": (0, 100.0), "B": (0, 100.0)}),
            {"A": 0.9, "B": 0.1}, cash=10, threshold=0.001,
            default_min_order_value=0.0)
        assert res.cash_after >= 0
        assert res.cash_after <= res.cash_before + 1e-6

    def test_no_negative_position_sell_capped(self):
        # target far below holding -> sell must not exceed holding
        pos = _positions({"A": (10, 50.0)})  # holding value 500
        res = suggest_rebalance_orders(
            pos, {"A": 0.0}, cash=0, threshold=0.001,
            default_min_order_value=0.0)
        if res.proposals:
            a = res.proposals[0]
            # adjusted sell qty <= held (10)
            assert abs(a.adjusted_order_quantity) <= 10 + 1e-6


class TestMultipleSymbols:
    def test_different_min_sizes(self):
        pos = _positions({"A": (0, 10.0), "B": (0, 10.0), "C": (0, 10.0)})
        res = suggest_rebalance_orders(
            pos, {"A": 0.34, "B": 0.33, "C": 0.33}, cash=3000,
            threshold=0.001, min_order_overrides={"A": 500.0, "B": 20.0, "C": 20.0},
            default_min_order_value=20.0)
        a = next(p for p in res.proposals if p.symbol == "A")
        b = next(p for p in res.proposals if p.symbol == "B")
        # A has high min -> likely below or skipped; B normal
        assert a.min_order_size == 500.0
        assert b.min_order_size == 20.0


class TestReproducibility:
    def test_same_input_same_output(self):
        pos_spec = {"A": (10, 10.0), "B": (5, 20.0)}
        targets = {"A": 0.4, "B": 0.6}
        r1 = suggest_rebalance_orders(_positions(pos_spec), targets, cash=500,
                                      threshold=0.001, seed=42)
        r2 = suggest_rebalance_orders(_positions(pos_spec), targets, cash=500,
                                      threshold=0.001, seed=42)
        assert r1.run_id == r2.run_id
        assert r1.data_hash == r2.data_hash
        assert r1.cash_after == r2.cash_after
        assert len(r1.proposals) == len(r2.proposals)
        for p1, p2 in zip(r1.proposals, r2.proposals):
            assert p1.adjusted_order_quantity == p2.adjusted_order_quantity
            assert p1.fees_estimate == p2.fees_estimate


class TestNoExecution:
    def test_result_has_no_order_path(self):
        res = suggest_rebalance_orders(
            _positions({"A": (0, 10.0), "B": (0, 10.0)}), {"A": 0.5, "B": 0.5},
            cash=1000, threshold=0.001)
        assert isinstance(res, RebalanceOrdersResult)
        assert res.disclaimer
        # no "placed", "executed", "routed" semantics
        assert not hasattr(res, "executed")
