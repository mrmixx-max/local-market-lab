# API Reference

FastAPI backend at `http://127.0.0.1:8322`.

## Health & System

### `GET /api/v1/health`
```bash
curl http://127.0.0.1:8322/api/v1/health
```
Returns service status, DB connectivity, instrument count, uptime, and upstream (Ollama/Yahoo) availability.

### `GET /api/v1/system/info`
```bash
curl http://127.0.0.1:8322/api/v1/system/info
```
Returns version, uptime, DB path, and DB file size.

## Market Data

### `GET /api/v1/market/symbols`
List instruments.
```bash
curl http://127.0.0.1:8322/api/v1/market/symbols
```

### `GET /api/v1/market/prices/{symbol}?limit=N`
Price history.
```bash
curl http://127.0.0.1:8322/api/v1/market/prices/IWDA?limit=30
```

### `GET /api/v1/market/yahoo/{symbol}`
Yahoo Finance fallback for real-time prices.
```bash
curl http://127.0.0.1:8322/api/v1/market/yahoo/AAPL
```

### `GET /api/v1/market/data/{symbol}?source=yahoo|alphavantage`
Fetch OHLCV bars from external source with caching.
```bash
curl "http://127.0.0.1:8322/api/v1/market/data/AAPL?source=yahoo&years=5"
curl "http://127.0.0.1:8322/api/v1/market/data/MSFT?source=alphavantage"
```

### `POST /api/v1/market/indicators/{symbol}`
Compute technical indicators (SMA, EMA, RSI, MACD, Bollinger).
```bash
curl -X POST http://127.0.0.1:8322/api/v1/market/indicators/IWDA \
  -H "Content-Type: application/json" \
  -d '{"indicator":"sma","period":20}'
```
Indicators: `sma`, `ema`, `rsi`, `macd`, `bollinger`.

### `GET /api/v1/quality/report/{symbol}`
Run data quality checks on a symbol.
```bash
curl "http://127.0.0.1:8322/api/v1/quality/report/IWDA?source=yahoo"
```

### `GET /api/v1/market/cache/stats`
Cache statistics.
```bash
curl http://127.0.0.1:8322/api/v1/market/cache/stats
```

### `DELETE /api/v1/market/cache?symbol=IWDA`
Invalidate cache entries.
```bash
curl -X DELETE "http://127.0.0.1:8322/api/v1/market/cache?symbol=IWDA"
```

## Portfolio

### `GET /api/v1/portfolio/{name}`
Valuation (positions, cost basis, FX). Optional: `?benchmark=IWDA&include_analytics=true`
```bash
curl http://127.0.0.1:8322/api/v1/portfolio/mybook
curl "http://127.0.0.1:8322/api/v1/portfolio/demo?benchmark=IWDA&include_analytics=true"
```

### `GET /api/v1/portfolio/{name}/rebalancing?threshold=0.05`
Analyze drift and suggest rebalancing proposals.
```bash
curl "http://127.0.0.1:8322/api/v1/portfolio/demo/rebalancing?threshold=0.05"
```

### `POST /api/v1/portfolio/{name}/rebalance`
Generate rebalancing proposals for target weights.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/portfolio/demo/rebalance \
  -H "Content-Type: application/json" \
  -d '{"target_weights":{"IWDA":0.6,"AGGH":0.4},"threshold":0.05,"transaction_cost_bps":10}'
```

## Backtest

### `POST /api/v1/backtest`
Run backtest. Body: `{symbols, strategy, fees_bps, slippage_bps}`.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{"symbols":["IWDA","EIMI"],"strategy":"buy-and-hold"}'
```
Strategies: `buy-and-hold`, `periodic-rebalance`.

## Scenario

### `POST /api/v1/scenario`
Run Monte-Carlo or block-bootstrap. Body: `{symbol, kind, runs, seed, horizon_days}`.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/scenario \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","kind":"bootstrap","runs":2000,"seed":42}'
```
Kinds: `mc` (iid), `bootstrap` (block).

### `POST /api/v1/scenario/stress`
Run a stress-test scenario (historical or hypothetical).
```bash
curl -X POST http://127.0.0.1:8322/api/v1/scenario/stress \
  -H "Content-Type: application/json" \
  -d '{"scenario":"2008_financial_crisis","scenario_type":"historical","positions":{"IWDA":0.6,"AGGH":0.4},"seed":42}'
```
Historical scenarios: `2008_financial_crisis`, `2020_covid_crash`, `2022_inflation_shock`.
Hypothetical scenarios: `crash_30pct`, `volatility_spike`, `rates_300bp`.

### `POST /api/v1/scenario/crisis`
Run a crisis scenario analysis.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/scenario/crisis \
  -H "Content-Type: application/json" \
  -d '{"crisis_type":"correlation_break","positions":{"IWDA":0.5,"EIMI":0.3,"AGGH":0.2},"params":{}}'
```
Types: `correlation_break`, `liquidity_crunch`, `sector_rotation`.

### `POST /api/v1/scenario/forecast/{symbol}`
Generate ML forecast (linear + Holt + ARIMA-like + ensemble).
```bash
curl -X POST http://127.0.0.1:8322/api/v1/scenario/forecast/IWDA \
  -H "Content-Type: application/json" \
  -d '{"horizon":30}'
```

### `POST /api/v1/metrics/advanced`
Advanced risk metrics: VaR, CVaR, correlation, rolling Sharpe, drawdown, attribution.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/metrics/advanced \
  -H "Content-Type: application/json" \
  -d '{"symbols":["IWDA","EIMI"],"confidence":0.95,"window":63}'
