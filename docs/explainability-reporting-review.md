# Explainability & Reporting — Code Review

**Project:** Local Market Lab v0.9.0
**Reviewer:** Agent 3 (Explainability und Reporting)
**Date:** 2026-08-24
**Scope:** `packages/explainability/`, `packages/reports/`, `packages/domain/entities.py`

---

## 1. Permutation Feature Importance (`packages/explainability/importance.py`)

### 1.1 Leakage Check

| Check | Status | Detail |
|---|---|---|
| Train/test separation | **WARN** | `permutation_importance()` computes `baseline = predict(X)` and `base_err = _error(baseline, y, metric)` on the same array `X` that is subsequently permuted. No hold-out split is applied. If the model overfits, noise features will show inflated importance on training data. |
| `splits_used` label accuracy | **WARN** | The result is tagged `splits_used=_splits_str()` → `"walk_forward_252_63_21"` but the function does not implement walk-forward splits — it simply labels the result as if it did. This is misleading provenance. |
| RNG seeding | **PASS** | `rng = np.random.default_rng(seed)` — deterministic given seed. |
| Feature isolation | **PASS** | Permutes one feature at a time (`X_perm[:, f] = rng.permutation(...)`) — correct isolation. |
| Repeat averaging | **PASS** | `n_repeats` loop with mean/std — correct. |

**Recommendation:**
- Accept an optional `X_test, y_test` parameter (or a pre-computed split index) so baseline and permutation errors are computed on held-out data.
- Change `splits_used` to reflect actual methodology (e.g., `"full_sample_no_split"`) or remove the field when no split is used.

### 1.2 SHAP-like Approximation

| Check | Status | Detail |
|---|---|---|
| Labeled as approximation | **WARN** | Docstring says "Approximate SHAP values" but the return dict has no explicit `approximation: true` or `method: "marginal_contribution"` field. Consumers of the dict cannot programmatically distinguish exact SHAP from this approximation. |
| Marginal contribution logic | **PASS** | `_build_instance` blends instance features with background; `shap_vals[f] = mean(p1 - p0)` over random subsets — correct Shapley-like estimation. |
| Efficiency | **INFO** | `O(n_features × n_samples × predict_cost)` — acceptable for small models, will be slow for large feature sets. |
| Sum-to-prediction property | **PASS** | Test `test_shap_sums_to_prediction_minus_base` verifies Σshap ≈ prediction − base_value (tolerance 3.0 for Monte Carlo noise). |

**Recommendation:**
- Add `"approximation": true` and `"method": "marginal_contribution"` to the return dict.

### 1.3 Error Metrics (`_error`)

| Check | Status | Detail |
|---|---|---|
| MSE | **PASS** | `np.mean((pred - y) ** 2)` — correct. |
| MAE | **PASS** | `np.mean(np.abs(pred - y))` — correct. |
| RMSE | **PASS** | `np.sqrt(np.mean((pred - y) ** 2))` — correct. |
| Unknown metric | **PASS** | Raises `ValueError`. |

---

## 2. Diebold-Mariano Test (`packages/explainability/comparison.py`)

### 2.1 Loss Functions

| Check | Status | Detail |
|---|---|---|
| MSE loss differential | **PASS** | `d = (p1 - a)**2 - (p2 - a)**2` — correct. |
| MAE loss differential | **PASS** | `d = np.abs(p1 - a) - np.abs(p2 - a)` — correct. |
| Unknown loss | **PASS** | Raises `ValueError`. |

### 2.2 HAC Variance Estimator

| Check | Status | Detail |
|---|---|---|
| Newey-West kernel | **PASS** | Bartlett weights `w = 1 - lag / (h + 1)` — standard Newey-West. |
| Long-run variance | **PASS** | `var_d = gamma0 + 2 * Σ w * gamma_l` — correct. |
| Zero-variance edge case | **PASS** | Returns `dm_stat=0.0, p_value=1.0, note="zero variance"` — graceful. |

### 2.3 Test Statistic

| Check | Status | Detail |
|---|---|---|
| DM statistic | **PASS** | `mean_d / sqrt(var_d / n)` — correct normal approximation. |
| Two-sided p-value | **PASS** | `2 * (1 - Φ(|dm_stat|))` — correct. |
| Significance threshold | **PASS** | `p < 0.05` — standard. |
| Better model direction | **PASS** | `mean_d < 0` → model1 better (lower loss) — correct. |

### 2.4 Walk-Forward Table

