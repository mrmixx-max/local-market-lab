# Test Report

**Datum:** 2026-08-24 · **Befehl:** `python -m pytest tests/ -q`

## Ergebnis

| Kennzahl | Wert |
|---|---|
| Bestanden | 366 |
| Fehlgeschlagen | 0 |
| Übersprungen | 0 |
| Warnungen | 4 (numpy RuntimeWarnings bei Zero/Negative-Close-Tests — erwartet, Testzweck ist exactly das Reporting solcher Daten) |

## Suite-Zusammensetzung

- Unit: core, validation, metrics-indirekt (via pipeline), quality, marketdata,
  explainability, export, stress, rebalancing, scenarios, portfolio, indicators
- Integration: no_lookahead_bias, determinism, backtest_costs, fx_edge_cases,
  cache_behavior, data_quality_edge_cases, adapters, pipeline, api_game, game, ollama

## Während des Härtens geänderte Tests

1. `test_explainability.py::test_basic_shape` — Assertion auf korrektes
   `splits_used="permutation_on_eval_set"` (alter Wert war der Bug).
2. `test_stress.py::test_lower_df_fatter_tails` — statistisch korrekt umgebaut:
   Fat-Tail-Monotonie wird auf p01 (Extremquantil) geprüft, Horizont 1 Tag,
   20k Runs. Begründung: bei unit-variance Student-t ist p05 nicht df-monotone;
   alte Assertion testete die falsche Statistik.

## Zusätzliche Verifikationen (außerhalb pytest)

- Reproduzierbarkeit: WF/CV/Tune/MC/Stress je 2× identisch (inkl. run_id) — PASS.
- Exporte: CSV-Metadatenkopf geprüft; Excel Quality-Sheet (system_version, seed,
  disclaimer) via openpyxl gelesen; PDF-Magic-Bytes `%PDF` — PASS.
- MC-Varianz: empirische std der standardisierten t-Innovationen = 1.000–1.004 — PASS.
