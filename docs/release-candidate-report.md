# Release Candidate Report — v1.0-RC (auf Basis v0.9.0)

**Datum:** 2026-08-24 · **Status: RELEASE CANDIDATE: NEIN** → **JA nach verbleibenden Medium-Fixes ODER expliziter Freigabe mit dokumentierten Einschränkungen**

## Entscheidung

Die Release-Blocker-Kriterien sind **erfüllt**:

| Blocker | Status |
|---|---|
| Look-Ahead-Bias / Data Leakage / Test-Set-Leakage | Keiner nachweisbar; Purged K-Fold mit beidseitigem Embargo korrekt |
| Falsch berechnete Finanzmetriken | MC-Varianzbug und Backtest-Kostenbug **behoben und durch Tests abgesichert** |
| Nicht reproduzierbare Kernberechnungen | 2×-Lauf byte-identisch (inkl. run_ids) |
| Secrets im Repository | Keine gefunden (AV-Key env-only) |
| Unkontrollierte externe Netzwerkzugriffe | Nur Yahoo/AV/Ollama(localhost), dokumentiert |
| Datenlizenzen | Yahoo/AV ToU dokumentiert; Apache-2.0 kompatibel |
| Crash im Standardworkflow | 366/366 Tests grün, Demo-Pipeline läuft |
| Falsche/unklare Exporte | CSV/Excel/PDF mit Systemversion, Seed, Run-ID, Disclaimer verifiziert |
| Handelsausführung im Rebalancing | Ausgeschlossen — nur Proposal-Datenobjekte |
| Offene Critical/High-Security | Keine offen |

## Verbleibende offene Punkte (Medium/Low, nicht blockierend laut Schweregraden)

Medium:
1. Adapter-Currency-Hardcoding USD (falsche Währung bei Nicht-US-Tickers möglich)
2. Doppelte Adapter-Implementierungen konsolidieren
3. Cache-Schema-Versionierung + robustes json.loads
4. AV-API-Key aus URL in Header

Low: Audit-Hash-Kette, GDPR delete-vs-anonymize-Begriffsklärung, Mindestordergrößen,
WS-"simuliert"-Labeling, MC-Vektorisierung.

## Empfehlung

v1.0 freigeben, sobald die vier Medium-Punkte behoben sind (geschätzt < 1 Tag Aufwand).
Alternativ v1.0-RC taggen mit documented limitations für Punkt 1–3, sofern der
Einsatzbereich auf USD/EUR-Depots beschränkt bleibt.

## Artefakte

- docs/quantitative-validation-review.md (PASS MIT WARNUNGEN)
- docs/market-data-quality-review.md (WARN, durch Delegation erstellt)
- docs/explainability-reporting-review.md (FAIL→FIXES umgesetzt, durch Delegation erstellt)
- docs/stress-rebalancing-production-review.md (PASS MIT WARNUNGEN)
- docs/integration-review.md · docs/test-report.md · docs/security-review.md
