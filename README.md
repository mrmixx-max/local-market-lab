# Local Market Lab

[![CI](https://github.com/mrmixx-max/local-market-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/mrmixx-max/local-market-lab/actions/workflows/ci.yml)
[![Windows Build](https://github.com/mrmixx-max/local-market-lab/actions/workflows/windows-build.yml/badge.svg)](https://github.com/mrmixx-max/local-market-lab/actions/workflows/windows-build.yml)

**Portfolio-Analytics, Backtesting und Szenario-Simulation — standardmäßig lokal, ohne Investment-Signale. Optionale Datenadapter (Yahoo Finance, Alpha Vantage) benötigen Netzwerkzugriff.**

> Research tool. Not financial advice. No buy/sell signals. No forecasts disguised as math.

Local Market Lab (`lml`) is a local-first workbench for portfolio analysis, backtesting and
scenario simulation. All data stays on your machine unless you explicitly pull from an external
provider. There is no cloud, no account, no telemetry.

## Install

### Windows Installer (Recommended)

Download the latest `LocalMarketLab-Setup-v*.exe` from the [Releases](https://github.com/mrmixx-max/local-market-lab/releases) page.

1. Run the installer (no admin rights required)
2. Choose installation folder (default: `%LOCALAPPDATA%\Local Market Lab`)
3. Optionally create a Desktop shortcut
4. Launch from the Start Menu

The installer includes:
- Automatic uninstaller (via Windows "Apps & Features")
- Start Menu and Desktop shortcuts
- All dependencies bundled (no Python installation needed)
- LZMA2-compressed installer (~15MB download)

### Portable Version

Download `LocalMarketLab.exe` from Releases — runs standalone, no installation required.

### From Source

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

## New in v0.9

- **10 Windows App tabs** with PyQt6 + pyqtgraph
- **Walk-Forward Validation, Time-Series CV, Hyperparameter-Tuning**
- **Stress Tests & Crisis Scenarios** (2008, 2020, 2022, Crash -30%, etc.)
- **Rebalancing-Assistant** (proposals only, never executes)
- **PDF/Excel/CSV Export**
- **Explainability** (Feature Importance, SHAP-like Approximation, Diebold-Mariano)
- **Ollama Integration** (local LLM chat)
- **Bank-Ready Compliance** (BaFin-report, GDPR export/deletion)
- **Data Quality Layer** (missing, splits, FX, timestamps, outliers)
- **Yahoo Finance + Alpha Vantage** adapters with local cache
- **CI/CD**, **Docker**, **Inno Setup Installer**

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
| `lml backtest P [--strategy S] [--fees N] [--slippage N]` | run backtest |
| `lml scenario mc/bootstrap/replay` | run scenarios |
| `lml game create/order/tick/state/leaderboard` | paper-trading game |
| `lml doctor` | workspace health check |

## New in this release

### Data Quality Checks
```bash
# Check quality of a price series
curl "http://127.0.0.1:8322/api/v1/quality/report/IWDA?source=yahoo"
```
Detects missing data, splits, FX mismatches, stale data, and price outliers.

### Walk-Forward & Cross-Validation
```bash
# Walk-forward validation
curl -X POST http://127.0.0.1:8322/api/v1/validation/walk-forward \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","train_window":252,"test_window":63,"step":21}'

# Time-series cross-validation
curl -X POST http://127.0.0.1:8322/api/v1/validation/cv \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","n_splits":5,"gap":21}'

# Hyperparameter tuning
curl -X POST http://127.0.0.1:8322/api/v1/validation/hyperparameter \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","param_grid":{"lookback":[10,20,50]},"n_trials":10}'
```

### Stress Testing & Crisis Scenarios
```bash
# Historical stress test
curl -X POST http://127.0.0.1:8322/api/v1/scenario/stress \
  -H "Content-Type: application/json" \
  -d '{"scenario":"2008_financial_crisis","positions":{"IWDA":0.6,"AGGH":0.4}}'

# Crisis analysis (correlation break, liquidity crunch, sector rotation)
curl -X POST http://127.0.0.1:8322/api/v1/scenario/crisis \
  -H "Content-Type: application/json" \
  -d '{"crisis_type":"correlation_break","positions":{"IWDA":0.5,"EIMI":0.3}}'
```

### Export (PDF, Excel, CSV)
```bash
curl -X POST http://127.0.0.1:8322/api/v1/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"title":"Report","metrics":{"cagr":10.5}}' --output report.pdf

curl -X POST http://127.0.0.1:8322/api/v1/export/excel \
  -H "Content-Type: application/json" \
  -d '{"metrics":{"cagr":10.5}}' --output report.xlsx
```

### Technical Indicators
```bash
curl -X POST http://127.0.0.1:8322/api/v1/market/indicators/IWDA \
  -H "Content-Type: application/json" \
  -d '{"indicator":"rsi","period":14}'
```
Supported: `sma`, `ema`, `rsi`, `macd`, `bollinger`.

### Advanced Risk Metrics
```bash
curl -X POST http://127.0.0.1:8322/api/v1/metrics/advanced \
  -H "Content-Type: application/json" \
  -d '{"symbols":["IWDA","EIMI"],"confidence":0.95}'
```

### Compliance & Audit
```bash
curl http://127.0.0.1:8322/api/v1/compliance/report
curl -X POST http://127.0.0.1:8322/api/v1/compliance/integrity-check
```

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
packages/validation/    walk-forward, cross-validation, hyperparameter tuning
packages/quality/       data quality checks (missing, splits, outliers, stale)
packages/explainability/ feature importance (permutation, SHAP-like Approximation), model comparison
packages/scenarios/     stress tests, crisis scenarios, regime switching
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

## Windows App (PyQt6 + pyqtgraph)

The Windows desktop app provides a Bloomberg-terminal-style interface with 10 tabs:

| Tab | Features |
|-----|----------|
| **Markets** | Candlestick charts, SMA/EMA/RSI/MACD/Bollinger indicators, crosshair |
| **Backtest** | Strategy comparison, equity curves, cost analysis (fees/slippage/spread) |
| **Scenarios** | Monte-Carlo, stress tests, crisis scenarios, histograms |
| **Validation** | Walk-forward, time-series CV, hyperparameter tuning |
| **Explainability** | Feature importance, model comparison |
| **Rebalancing** | Drift detection, proposals (read-only, never executes) |
| **Export** | PDF, Excel, CSV report generation |
| **Risk** | VaR/CVaR, drawdown, correlation matrix |
| **Ollama** | Local LLM chat with model selection |
| **Game** | Paper-trading challenges, leaderboard |

All charts use `pyqtgraph` for hardware-accelerated rendering. Data refreshes automatically every 3 seconds.

## Build from Source (Windows)

### Prerequisites
- Python 3.10+
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (for installer)
- [UPX](https://github.com/upx/upx/releases) (optional, for additional compression)

### Build Steps

```bash
# Clone
git clone https://github.com/mrmixx-max/local-market-lab.git
cd local-market-lab

# Install dependencies
pip install -e "."
pip install pyinstaller

# Build EXE + Installer
cd windows
build.bat
```

Output:
- `windows/src/dist/LocalMarketLab.exe` — standalone EXE (target: <30MB with UPX)
- `windows/installer/output/LocalMarketLab-Setup-v{version}.exe` — installer

### Build Options
```bash
build.bat --clean          # Clean build (removes cached artifacts)
build.bat --no-installer   # Build EXE only, skip Inno Setup
build.bat --no-upx         # Skip UPX compression
```

### Build Optimization

The build is optimized for minimal EXE size through:

1. **Qt6 DLL Excludes** — Only Qt6Core, Qt6Gui, Qt6Widgets are bundled. All Quick, QML, Multimedia, PDF, Network, and other unused Qt modules are excluded (~40MB savings).
2. **UPX Compression** — All compressible binaries are UPX-packed (~50% size reduction).
3. **Unused Module Excludes** — sklearn, pandas, matplotlib, scipy, tensorflow, torch, flask, django, fastapi, and 100+ other unused modules are excluded.
4. **Numpy Optimization** — Only numpy core runtime is bundled; distutils, tests, docs, and f2py are excluded (~5MB savings).
5. **FFmpeg Excludes** — avcodec, avformat, avutil, swresample, swscale DLLs excluded (~37MB savings).
6. **LZMA2 Compression** — Inno Setup uses ultra64 LZMA2 solid compression for the installer.

## CI/CD

### GitHub Actions

The project uses two GitHub Actions workflows:

- **CI** (`ci.yml`) — Runs on every push/PR. Lints with black/flake8 and runs pytest on Python 3.10–3.13.
- **Windows Build** (`windows-build.yml`) — Runs on push to main/develop, tags, and PRs. Builds the Windows EXE and installer, checks size (<30MB limit), and creates releases.

### Release Process

1. Update version in `windows/src/version_info.txt` and `windows/installer/setup.iss`
2. Push a tag: `git tag v0.9.1 && git push origin v0.9.1`
3. GitHub Actions automatically builds and creates a release with:
   - `LocalMarketLab-Setup-v{version}.exe` (installer)
   - `LocalMarketLab.exe` (portable)
   - SHA256 checksums

## Docker

```bash
# build and run
docker compose up --build

# with Ollama support
docker compose --profile full up --build
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage
pytest tests/ --cov=packages --cov-report=html
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
