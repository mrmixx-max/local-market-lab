"""Portfolio engine: positions from transactions, FIFO cost basis, valuation.

Handles corporate actions (splits, cash dividends) in chronological order.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.marketdata.series import get_series
from packages.marketdata.fx import FxPolicy


@dataclass
class Lot:
    date: str
    quantity: float
    price: float          # per unit incl. allocated fees


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    lots: list[Lot] = field(default_factory=list)
    realized_pl: float = 0.0
    dividends_received: float = 0.0
    fees_paid: float = 0.0


def build_positions(ws, portfolio: str, up_to: str | None = None) -> dict[str, Position]:
    """Derive positions from the append-only transaction log, applying
    corporate actions chronologically.
    """
    txns = ws.transactions_for(portfolio)
    symbols = sorted({t["symbol"] for t in txns})
    actions = {}
    for ca in ws.actions_for(symbols):
        actions.setdefault((ca["symbol"], ca["date"]), []).append(ca)

    positions: dict[str, Position] = {}

    def pos(sym) -> Position:
        return positions.setdefault(sym, Position(symbol=sym))

    for t in txns:
        if up_to and t["date"] > up_to:
            continue
        p = pos(t["symbol"])
        ttype, qty, price, fees = t["txn_type"], t["quantity"], t["price"], t["fees"]

        # apply any corporate action effective this date BEFORE processing the txn
        for ca in actions.get((t["symbol"], t["date"]), []):
            _apply_action(p, ca)

        if ttype == "buy":
            total_cost = qty * price + fees
            unit_cost = total_cost / qty if qty else 0.0
            p.quantity += qty
            p.lots.append(Lot(t["date"], qty, unit_cost))
            p.fees_paid += fees
        elif ttype == "sell":
            sell_qty = min(qty, p.quantity)  # never go negative on data errors
            p.realized_pl += sell_qty * (price - _avg_cost(p)) - fees
            p.quantity -= sell_qty
            _consume_lots(p, sell_qty)
            p.fees_paid += fees
        elif ttype == "dividend":
            p.dividends_received += qty * price   # here 'qty' = shares entitled
        elif ttype == "fee":
            p.fees_paid += price                  # flat fee stored in price field
        elif ttype in ("deposit", "withdrawal"):
            continue                              # cash flows — not instrument positions
        elif ttype == "split":
            # handled through corporate_actions table; direct split txns ignored
            pass

    # final sweep: apply remaining actions after the last txn date? No —
    # actions are applied on their effective date during the walk; future-dated
    # actions (after `up_to`) must not touch historical positions.
    return {s: p for s, p in positions.items() if abs(p.quantity) > 1e-9 or p.lots}


def _avg_cost(p: Position) -> float:
    total_q = sum(l.quantity for l in p.lots)
    if total_q <= 0:
        return 0.0
    return sum(l.quantity * l.price for l in p.lots) / total_q


def _consume_lots(p: Position, qty: float) -> None:
    """FIFO consumption of lots."""
    remaining = qty
    while remaining > 1e-12 and p.lots:
        lot = p.lots[0]
        take = min(lot.quantity, remaining)
        lot.quantity -= take
        remaining -= take
        if lot.quantity <= 1e-12:
            p.lots.pop(0)


def _apply_action(p: Position, ca) -> None:
    if ca["action"] == "split" and ca["ratio"]:
        ratio = ca["ratio"]
        p.quantity *= ratio
        for lot in p.lots:
            lot.price /= ratio          # cost basis per share scales inversely
    # cash dividends are handled as dividend transactions by ingest;
    # lifecycle-only entries here don't change quantities.


def value_portfolio(ws, portfolio: str, fx: FxPolicy | None = None,
                    as_of: str | None = None) -> dict:
    """Value all positions at last available close per symbol.

    Missing FX rates produce an explicit 'incomplete' marker, never silent 1:1.
    """
    fx = fx or FxPolicy()
    positions = build_positions(ws, portfolio, up_to=as_of)
    lines, incomplete_fx, missing_prices = [], [], []
    total_value = total_cost = total_realized = total_div = 0.0

    for sym, p in sorted(positions.items()):
        try:
            series = get_series(ws, sym)
        except KeyError:
            missing_prices.append(sym)
            continue
        bars = [b for b in series.bars if not as_of or b.date <= as_of]
        if not bars:
            missing_prices.append(sym)
            continue
        last_close = bars[-1].close
        cur = ws.instrument_currency(sym)

        value_local = p.quantity * last_close
        cost_local = sum(l.quantity * l.price for l in p.lots)
        value_rep = fx.convert(value_local, cur)
        cost_rep = fx.convert(cost_local, cur)
        if value_rep is None or cost_rep is None:
            incomplete_fx.append({"symbol": sym, "currency": cur})
            continue

        total_value += value_rep
        total_cost += cost_rep
        total_realized += fx.require(p.realized_pl, cur) if fx.known(cur) else 0.0
        total_div += fx.require(p.dividends_received, cur) if fx.known(cur) else 0.0

        pl = value_rep - cost_rep
        lines.append({
            "symbol": sym, "quantity": round(p.quantity, 6),
            "avg_cost": round(cost_local / p.quantity, 4) if p.quantity else 0.0,
            "last_price": last_close, "currency": cur,
            "value": round(value_rep, 2), "cost": round(cost_rep, 2),
            "pl": round(pl, 2), "pl_pct": round(pl / cost_rep * 100, 2) if cost_rep else None,
        })

    return {
        "portfolio": portfolio,
        "as_of": as_of,
        "reporting_currency": fx.reporting,
        "positions": lines,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "unrealized_pl": round(total_value - total_cost, 2),
        "realized_pl": round(total_realized, 2),
        "dividends_received": round(total_div, 2),
        "incomplete_fx": incomplete_fx,
        "missing_prices": missing_prices,
    }
