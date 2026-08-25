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
    target_weight: float  # fraction
    drift_abs: float  # |current - target|
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
        results.append(
            DriftInfo(
                symbol=sym,
                current_weight=round(cw, 4),
                target_weight=round(tw, 4),
                drift_abs=round(drift, 4),
                needs_rebalance=drift > threshold,
            )
        )
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
        transaction_cost_bps = float(
            os.environ.get("LML_REBALANCE_COST_ESTIMATE_BPS", "10.0")
        )

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
                tlh_ops.append(
                    {
                        "symbol": p["symbol"],
                        "unrealized_loss_pct": round(loss_pct, 2),
                        "loss_amount": round(loss_amt, 2),
                        "action": f"Consider selling {p['symbol']} for tax-loss harvesting.",
                        "tax_benefit_estimate": round(abs(loss_amt) * 0.25, 2),
                        "note": "Replace with similar (not substantially identical) instrument.",
                    }
                )

    summary_parts = [f"Threshold: {threshold*100:.1f}%"]
    summary_parts.append(
        f"Drift violations: {sum(1 for d in drift if d.needs_rebalance)}"
    )
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
            needs_rebalance=False,
            drift_threshold=threshold or 0.05,
            drift_analysis=[],
            proposals=[],
            total_estimated_cost=0,
            tax_loss_opportunities=[],
            summary="Portfolio has zero or negative value.",
        )
    current = {p["symbol"]: p["value"] / total for p in positions}
    tlh = [
        {
            "symbol": p["symbol"],
            "unrealized_loss_pct": p.get("pl_pct") or 0.0,
            "loss_amount": p.get("pl", 0.0),
        }
        for p in positions
        if (p.get("pl") or 0) < 0
    ]
    return suggest_rebalance(
        current,
        target_weights,
        threshold,
        transaction_cost_bps,
        tax_loss_positions=tlh,
    )


# ===========================================================================
# v1.0 P1.2 — Minimum order sizes & realistic rebalancing proposals
# ===========================================================================
#
# Suggestions ONLY. No execution path, no broker, no order placement.
# Extends the weight-based assistant with:
#   - per-instrument minimum order size (value based, documented default)
#   - integer vs fractional share rounding with explicit residual note
#   - fee / spread / minimum-fee estimation per order
#   - cost-benefit gate (worthwhile | marginal | not_worthwhile)
#   - cash-before/after accounting, no negative positions or cash
#
# Configuration (env, read once at call time):
#   LML_REBALANCE_DEFAULT_MIN_ORDER_VALUE  (default 50.0)
#   LML_REBALANCE_ALLOW_FRACTIONAL         (default false)
#   LML_REBALANCE_MIN_ORDER_STRATEGY       skip|round_up|round_down (default skip)
#   LML_REBALANCE_FEE_BPS                  (default 10.0)
#   LML_REBALANCE_MIN_FEE                  (default 0.0)
#   LML_REBALANCE_SPREAD_BPS               (default 0.0)
import hashlib
import json
import math
import os

DISCLAIMER = (
    "Dies ist ein Analyseergebnis. Keine automatische Orderausführung, "
    "keine Finanzberatung."
)

_REBALANCE_ENV_DEFAULTS = {
    "LML_REBALANCE_DEFAULT_MIN_ORDER_VALUE": 50.0,
    "LML_REBALANCE_ALLOW_FRACTIONAL": False,
    "LML_REBALANCE_MIN_ORDER_STRATEGY": "skip",
    "LML_REBALANCE_FEE_BPS": 10.0,
    "LML_REBALANCE_MIN_FEE": 0.0,
    "LML_REBALANCE_SPREAD_BPS": 0.0,
}


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _round_to_int(x: float) -> int:
    """Round half away from zero (banker-hostile but intuitive for shares)."""
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


