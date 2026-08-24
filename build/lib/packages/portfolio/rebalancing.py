"""Rebalancing assistant: drift detection, suggestions, tax-loss harvesting.

@experimental — Suggestions only, NEVER executes trades.

Configuration via .env:
- LML_REBALANCE_DRIFT_THRESHOLD (default: 0.05)
- LML_REBALANCE_COST_ESTIMATE_BPS (default: 10)
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from packages.domain.entities import RebalancingProposal


@dataclass
class DriftInfo:
    symbol: str
    current_weight: float  # fraction
    target_weight: float   # fraction
    drift_abs: float       # |current - target|
    needs_rebalance: bool


@dataclass
class RebalanceResult:
    needs_rebalance: bool
    drift_threshold: float
    drift_analysis: list[DriftInfo]
    proposals: list[RebalancingProposal]
    total_estimated_cost: float
    tax_loss_opportunities: list[dict]
    summary: str


def detect_drift(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    threshold: float | None = None,
) -> list[DriftInfo]:
    """Identify positions where |current - target| exceeds threshold.

    Threshold from LML_REBALANCE_DRIFT_THRESHOLD env or parameter.
    """
    if threshold is None:
        threshold = float(os.environ.get("LML_REBALANCE_DRIFT_THRESHOLD", "0.05"))
    all_syms = set(current_weights) | set(target_weights)
    results: list[DriftInfo] = []
    for sym in sorted(all_syms):
        cw = current_weights.get(sym, 0.0)
        tw = target_weights.get(sym, 0.0)
        drift = abs(cw - tw)
        results.append(DriftInfo(
            symbol=sym,
            current_weight=round(cw, 4),
            target_weight=round(tw, 4),
            drift_abs=round(drift, 4),
            needs_rebalance=drift > threshold,
        ))
    return results


def suggest_rebalance(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    threshold: float | None = None,
    transaction_cost_bps: float | None = None,
    drift_cost_per_day_bps: float = 0.1,
    holding_period_days: int = 30,
    tax_loss_positions: list[dict] | None = None,
) -> RebalanceResult:
    """Generate rebalancing proposals with cost-benefit analysis.

    NEVER executes trades — only generates RebalancingProposal suggestions.

    Cost: transaction fees.
    Benefit: tracking error reduction over holding period.
    Net = benefit - cost. Only suggest if net > 0 or drift > 2x threshold.
    """
    if threshold is None:
        threshold = float(os.environ.get("LML_REBALANCE_DRIFT_THRESHOLD", "0.05"))
    if transaction_cost_bps is None:
        transaction_cost_bps = float(os.environ.get("LML_REBALANCE_COST_ESTIMATE_BPS", "10.0"))

    drift = detect_drift(current_weights, target_weights, threshold)
    proposals: list[RebalancingProposal] = []
    total_cost = 0.0

    for d in drift:
        if not d.needs_rebalance:
            continue
        change = d.target_weight - d.current_weight
        if abs(change) < 0.001:
            continue
        action = "buy" if change > 0 else "sell"
        cost = abs(change) * transaction_cost_bps / 10000  # convert bps to fraction
        benefit = d.drift_abs * drift_cost_per_day_bps * holding_period_days / 100
        net = benefit - cost

        if d.drift_abs > 2 * threshold or net > 0:
            prop = RebalancingProposal(
                symbol=d.symbol,
                current_weight=round(d.current_weight, 4),
                target_weight=round(d.target_weight, 4),
                drift=round(d.drift_abs, 4),
                action=action,
                estimated_cost=round(cost, 6),
                tax_impact=0.0,
            )
            proposals.append(prop)
            total_cost += cost

    # Tax-loss harvesting indicator (information only, no execution)
    tlh_ops: list[dict] = []
    if tax_loss_positions:
        for p in tax_loss_positions:
            loss_pct = p.get("unrealized_loss_pct", 0.0)
            if loss_pct < -5.0:
                loss_amt = p.get("loss_amount", 0.0)
                tlh_ops.append({
                    "symbol": p["symbol"],
                    "unrealized_loss_pct": round(loss_pct, 2),
                    "loss_amount": round(loss_amt, 2),
                    "action": f"Consider selling {p['symbol']} for tax-loss harvesting.",
                    "tax_benefit_estimate": round(abs(loss_amt) * 0.25, 2),
                    "note": "Replace with similar (not substantially identical) instrument.",
                })

    summary_parts = [f"Threshold: {threshold*100:.1f}%"]
    summary_parts.append(f"Drift violations: {sum(1 for d in drift if d.needs_rebalance)}")
    summary_parts.append(f"Proposals: {len(proposals)}")
    if tlh_ops:
        summary_parts.append(f"TLH opportunities: {len(tlh_ops)}")
    summary_parts.append(f"Total est. cost: {total_cost:.4f}")

    return RebalanceResult(
        needs_rebalance=len(proposals) > 0,
        drift_threshold=threshold,
        drift_analysis=drift,
        proposals=proposals,
        total_estimated_cost=round(total_cost, 6),
        tax_loss_opportunities=tlh_ops,
        summary="; ".join(summary_parts),
    )


def rebalance_from_valuation(
    valued: dict,
    target_weights: dict[str, float],
    threshold: float | None = None,
    transaction_cost_bps: float | None = None,
) -> RebalanceResult:
    """Convenience: build current weights from a valuation result.

    NEVER executes trades — only generates proposals.
    """
    positions = valued.get("positions", [])
    total = valued.get("total_value", 0)
    if total <= 0:
        return RebalanceResult(
            needs_rebalance=False, drift_threshold=threshold or 0.05,
            drift_analysis=[], proposals=[], total_estimated_cost=0,
            tax_loss_opportunities=[],
            summary="Portfolio has zero or negative value.",
        )
    current = {p["symbol"]: p["value"] / total for p in positions}
    tlh = [
        {"symbol": p["symbol"],
         "unrealized_loss_pct": p.get("pl_pct") or 0.0,
         "loss_amount": p.get("pl", 0.0)}
        for p in positions if (p.get("pl") or 0) < 0
    ]
    return suggest_rebalance(
        current, target_weights, threshold, transaction_cost_bps,
        tax_loss_positions=tlh,
    )
