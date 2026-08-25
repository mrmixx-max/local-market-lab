# P2-Architektur — Technische Entscheidungen (Entwurf)

**Stand:** 2026-08-25 · Status: Entwurf zur Umsetzung in P2-Reihenfolge

## P2.4 CV-Embargo

```text
packages/validation/embargo.py          # EmbargoLogik + Prüfung
tests/unit/test_embargo.py              # Leakage-Tests
```

- Embargo-Fenster = `warmup_bars + label_horizon` vor jedem Test-Split
- `walk_forward_backtest()` erhält Parameter `embargo: int | "auto"`
  (auto = aus Feature-Spezifikation abgeleitet, dokumentiert)
- Leakage-Test: Indizes der Trainings-Features dürfen den Bereich
  `[test_start - embargo, test_start)` nicht berühren — Verstoß → Fehler
- Referenzfall in `fixtures`: gleicher Lauf mit/ohne Embargo, Metrik-
  Differenz als dokumentierter Goldenwert

## P2.2 Manifest-Executors

```text
apps/cli/rerun_cli_helpers.py           # Registry bleibt Einstiegspunkt
packages/artifacts/executors/
  __init__.py        # register() + get_executor(job_type)
  backtest.py        # rekonstruiert Workspace-Zugriff aus data_lineage
  scenario.py
  validation.py
  tuning.py
  stress.py
  rebalancing.py
tests/integration/test_executors.py     # Golden-Manifest je Jobtyp
```

- Vertrag: `executor(manifest) -> result` — deterministisch bei gleichen
  parameters+seed+data; sonst Exception
- `UnsupportedManifestExecutor(ValueError)` für fehlende Typen — ersetzt die
  aktuellen `AttributeError`-Fälle
- Data-Lineage-Prüfung: data_hash des Manifests gegen aktuelle DB prüfen,
  Drift → DriftError (P1.4-Pfad wiederverwendet)
- Async-Rerun läuft über bestehenden `rerun`-Jobtyp, sync über CLI —
  identischer Executor

## P2.5 Worker-Restart

```text
packages/jobs/worker.py                 # Startup-Recovery
packages/jobs/store.py                  # Statusübergänge
tests/unit/test_worker_recovery.py
tests/integration/test_crash_recovery.py
```

- Beim Worker-Start: alle Jobs mit Status `running` → `failed`,
  error = `interrupted_by_restart`, finished_at gesetzt
- `queued` bleibt unberührt und wird normal verarbeitet
- Kein Checkpointing innerhalb von Jobs (explizite Design-Grenze)
- WAL-Tests: Kill -9 während Commit; Lock-Verhalten nach Crash;
  Recovery-Zeit messen; WAL-Checkpoint nach Recovery erzwingen
- Dokumentation: Known Limitation wird präzisiert (nicht gestrichen):
  keine Wiederaufnahme laufender Jobs, kein HA-Versprechen

## P2.3 Audit-Hash-Kette

```text
packages/artifacts/audit_chain.py       # append(), verify(), migrate()
tests/unit/test_audit_chain.py
tests/integration/test_audit_migration.py
```

- Eintrag: `{seq, prev_hash, entry_type, manifest_id, payload_hash,
  created_at}` — `entry_hash = stable_hash({prev_hash, seq, entry_type,
  manifest_id, payload_hash})` (created_at bewusst außerhalb, wie P1.4)
- Genesis: `prev_hash = "0"*64`, Migration erzeugt einen
  Migrations-Genesis-Eintrag mit Zählung der übernommenen Manifeste
- `verify()` liefert Bruchposition; Reparatur nur durch Neuaufbau der Kette
  ab Bruchpunkt mit neuem Genesis — nie stilles Umschreiben
- Performance: inkrementelle Prüfung O(1) pro neuem Eintrag,
  Vollvalidierung als expliziter Befehl
- Klartext-Grenze: technische Manipulationserkennung; **keine**
  Compliance-/rechtliche Unveränderbarkeitsbehauptung

## P2.1 Portfolio-Ziele & Risiko-Budgets

```text
packages/portfolio/targets.py           # Zielallokation + Drift
packages/portfolio/risk_budget.py       # Limits, Warnstufen
apps/api/target_routes.py               # read-only Endpunkte
tests/unit/test_targets.py
```

- Speicherung: `portfolio_targets`-Tabelle (portfolio, symbol, weight,
  risk_budget, updated_at) — Versionierung via Manifest bei Änderung
- Drift: absolute und relative Abweichung, Warnstufen (ok/watch/breach),
  Schwellen konfigurierbar
- Interlock mit P1.2: Rebalancing-Vorschläge markieren Orders unter
  Mindestgröße weiterhin `below_minimum`; Warnungen empfehlen keine
  Ausführung unter der Grenze
- Harte Grenze: nur Analyse/Warnung. Keine Orderausführung, kein Broker-
  Anschluss, keine Automatik — wird im Code per Language-Guard erzwungen

## Querschnitt (gilt für alle P2-Items)

- Jedes Item: Regressionstests zuerst, Manifest-Pflicht wo Ergebnisse
  entstehen, Determinismus (Seed) wo Zufall vorkommt
- Release je Item nur nach Release-Regeln (v1.1.x / v1.1, kein Feature in Patch)
- Docs aktualisieren: known-limitations, methodology, CHANGELOG
