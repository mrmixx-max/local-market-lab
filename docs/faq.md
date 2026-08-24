# Frequently Asked Questions

## General

**Q: What is Local Market Lab?**
A: A privacy-first, local-first workbench for portfolio analytics, backtesting, and
scenario simulation. All data stays on your machine. No cloud, no account, no telemetry.

**Q: Is this financial advice?**
A: **No.** LML is exclusively for research and education. No buy/sell signals, no
recommendations, no forecasts disguised as math. Every scenario result includes
explicit limitations.

**Q: Why no real market data included?**
A: Privacy. Real data requires API keys and sends queries to external servers. LML
works completely offline with synthetic data or your own CSV imports. External data
(Yahoo, Alpha Vantage) is optional.

**Q: What's new in this release?**
A: Data quality checks, walk-forward validation, hyperparameter tuning, stress testing,
crisis scenarios, technical indicators, advanced risk metrics, multi-format export
(PDF/Excel/CSV), explainability, and compliance/audit features.

---

## Data & Import

**Q: How do I import my own portfolio?**
A: Use CSV import:
```bash
lml import txn my-trades.csv --portfolio mybook
lml import prices prices-iwda.csv IWDA
```
CSV formats are tolerant about headers (EN/DE) and delimiters (`;` or `,`).

**Q: Can I use real market data?**
A: Yes, via Yahoo Finance (no API key needed) or Alpha Vantage (requires API key):
```bash
lml import market AAPL --adapter yahoo
lml import market MSFT --adapter alphavantage
```
Set `ALPHAVANTAGE_KEY` environment variable for Alpha Vantage.

**Q: How do I check data quality?**
A: Use the quality report endpoint:
```bash
curl "http://127.0.0.1:8322/api/v1/quality/report/IWDA?source=yahoo"
```
This checks for missing data, splits, FX mismatches, stale data, and price outliers.

---

## Validation & Models

**Q: What is walk-forward validation?**
A: A robust backtesting method that trains on expanding windows and tests on
out-of-sample periods. Prevents look-ahead bias and gives realistic performance
estimates.

```bash
curl -X POST http://127.0.0.1:8322/api/v1/validation/walk-forward \
  -H "Content-Type: application/json" \
  -d '{"symbol":"IWDA","train_window":252,"test_window":63,"step":21}'
```

**Q: What is purged cross-validation?**
A: K-fold CV with a gap between train and test folds to prevent information leakage
from autocorrelated time series data.

**Q: How does hyperparameter tuning work?**
A: Random or grid search over parameter combinations with walk-forward evaluation.
Reproducible via seed control.

---

## Stress Testing

**Q: What stress scenarios are available?**
A: Three historical crises (2008 Financial, 2020 COVID, 2022 Inflation) and three
hypothetical scenarios (30% crash, volatility spike, +300bp rate shock).

**Q: What crisis analyses are available?**
A: Correlation break (diversification loss), liquidity crunch (market impact costs),
and sector rotation (sector-specific shocks).

---

## Export & Reports

**Q: How do I export a PDF report?**
A: Use the PDF export endpoint:
```bash
curl -X POST http://127.0.0.1:8322/api/v1/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"title":"My Report","metrics":{"cagr":10.5},"trades":[...]}' \
  --output report.pdf
```

**Q: What does the Excel export include?**
A: Multi-sheet workbook with Summary, Trades, Equity, Drawdown, and Quality sheets.

---

## Compliance

**Q: What does "Bank-Ready" mean?**
A: LML provides an append-only audit log, SHA-256 data integrity checks, and
BaFin-style compliance reports. **Note:** This is a research tool, not a regulated
banking system. It provides audit trail capabilities but does not include encryption
at rest, access control, or digital signatures.

**Q: How do I export user data (GDPR)?**
A: Use the compliance export endpoint:
```bash
curl http://127.0.0.1:8322/api/v1/compliance/export/username
```

---

## Configuration

**Q: What environment variables are available?**

| Variable | Default | Description |
|----------|---------|-------------|
| `LML_HOST` | `127.0.0.1` | API server host |
| `LML_PORT` | `8322` | API server port |
| `LML_DB` | `./data/marketlab.db` | SQLite path |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server |
| `LML_CORS_ORIGINS` | `*` | CORS origins |
| `LML_CACHE_TTL_HOURS` | `24` | Market data cache TTL |
| `LML_QUALITY_MISSING_THRESHOLD` | `0.05` | Missing data warning threshold |
| `LML_QUALITY_STALE_HOURS` | `24` | Stale data threshold |
| `LML_WF_TRAIN_WINDOW` | `252` | Walk-forward train window |
| `LML_WF_TEST_WINDOW` | `63` | Walk-forward test window |
| `LML_WF_STEP` | `21` | Walk-forward step size |
| `LML_CV_SPLITS` | `5` | CV number of splits |
| `LML_CV_GAP` | `21` | CV purge gap |
| `LML_STRESS_MAX_DD_THRESHOLD` | `0.30` | Stress max drawdown alert |
| `LML_EXPORT_PDF_PATH` | `./exports` | PDF export directory |
| `LML_EXPORT_EXCEL_PATH` | `./exports` | Excel export directory |
| `LML_EXPORT_CSV_PATH` | `./exports` | CSV export directory |
| `ALPHAVANTAGE_KEY` | — | Alpha Vantage API key |

---

## Technical

**Q: Why Python and not C++/Rust?**
A: Readability, reproducibility, easy installation. Performance is sufficient for
the target use case (thousands of scenario runs complete in <1s).

**Q: Does this work on macOS/Linux?**
A: Yes, the web UI and CLI are platform-independent. The Windows app (PyQt6) is
Windows-specific.

**Q: How reproducible are results?**
A: Every scenario, validation, and export run records seed, parameters, and a data
hash. Same inputs always produce same outputs. Results are deterministic when using
the same seed.
