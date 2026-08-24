# Security, Privacy & Compliance Review

**Project:** Local Market Lab
**Version:** 0.1.0
**Commit:** 1aa285d
**Date:** 2026-08-24
**Reviewer:** Security Audit Agent

---

## Executive Summary

This review covers the security, privacy, and compliance posture of the Local Market Lab roadmap implementation. The codebase is a local-first portfolio analytics, backtesting, and scenario simulation tool.

**Overall Rating: LOW-MEDIUM RISK**

The codebase demonstrates good security practices:
- All SQL queries use parameterized statements
- No command injection, no pickle deserialization
- Secrets are not logged or stored in the repository
- Rebalancing is correctly suggestion-only (no trade execution)
- Clear disclaimers about non-advisory nature

**Key Findings:**
- **Critical:** 0
- **High:** 3 (all fixed)
- **Medium:** 5 (documented, mitigations available)
- **Low:** 4 (documented)

---

## 1. Input Validation

### 1.1 API Endpoints — Parameter Validation

| Endpoint | Method | Validation | Status |
|----------|--------|------------|--------|
| `/api/v1/health` | GET | None needed | ✅ |
| `/api/v1/system/info` | GET | None needed | ✅ |
| `/api/v1/market/symbols` | GET | None needed | ✅ |
| `/api/v1/market/prices/{symbol}` | GET | Symbol regex + parameterized SQL | ✅ |
| `/api/v1/market/yahoo/{symbol}` | GET | Symbol regex (prevents URL injection) | ✅ FIXED |
| `/api/v1/market/indicators/{symbol}` | POST | Symbol regex + parameterized SQL | ✅ FIXED |
| `/api/v1/market/data/{symbol}` | GET | Symbol regex, Query-enforced `source` | ✅ FIXED |
| `/api/v1/quality/report/{symbol}` | GET | Symbol regex | ✅ FIXED |
| `/api/v1/market/cache` | DELETE | Symbol regex | ✅ FIXED |
| `/api/v1/portfolio/{name}` | GET | Parameterized SQL | ✅ |
| `/api/v1/portfolio/{name}/rebalancing` | GET | Type-safe (threshold: float) | ✅ |
| `/api/v1/portfolio/{name}/rebalance` | POST | Pydantic model validation | ✅ |
| `/api/v1/backtest` | POST | Dict-based (no free-text SQL) | ✅ |
| `/api/v1/scenario` | POST | Type-safe integers | ✅ |
| `/api/v1/scenario/stress` | POST | Pydantic model + allowlist | ✅ |
| `/api/v1/scenario/crisis` | POST | Pydantic model + allowlist | ✅ |
| `/api/v1/scenario/forecast/{symbol}` | POST | Parameterized SQL | ✅ |
| `/api/v1/validation/walk-forward` | POST | Type-safe | ✅ |
| `/api/v1/validation/cv` | POST | Type-safe | ✅ |
| `/api/v1/validation/hyperparameter` | POST | Type-safe | ✅ |
| `/api/v1/export/pdf` | POST | No file paths from user | ✅ |
| `/api/v1/export/excel` | POST | No file paths from user | ✅ |
| `/api/v1/export/csv` | POST | Kind allowlist | ✅ FIXED |
| `/api/v1/explainability/importance` | GET | numpy.asarray validation | ✅ |
| `/api/v1/explainability/compare` | GET | Dict-based | ✅ |
| `/api/v1/ollama/models` | GET | No user input | ✅ |
| `/api/v1/ollama/chat` | POST | Model string, messages list | ✅ |
| `/api/v1/ollama/optimize_prompt` | POST | Template-key lookup | ✅ |
| `/api/v1/game/create` | POST | Type-safe | ✅ |
| `/api/v1/game/{id}/order` | POST | Type-safe | ✅ |
| `/api/v1/game/{id}/tick` | POST | Type-safe | ✅ |
| `/api/v1/lobby/rooms` | POST/WS | Dict-based | ✅ |
| `/api/v1/compliance/audit-log` | GET | Type-safe limit | ✅ |
| `/api/v1/compliance/export/{user}` | GET | Parameterized SQL | ✅ |

### 1.2 Symbol Validation

All ticker symbols are now validated against the regex: `^[A-Za-z0-9.\-^=]{1,20}$`

This allows:
- Standard tickers (AAPL, MSFT, IWDA)
- Yahoo-style tickers (BTC-USD, ^GDAXI)
- Index tickers (=DAX)

