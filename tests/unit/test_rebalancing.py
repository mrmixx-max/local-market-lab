"""Tests for rebalancing assistant: drift detection, proposals, tax-loss harvesting.

Verifies that the assistant NEVER executes trades — only RebalancingProposal
suggestions are generated.
"""

from __future__ import annotations

import pytest

from packages.portfolio.rebalancing import (
    detect_drift,
    rebalance_from_valuation,
    suggest_rebalance,
)


class TestDetectDrift:
    def test_no_drift(self):
        weights = {"A": 0.5, "B": 0.3, "C": 0.2}
        result = detect_drift(weights, weights, threshold=0.05)
        assert all(not d.needs_rebalance for d in result)

    def test_drift_detected(self):
        current = {"A": 0.60, "B": 0.25, "C": 0.15}
        target = {"A": 0.50, "B": 0.30, "C": 0.20}
        result = detect_drift(current, target, threshold=0.05)
        a_drift = next(d for d in result if d.symbol == "A")
        assert a_drift.needs_rebalance
        assert a_drift.drift_abs == pytest.approx(0.10)

    def test_missing_symbol_in_target(self):
        current = {"A": 0.7, "B": 0.3}
        target = {"A": 0.5, "B": 0.3, "C": 0.2}
        result = detect_drift(current, target, threshold=0.05)
        c_drift = next(d for d in result if d.symbol == "C")
        assert c_drift.current_weight == 0.0
        assert c_drift.needs_rebalance

    def test_default_threshold_from_env(self, monkeypatch):
        monkeypatch.setenv("LML_REBALANCE_DRIFT_THRESHOLD", "0.10")
        current = {"A": 0.58, "B": 0.42}
        target = {"A": 0.50, "B": 0.50}
        result = detect_drift(current, target)
        a_drift = next(d for d in result if d.symbol == "A")
        assert not a_drift.needs_rebalance  # 0.08 < 0.10


class TestSuggestRebalance:
    def test_suggests_proposals_on_drift(self):
        current = {"A": 0.65, "B": 0.20, "C": 0.15}
        target = {"A": 0.50, "B": 0.30, "C": 0.20}
        result = suggest_rebalance(current, target, threshold=0.05)
        assert result.needs_rebalance
        assert len(result.proposals) > 0
        # A should be sold
        a_prop = next((p for p in result.proposals if p.symbol == "A"), None)
        assert a_prop is not None
        assert a_prop.action == "sell"
        assert a_prop.estimated_cost > 0

    def test_no_proposals_when_within_threshold(self):
        current = {"A": 0.52, "B": 0.28, "C": 0.20}
        target = {"A": 0.50, "B": 0.30, "C": 0.20}
        result = suggest_rebalance(current, target, threshold=0.05)
        assert not result.needs_rebalance
        assert len(result.proposals) == 0

    def test_proposal_has_tax_impact_field(self):
        current = {"A": 0.65, "B": 0.35}
        target = {"A": 0.50, "B": 0.50}
        result = suggest_rebalance(current, target, threshold=0.05)
        for p in result.proposals:
            assert hasattr(p, "tax_impact")
            assert hasattr(p, "drift")

    def test_no_trade_execution(self):
        """Verify that suggest_rebalance NEVER executes trades."""
        current = {"A": 0.65, "B": 0.35}
        target = {"A": 0.50, "B": 0.50}
        result = suggest_rebalance(current, target, threshold=0.05)
        # Result only contains proposals, no execution flags
        assert isinstance(result.proposals, list)
        assert not hasattr(result, "executed")
        assert not hasattr(result, "orders")


class TestTaxLossHarvesting:
    def test_flags_loss_positions(self):
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.5, "B": 0.5}
        tlh = [{"symbol": "B", "unrealized_loss_pct": -15.0, "loss_amount": -7500.0}]
        result = suggest_rebalance(
            current, target, threshold=0.05, tax_loss_positions=tlh
        )
        assert len(result.tax_loss_opportunities) == 1
        assert result.tax_loss_opportunities[0]["symbol"] == "B"
        assert "tax_benefit_estimate" in result.tax_loss_opportunities[0]

    def test_ignores_small_losses(self):
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.5, "B": 0.5}
        tlh = [{"symbol": "B", "unrealized_loss_pct": -3.0, "loss_amount": -100.0}]
        result = suggest_rebalance(
            current, target, threshold=0.05, tax_loss_positions=tlh
        )
        assert len(result.tax_loss_opportunities) == 0

    def test_tlh_is_information_only(self):
        """TLH output must be informational, not an execution instruction."""
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.5, "B": 0.5}
        tlh = [{"symbol": "B", "unrealized_loss_pct": -20.0, "loss_amount": -10000.0}]
        result = suggest_rebalance(
            current, target, threshold=0.05, tax_loss_positions=tlh
        )
        opp = result.tax_loss_opportunities[0]
        assert "action" in opp
        assert "note" in opp  # includes disclaimer


class TestRebalanceFromValuation:
    def test_equal_weight_target(self):
        valued = {
            "total_value": 100000.0,
            "positions": [
                {"symbol": "A", "value": 60000.0, "pl": 5000.0, "pl_pct": 9.1},
                {"symbol": "B", "value": 30000.0, "pl": -2000.0, "pl_pct": -6.2},
                {"symbol": "C", "value": 10000.0, "pl": -500.0, "pl_pct": -4.8},
            ],
        }
        target = {"A": 0.333, "B": 0.333, "C": 0.334}
        result = rebalance_from_valuation(valued, target, threshold=0.05)
        assert result.needs_rebalance
        assert any(p.symbol == "A" and p.action == "sell" for p in result.proposals)

    def test_empty_portfolio(self):
        valued = {"total_value": 0, "positions": []}
        result = rebalance_from_valuation(valued, {}, 0.05)
        assert not result.needs_rebalance

    def test_tlh_from_valuation(self):
        valued = {
            "total_value": 100000.0,
            "positions": [
                {"symbol": "A", "value": 50000.0, "pl": 2000.0, "pl_pct": 4.2},
                {"symbol": "B", "value": 50000.0, "pl": -8000.0, "pl_pct": -13.8},
            ],
        }
        target = {"A": 0.5, "B": 0.5}
        result = rebalance_from_valuation(valued, target, threshold=0.05)
        assert len(result.tax_loss_opportunities) == 1
        assert result.tax_loss_opportunities[0]["symbol"] == "B"
