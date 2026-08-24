# Post-Release Report — v0.9.1

**Datum:** 2026-08-24 · **Basis:** Commit afc7948, Release v0.9.1 (Latest)

## Feedback-Lage

- GitHub Issues: 0 offen, 0 geschlossen
- Externe Beta-Rückmeldungen: noch keine (Plan vorhanden: docs/beta-test-plan.md)
- Interne Validierung: 12/12 Beta-Tests PASS, 385/385 Regressionstests

**Keine reproduzierbaren Nutzerfehler → kein Patch-Release erforderlich.**
Es wurden keine Bugs "spekulativ" reproduziert; die bekannten Limitations sind
bereits mit Regressionstests bzw. dokumentierten Warnungen abgesichert.

## Bekannte Limitations — Blockierend? Nein.

| Limitation | Kategorie | Status |
|---|---|---|
| Rebalancing ohne Mindestordergrößen | Feature-Wunsch/Berechnung | dokumentiert, P1 in v1.0-Roadmap |
| Synchrone Langläufer (kein Job-Queue) | Performance/UX | dokumentiert, P1 |
| Simulierter WebSocket-Feed | Datenqualität | dokumentiert + Label "simuliert", P1 |
| CV-Embargo in Indizes | methodisch | dokumentiert, P2 |
| Currency `unknown` ohne Ticker-Marker | Datenqualität | by design (INCOMPLETE-Policy), P3 |

## Sicherheits- und Korrektheits-Posture

- 0 Critical / 0 High (pip-audit-Findings betreffen Fremdpakete der Umgebung)
- Keine Order-Ausführungspfade; AV-Key ausschließlich im Header
- FX ohne stillen Fallback; Exporte mit vollständigen Metadaten
- Reproduzierbarkeit testbelegt (Seed 42, identischer Data-Hash)

## Empfehlung

1. Externe Beta-Rückläufe aktiv einsammeln (Testplan liegt bereit).
2. v1.0-Umsetzung gemäß docs/v1.0-roadmap.md starten — P0 existiert nicht
   (keine offenen Bugs), Start direkt bei P1.
3. Nächster Patch-Release nur bei reproduzierten Bugs aus echtem Feedback.
