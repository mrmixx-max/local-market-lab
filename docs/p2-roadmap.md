# P2-Roadmap — Local Market Lab

**Stand:** 2026-08-25 · Ausgangsbasis: v1.0.0 (stable) · Feature-Freeze für v1.0.x bleibt

## Priorisierungsregeln (bindend)

1. Reproduzierte Bugs und Sicherheitsprobleme
2. Falsche oder missverständliche Berechnungen
3. Datenintegrität und Reproduzierbarkeit
4. Job-Stabilität
5. Portfolio- und Risiko-Funktionen
6. Komfort- und UI-Verbesserungen
7. Neue Plattformfeatures

Nicht beginnen vor P2-Bewertung: Mobile-App, Multiplayer, Cloud-Sync.

## Priorisierte P2-Items

| Rang | Item | Kategorie (Regel) | Begründung |
|---:|---|---|---|
| 1 | **P2.4 CV-Embargo** | (2) Berechnungskorrektheit | Zeitabhängige Features können unbeabsichtigt Zukunftsinformationen nutzen — korrektheitskritisch für alle Validierungsergebnisse |
| 2 | **P2.2 Vollständige Manifest-Executors** | (3) Reproduzierbarkeit | Rerun-Versprechen nur teilweise eingelöst; klarer Fehler existiert bereits, muss systematisch werden |
| 3 | **P2.5 Worker-Restart-Verhalten** | (4) Job-Stabilität | Aktuelles Verhalten bei API-Absturz ist undefiniert dokumentiert; Entscheidung + WAL-Tests fehlen |
| 4 | **P2.3 Audit-Hash-Kette** | (3) Datenintegrität | Manipulationserkennung für Run-Historie; Aufbau auf P1.4-Hashes, daher nach Executor-Klarheit |
| 5 | **P2.1 Portfolio-Ziele & Risiko-Budgets** | (5) Portfolio-Funktionen | Größter Nutzerwert, aber rein additiv — keine Korrektheit/Lücke |

## P2.1 Portfolio-Ziele und Risiko-Budgets

- Zielallokationen pro Portfolio (`target_weights`), Risiko-Limits (z. B. max
  Positionsgewicht, Volatilitätsbudget)
- Drift-Berechnung gegenüber Ziel und Budget mit Schwellen/Warnstufen
- Warnungen als Reports/Flags — **keine automatische Orderausführung**
  (Design-Grenze bleibt; Language-Guard gilt weiter)
- Kompatibilität mit P1.2-Mindestordergrößen: Drift-Warnungen respektieren
  `below_minimum`-Markierungen; Vorschläge bleiben Vorschläge
- Akzeptanz: Determinismus (Seed), Manifest-Pflicht, Regressionstests

## P2.2 Vollständige Manifest-Executors

- Jeder relevante Jobtyp aus Manifesten rekonstruierbar:
  `backtest`, `scenario` (mc/bootstrap/replay), `validation`, `tuning`,
  `stress`, `rebalancing`
- Keine generischen Platzhalter-Executors; nicht unterstützte Jobtypen
  werfen eine klare `UnsupportedManifestExecutor`-Meldung
- Sync- und Async-Rerun über denselben Executor-Pfad
- Result-Hash-Vergleich Pflicht: byte_identical vs. rerun_with_drift
- Akzeptanz: je Jobtyp ein Golden-Manifest-Test mit identischem result_hash

## P2.3 Audit-Hash-Kette

- Verkettete Einträge: `entry_hash = H(prev_hash || canonical(entry))`
- Genesis-Eintrag definiert; Schlüssel und Feldreihenfolge fest specifiziert
  (kanonische JSON-Serialisierung wie P1.4)
- Manipulationserkennung: Kettbruch wird beim Lesen gemeldet, nie still repariert
- Migration bestehender Logs: einmalige Verkettung bestehender Manifeste mit
  dokumentiertem Migrations-Genesis (keine rückwirkenden Behauptungen)
- Performance: Kettenprüfung inkrementell, Vollvalidierung optional
- **Grenze:** technische Integrität, keine rechtliche Compliance-Aussage

## P2.4 CV-Embargo

- Embargo-Zeitraum in zeitabhängigen Features und Indizes berücksichtigen
  (Indikator-Warmup, Label-Horizont, Split-Grenzen)
- Leakage-Tests: Features am Split-Anfang dürfen keinen Zugriff auf
  Embargo-Daten haben
- Referenzfall: identischer Backtest mit und ohne Embargo — dokumentierter
  Unterschied in Metriken
- Verhalten in `docs/methodology.md` dokumentieren

## P2.5 Worker-Restart-Verhalten

Entscheidungsvorlage (Empfehlung):
- Jobs in `queued` bei Restart → weiter in Queue (zustandslos, sicher wiederaufnehmbar)
- Jobs in `running` bei Absturz → beim Neustart als **failed** markieren
  mit Grund `interrupted_by_restart`; kein stiller Verlust, keine falsche
  Wiederaufnahme (Zwischenstände sind nicht checkpointed)
- „Lost" entfällt damit als Status; Known Limitation präzisieren statt streichen
- SQLite-WAL-Verhalten testen: Crash während Commit, Lock nach Kill,
  Recovery-Zeit
- **Keine Hochverfügbarkeitsgarantie** — Dokumentation formuliert Grenzen,
  verspricht nichts

## Sequenzierung

```text
P2.4 → P2.2 → P2.5 → P2.3 → P2.1
(jeweils mit Tests, Clean-Venv-Check, E2E; Releases nur nach Release-Regeln)
```
