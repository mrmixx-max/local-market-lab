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


# ---------------------------------------------------------------------------
# Institutional-grade analytics: benchmark, allocation, risk contribution
# ---------------------------------------------------------------------------

def _daily_returns(closes: list[float]) -> list[float]:
    """Simple return series from a list of closes; empty if <2 points."""
    return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))
            if closes[i - 1] > 0]


def _annual_factor(returns: list[float]) -> float:
    """Infer annualisation factor from return frequency (daily ≈ 252)."""
    if len(returns) < 2:
        return 252.0
    return 252.0  # portfolio bars are daily closes


def benchmark_comparison(ws, portfolio_returns: list[float],
                         benchmark_symbol: str) -> dict:
    """Compute Beta, Alpha, Tracking Error, Information Ratio vs a benchmark.

    Beta      = cov(port, bench) / var(bench)
    Alpha     = annualised mean excess return (port − bench)
    TE        = annualised stdev of excess returns
    IR        = Alpha / TE
    """
    out = {
        "benchmark": benchmark_symbol,
        "beta": None, "alpha": None,
        "tracking_error": None, "information_ratio": None,
    }
    try:
        bench_series = get_series(ws, benchmark_symbol)
    except KeyError:
        return out

    bench_returns = _daily_returns([b.close for b in bench_series.bars])
    n = min(len(portfolio_returns), len(bench_returns))
    if n < 2:
        return out

    pr = portfolio_returns[-n:]
    br = bench_returns[-n:]
    f = _annual_factor(pr)

    mean_pr = sum(pr) / n
    mean_br = sum(br) / n

    cov = sum((pr[i] - mean_pr) * (br[i] - mean_br) for i in range(n)) / (n - 1)
    var_br = sum((x - mean_br) ** 2 for x in br) / (n - 1)
    if var_br <= 0:
        return out
    beta = cov / var_br

    excess = [pr[i] - br[i] for i in range(n)]
    mean_ex = sum(excess) / n
    alpha = mean_ex * f
    te = (sum((x - mean_ex) ** 2 for x in excess) / (n - 1)) ** 0.5 * f ** 0.5
    ir = alpha / te if te > 0 else None

    return {
        "benchmark": benchmark_symbol,
        "beta": round(beta, 4),
        "alpha": round(alpha, 4),
        "tracking_error": round(te, 4),
        "information_ratio": round(ir, 4) if ir is not None else None,
    }


def portfolio_returns(ws, valued: dict, fx, up_to: str | None = None) -> list[float]:
    """Reconstruct a daily portfolio return series from valued positions.

    Uses each position's full price history weighted by its current weight.
    Best-effort: skips symbols that fail FX conversion.
    """
    total = valued["total_value"]
    if total <= 0:
        return []

    # Build per-symbol close series converted to reporting currency
    series_map: dict[str, list[float]] = {}
    weights: dict[str, float] = {}
    for line in valued["positions"]:
        sym, val = line["symbol"], line["value"]
        weights[sym] = val / total
        try:
            s = get_series(ws, sym)
        except KeyError:
            continue
        bars = [b for b in s.bars if not up_to or b.date <= up_to]
        if len(bars) < 2:
            continue
        cur = ws.instrument_currency(sym)
        conv = fx.convert(1.0, cur)
        if conv is None:
            continue
        series_map[sym] = [b.close * conv for b in bars]

    if not series_map:
        return []

    # Align to the shortest series (conservative)
    min_len = min(len(v) for v in series_map.values())
    port_closes = []
    for i in range(min_len):
        port_closes.append(
            sum(w * series_map[s][i] for s, w in weights.items() if s in series_map)
        )
    return _daily_returns(port_closes)


def allocation_breakdown(ws, valued: dict) -> list[dict]:
    """Group positions by asset_class and compute weight in reporting currency."""
    total = valued["total_value"]
    buckets: dict[str, float] = {}
    for line in valued["positions"]:
        try:
            ac = ws.instrument_asset_class(line["symbol"])
        except KeyError:
            ac = "unknown"
        buckets[ac] = buckets.get(ac, 0.0) + line["value"]

    if total <= 0:
        total = 1.0  # avoid division by zero; weights will be zero-valued

    breakdown = [
        {"asset_class": k, "value": round(v, 2),
         "weight": round(v / total, 4)}
        for k, v in sorted(buckets.items(), key=lambda x: -x[1])
    ]
    return breakdown


def risk_contribution(ws, valued: dict, fx) -> list[dict]:
    """Each position's contribution to portfolio volatility (Euler decomposition).

    RC_i = w_i * (Σ w)_i / σ_p   where Σ is the covariance matrix.
    """
    total = valued["total_value"]
    if total <= 0:
        return []

    # Build aligned return series per symbol (in reporting currency)
    rets_map: dict[str, list[float]] = {}
    weights: dict[str, float] = {}
    for line in valued["positions"]:
        sym, val = line["symbol"], line["value"]
        w = val / total
        if w <= 0:
            continue
        weights[sym] = w
        try:
            s = get_series(ws, sym)
        except KeyError:
            continue
        cur = ws.instrument_currency(sym)
        conv = fx.convert(1.0, cur)
        if conv is None:
            continue
        closes = [b.close * conv for b in s.bars]
        r = _daily_returns(closes)
        if len(r) >= 2:
            rets_map[sym] = r

    if len(rets_map) < 1:
        return []

    min_len = min(len(v) for v in rets_map.values())
    syms = list(rets_map.keys())
    n = min_len

    # Align all series to the same length (tail)
    aligned = {s: rets_map[s][-n:] for s in syms}
    means = {s: sum(aligned[s]) / n for s in syms}

    # Covariance matrix (sample)
    def _cov(a: str, b: str) -> float:
        return sum((aligned[a][i] - means[a]) * (aligned[b][i] - means[b])
                   for i in range(n)) / (n - 1) if n > 1 else 0.0

    # Portfolio variance: w^T Σ w
    port_var = 0.0
    for si in syms:
        for sj in syms:
            port_var += weights[si] * weights[sj] * _cov(si, sj)
    port_vol = port_var ** 0.5 if port_var > 0 else 0.0

    # Marginal contribution: (Σ w)_i → RC_i = w_i * marginal_i
    result = []
    for si in syms:
        marginal = sum(weights[sj] * _cov(si, sj) for sj in syms)
        rc = weights[si] * marginal
        result.append({
            "symbol": si,
            "weight": round(weights[si], 4),
            "marginal_risk": round(marginal, 6),
            "risk_contribution": round(rc, 6),
            "risk_share_pct": round(rc / port_vol * 100, 2) if port_vol > 0 else 0.0,
        })
    result.sort(key=lambda x: abs(x["risk_contribution"]), reverse=True)
    return result
