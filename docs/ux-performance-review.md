# UX & Performance Review — Local Market Lab v0.1.0

> Reviewed: 2026-08-24 | Commit: `1aa285d` | Tests: 363 passed, 2 failed

---

## 1. Executive Summary

The new Roadmap implementation adds significant functionality: validation (walk-forward,
cross-validation, hyperparameter tuning), stress testing, crisis scenarios, data quality
checks, explainability, multi-format export, and compliance features. The core pipeline
works end-to-end and the CLI `demo` command runs without issues.

**Critical findings:** 2 bugs that cause HTTP 500 errors, 1 wrong HTTP method on an
explainability endpoint, 2 failing tests in the backtest cost logic, and several UX
gaps where new API features are not exposed in the Web UI or documented.

---

## 2. Quickstart Verification

### 2.1 CLI — PASSED

```bash
lml demo
# Output: prices imported, transactions, portfolio valuation, backtest summary
# Works without manual intervention.
```

### 2.2 API Server — PASSED (with notes)

```bash
python -m apps.api  # Starts on 127.0.0.1:8322
```

- Health endpoint responds correctly with Ollama/Yahoo availability checks.
- All core endpoints (portfolio, backtest, scenario, game, indicators) work.
- **Issue:** Port 8322 may be blocked if already in use (common on dev machines).

### 2.3 Web UI — PARTIALLY PASSED

- Serves correctly at `http://127.0.0.1:8322/`
- Markets, Backtest, Scenarios, Risk, Game, Ollama tabs present.
- **Issue:** New API features (validation, stress, export, compliance, indicators) are
  NOT exposed in the Web UI. Users cannot discover these features through the interface.

### 2.4 Windows App — NOT TESTABLE (headless environment)

- Code review: Hardcoded `API_URL = "http://127.0.0.1:8322"` — no config override.
- Splash screen checks API health but doesn't show user-friendly error if unreachable.
- No loading states or progress indicators for long operations.

---

## 3. End-to-End Workflow Verification

| Step | Status | Notes |
|------|--------|-------|
| Data import | PASS | `lml demo` seeds synthetic data; `lml import` works for CSV |
| Data quality check | PASS | Quality checks run on market data; QualityReport with score |
| Model validation | PASS (bug) | Walk-forward and CV work; **Hyperparameter tuning returns HTTP 500** |
| Backtest | PASS | Buy-and-hold and periodic-rebalance work |
| Stress test | PASS | Historical and hypothetical scenarios with limitations |
| Rebalancing | PASS | Drift analysis and proposals generated |
| Report export | PASS | PDF, Excel, CSV all functional |

---

## 4. Bugs Found

### 4.1 CRITICAL: Hyperparameter Tuning HTTP 500

**Endpoint:** `POST /api/v1/validation/hyperparameter`
**Error:** `_default_strategy() got an unexpected keyword argument 'lookback'`

**Root cause:** The default `_default_strategy` function in `apps/api/main.py` (line 551)
accepts only `(train_data, test_data)` but the default `param_grid` includes `lookback`
and `threshold` keys.

**Fix:** Either make `_default_strategy` accept `**kwargs`, or change the default
param_grid to match the function signature.

**File:** `apps/api/main.py`, lines 551-559 and 621-623.

### 4.2 CRITICAL: Explainability Importance — Wrong HTTP Method

**Endpoint:** `GET /api/v1/explainability/importance`
**Error:** `405 Method Not Allowed` when called with body data

**Root cause:** The route is defined as `@explain_router.get("/importance")` but expects
a request body (`payload: dict`). GET requests with bodies are non-standard and blocked
by most HTTP clients/servers.

**Fix:** Change to `@explain_router.post("/importance")`.

**File:** `apps/api/export_routes.py`, line 103.

### 4.3 HIGH: Backtest Cost Tests Failing

Two tests in `tests/integration/test_backtest_costs.py` fail:
- `test_rebalance_costs_accumulate`: Expected `costly_return < free_return`, got `1.79 < 0.28`
- `test_spread_increases_cost`: Expected `high_spread_return < low_spread_return`, got `0.87 < 0.43`

**Impact:** Suggests fee/slippage logic may not be correctly reducing returns in all
scenarios, or test expectations are miscalibrated for the current fee model.

### 4.4 MEDIUM: Invalid Strategy Silently Falls Back

**Endpoint:** `POST /api/v1/backtest`
**Behavior:** Unknown strategy names silently fall back to `BuyAndHold()` instead of
returning a 400 error.

**File:** `apps/api/main.py`, line 337-338.

### 4.5 LOW: Unknown Symbol Returns 200 with Empty Bars

**Endpoint:** `GET /api/v1/market/prices/UNKNOWN`
**Behavior:** Returns `200 {"symbol": "UNKNOWN", "bars": []}` instead of 404.

---

## 5. Performance Analysis

