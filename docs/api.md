# API Reference

FastAPI backend at `http://127.0.0.1:8322`.

## Health & Market Data

### `GET /api/v1/health`
```bash
curl http://127.0.0.1:8322/api/v1/health
```

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

## Portfolio

### `GET /api/v1/portfolio/{name}`
Valuation (positions, cost basis, FX).
```bash
curl http://127.0.0.1:8322/api/v1/portfolio/mybook
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

## Trading Game

### `GET /api/v1/game/challenges` — List challenges.
```bash
curl http://127.0.0.1:8322/api/v1/game/challenges
```

### `POST /api/v1/game/create` — Create game.
```bash
curl -X POST http://127.0.0.1:8322/api/v1/game/create \
  -H "Content-Type: application/json" \
  -d '{"player":"alice","symbols":["IWDA","EIMI"],"days":63,"seed":42}'
```

### `GET /api/v1/game/leaderboard` — Leaderboard.
```bash
curl http://127.0.0.1:8322/api/v1/game/leaderboard
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

## WebSockets

| Endpoint | Purpose |
|---|---|
| `/ws/market` | Live ticks (subscribe `{action, symbols}`) |
| `/ws/lobby/{room_id}` | Multiplayer lobby events |
| `/ws/game/{game_id}` | Game state feed |