This blocks:
- Path traversal attempts (`../../../etc/passwd`)
- URL injection (`foo?bar=1`, `foo#anchor`)
- SQL injection (symbols are always parameterized)
- Command injection

---

## 2. Injection Attack Surface

### 2.1 SQL Injection

**Risk: NONE**

All SQL queries use parameterized statements (`?` placeholders). The `Workspace` class in `packages/storage/workspace.py` consistently uses:
```python
ws.conn.execute("SELECT ... WHERE symbol=?", (symbol.upper(),))
```

No string interpolation or concatenation is used in SQL.

### 2.2 Path Traversal

**Risk: LOW (Fixed)**

The CSV export endpoint now validates the `kind` parameter against an allowlist (`trades`, `equity`, `scenario`). Previously, arbitrary strings could be passed to construct filenames.

**Fix:** Added `_EXPORT_KIND_ALLOWED = frozenset({"trades", "equity", "scenario"})` in `export_routes.py`.

### 2.3 Command Injection

**Risk: NONE**

No subprocess calls, no `os.system()`, no `eval()`, no `exec()` found in the API or package code. The `windows/src/` files use Qt's `app.exec()` which is safe.

### 2.4 Insecure Deserialization

**Risk: NONE**

No `pickle`, `marshal`, or `shelve` usage found. YAML is used only in `pyyaml>=6.0` but no `yaml.load()` with unsafe loaders found in the codebase.

---

## 3. CORS, Rate Limiting, Request-ID

### 3.1 CORS

**Previous Risk: HIGH — Fixed**

Before fix: `allow_methods=["*"]`, `allow_headers=["*"]`, default origins `["*"]`.

**Fix applied:**
```python
allow_origins=["http://localhost:3000", "http://localhost:8000", ...]
allow_methods=["GET", "POST", "PUT", "DELETE"]
allow_headers=["Content-Type", "Authorization", "X-Request-ID"]
```

CORS can be customized via `LML_CORS_ORIGINS` environment variable.

### 3.2 Rate Limiting

**Risk: MEDIUM**

- Sliding window rate limiter: 100 requests/minute per IP
- Implemented in `packages/api/middleware.py`
- Returns `429` with `Retry-After: 60` header

**Limitations:**
- No global rate limit (only per-IP)
- In-memory storage (resets on restart)
- No burst protection beyond the window

**Recommendation:** For production, consider Redis-backed rate limiting.

### 3.3 Request-ID

**Status: IMPLEMENTED**

- `RequestIDMiddleware` attaches unique request IDs
- Honors `X-Request-ID` header from client
- Returns `X-Request-ID` in response
- Used in all log entries

---

## 4. Secrets and Sensitive Data in Logs

### 4.1 Logging Audit

**Risk: NONE — No secrets logged**

Verified:
- No API keys in logs (Alpha Vantage key is in env vars only)
- No tokens or passwords in logs
- Request IDs and paths are logged (no query parameters)
- Exception messages are logged internally but not exposed to clients (see fix below)

### 4.2 Exception Detail Leakage

**Previous Risk: HIGH — Fixed**

Before fix: `ExceptionHandlerMiddleware` returned `str(exc)` in the response body, potentially leaking internal paths, SQL details, or stack traces.

**Fix applied:** Error responses now return a generic message:
```json
{
  "error": "internal_server_error",
    "request_id": "...",
    "detail": "An unexpected error occurred. Check server logs."
}
```

Internal details are still logged server-side for debugging.

### 4.3 System Info Endpoint

**Previous Risk: MEDIUM — Fixed**

Before fix: `/api/v1/system/info` returned the full database path, potentially revealing filesystem structure.

**Fix applied:** Only the filename (not the full path) is now returned.

---

## 5. Market Data Providers & External HTTP

### 5.1 Yahoo Finance

**Risk: MEDIUM**

- User-Agent spoofing (legitimate for Yahoo compatibility)
- Symbol validation prevents URL injection
- Timeout configurable via `LML_YAHOO_TIMEOUT` (default: 10s)
- Falls back from query1 to query2 endpoint

**License compliance:** Adapter metadata correctly notes "Yahoo Terms of Service — non-commercial, no redistribution."

### 5.2 Alpha Vantage

**Risk: LOW**