### 5.1 Response Times (local, synthetic data 540 bars)

| Operation | Time | Assessment |
|-----------|------|------------|
| Health check | ~800ms | SLOW — synchronous Ollama+Yahoo checks block event loop |
| Scenario (10,000 runs, 252 days) | 640ms | Acceptable (pure Python random) |
| Walk-forward (252/63/21) | 20ms | Fast |
| Backtest | 30ms | Fast |
| Portfolio with analytics | 40ms | Fast |
| Indicators (SMA/EMA/RSI) | <10ms | Fast |
| Export PDF (no charts) | <50ms | Fast |
| Export Excel | <50ms | Fast |

### 5.2 Bottleneck: Health Check Synchronous Network Calls

The `health` endpoint makes synchronous `urllib.request.urlopen` calls to Ollama (3s
timeout) and Yahoo (5s timeout) inside an async handler. This blocks the event loop
for ~800ms per request and serializes all concurrent health checks.

**Recommendation:** Use `asyncio.to_thread()` or `aiohttp` for non-blocking checks,
or make health checks cached/frequency-limited.

### 5.3 Memory Considerations

- **Scenario engine** stores all `runs` final values in memory as a list of floats.
  At 10,000 runs this is ~80KB — negligible. At 1,000,000 runs it would be ~8MB.
- **Walk-forward** re-runs strategy for OOS aggregation (line 169-171 in walk_forward.py).
  This duplicates computation but keeps memory low.
- **No streaming** for large exports. PDF/Excel fully buffered in `io.BytesIO`.
  Fine for current scale but could OOM with thousands of charts.

### 5.4 Cache Behavior

- **MarketDataCache**: SQLite-based with TTL (default 24h). Works correctly.
- **No result caching** for expensive computations (scenarios, backtests).
  Repeated identical requests recompute from scratch.
- **No request-level cache** on the API layer.

---

## 6. Error Messages & User Feedback

### 6.1 Good Examples

| Endpoint | Error | Quality |
|----------|-------|---------|
| Unknown crisis scenario | `"unknown crisis: X. available: ['2008_financial_crisis', ...]"` | ✅ Helpful — lists valid options |
| Empty positions | `"positions required (symbol -> weight fraction)"` | ✅ Clear requirement |
| Invalid indicator | `"unknown indicator: invalid"` | ✅ Clear |
| Data too short (validation) | `"data length N < train_window + test_window (X + Y)"` | ✅ Specific |

### 6.2 Needs Improvement

| Issue | Current | Recommended |
|-------|---------|-------------|
| Strategy fallback | Silent fallback to buy-and-hold | Return 400 with valid strategies list |
| Unknown symbol | 200 with empty bars | Return 404 |
| Hyperparameter 500 | Internal server error | Fix default strategy signature |
| No progress indicators | — | WebSocket or polling for scenarios >5000 runs |

---

## 7. Claims Verification

### 7.1 "Reproducible" — PARTIALLY VERIFIED

- ✅ Scenarios use seeded RNG (`random.Random(seed)`)
- ✅ Artifacts record seed, data hash, and parameters
- ✅ `build_manifest()` captures data lineage
- ⚠️ Backtest engine doesn't expose seed in results (deterministic but not documented)
- ⚠️ Walk-forward OOS aggregation re-runs strategy (line 169) — could introduce
  non-determinism if strategy uses randomness internally

### 7.2 "Local" — VERIFIED

- ✅ SQLite storage, no cloud dependencies
- ✅ Synthetic data generation works offline
- ⚠️ Health check calls external services (Ollama, Yahoo) — doesn't fail if
  unreachable but adds latency
- ⚠️ Yahoo/AlphaVantage adapters require internet for real data

### 7.3 "Bank-Ready" — OVERCLAIMED

The `packages/compliance/bank_ready.py` module provides:
- ✅ Append-only audit log (user, timestamp, action, params, hash)
- ✅ SHA-256 table checksums for data integrity
- ✅ BaFin-style compliance report (JSON)
- ✅ GDPR data export and anonymization

**However:**
- ⚠️ No encryption at rest (SQLite database is plaintext)
- ⚠️ No access control or authentication (any client can call any endpoint)
- ⚠️ No log integrity verification (audit log rows can be modified in SQLite)
- ⚠️ GDPR deletion only anonymizes transactions table, not prices or artifacts
- ⚠️ No digital signatures on reports
- ⚠️ Rate limiter is per-IP only (no user-level rate limiting)

**Recommendation:** Soften claim to "audit trail" or "compliance-ready" instead of
"Bank-Ready", and document the limitations clearly.

---

## 8. Documentation Gaps

### 8.1 Missing from API Reference (`docs/api.md`)