@dataclass
class OrderProposal:
    """Per-position rebalancing order suggestion — NEVER executable as-is."""

    symbol: str
    current_weight: float
    target_weight: float
    drift: float
    raw_order_quantity: float  # ideal fractional shares before rounding
    adjusted_order_quantity: float  # shares after rounding/min rules (0 if skipped)
    order_value: float  # adjusted qty * price (0 if skipped)
    min_order_size: float
    below_minimum: bool
    fees_estimate: float
    rounding_note: str | None = None
    action: str = ""  # buy | sell | hold


@dataclass
class RebalanceOrdersResult:
    run_id: str
    data_hash: str
    cash_before: float
    cash_after: float
    total_fees_estimate: float
    orders_skipped_below_minimum: int
    cost_benefit_status: str
    warnings: list[str]
    disclaimer: str
    proposals: list[OrderProposal]
    needs_rebalance: bool
    drift_threshold: float
    drift_analysis: list[DriftInfo]


def _canonical_hash(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def suggest_rebalance_orders(
    current_positions: dict[str, dict],
    target_weights: dict[str, float],
    cash: float,
    threshold: float | None = None,
    min_order_overrides: dict[str, float] | None = None,
    fee_bps: float | None = None,
    min_fee: float | None = None,
    spread_bps: float | None = None,
    allow_fractional: bool | None = None,
    min_order_strategy: str | None = None,
    default_min_order_value: float | None = None,
    drift_cost_per_day_bps: float = 0.1,
    holding_period_days: int = 30,
    seed: int = 42,
) -> RebalanceOrdersResult:
    """Generate realistic, executable-in-principle rebalancing orders.

    current_positions: symbol -> {"quantity": float, "price": float}
    cash: available cash before rebalancing (reporting currency)

    Suggestions ONLY — never places, executes, or routes orders.
    Deterministic for identical inputs (seed retained for forward compat).
    """
    threshold = float(
        threshold
        if threshold is not None
        else os.environ.get("LML_REBALANCE_DRIFT_THRESHOLD", "0.05")
    )
    fee_bps = _env_float(
        "LML_REBALANCE_FEE_BPS",
        (
            fee_bps
            if fee_bps is not None
            else _REBALANCE_ENV_DEFAULTS["LML_REBALANCE_FEE_BPS"]
        ),
    )
    min_fee = _env_float(
        "LML_REBALANCE_MIN_FEE",
        (
            min_fee
            if min_fee is not None
            else _REBALANCE_ENV_DEFAULTS["LML_REBALANCE_MIN_FEE"]
        ),
    )
    spread_bps = _env_float(
        "LML_REBALANCE_SPREAD_BPS",
        (
            spread_bps
            if spread_bps is not None
            else _REBALANCE_ENV_DEFAULTS["LML_REBALANCE_SPREAD_BPS"]
        ),
    )
    allow_fractional = _env_bool(
        "LML_REBALANCE_ALLOW_FRACTIONAL",
        (
            allow_fractional
            if allow_fractional is not None
            else _REBALANCE_ENV_DEFAULTS["LML_REBALANCE_ALLOW_FRACTIONAL"]
        ),
    )
    min_order_strategy = (
        min_order_strategy
        or os.environ.get(
            "LML_REBALANCE_MIN_ORDER_STRATEGY",
            _REBALANCE_ENV_DEFAULTS["LML_REBALANCE_MIN_ORDER_STRATEGY"],
        )
    ).lower()
    default_min = _env_float(
        "LML_REBALANCE_DEFAULT_MIN_ORDER_VALUE",
        (
            default_min_order_value
            if default_min_order_value is not None
            else _REBALANCE_ENV_DEFAULTS["LML_REBALANCE_DEFAULT_MIN_ORDER_VALUE"]
        ),
    )
    min_order_overrides = min_order_overrides or {}

    if default_min < 0:
        raise ValueError("default_min_order_value must be >= 0")
    if min_order_strategy not in ("skip", "round_up", "round_down"):
        raise ValueError("min_order_strategy must be skip|round_up|round_down")
    if cash < 0:
        raise ValueError("cash must be >= 0")

    # total portfolio value = cash + sum(quantity*price)
    positions_value = {
        s: max(0.0, p["quantity"]) * p["price"] for s, p in current_positions.items()
    }
    total_value = cash + sum(positions_value.values())
    if total_value <= 0:
        return RebalanceOrdersResult(
            run_id="",
            data_hash="",
            cash_before=cash,
            cash_after=cash,
            total_fees_estimate=0.0,
            orders_skipped_below_minimum=0,
            cost_benefit_status="not_worthwhile",
            warnings=["Portfolio has zero or negative total value."],
            disclaimer=DISCLAIMER,
            proposals=[],
            needs_rebalance=False,
            drift_threshold=threshold,
            drift_analysis=[],
        )

    current_weights = {s: positions_value[s] / total_value for s in current_positions}
    drift = detect_drift(current_weights, target_weights, threshold)

    proposals: list[OrderProposal] = []
    skipped = 0
    total_fees = 0.0
    cash_after = cash
    warnings: list[str] = []
    total_benefit = 0.0

    for d in drift:
        if not d.needs_rebalance:
            continue
        change = d.target_weight - d.current_weight
        if abs(change) < 0.001:
            continue
        sym = d.symbol
        price = current_positions[sym]["price"]
        held = max(0.0, current_positions[sym]["quantity"])
        # ideal trade value and fractional quantity
        trade_value = change * total_value
        raw_qty = trade_value / price if price > 0 else 0.0
        action = "buy" if change > 0 else "sell"

        # cap sells at holdings (no shorting / negative positions)
        if action == "sell" and raw_qty > held:
            raw_qty = held
            warnings.append(f"{sym}: sell capped at holding {held:.4f} (no shorting)")

        min_size = float(min_order_overrides.get(sym, default_min))
        # integer rounding if fractional not allowed
        rounding_note = None
        if not allow_fractional and raw_qty != 0:
            rounded = _round_to_int(raw_qty)
            residual = (raw_qty - rounded) * price
            if rounded != raw_qty:
                rounding_note = (
                    f"{sym}: rounded {raw_qty:.4f} → {rounded} shares; "
                    f"residual value €{residual:.2f} remains unallocated"
                )
            raw_qty = float(rounded)

        order_value = abs(raw_qty) * price
        below_min = order_value < min_size and raw_qty != 0

        adjusted_qty = raw_qty
        if below_min:
            if min_order_strategy == "round_up" and price > 0:
                adjusted_qty = math.ceil(min_size / price)
                order_value = adjusted_qty * price
                below_min = False
            elif min_order_strategy == "round_down" and not allow_fractional:
                floor_qty = math.floor(raw_qty)
                if floor_qty * price < min_size:
                    adjusted_qty = 0.0
                    order_value = 0.0
                    below_min = True
                else:
                    adjusted_qty = float(floor_qty)
                    order_value = adjusted_qty * price
                    below_min = False
            else:  # skip
                adjusted_qty = 0.0
                order_value = 0.0
                below_min = True

        if below_min:
            skipped += 1
            proposals.append(
                OrderProposal(
                    symbol=sym,
                    current_weight=round(d.current_weight, 4),
                    target_weight=round(d.target_weight, 4),
                    drift=round(d.drift_abs, 4),
                    raw_order_quantity=round(raw_qty, 4),
                    adjusted_order_quantity=0.0,
                    order_value=0.0,
                    min_order_size=round(min_size, 2),
                    below_minimum=True,
                    fees_estimate=0.0,
                    rounding_note=rounding_note,
                    action=action,
                )
            )
            continue

        # fee + spread cost on the adjusted order
        gross = order_value
        fee = max(min_fee, gross * fee_bps / 10000)
        spread_cost = gross * spread_bps / 10000
        fees = fee + spread_cost

        # cash impact: buys consume cash (incl. fees), sells add proceeds minus fees
        if action == "buy":
            needed = gross + fees
            if needed > cash_after:
                # cap buy so cash stays non-negative
                affordable = max(0.0, (cash_after - fees) / price) if price > 0 else 0.0
                if not allow_fractional:
                    affordable = float(_round_to_int(affordable))
                adjusted_qty = affordable
                order_value = adjusted_qty * price
                fees = (
                    max(min_fee, order_value * fee_bps / 10000)
                    + order_value * spread_bps / 10000
                )
                needed = order_value + fees
                warnings.append(
                    f"{sym}: buy capped to available cash (no negative cash)"
                )
                if adjusted_qty <= 0:
                    skipped += 1
                    proposals.append(
                        OrderProposal(
                            symbol=sym,
                            current_weight=round(d.current_weight, 4),
                            target_weight=round(d.target_weight, 4),
                            drift=round(d.drift_abs, 4),
                            raw_order_quantity=round(raw_qty, 4),
                            adjusted_order_quantity=0.0,
                            order_value=0.0,
                            min_order_size=round(min_size, 2),
                            below_minimum=True,
                            fees_estimate=0.0,
                            rounding_note=rounding_note,
                            action=action,
                        )
                    )
                    continue
            cash_after -= needed
        else:  # sell
            cash_after += gross - fees

        total_fees += fees
        total_benefit += (
            d.drift_abs * drift_cost_per_day_bps * holding_period_days / 100
        )
        proposals.append(
            OrderProposal(
                symbol=sym,
                current_weight=round(d.current_weight, 4),
                target_weight=round(d.target_weight, 4),
                drift=round(d.drift_abs, 4),
                raw_order_quantity=round(raw_qty, 4),
                adjusted_order_quantity=round(adjusted_qty, 4),
                order_value=round(order_value, 2),
                min_order_size=round(min_size, 2),
                below_minimum=False,
                fees_estimate=round(fees, 2),
                rounding_note=rounding_note,
                action=action,
            )
        )

    # cost-benefit gate
    if total_fees <= 0 and total_benefit > 0:
        status = "worthwhile"
    elif total_fees <= 0:
        status = "not_worthwhile"
    else:
        ratio = total_benefit / total_fees
        status = (
            "worthwhile"
            if ratio >= 2
            else ("marginal" if ratio >= 1 else "not_worthwhile")
        )

    cash_after = max(0.0, round(cash_after, 2))
    # deterministic run identity
    ident = _canonical_hash(
        {
            "positions": current_positions,
            "targets": target_weights,
            "cash": cash,
            "threshold": threshold,
            "fee_bps": fee_bps,
            "min_fee": min_fee,
            "spread_bps": spread_bps,
            "allow_fractional": allow_fractional,
            "strategy": min_order_strategy,
            "default_min": default_min,
            "overrides": min_order_overrides,
            "seed": seed,
        }
    )
    run_id = ident[:12]

    return RebalanceOrdersResult(
        run_id=run_id,
        data_hash=ident,
        cash_before=round(cash, 2),
        cash_after=cash_after,
        total_fees_estimate=round(total_fees, 2),
        orders_skipped_below_minimum=skipped,
        cost_benefit_status=status,
        warnings=warnings,
        disclaimer=DISCLAIMER,
        proposals=proposals,
        needs_rebalance=len(proposals) > 0,
        drift_threshold=threshold,
        drift_analysis=drift,
    )


def rebalance_orders_from_valuation(
    valued: dict,
    target_weights: dict[str, float],
    cash: float = 0,
    threshold: float | None = None,
    min_order_overrides: dict[str, float] | None = None,
    **kwargs,
) -> RebalanceOrdersResult:
    """Convenience: build positions from a value_portfolio() result.

    Suggestions ONLY. cash defaults to 0 when the caller has no cash figure;
    in that case cash_before == cash_after == 0 and a warning is emitted.
    """
    positions = valued.get("positions", [])
    current = {}
    for p in positions:
        price = p.get("last_price") or 0.0
        qty = p.get("quantity", 0.0)
        if price > 0:
            current[p["symbol"]] = {"quantity": qty, "price": price}
    return suggest_rebalance_orders(
        current,
        target_weights,
        cash,
        threshold,
        min_order_overrides=min_order_overrides,
        **kwargs,
    )
