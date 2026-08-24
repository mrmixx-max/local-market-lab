"""Local Market Lab CLI.

  lml demo                       seed synthetic data + run full pipeline
  lml import txn FILE --portfolio P
  lml import prices FILE SYMBOL
  lml portfolio NAME             valuation report
  lml backtest NAME [--strategy buy-and-hold|rebalance-quarterly]
  lml scenario mc SYMBOL | bootstrap SYMBOL | replay NAME
  lml report ...                 markdown export
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

app = typer.Typer(help="Local Market Lab — research tool, no investment advice.",
                  no_args_is_help=True)

DB_OPT = typer.Option("./data/marketlab.db", "--db", envvar="LML_DB")


def _ws(db: str):
    from packages.storage.workspace import Workspace
    return Workspace(db)


@app.command()
def demo(db: str = DB_OPT):
    """Seed synthetic fixtures and print a quick end-to-end summary."""
    ws = _ws(db)
    from packages.ingest.fixtures import load_demo
    report = load_demo(ws)
    typer.echo(f"prices imported: {report['prices']}")
    typer.echo(f"transactions inserted: {report['transactions']['inserted']}")

    from packages.portfolio.engine import value_portfolio
    val = value_portfolio(ws, "demo")
    typer.echo(f"\nportfolio 'demo': value={val['total_value']:,.2f} "
               f"cost={val['total_cost']:,.2f} P/L={val['unrealized_pl']:+,.2f} "
               f"{val['reporting_currency']}")

    from packages.backtest.engine import (Assumptions, BuyAndHold,
                                          PeriodicRebalance, run_backtest)
    from packages.marketdata.series import aligned_closes
    dates, prices = aligned_closes(ws, ["IWDA", "EIMI", "AGGH"])
    for strat in (BuyAndHold(), PeriodicRebalance(63)):
        r = run_backtest(prices, strat, Assumptions())
        m = r["metrics"]
        typer.echo(f"{strat.name:<22} CAGR={m['cagr_pct']:>7}%  MaxDD={m['max_drawdown_pct']:>6}%  "
                   f"Sharpe={m['sharpe']:>6}")
    typer.echo("\n(research output — not investment advice)")


@app.command()
def portfolio(name: str, db: str = DB_OPT):
    """Valuation of a portfolio."""
    from packages.portfolio.engine import value_portfolio
    import json as _json
    val = value_portfolio(_ws(db), name)
    typer.echo(_json.dumps(val, indent=2))


@app.command()
def backtest(name: str, strategy: str = "buy-and-hold", db: str = DB_OPT,
             fees_bps: float = 10.0, slippage_bps: float = 5.0):
    """Run a backtest on an imported portfolio."""
    from packages.backtest.engine import (Assumptions, BuyAndHold,
                                          PeriodicRebalance, backtest_from_workspace)
    from packages.artifacts.manifest import build_manifest, load_json, save

    if strategy == "buy-and-hold":
        strat = BuyAndHold()
    elif strategy in ("rebalance-quarterly", "rebalance"):
        strat = PeriodicRebalance(63)
    else:
        raise typer.BadParameter(f"unknown strategy {strategy!r}")

    ws = _ws(db)
    result = backtest_from_workspace(ws, name, strat,
                                     Assumptions(fees_bps=fees_bps,
                                                 slippage_bps=slippage_bps))
    manifest = build_manifest(
        kind="backtest",
        params={"strategy": strat.name},
        assumptions=result["assumptions"], seed=None,
        data_lineage={"symbols": result["symbols"],
                      "date_range": [result["dates"][0], result["dates"][-1]],
                      "hash": f"rows:{len(result['dates'])}"},
    )
    artifact_id = save(ws, manifest)
    m = result["metrics"]; b = result["benchmark_metrics"]
    typer.echo(f"artifact {artifact_id}")
    typer.echo(f"{'metric':<12}{'strategy':>12}{'benchmark':>12}")
    for k in ("total_return_pct", "cagr_pct", "volatility_pct",
              "max_drawdown_pct", "sharpe", "sortino", "calmar"):
        typer.echo(f"{k:<12}{m[k]:>12}{b[k]:>12}")


@app.command()
def scenario(kind: str = "bootstrap", symbol: str = "IWDA",
             runs: int = 2000, seed: int = 42, horizon: int = 252,
             portfolio_name: str | None = None, db: str = DB_OPT):
    """Run scenarios. kinds: mc | bootstrap | replay"""
    from packages.scenarios.engine import (block_bootstrap, historical_replay,
                                           monte_carlo_iid)
    from packages.artifacts.manifest import build_manifest, save
    ws = _ws(db)

    if kind == "mc":
        res = monte_carlo_iid(ws, symbol, horizon, runs, seed)
    elif kind == "bootstrap":
        res = block_bootstrap(ws, symbol, horizon, runs, seed)
    elif kind == "replay":
        target = portfolio_name or "demo"
        txns = ws.transactions_for(target)
        symbols = sorted({t["symbol"] for t in txns} - {"CASH"})
        out = historical_replay(ws, symbols)
        manifest = build_manifest("replay", {"symbols": symbols}, None, None,
                                  {"symbols": symbols})
        save(ws, manifest)
        typer.echo(json.dumps(out, indent=2))
        return
    else:
        raise typer.BadParameter("kind must be mc|bootstrap|replay")

    s = res.summary()
    manifest = build_manifest("scenario", {"method": s["method"], "runs": s["runs"]},
                              None, seed, {"symbols": [symbol]})
    save(ws, manifest)
    typer.echo(json.dumps(s, indent=2))


@app.command()
def doctor(db: str = DB_OPT):
    """Check workspace health."""
    ws = _ws(db)
    n_txn = len(list(ws.conn.execute("SELECT 1 FROM transactions")))
    n_prices = ws.conn.execute("SELECT COUNT(*) c FROM prices").fetchone()["c"]
    n_instr = ws.conn.execute("SELECT COUNT(*) c FROM instruments").fetchone()["c"]
    n_art = ws.conn.execute("SELECT COUNT(*) c FROM artifacts").fetchone()["c"]
    typer.echo(f"instruments={n_instr} transactions={n_txn} price_rows={n_prices} "
               f"artifacts={n_art} db={ws.db_path}")


if __name__ == "__main__":
    app()