| Check | Status | Detail |
|---|---|---|
| Row aggregation | **PASS** | All windows listed with rounded metrics. |
| Summary stats | **PASS** | Per-model mean/std of MSE/MAE, n_windows — correct. |

### 2.5 `compare_models`

| Check | Status | Detail |
|---|---|---|
| Window matching | **PASS** | Only common windows compared — correct. |
| DM on pooled predictions | **INFO** | Concatenates all window predictions into one series before DM. Valid approach but assumes independence across windows; acceptable for non-overlapping test sets. |
| Provenance | **PASS** | Returns `run_id`, `data_hash`, `splits_used`, `data_quality`. |

---

## 3. Export (`packages/reports/export.py`)

### 3.1 CSV Export

| Check | Status | Detail |
|---|---|---|
| `run_id` | **PASS** | Generated via `_run_id()`, embedded in filename and `ExportResult`. |
| `data_hash` | **PASS** | SHA-256 of CSV content. |
| `data_quality` | **PASS** | Embedded in `ExportResult`. |
| `system_version` | **FAIL** | Not included anywhere in CSV export or `ExportResult`. |
| `seed` | **FAIL** | Not included. |
| `data_source` | **WARN** | Available via `data_quality.source` but not as a top-level column in CSV. |
| `metrics` | **FAIL** | Not included — CSV is raw data only, no metrics metadata. |
| `disclaimer` | **FAIL** | Not included. |
| Empty input handling | **PASS** | `csv_trades([])` returns valid `ExportResult` with `rows=0`. |
| File integrity | **PASS** | Files are written and readable (verified by tests). |

### 3.2 PDF Export

| Check | Status | Detail |
|---|---|---|
| `run_id` | **PASS** | In PDF header: `"Run: {run_id} · {timestamp}"`. |
| `data_hash` | **PASS** | In `ExportResult.metadata`. |
| `data_quality` | **PASS** | In `ExportResult`. |
| `system_version` | **FAIL** | Not included. |
| `seed` | **FAIL** | Not included. |
| `data_source` | **FAIL** | Not included. |
| `metrics` | **WARN** | Rendered as table but not in a machine-readable metadata block. |
| `disclaimer` | **FAIL** | Not included in PDF. |
| Chart rendering | **WARN** | Silent `except Exception` — chart failures are swallowed with "[chart unavailable]" but no log/warning. |
| Trade table limit | **INFO** | First 100 rows only — acceptable but not documented in the function signature. |

### 3.3 Excel Export

| Check | Status | Detail |
|---|---|---|
| `run_id` | **PASS** | In Quality sheet. |
| `data_hash` | **PASS** | In `ExportResult`. |
| `data_quality` | **PASS** | Quality sheet has `n_observations`, `missing_pct`, `source`, `start_date`, `end_date`, `created_at`. |
| `system_version` | **FAIL** | Not included. |
| `seed` | **FAIL** | Not included. |
| `data_source` | **WARN** | In Quality sheet as `source` but not as a top-level field. |
| `metrics` | **WARN** | Summary sheet has metrics but Quality sheet does not. |
| `disclaimer` | **FAIL** | Not included. |
| Sheet structure | **PASS** | Summary, Trades, Equity, Drawdown, Quality — all present. |
| Empty trades | **PASS** | Header row written even when `trades` is empty. |

---

## 4. Report Builders (`packages/reports/builders.py`)

| Check | Status | Detail |
|---|---|---|
| Disclaimer (portfolio) | **PASS** | `RESEARCH_DISCLAIMER` appended. |
| Disclaimer (backtest) | **PASS** | `RESEARCH_DISCLAIMER` appended. |
| Disclaimer (scenario) | **PASS** | Both `SCENARIO_DISCLAIMER` and `RESEARCH_DISCLAIMER` appended. |
| Methodology section | **PASS** | All three builders include methodology. |
| Limitations section | **PASS** | All three include limitations. |
| `system_version` | **FAIL** | Not included in any builder. |
| `run_id` | **FAIL** | Not included (backtest has `artifact_id` from manifest but not a run_id). |
| `data_hash` | **FAIL** | Not included. |
| `seed` | **WARN** | Scenario builder includes `seed` from manifest; portfolio and backtest do not. |
| `metrics` | **WARN** | Present in output but not as a structured metadata block. |
| Language guard | **PASS** | All builders call `assert_clean()` before returning. |

---

## 5. Domain Entities (`packages/domain/entities.py`)

### 5.1 `ExportResult`