- `POST /api/v1/scenario/stress` — stress test endpoint
- `POST /api/v1/scenario/crisis` — crisis scenarios
- `GET/POST /api/v1/portfolio/{name}/rebalancing` — rebalancing
- `POST /api/v1/market/indicators/{symbol}` — technical indicators
- `POST /api/v1/metrics/advanced` — advanced risk metrics
- `POST /api/v1/scenario/forecast/{symbol}` — ML forecast
- `POST /api/v1/validation/*` — walk-forward, CV, hyperparameter
- `POST /api/v1/export/*` — PDF, Excel, CSV export
- `GET /api/v1/explainability/*` — feature importance, model comparison
- `GET/POST /api/v1/compliance/*` — audit, integrity, GDPR
- `GET /api/v1/system/info` — runtime metadata
- `GET /api/v1/market/data/{symbol}` — external data fetch
- `GET /api/v1/quality/report/{symbol}` — quality checks
- `GET /api/v1/market/cache/stats` — cache statistics
- `DELETE /api/v1/market/cache` — cache invalidation
- `GET /api/v1/market/yahoo/{symbol}` — Yahoo fallback

### 8.2 Missing from README

- New CLI commands: `lml quality`, `lml validate` (if planned)
- New environment variables: `LML_CACHE_TTL_HOURS`, `LML_QUALITY_*`, `LML_WF_*`,
  `LML_CV_*`, `LML_STRESS_MAX_DD_THRESHOLD`, `LML_EXPORT_*_PATH`
- Export and explainability features
- Validation features (walk-forward, CV, hyperparameter)
- Stress testing and crisis scenarios

### 8.3 Web UI Not Updated

New tabs/sections needed for:
- Validation (walk-forward results, CV folds, hyperparameter trials)
- Stress testing (scenario selection, results timeline)
- Data quality dashboard
- Export panel (PDF/Excel/CSV download)
- Compliance viewer

---

## 9. Concrete Improvement Recommendations

### 9.1 Critical Fixes (block release)

1. **Fix hyperparameter default strategy** — accept `**kwargs` or change default grid
2. **Fix explainability route method** — GET → POST
3. **Fix backtest cost tests** — investigate fee logic or fix test expectations

### 9.2 High Priority (UX impact)

4. **Add loading indicators** for operations >1s (scenarios, exports)
5. **Implement progress reporting** via WebSocket or polling for long jobs
6. **Return 400 for unknown strategies** instead of silent fallback
7. **Return 404 for unknown symbols** in prices endpoint
8. **Make health check non-blocking** (async or cached)
9. **Soften "Bank-Ready" claim** with documented limitations

### 9.3 Medium Priority (discoverability)

10. **Add Web UI sections** for validation, stress, export, quality
11. **Document all new API endpoints** with curl examples
12. **Add environment variable reference** to README
13. **Create FAQ entry** for new features (validation, stress, explainability)
14. **Add Windows app config** for API URL (not hardcoded)

### 9.4 Low Priority (optimization)

15. **Add result caching** for identical scenario/backtest requests
16. **Stream large exports** instead of buffering in memory
17. **Add pagination** to prices endpoint for very long series
18. **Implement request-level memoization** for repeated quality checks

---

## 10. Test Coverage Assessment

| Package | Test File | Coverage | Notes |
|---------|-----------|----------|-------|
| validation | test_validation.py | ✅ 20 tests | Walk-forward, CV, hyperparameter |
| stress | test_stress.py | ✅ 15 tests | Historical, hypothetical, fat-tail |
| quality | test_quality.py | ✅ ~10 tests | Missing data, splits, outliers |
| explainability | test_explainability.py | ✅ ~8 tests | Permutation, SHAP, DM test |
| export | test_export.py | ✅ ~8 tests | PDF, Excel, CSV |
| scenarios | test_scenarios.py | ✅ ~12 tests | MC, bootstrap, replay |
| marketdata | test_marketdata.py | ✅ ~8 tests | Adapters, cache, indicators |
| rebalancing | test_rebalancing.py | ✅ ~6 tests | Drift, proposals, costs |

**Missing test coverage:**
- API endpoint integration tests for new routes (validation, stress, export)
- Error handling edge cases (invalid payloads, missing data)
- Performance/load tests (100k scenario runs, 10k hyperparameter trials)
- WebSocket tests (market feed, game state)

---

## 11. Conclusion

The implementation is **functionally solid** with good domain modeling and clean
architecture. The main issues are:

1. **2 blocking bugs** (hyperparameter 500, explainability HTTP method)
2. **2 failing tests** (backtest cost logic)
3. **Significant documentation gaps** (~15 endpoints undocumented)
4. **Web UI doesn't expose new features**
5. **Performance bottleneck** in health check (synchronous network calls)

After fixing the critical bugs and updating documentation, the release will be ready
for users. The "Bank-Ready" claim should be scoped more precisely.

---

*Review method: Manual API testing (curl via Python urllib), code review of all new
packages, performance timing, test suite execution. Environment: Windows 11, Python 3.11.15.*
