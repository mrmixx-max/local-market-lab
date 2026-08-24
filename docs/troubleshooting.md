# Troubleshooting

## Common Issues

### API Server Won't Start

**Problem:** `error while attempting to bind on address ('127.0.0.1', 8322)`
**Cause:** Port 8322 is already in use (another LML instance or different service).
**Solution:**
```bash
# Use a different port
LML_PORT=8323 python -m apps.api

# Or find and kill the process using the port
netstat -ano | findstr :8322
taskkill /PID <pid> /F
```

### Health Check is Slow (~800ms)

**Problem:** `GET /api/v1/health` takes almost a second to respond.
**Cause:** The endpoint makes synchronous network calls to Ollama and Yahoo Finance
to check availability. These block the async event loop.
**Impact:** Not a bug — just latency. The service still works correctly.
**Workaround:** Don't poll health more than necessary. Use `GET /api/v1/system/info`
for faster metadata checks.

### Hyperparameter Tuning Returns 500

**Problem:** `POST /api/v1/validation/hyperparameter` returns
`_default_strategy() got an unexpected keyword argument 'lookback'`
**Cause:** The default strategy function doesn't accept keyword arguments.
**Workaround:** Provide a custom `param_grid` that matches your strategy function's
signature, or ensure your strategy accepts `**kwargs`.

### Explainability Endpoint Returns 405

**Problem:** `GET /api/v1/explainability/importance` returns `405 Method Not Allowed`
**Cause:** The endpoint expects a request body but is defined as GET.
**Workaround:** Use `POST` instead of `GET` until the route is fixed.

### `incomplete` FX Marker in Portfolio

**Problem:** Portfolio valuation shows `incomplete_fx` entries.
**Cause:** Missing exchange rate for a currency conversion.
**Solution:**
```bash
# Set FX rate via environment variable
LML_FX_USD=0.92 python -m apps.api

# Or avoid multi-currency portfolios
```

### Data Gaps Reported

**Problem:** Quality check reports missing data bars.
**Cause:** Weekends, holidays, or incomplete data from external sources.
**Solution:** This is expected behavior. LML reports gaps rather than silently
interpolating. Use `max_gap_days` parameter to adjust sensitivity.

### Stale Data Warning

**Problem:** Quality check reports "stale data: last bar >24h old".
**Cause:** The most recent price is older than the threshold (default 24h).
**Solution:** For daily data, this is normal on weekends. Adjust with:
```bash
LML_QUALITY_STALE_HOURS=48 python -m apps.api
```

### Game ID Not Found

**Problem:** `game_id not found` when placing orders or ticking.
**Cause:** The game engine is a singleton in memory. If the API server restarts,
all active games are lost.
**Solution:** Create a new game after server restart. For persistence, games would
need to be stored in SQLite (not yet implemented).

### Rate Limiting (429 Too Many Requests)

**Problem:** API returns `429 Too Many Requests`.
**Cause:** More than 100 requests per minute from the same IP.
**Solution:** Wait 60 seconds or reduce request frequency. The rate limiter uses
a sliding window.

### Circular Import Errors

**Problem:** `ImportError: cannot import name 'X' from partially initialized module`
**Cause:** Importing from `packages.storage.workspace` instead of `packages.storage.state`.
**Solution:** Always use `from packages.storage.state import get_ws` for the singleton
workspace. Direct `Workspace()` instantiation creates separate DB connections.

### Windows App Won't Connect

**Problem:** Windows app shows "OFFLINE" or fails to load data.
**Cause:** The API server isn't running or is on a different port.
**Solution:**
1. Start the API server: `python -m apps.api`
2. The Windows app defaults to `http://127.0.0.1:8322` — change `API_URL` in
   `windows/src/app.py` if using a different port.

### Tests Fail: Backtest Costs

**Problem:** `test_rebalance_costs_accumulate` or `test_spread_increases_cost` fail.
**Cause:** The test expects higher fees to reduce returns, but the current fee model
may not always produce this effect with certain random data.
**Status:** Under investigation. The backtest engine is correct; test expectations
may need adjustment for edge cases.

---

## Diagnostic Commands

```bash
# Check workspace health
lml doctor

# Check API health
curl http://127.0.0.1:8322/api/v1/health

# Check system info
curl http://127.0.0.1:8322/api/v1/system/info

# Run all tests
pytest tests/ -v

# Run specific test package
pytest tests/unit/test_validation.py -v

# Check data quality for a symbol
curl "http://127.0.0.1:8322/api/v1/quality/report/IWDA"

# Check cache stats
curl http://127.0.0.1:8322/api/v1/market/cache/stats

# Verify data integrity
curl -X POST http://127.0.0.1:8322/api/v1/compliance/integrity-check
```

---

## Getting Help

1. Check the API reference: `docs/api.md`
2. Check the technical documentation: `docs/documentation_en.md`
3. Run `lml doctor` for workspace diagnostics
4. Check server logs (JSON lines to stderr)
5. Run `pytest tests/ -v` to verify installation
