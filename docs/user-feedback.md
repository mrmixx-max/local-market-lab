# User Feedback Log — v0.9.1

**Stand:** 2026-08-24, einen Tag nach Stable-Release

## Eingegangene Meldungen

| Kanal | Anzahl |
|---|---|
| GitHub Issues | 0 |
| Beta-Test-Rückläufe (extern) | 0 — Beta-Plan liegt vor, externe Tester noch nicht befragt |
| Interne Beta-Zyklen | 12/12 PASS (scripts/beta_cycle.py), dokumentiert in docs/beta-test-report.md |

## Kategorisierung

Keine externen Meldungen → keine Gruppierung möglich (keine Spekulation).

Die folgende Tabelle listet die **bekannten Einschränkungen** (aus dem eigenen
Audit, nicht Nutzerfeedback), die bei eingehendem Feedback die wahrscheinlichsten
Meldungskategorien darstellen:

| Bekannte Limitation | Wahrscheinliche Kategorie |
|---|---|
| Rebalancing ohne Mindestordergrößen | Feature-Wunsch / falsche Berechnung |
| Synchrone Langläufer (kein Job-Queue) | Performance / UX |
| Simulierter WebSocket-Feed | Datenqualität / Feature-Wunsch |
| CV-Embargo in Indizes statt Kalendertagen | Datenqualität (methodisch) |
| Currency-Erkennung ohne Marker = unknown | Datenqualität |

## Aufnahmeprozess

Neue Meldungen laufen über die Issue-Vorlage (.github/ISSUE_TEMPLATE/bug_report.yml)
und werden hier mit Kategorie, Reproduktionsstatus und Fix-Referenz ergänzt.
