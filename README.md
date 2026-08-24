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

# external market data (synthetic, yahoo, alphavantage)
lml import market AAPL --adapter yahoo
lml import market MSFT --adapter alphavantage
```

CSV formats are tolerant about headers (EN/DE) and delimiters (`;` or `,`).

## Trading Game (paper-training)

```bash
# create a game
lml game create --symbols IWDA,EIMI,AGGH --days 63 --seed 42

# place orders
lml game order game_abc123 IWDA buy 100
lml game order game_abc123 EIMI sell 50

# advance time
lml game tick game_abc123 5

# check state
lml game state game_abc123

# leaderboard
lml game leaderboard
```

Or use the web UI (F6 TRADE) for a visual trading experience with live P&L.

## API + Web UI

```bash
# start the API server
python -m apps.api

# open the web UI
start http://127.0.0.1:8322/
```

The web UI features:
- **Markets tab**: price charts, watchlist, portfolio positions
- **Backtest tab**: equity curves, strategy comparison
- **Scenarios tab**: Monte-Carlo distributions, percentiles
- **Trade! tab**: paper-trading game with order entry and leaderboard
- **Ollama tab**: local LLM chat with trading prompt optimizer

## CLI commands

| Command | Purpose |
|---|---|
| `lml demo` | end-to-end synthetic demo |
| `lml import txn FILE --portfolio P` | import transactions CSV |
| `lml import prices FILE SYMBOL` | import price series CSV |
| `lml import market SYMBOL --adapter A` | import from external source |
| `lml portfolio P` | valuation of portfolio `P` |
| `lml backtest P` | run buy-and-hold + rebalance backtests |
| `lml scenario mc/bootstrap/replay` | run scenarios |
| `lml game create/order/tick/state/leaderboard` | paper-trading game |
| `lml doctor` | workspace health check |

## Architecture

```
packages/core/          Money (Decimal-only), dates, hashing
packages/domain/        Instrument, Transaction, CorporateAction, PriceSeries
packages/storage/       SQLite workspace (instruments, txns, prices, artifacts)
packages/ingest/        CSV importers (tolerant, per-row error reports)
packages/marketdata/    price access, quality checks, FX policy, adapters
packages/portfolio/     position engine, FIFO cost basis, valuation
packages/metrics/       CAGR, MaxDD, Sharpe, Sortino, Calmar (pure functions)
packages/backtest/      event-loop engine + strategies (Buy&Hold, PeriodicRebalance)
packages/scenarios/     Monte-Carlo (iid + block-bootstrap), historical replay
packages/artifacts/     reproducibility manifests (seed + data hash + params)
packages/compliance/    disclaimers + language guard
packages/reports/       markdown report builders (methodology + limitations)
packages/game/          paper-trading engine + multiplayer lobby
packages/ollama/        local LLM client
apps/cli/               Typer CLI
apps/api/               FastAPI backend (REST + WebSocket)
apps/web/               Bloomberg-style terminal UI
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

## Docker

```bash
# build and run
docker compose up --build

# with Ollama support
docker compose --profile full up --build
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