```

## Validation

### `POST /api/v1/validation/walk-forward`
Walk-forward backtest on a price series.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/validation/walk-forward \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","train_window":252,"test_window":63,"step":21}'
```

### `POST /api/v1/validation/cv`
Time-series cross-validation (purged K-Fold).
```bash
curl -X POST http://127.0.0.1:8322/api/v1/validation/cv \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","n_splits":5,"gap":21}'
```

### `POST /api/v1/validation/hyperparameter`
Hyperparameter tuning (random or grid search).
```bash
curl -X POST http://127.0.0.1:8322/api/v1/validation/hyperparameter \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","param_grid":{"lookback":[10,20,50],"threshold":[0.01,0.02]},"n_trials":10,"method":"random"}'
```

## Export

### `POST /api/v1/export/pdf`
Generate PDF report.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"title":"My Report","metrics":{"cagr_pct":10.5},"trades":[{"symbol":"IWDA","side":"buy","qty":10}]}' \
  --output report.pdf
```

### `POST /api/v1/export/excel`
Generate Excel workbook.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/export/excel \
  -H "Content-Type: application/json" \
  -d '{"metrics":{"cagr_pct":10.5},"trades":[]}' \
  --output report.xlsx
```

### `POST /api/v1/export/cv`
Export data as CSV.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/export/csv \
  -H "Content-Type: application/json" \
  -d '{"kind":"trades","trades":[{"symbol":"IWDA","side":"buy","qty":10}]}' \
  --output trades.csv
```
Kinds: `trades`, `equity`, `scenario`.

## Explainability (@experimental)

### `POST /api/v1/explainability/importance`
Compute permutation importance and SHAP-like values.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/explainability/importance \
  -H "Content-Type: application/json" \
  -d '{"X":[[1,2],[3,4],[5,6]],"y":[1,2,3],"feature_names":["f1","f2"],"metric":"mse"}'
```

### `POST /api/v1/explainability/compare`
Compare models via walk-forward results or Diebold-Mariano test.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/explainability/compare \
  -H "Content-Type: application/json" \
  -d '{"mode":"dm","pred1":[1,2,3],"pred2":[1.1,2.1,2.9],"actual":[1,2,3]}'
```
Modes: `walkforward`, `dm`, `compare`.

## Trading Game

### `POST /api/v1/game/create` — Create game.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/game/create \
  -H "Content-Type: application/json" \
  -d '{"player":"alice","symbols":["IWDA","EIMI"],"days":63,"seed":42}'
```

### `POST /api/v1/game/{game_id}/order` — Place order.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/game/game_abc123/order \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","side":"buy","quantity":100}'
```

### `POST /api/v1/game/{game_id}/tick?days=N` — Advance N days.
```bash
curl -X POST "http://127.0.0.1:8322/api/v1/game/game_abc123/tick?days=5"
```

### `GET /api/v1/game/{game_id}` — Current state.
```bash
curl http://127.0.0.1:8322/api/v1/game/game_abc123
```

### `GET /api/v1/game/leaderboard` — Leaderboard.
```bash
curl http://127.0.0.1:8322/api/v1/game/leaderboard
```

### `GET /api/v1/game/challenges` — List challenges.
```bash
curl http://127.0.0.1:8322/api/v1/game/challenges
```

## Lobby

### `GET /api/v1/lobby/rooms` — List rooms.
### `POST /api/v1/lobby/rooms` — Create room (`{host}`).
### `GET /api/v1/lobby/rooms/{room_id}` — Room details.
```bash
curl http://127.0.0.1:8322/api/v1/lobby/rooms
curl -X POST http://127.0.0.1:8322/api/v1/lobby/rooms -H "Content-Type: application/json" -d '{"host":"alice"}'
curl http://127.0.0.1:8322/api/v1/lobby/rooms/room_xyz
```

## Ollama Bridge

### `GET /api/v1/ollama/models` — List local models.
```bash
curl http://127.0.0.1:8322/api/v1/ollama/models
```

### `POST /api/v1/ollama/chat` — Proxy chat (`{model, messages}`).
```bash
curl -X POST http://127.0.0.1:8322/api/v1/ollama/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"Explain Sharpe ratio"}]}'
```

### `POST /api/v1/ollama/optimize_prompt` — Trading prompt template.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/ollama/optimize_prompt \
  -H "Content-Type: application/json" \
  -d '{"goal":"paper-trading coach","style":"concise"}'
```

## Compliance

### `GET /api/v1/compliance/audit-log` — Audit log entries.
```bash
curl http://127.0.0.1:8322/api/v1/compliance/audit-log
```

### `POST /api/v1/compliance/integrity-check` — Run data integrity check.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/compliance/integrity-check
```

### `GET /api/v1/compliance/report` — Compliance report.
```bash
curl http://127.0.0.1:8322/api/v1/compliance/report
```

### `GET /api/v1/compliance/export/{user}` — GDPR data export.
```bash
curl http://127.0.0.1:8322/api/v1/compliance/export/alice
```

### `DELETE /api/v1/compliance/delete-account/{user}` — GDPR anonymization.
```bash
curl -X DELETE http://127.0.0.1:8322/api/v1/compliance/delete-account/alice
```

## WebSockets

| Endpoint | Purpose |
|---|---|
| `/ws/market` | Live ticks (subscribe `{action, symbols}`) |
| `/ws/lobby/{room_id}` | Multiplayer lobby events |
| `/ws/game/{game_id}` | Game state feed |
