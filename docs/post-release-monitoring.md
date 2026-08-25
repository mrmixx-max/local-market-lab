# Post-Release Monitoring — v1.0.0

**Start:** 2026-08-25 · **Release:** v1.0.0 (Latest) · **Zyklus:** laufend

## Monitoring-Kanäle

| Kanal | Prüfung | Befund bei Start |
|---|---|---|
| GitHub Issues (open + closed) | täglich in der ersten Woche, dann wöchentlich | 0 Issues gesamt |
| GitHub Discussions | aktiviert? nein — Feedback läuft über Issues | — |
| Release-Reaktionen/Feedback auf v1.0.0, rc.2, rc.1 | wöchentlich | keine Rückmeldungen |

## Triage-Kategorien (bei jeder Meldung prüfen)

Installation · Start/Crash · Datenimport · Datenqualität · Backtest ·
Job-Queue · Rerun · Rebalancing · Exporte · Windows-Installer · Portable EXE

## Grundsätze

- Keine Fehler behaupten, wenn keine Meldungen vorliegen.
- Keine externen Tests als durchgeführt ausgeben, die nicht stattfanden.
- Keine unnötigen Nutzer- oder Portfoliodaten anfordern.
- API-Keys/Tokens/private Daten gehören nicht in Issues — Hinweis steht in
  den Issue-Templates; bei Verstoß: Meldung redigieren und Autor informieren.

## Status-Log

| Datum | Ereignis |
|---|---|
| 2026-08-25 | Stable v1.0.0 veröffentlicht (Latest). 0 offene Issues. Monitoring aktiv. |

## Bekannter Beobachtungsposten aus dem RC-Zyklus (kein Bug)

Der generische Rerun-Job (`kind=rerun` über die API) verweist für einzelne
Jobtypen auf `*_from_manifest`-Funktionen, die noch nicht existieren → klarer
Fehler statt stiller Fehlfunktion. Die P1.4-Rerun-Engine selbst funktioniert
byte-identisch. Geplant als **P2.2**.