| Required Field | Status | Detail |
|---|---|---|
| `run_id` | **PASS** | Present. |
| `system_version` | **FAIL** | Not present. |
| `data_source` | **WARN** | Via `data_quality.source`. |
| `data_hash` | **PASS** | Present. |
| `seed` | **FAIL** | Not present. |
| `metrics` | **FAIL** | Not present (could be in `metadata` but not enforced). |
| `disclaimer` | **FAIL** | Not present. |

### 5.2 `ExplainabilityResult`

| Required Field | Status | Detail |
|---|---|---|
| `run_id` | **PASS** | Present. |
| `system_version` | **FAIL** | Not present. |
| `data_source` | **WARN** | Via `data_quality.source`. |
| `data_hash` | **PASS** | Present. |
| `seed` | **FAIL** | Not present (seed is used in `permutation_importance` but not stored in result). |
| `metrics` | **FAIL** | Not present. |
| `disclaimer` | **FAIL** | Not present. |

### 5.3 `ModelComparison`

| Required Field | Status | Detail |
|---|---|---|
| `run_id` | **PASS** | Present. |
| `system_version` | **FAIL** | Not present. |
| `data_source` | **WARN** | Via `data_quality.source`. |
| `data_hash` | **PASS** | Present. |
| `seed` | **FAIL** | Not present. |
| `metrics` | **FAIL** | Not present. |
| `disclaimer` | **FAIL** | Not present. |

---

## 6. Required Fields Summary

| Field | CSV | PDF | Excel | Builders | Entities |
|---|---|---|---|---|---|
| Systemversion | ❌ FAIL | ❌ FAIL | ❌ FAIL | ❌ FAIL | ❌ FAIL |
| Run-ID | ✅ PASS | ✅ PASS | ✅ PASS | ❌ FAIL | ✅ PASS |
| Datenquelle | ⚠️ WARN | ❌ FAIL | ⚠️ WARN | ⚠️ WARN | ⚠️ WARN |
| Data-Hash | ✅ PASS | ✅ PASS | ✅ PASS | ❌ FAIL | ✅ PASS* |
| Seed | ❌ FAIL | ❌ FAIL | ❌ FAIL | ⚠️ WARN | ❌ FAIL |
| Metriken | ❌ FAIL | ⚠️ WARN | ⚠️ WARN | ⚠️ WARN | ❌ FAIL |
| Disclaimer | ❌ FAIL | ❌ FAIL | ❌ FAIL | ✅ PASS | ❌ FAIL |

\* `ExplainabilityResult` and `ModelComparison` have `data_hash`; `ExportResult` also has it.

---

## 7. Overall Status

| Area | Status | Critical Issues |
|---|---|---|
| Permutation Importance — Leakage | **WARN** | No train/test split; misleading `splits_used` label |
| Permutation Importance — SHAP | **WARN** | Approximation not flagged in return dict |
| Diebold-Mariano Test | **PASS** | Correct loss functions, HAC variance, test statistic |
| Walk-Forward Table | **PASS** | Correct aggregation |
| CSV Export | **FAIL** | Missing system_version, seed, disclaimer, metrics |
| PDF Export | **FAIL** | Missing system_version, seed, disclaimer, data_source |
| Excel Export | **FAIL** | Missing system_version, seed, disclaimer |
| Report Builders | **WARN** | Disclaimer present; missing system_version, run_id, data_hash |
| Domain Entities | **FAIL** | `ExportResult`, `ExplainabilityResult`, `ModelComparison` all missing required metadata fields |

---

## 8. Action Items (Priority Order)

1. **Add `system_version` to all export paths and entities** — read from `packages.domain.constants` or a version file; include in `ExportResult`, `ExplainabilityResult`, `ModelComparison` as a required field.
2. **Add `seed` to `ExportResult` and explainability results** — propagate the seed used for RNG into the result objects.
3. **Add `disclaimer` to PDF, Excel, and CSV exports** — PDF: add a footer or metadata section; Excel: add to Quality sheet; CSV: add as a comment header or sidecar `.meta` file.
4. **Fix `permutation_importance` train/test separation** — accept optional `X_test`/`y_test` or split indices; default to current behavior with a warning if not provided.
5. **Fix `splits_used` label** — use accurate label (e.g., `"full_sample"`) when no walk-forward split is applied.
6. **Add `approximation` flag to `shapley_approx` return dict** — `{"approximation": true, "method": "marginal_contribution"}`.
7. **Add `run_id` and `data_hash` to report builders** — generate at build time and include in markdown output.
8. **Add `metrics` to Quality sheet in Excel** — or create a dedicated Metadata sheet with all required fields.
