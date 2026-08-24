# Release Audit v0.9.1 (stable)

**Datum:** 2026-08-24 · **Git-Stand:** c06eabc + Release-Prep-Commits · **Systemversion:** 0.9.1-rc.1

## Ausgeführte Befehle & Ergebnisse

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Testsuite | `pytest tests/ -q` | **385 passed, 0 failed, 0 skipped** |
| Coverage | `pytest --cov=packages --cov=apps` | 71 % gesamt; kritische Module 92–97 % |
| Linter | `ruff check packages/ apps/ --select F,E9 --fix` | 27 auto-fixes (unused imports), Rest dokumentiert |
| Dependency-Scan | `pip-audit --skip-editable` | 2 Findings (chromadb, pdfkit) — **gehören zu anderen Projekten** der geteilten Umgebung, nicht zu local-market-lab |
| Secret-Scan | grep über py/toml/yml/iss | keine Secrets im Repository |
| Clean-Venv | `python -m venv` + `pip install -e ".[dev,analytics,export]"` + pytest | **385/385 grün**; dabei fehlende Dep `requests` aufgedeckt und in pyproject ergänzt |
| E2E-Lauf 2× | `scripts/e2e_audit.py` | alle Schritte PASS; **Ergebnisse byte-identisch** (Seed 42) |
| Exportvergleich | CSV-Metadatenkopf, Excel-Quality-Sheet, PDF-Magic geprüft | PASS |

## E2E-Ergebnis (Run 1 == Run 2)

data_hash `9834427b65434a7d` · Quality: 750 Punkte, 0 Duplikate · WF: 21 Folds,
OOS-Sharpe −0.17 · Purged CV avg 0.4731 · Tuning best w=0.5 (−0.545) ·
Backtest: PeriodicRebalance schlägt Buy&Hold leicht (134.02 vs 133.83 bei Kosten) ·
Stress 2008 DD −29.4 % · MC p01 0.654 · Rebalancing: 2 Vorschläge, Kosten 2.4 bp.

Hinweis: DM-Vergleich im Audit-Skript leer, weil die Test-WalkForwardResults keine
`predictions` tragen — direkter DM-Aufruf verifiziert (stat −2.06, p 0.039).

## Offene Probleme

- Medium: Rebalancing ohne Mindestordergrößen; synchrone Langläufer (kein Job-Queue); WS simuliert.
- Low: AV-Key-Länge unvalidiert; Audit-Log ohne Hash-Kette; CV-Embargo in Indizes statt Kalendertagen.

## Status: PASS MIT WARNUNGEN — Release Candidate freigegeben als Pre-Release
