# Local Market Lab - Practitioner's Guide (Book)

A technical manual for Local Market Lab: reproducible portfolio research,
scenario simulation, and the PredictionMarker method.

## Files

| File | Format | Pages* | Notes |
|------|--------|--------|-------|
| `LML_Practitioners_Guide.pdf` | PDF | 58 | KDP 6x9, print-ready |
| `LML_Practitioners_Guide.docx` | DOCX | - | 156 headings, editable source |
| `LML_Practitioners_Guide.epub` | EPUB | - | reflowable, 25 chapters |

\* Page count is at 11pt / 6x9 layout. The content is ~156 headings across
12 core chapters + 8 deep-dive chapters (worked arithmetic, source-code
walkthroughs of `predict.py` / `indicators.py` / `risk.py`, a build-your-own
marker lab, comparison tables, and a limits chapter).

## Content

The book explains every marker family the engine emits:

- **Indicator Markers** - SMA, EMA, RSI, MACD, Bollinger
- **Prediction Markers** - the `ensemble_forecast` band (linear / Holt / AR(1))
- **Scenario Markers** - Monte-Carlo, block bootstrap, historical replay
- **Risk Markers** - VaR, CVaR, max drawdown, Sharpe, Sortino, Calmar
- **Drift Markers** - `|current - target|` weight, rebalance proposal
- **Integrity Markers** - the manifest digest (reproducibility seal)

Every chapter ends with *Try This*, *Common Mistakes*, and *FAQ* sections.

## Reproducibility

The charts in this book were generated from the actual repository source
(`packages/scenarios/predict.py`, `packages/marketdata/indicators.py`,
`packages/metrics/risk.py`) using `make_charts2.py`. The book content model
(`trading_book_content_v2.py`) and builder (`build_trading_book.py`) live in
the author's working tree; the rendered artifacts are committed here so the
book travels with the code it documents.

## Disclaimer

This book contains no investment advice. Local Market Lab produces scenarios
and analytics, never buy or sell orders. The engine never executes trades.

---
Author: Erik Gieske — builds local-first tools that prove their own math
and never phone home.
