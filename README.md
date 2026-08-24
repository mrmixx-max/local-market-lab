# Local Market Lab

**Privacy-first portfolio analytics, backtesting, and scenario simulation — without investment signals.**

> Research tool. Not financial advice. No buy/sell signals. No forecasts disguised as math.

Local Market Lab (`lml`) is a local-first workbench for portfolio analysis, backtesting and
scenario simulation. All data stays on your machine unless you explicitly pull from an external
provider. There is no cloud, no account, no telemetry.

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Quick start — synthetic demo

```bash
lml demo
```

Seeds deterministic synthetic prices and a demo portfolio, then prints a valuation,
backtest summary and scenario percentiles.

## Import your own data

```bash
# portfolio positions + transactions
lml import txn examples/my-trades.csv --portfolio mybook

# price series (one CSV per instrument)
lml import prices examples/prices-iwda.csv IWDA
lml import prices examples/prices-btc.csv BTC-EUR
```

CSV formats are tolerant about headers (EN/DE) and delimiters (`;` or `,`).

Once imported:

```bash
lml portfolio mybook                   # valuation at last available close
lml backtest mybook --strategy rebalance-quarterly
lml scenario bootstrap IWDA --runs 5000 --seed 7
lml scenario replay mybook             # historical replay of equal-weight index
lml doctor                             # workspace health
```

## CLI commands

| Command | Purpose |
|---|---|
| `lml demo` | end-to-end synthetic demo |
| `lml import txn FILE --portfolio P` | import transactions CSV |
| `lml import prices FILE SYMBOL` | import price series CSV |
| `lml portfolio P` | valuation of portfolio `P` |
| `lml backtest P` | run buy-and-hold + rebalance backtests |
| `lml scenario mc SYMBOL` | iid Monte-Carlo simulation |
| `lml scenario bootstrap SYMBOL` | block-bootstrap simulation |
| `lml scenario replay P` | historical replay of an imported portfolio |
| `lml doctor` | workspace health check |

## Architecture

```
packages/core/          Money (Decimal-only), dates, hashing
packages/domain/        Instrument, Transaction, CorporateAction, PriceSeries
packages/storage/       SQLite workspace (instruments, txns, prices, artifacts)
packages/ingest/        CSV importers (tolerant, per-row error reports)
packages/marketdata/    price access, quality checks, FX policy (no silent 1:1)
packages/portfolio/     position engine, FIFO cost basis, valuation
packages/metrics/       CAGR, MaxDD, Sharpe, Sortino, Calmar (pure functions)
packages/backtest/      event-loop engine + strategies (Buy&Hold, PeriodicRebalance)
packages/scenarios/     Monte-Carlo (iid + block-bootstrap), historical replay
packages/artifacts/     reproducibility manifests (seed + data hash + params)
packages/compliance/    disclaimers + language guard
packages/reports/       markdown report builders (methodology + limitations mandatory)
apps/cli/               Typer CLI (see above)
apps/web/               Bloomberg-style terminal UI (single HTML, seeded demo)
```

## What this tool does NOT do

- **No trading signals.** The word "signal" does not appear in the API surface.
- **No "buy/sell/hold" recommendations.** Reports use the language guard to enforce this.
- **No silent FX conversion.** Missing FX rates produce an explicit INCOMPLETE marker.
- **No gap-filling.** Data gaps are reported, never silently interpolated.
- **No prediction-as-forecast framing.** Scenarios carry mandatory limitation notes.

## Design principles

1. **Decimal money.** `float` is forbidden for monetary values. All arithmetic uses `Decimal`.
2. **Append-only transactions.** Corrections create new rows, never mutate history.
3. **Seeded reproducibility.** Every scenario run records seed, parameters and a data hash.
4. **Explicit assumptions.** Fees, slippage, rebalance frequency are recorded in every artifact.
5. **Methodology notes mandatory.** Every report states how ratios are annualized.
6. **Privacy by default.** Local SQLite, no network calls, no telemetry.

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Acknowledgements

This tool synthesizes ideas from the local-first, reproducible-research and
privacy-preserving computation communities. It is intentionally a local workbench,
not a SaaS platform.