- API key from environment variable only (`ALPHAVANTAGE_KEY`)
- Rate-limit aware (exponential backoff)
- Retry logic with `MAX_RETRIES = 3`
- 12-second spacing between requests (free tier compliance)

**Key protection:** The API key is never logged. It is only used in URL construction for Alpha Vantage's API.

### 5.3 Network Egress Control

- Default mode is offline (synthetic data adapter)
- External calls only happen when explicitly requested
- `offline=True` parameter available on adapters

---

## 6. Ollama and Model Response Handling

### 6.1 Ollama Client

**Risk: LOW**

- Connects only to `OLLAMA_HOST` (default: localhost:11434)
- All requests via HTTP to local daemon
- No authentication (expected for local-only)
- Timeout configurable (default: 180s)

### 6.2 Model Response Handling

**Risk: NONE**

- Responses are treated as opaque strings
- No parsing of model output as code
- No execution of model-suggested commands
- Chat history is transient (not persisted)

### 6.3 Prompt Templates

- Templates are static strings in code
- User input is inserted as conversation messages, not system prompts
- System prompts explicitly state: "I don't predict prices"

---

## 7. Export Functions

### 7.1 File Export Audit

| Export Type | Path Control | Content Validation | Status |
|-------------|--------------|-------------------|--------|
| PDF | Internal (run_id-based) | User-supplied metrics/trades | ✅ |
| Excel | Internal (run_id-based) | User-supplied metrics/trades | ✅ |
| CSV trades | Internal (run_id-based) | User-supplied trades | ✅ |
| CSV equity | Internal (run_id-based) | User-supplied curve | ✅ |
| CSV scenario | Internal (run_id-based) | User-supplied runs | ✅ |

### 7.2 Path Traversal Protection

**Fix applied:** The `kind` parameter in CSV export is validated against an allowlist. Filenames are constructed as `{kind}_{run_id}.ext` where `run_id` is a UUID — no user-controlled path components.

### 7.3 Data Leakage

- Export files are written to `./exports/` directory (configurable via `LML_EXPORT_*_PATH`)
- Files are served via `Response` with `Content-Disposition: attachment`
- No directory listing endpoint
- `.gitignore` excludes `*.db`, `*.sqlite`, and user data

---

## 8. Audit Logs

### 8.1 Implementation

The `AuditLogger` in `packages/compliance/bank_ready.py` provides:
- Append-only log table (`audit_log`)
- Records: user, timestamp, action, params, result_hash
- Used for GDPR export/deletion events

### 8.2 Integrity

**Risk: MEDIUM**

- Table checksums are computed and stored (`DataIntegrity` class)
- Verification on demand via `/api/v1/compliance/integrity-check`
- No cryptographic chain between entries (no hash-of-previous)

**Recommendation:** For bank-grade audit trails, implement hash chaining.

### 8.3 GDPR Compliance

- Data export: `GET /api/v1/compliance/export/{user}`
- Data deletion: `DELETE /api/v1/compliance/delete-account/{user}`
- Anonymization replaces portfolio name with hash

---

## 9. Rebalancing — Suggestion Only

### 9.1 Safety Verification

**Confirmed: NO TRADE EXECUTION**

The rebalancing module (`packages/portfolio/rebalancing.py`) is correctly suggestion-only:
- Returns `RebalancingProposal` dataclasses (not orders)
- Never calls broker APIs
- Never modifies positions in the database
- API responses include `"disclaimer": "Suggestions only — no trades executed."`

### 9.2 Trade Execution Audit

| Component | Executes Orders | Status |
|-----------|-----------------|--------|
| Rebalancing module | No (suggestions only) | ✅ |
| Portfolio engine | No (read-only valuation) | ✅ |
| Game module | Yes (paper trades, internal) | ✅ |
| Backtest engine | Yes (simulated, no real money) | ✅ |
| CLI | No | ✅ |

---

## 10. Disclaimer and Compliance Messaging

### 10.1 Disclaimer Implementation

**Status: IMPLEMENTED**

`packages/compliance/guard.py` provides:
- `RESEARCH_DISCLAIMER`: Clear statement of non-advisory nature
- `SCENARIO_DISCLAIMER`: Clarifies simulation vs. forecast
- `check_language()`: Pattern-matches forbidden advice phrases

### 10.2 Blocked Language Patterns

The following patterns are blocked in generated output:
- "Kaufsignal", "Verkaufssignal", "buy signal", "sell signal"
- "garantiert", "guaranteed"
- "sichere Rendite", "safe return"
- "beste Anlage", "best investment"
- "Empfehlung: kaufen/verkaufen", "recommend buying/selling"

