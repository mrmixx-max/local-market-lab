# Quantitative Validation Review

**Status: PASS MIT WARNUNGEN** (nach Fixes)
**Geprüft:** packages/validation/*, packages/metrics/risk.py, packages/backtest/engine.py, packages/scenarios/stress.py
**Datum:** 2026-08-24 · **Reviewer:** ox-alpha (Eigenreview, Delegation ausgefallen)

## Geprüfte Module und Befehle

| Modul | Prüfung | Ergebnis |
|---|---|---|
| validation/walk_forward.py | Split-Logik, Look-Ahead, Metriken | PASS |
| validation/cv.py | Purged K-Fold inkl. Gap/Embargo | PASS (mit Einschränkung, s.u.) |
| validation/hyperparameter.py | Data Snooping, Seed-Kontrolle | WARN → Fixes dokumentiert |
| metrics/risk.py | Unabhängige Referenzrechnung Sharpe/Sortino/CAGR/MDD/VaR/CVaR | PASS |
| backtest/engine.py | Kostenmodell, Turnover | FAIL → FIXED |
| scenarios/stress.py (MC) | Student-t-Varianz | FAIL → FIXED |

Verifikationskommandos: `python -m pytest tests/unit/test_validation.py tests/integration/test_no_lookahead_bias.py tests/integration/test_determinism.py -q`

## Behobene Probleme (Critical/High)

1. **[FIXED — Critical] Monte-Carlo Student-t Varianz falsch** (`stress.py`):
   `z = sum(gauss(0,1) for _ in range(2))` hat Varianz 2 statt 1; alle Fat-Tail-Quantile
   waren um Faktor √2 verzerrt. Fix: `z = gauss(0,1)` plus Standardisierung
   `t / sqrt(df/(df-2))`, `df > 2` erzwungen. Verifiziert: empirische std = 1.00.
2. **[FIXED — High] Backtest-Kosten doppelt/gegenläufig gebucht** (`backtest/engine.py`):
   Zeile mit `cash -= trade_value + ... * 0` war toter Code, Kosten gingen nie in die
   Curve ein (Test `test_costs_reduces_final_value` schlug fehl). Fix: eine korrekte
   Deduktion `cash -= cost` + Kaufkosten reduzieren investierten Betrag.
3. **[FIXED — High] Stress-Test ignorierte Seed** (hardcoded `seed=42`) und generierte
   nicht-deterministische run_ids (uuid4). Fix: Seed wird durchgereicht,
   `run_id = stress-{scenario}-{seed}` deterministisch.

## Look-Ahead-Bias-Analyse

- Walk-forward: Train `[0:i]`, Test `[i:i+test_window]`, Test liegt strikt nach Train. Kein Leakage.
- Purged K-Fold: Gap wird vor UND nach dem Test-Fold entfernt (Embargo beidseitig). Korrekt.
- Hyperparameter-Tuning: Evaluation auf fixem 2/3–1/3-Split; Tuning sieht den letzten
  Drittel als "Test". **WARN (Medium)**: dieser Tuning-Test-Split ist danach nicht mehr
  unberührt — ein finales Holdout muss außerhalb des Tunings liegen. Dokumentiert,
  API-Routen müssen sicherstellen, dass das Final-Holdout separat bleibt.
- Feature-Engineering/Skalierung: Die Kernmodule sind rein (Listen von Preisen); es gibt
  keinen globalen Scaler. Skalierung im Modell-Code des Nutzers liegt außerhalb des Scope;
  dokumentierte Konvention: fit nur auf Trainingsfenster.

## Offene Risiken / WARN

- **CV auf Lücken-indizes**: `_purged_kfold_indices` entfernt Indizes, nicht Kalendertage.
  Bei Datenlücken ist der Embargo-Zeitraum in Handelstagen kleiner als nominal. (Low)
- **Sharpe ohne rf in CV-Metriken**: Standard rf=0, dokumentiert. (Low)
- **Walk-forward OOS-Aggregation ruft strategy_fn pro Fold erneut auf** — bei zustandsbehafteten
  Strategien mit Zufall muss der Aufruf deterministisch sein (Seed-Doku). (Low)

## Reproduzierbarkeit

Gleicher Lauf 2× (identischer Datensatz, Seed 42): WF-, CV-, Tune-, MC- und Stress-Ergebnisse
byte-identisch. **PASS** (siehe docs/integration-review.md).

## Status: PASS MIT WARNUNGEN

Kein nachweisbarer Look-Ahead-Bias, kein Test-Set-Leakage, keine zufällig gemischten
Zeitreihen, Metriken gegen Referenz verifiziert. Rest-WARN sind Medium/Low und dokumentiert.
