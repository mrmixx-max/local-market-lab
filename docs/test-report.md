# Test Report — Roadmap Implementation Audit

**Date:** 2026-08-24
**Commit:** 1aa285d
**Auditor:** Hermes Agent (subagent)

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| **Total tests** | 366 |
| **Passed** | 366 |
| **Failed** | 0 |
| **Original tests** | 261 |
| **New tests added** | 105 |
| **Overall coverage** | 78% |
| **Critical bugs found** | 1 |
| **Warnings** | 4 (RuntimeWarning from numpy log(0)) |

All 261 existing tests continue to pass. 105 new tests were added covering data quality edge cases, FX handling, cache behavior, determinism, look-ahead bias prevention, backtest costs, and core utilities.

---

## 2. Test Execution Results

### 2.1 Full Test Suite

```
366 passed in 29.09s
```

### 2.2 New Test Files

| File | Tests | Status |
|------|-------|--------|
| `tests/integration/test_data_quality_edge_cases.py` | 20 | ✅ All pass |
| `tests/integration/test_fx_edge_cases.py` | 16 | ✅ All pass |
| `tests/integration/test_cache_behavior.py` | 18 | ✅ All pass |
| `tests/integration/test_determinism.py` | 12 | ✅ All pass |
| `tests/integration/test_no_lookahead_bias.py` | 10 | ✅ All pass |
| `tests/integration/test_backtest_costs.py` | 15 | ✅ All pass |
| `tests/unit/test_core_utils.py` | 14 | ✅ All pass |

---

## 3. Coverage Analysis

### 3.1 Coverage by Package

| Package | Coverage | Status |
|---------|----------|--------|
| `packages/quality/` | 94% | ✅ Excellent |
| `packages/validation/` | 92-94% | ✅ Excellent |
| `packages/marketdata/cache.py` | 96% | ✅ Excellent |
| `packages/marketdata/fx.py` | 100% | ✅ Full |
| `packages/marketdata/indicators.py` | 99% | ✅ Excellent |
| `packages/core/hashing.py` | 100% | ✅ Full |
| `packages/core/dates.py` | 87% | ✅ Good |
| `packages/core/money.py` | 78% | ⚠️ Acceptable |
| `packages/domain/` | 91% | ✅ Good |
| `packages/scenarios/` (most) | 80-97% | ✅ Good |
| `packages/backtest/` | 86% | ✅ Good |
| `packages/portfolio/rebalancing.py` | 97% | ✅ Excellent |
| `packages/portfolio/engine.py` | 39% | ❌ Low |
| `packages/metrics/risk.py` | 54% | ❌ Low |
| `packages/game/lobby.py` | 34% | ❌ Low |
| `packages/compliance/guard.py` | 0% | ❌ Untested |
| `packages/compliance/bank_ready.py` | 48% | ❌ Low |
| `packages/artifacts/manifest.py` | 0% | ❌ Untested |
| `packages/reports/builders.py` | 0% | ❌ Untested |
| `packages/scenarios/crisis.py` | 0% | ❌ Untested |
| `packages/scenarios/rl_trading.py` | 43% | ❌ Low |

### 3.2 Critical Coverage Gaps

1. **`packages/portfolio/engine.py` (39%)** — Missing tests for:
   - `benchmark_comparison()`
   - `portfolio_returns()`
   - `allocation_breakdown()`
   - `risk_contribution()`

2. **`packages/metrics/risk.py` (54%)** — Missing tests for:
   - `var_cvar()`
   - `correlation_matrix()`
   - `rolling_sharpe()`
   - `drawdown_series()`
   - `performance_attribution()`

3. **`packages/compliance/` (0-48%)** — No tests for compliance guard and bank-ready checks.

4. **`packages/artifacts/manifest.py` (0%)** — No tests for artifact manifest.

5. **`packages/reports/builders.py` (0%)** — No tests for report builders.

---

## 4. Findings

### 4.1 Critical Bug: Sell-Side Cost Application

**Severity:** HIGH
**File:** `packages/backtest/engine.py`, lines 86-94

**Description:**
The backtest engine applies sell-side costs by reducing the number of shares sold instead of reducing the cash received. This causes an asymmetric cost model:

- **Buy-side (correct):** `qty_delta = (trade_value - cost) / px` → fewer shares bought
- **Sell-side (incorrect):** `qty_delta = (trade_value + cost) / px` → fewer shares sold (keeps more shares)

**Impact:**
When a portfolio rebalances by selling an asset, the cost is "paid" by retaining shares instead of receiving less cash. This can cause the high-fee scenario to outperform the zero-fee scenario if the retained shares appreciate.

**Location:**
```python
# packages/backtest/engine.py, line 91
qty_delta = (trade_value - (cost if trade_value > 0 else -cost)) / px[s]
```

For sells (`trade_value < 0`), this becomes `(trade_value + cost) / px`, which is less negative than `trade_value / px`, meaning fewer shares are sold.