### 10.3 Ollama System Prompts

All system prompts include explicit instructions:
- "I don't predict prices"
- "You do NOT predict whether a strategy will be profitable"
- "paper-trading results do not guarantee live-trading outcomes"
- "Suggestions only — no trades executed"

---

## 11. Dependency Security

### 11.1 Direct Dependencies

| Package | Version | License | Risk |
|---------|---------|---------|------|
| typer | >=0.12 | MIT | Low |
| fastapi | >=0.110 | MIT | Low |
| uvicorn[standard] | >=0.27 | BSD-3 | Low |
| pydantic | >=2.6 | MIT | Low |
| pyyaml | >=6.0 | MIT | Low |
| python-dateutil | >=2.9 | Apache-2.0/BSD | Low |

### 11.2 Optional Dependencies

| Package | Version | License | Risk |
|---------|---------|---------|------|
| numpy | >=1.26 | BSD-3 | Low |
| pandas | >=2.2 | BSD-3 | Low |
| yfinance | (optional) | Apache-2.0 | Low |
| reportlab | (optional) | BSD-3 | Low |
| openpyxl | (optional) | MIT | Low |
| requests | (optional) | Apache-2.0 | Low |

### 11.3 License Compatibility

**Project License:** Apache-2.0

All dependencies are compatible with Apache-2.0:
- MIT: Compatible
- BSD-3: Compatible
- Apache-2.0: Identical license

No GPL/AGPL dependencies found.

---

## 12. Repository Security

### 12.1 Secrets in Repository

**Status: CLEAN**

- `.env` is in `.gitignore`
- `.env.example` contains only placeholder values
- No API keys found in git history
- No `*.key`, `*.pem`, or `secrets*` files found

### 12.2 Sensitive Files in .gitignore

```
.env
*.db
*.sqlite
data/*
.vscode/
.idea/
```

---

## Findings Summary

### Critical (0)
None identified.

### High (3 — All Fixed)

| # | Finding | Fix |
|---|---------|-----|
| H1 | CORS wildcard (`*`) allows any origin | Default to localhost only, configurable via env |
| H2 | Exception handler leaks internal details to client | Generic error message, details in server logs only |
| H3 | CSV export `kind` parameter allows path traversal | Allowlist validation |

### Medium (5)

| # | Finding | Recommendation |
|---|---------|----------------|
| M1 | Rate limiter is per-IP only, in-memory | Consider Redis for distributed deployments |
| M2 | Audit log lacks hash chaining | Implement blockchain-style integrity for bank use |
| M3 | Yahoo adapter uses User-Agent spoofing | Monitor Yahoo ToS compliance |
| M4 | No request body size limits | Add FastAPI body size limits |
| M5 | WebSocket endpoints lack authentication | Add token-based auth for production |

### Low (4)

| # | Finding | Recommendation |
|---|---------|----------------|
| L1 | No request timeout on some endpoints | Add global timeout middleware |
| L2 | Python version exposed in `/system/info` | Consider removing for production |
| L3 | Game chat has no content filtering | Add profanity/filter for public rooms |
| L4 | No Content-Security-Policy headers | Add CSP headers for web UI |

---

## Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| No secrets in repository | ✅ PASS | `.env` in `.gitignore`, no keys in history |
| No uncontrolled network access | ✅ PASS | External calls opt-in, symbol validated |
| All user inputs validated | ✅ PASS | Regex on symbols, parameterized SQL, allowlists |
| No direct trading actions | ✅ PASS | Rebalancing is suggestion-only |
| Exports contain only authorized data | ✅ PASS | UUID-based filenames, kind allowlist |
| Security report in repository | ✅ PASS | This document (`docs/security-review.md`) |

---

## Recommendations for Production

1. **Add HTTPS termination** (reverse proxy with TLS)
2. **Implement authentication** (OAuth2 or API keys)
3. **Add request body size limits** (prevent DoS)
4. **Enable structured log aggregation** (ELK/Loki)
5. **Set up dependency vulnerability scanning** (Dependabot/Snyk)
6. **Add Content-Security-Piddleware**
7. **Configure CORS origins explicitly** for production domain
8. **Implement WebSocket authentication** for lobby/game endpoints

---

*Report generated automatically by Security Audit Agent.*
*For questions, contact the development team.*
