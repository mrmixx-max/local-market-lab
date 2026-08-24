# Beta-Test-Report — v0.9.1-rc.1

**Datum:** 2026-08-24 · **Umgebung:** Windows 10 (AMD64), Python 3.11.15 · **Commit:** e9575c5 (Tag v0.9.1-rc.1)

## Release-Validierung

| Check | Ergebnis |
|---|---|
| GitHub-Release vorhanden | ✅ erstellt nachträglich (fehlte initial) — Pre-Release, 4 Assets |
| Tag auf GitHub | ✅ refs/tags/v0.9.1-rc.1 |
| SHA256SUMS.txt vs. Artefakte | ✅ alle drei OK (`sha256sum -c`) |
| Wheel-Install in frischer Venv | ✅ Import + `lml --help` funktionieren; SYSTEM_VERSION = 0.9.1-rc.1, Cache-Schema 2 |

## Beta-Tests (scripts/beta_cycle.py)

| # | Test | Erwartet | Tatsächlich | Status |
|---|---|---|---|---|
| 1 | Demo-Daten laden | Preise im Workspace | 1620 Preiszeilen | PASS |
| 2 | CSV-Import (Semikolon-CSV) | Zeilen importiert | import_prices OK | PASS |
| 3 | Cache-Miss → Hit → Hit | None → Daten → Daten | exakt so | PASS |
| 4 | Datenqualität | Report mit Hash/Status | status=warning (Gap erkannt), Hash gesetzt | PASS |
| 5 | Backtest mit Kosten | Kosten senken Endwert | costly < free | PASS |
| 6 | Walk-Forward | Folds erzeugt, Seed dokumentiert | 7 Folds, seed=42 | PASS |
| 7 | Hyperparameter-Tuning | Trials + best_params | 2 Trials, Grid deterministisch | PASS |
| 8 | Explainability SHAP-Flag | approximation=true | true | PASS |
| 9 | Stress-Tests | deterministisch + p01 | identische run_id, dd=-0.57 | PASS |
| 10 | Rebalancing proposals-only | Vorschläge, kein Ausführungspfad | 2 Proposals, keine Order-Funktionen im Modul | PASS |
| 11 | Exporte ohne Key-Leak | AV-Key taucht nirgends auf | keine Leaks in CSV/XLSX/PDF+Metadaten | PASS |
| 12 | API Health + Path-Traversal | 200 mit Version / 404 bei ../.. | 200 "0.9.1-rc.1" / 404 | PASS |

**Ergebnis: 12/12 PASS, 0 FAIL.**

## Fehler während des Zyklus

| Fehler | Ursache | Fix |
|---|---|---|
| GitHub-Release fehlte beim ersten Check | Tag war gepusht, Release nie erstellt | Release als Pre-Release mit allen Assets erstellt |
| Beta-Skript: falscher Funktionsname `import_prices_csv` | Tippfehler im Audit-Skript, nicht im Produkt | Skript auf `import_prices` korrigiert (kein Produkt-Bug) |

## Leak- und Sicherheitsprüfung

- AV-Key (Testmarker) in keiner Exportdatei, keinem Metadaten-Dict, keinem Log.
- Path-Traversal (`%2E%2E%2Fetc`) → 400er/404er, kein Dateizugriff.
- Rebalancing-Modulquelltext geprüft: keine order/broker/exec-Pfade.

## SBOM

`artifacts/sbom-v0.9.1-rc.1.json` (CycloneDX 1.4 via pip-audit, 301 Komponenten).
Enthält die 2 bekannten pip-audit-Findings (chromadb/pdfkit) — Umgebungsartefakte
anderer Projekte, nicht Abhängigkeiten von local-market-lab.

## Release-Empfehlung

Nur bekannte, dokumentierte Probleme offen → **v0.9.1 stabil vorbereiten**
nach Beta-Rücklauf ohne neue reproduzierbare High/Medium-Fehler.