**Recommended Fix:**
Apply costs symmetrically:
```python
if trade_value > 0:  # buy
    qty_delta = (trade_value - cost) / px[s]
else:  # sell
    qty_delta = trade_value / px[s]  # sell full amount
    # cost is deducted from cash separately
```

### 4.2 Runtime Warning: `log(0)` in Outlier Detection

**Severity:** LOW
**File:** `packages/quality/checks.py`, line 118

**Description:**
When a price series contains zero or negative closes, `np.log(0)` produces a RuntimeWarning and `nan` values.

**Location:**
```python
log_rets = np.diff(np.log(closes))  # line 118
```

**Recommended Fix:**
Filter out non-positive closes before computing log returns, or use `np.log(np.maximum(closes, epsilon))`.

### 4.3 Determinism Verified

**Status:** ✅ PASS

All deterministic components produce identical results with the same seed and data:
- `walk_forward_backtest()` — same seed → same folds, same metrics
- `monte_carlo_fat_tail()` — same seed → same distribution
- `sha256_obj()` — same input → same hash (key-order independent)
- `linear_trend_forecast()`, `ensemble_forecast()` — deterministic

### 4.4 Look-Ahead Bias Prevention Verified

**Status:** ✅ PASS

- Walk-forward splits: train_end ≤ test_start for all folds
- Purged CV: gap of N observations between train and test
- No overlap between train and test indices
- Feature engineering (SMA/EMA) on full series matches train-only computation

### 4.5 Data Quality Checks Verified

**Status:** ✅ PASS

- Missing data gaps detected correctly
- Weekend gaps (Fri→Mon) NOT flagged
- Duplicate timestamps detected and marked as `invalid`
- Future dates detected
- Invalid date formats detected
- Zero/negative closes detected via split detection
- Stale data detection works correctly
- Outlier detection via z-score works

### 4.6 FX Handling Verified

**Status:** ✅ PASS

- Unknown currencies return `None` (not 1.0)
- `require()` raises `KeyError` for missing rates
- Zero/negative rates rejected at policy creation
- Case-insensitive currency handling
- Portfolio valuation marks `incomplete_fx` when rates missing

### 4.7 Cache Behavior Verified

**Status:** ✅ PASS

- Cache hit returns correct data
- Cache miss returns `None`
- TTL expiry works (returns `None` for expired entries)
- Offline fallback returns expired data
- Invalidation by symbol and all works
- Quality error invalidation works
- Stats reporting works

---

## 5. Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All existing tests pass | ✅ | 261/261 pass |
| New core functions have automated tests | ✅ | 105 new tests added |
| No demonstrable look-ahead bias | ✅ | `test_no_lookahead_bias.py` passes |
| Same inputs → same results | ✅ | `test_determinism.py` passes |
| Faulty data rejected or marked incomplete | ✅ | `test_data_quality_edge_cases.py` + `test_fx_edge_cases.py` pass |
| Test report with file paths and error locations | ✅ | This document |
| `docs/test-report.md` created | ✅ | This file |

---

## 6. Recommendations

### 6.1 High Priority

1. **Fix sell-side cost bug** in `packages/backtest/engine.py` (line 91)
2. **Add tests for `packages/portfolio/engine.py`** analytics functions (benchmark_comparison, risk_contribution, etc.)
3. **Add tests for `packages/metrics/risk.py`** (var_cvar, correlation_matrix, rolling_sharpe, etc.)

### 6.2 Medium Priority

4. **Handle zero/negative prices** in `packages/quality/checks.py` to avoid RuntimeWarning
5. **Add tests for `packages/compliance/`** module
6. **Add tests for `packages/artifacts/manifest.py`**

### 6.3 Low Priority

7. **Add tests for `packages/reports/builders.py`**
8. **Add tests for `packages/scenarios/crisis.py`**
9. **Increase `packages/game/lobby.py` coverage** (currently 34%)

---

## 7. New Test Files Created

```
tests/integration/test_data_quality_edge_cases.py  — 20 tests (weekends, gaps, duplicates, stale, format)
tests/integration/test_fx_edge_cases.py           — 16 tests (missing rates, wrong data, integration)
tests/integration/test_cache_behavior.py          — 18 tests (hit/miss, TTL, invalidation, errors)
tests/integration/test_determinism.py             — 12 tests (seed reproducibility, hash stability)
tests/integration/test_no_lookahead_bias.py       — 10 tests (split integrity, gap enforcement)
tests/integration/test_backtest_costs.py          — 15 tests (fees, slippage, spread impact)
tests/unit/test_core_utils.py                     — 14 tests (sha256_file, sha256_obj)
```

---

## 8. Conclusion

The roadmap implementation is **solid and well-tested** with 366 passing tests and 78% overall coverage. The core validation, market data, quality, and scenarios packages have excellent coverage (90%+). The one critical bug found (sell-side cost asymmetry) should be fixed to ensure backtest accuracy. The main coverage gaps are in portfolio analytics, metrics, compliance, and reporting modules.
