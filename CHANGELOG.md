# Changelog

## [1.0.0] — 2026-08-25 (Stable)

> Erster stabiler Release. Enthält alle rc-Fixes, keine neuen Features
> gegenüber rc.2. RC-Tags (v1.0.0-rc.1, v1.0.0-rc.2) bleiben unverändert.

### Fixed (aus dem externen RC-Zyklus)
- **High:** `lml backtest demo` crashte mit `MissingPriceError` für CASH —
  CASH wird aus der Backtest-Symbolmenge ausgeschlossen; Regressionstests.
- Wheel bündelt die Web-UI-Assets (`apps/web`).
- SHA256SUMS.txt: echte Dateinamen, vollständig (inkl. Installer + Manifest).

### Hinweise
- Installer nicht byte-reproduzierbar (Build-Zeitstempel); SHA256 gilt pro Artefakt.
- Externe Rückmeldungen: keine eingegangen; Aussagekraft begrenzt —
  dokumentiert in docs/external-feedback.md und docs/release-audit-v1.0.md.


## [1.0.0-rc.2] — 2026-08-25 (Pre-Release)

> Auslöser: reproduzierter High-Bug im RC-Zyklus (rc.2-Regel erfüllt).

### Fixed — High
- **`lml backtest demo` crashte** mit `MissingPriceError: no price data for
  'CASH'`: Demo-Fixtures enthalten eine CASH-Einlage ohne Preisreihe;
  `backtest_from_workspace()` schloss CASH nicht aus der Symbolmenge aus.
  Fix konsistent zum `scenarios replay`-Pfad; fehlende echte Kurse lösen
  weiterhin `MissingPriceError` (keine stille Ersetzung). 3 Regressionstests.

### Changed — Dokumentation/Assets (Low, dokumentiert)
- SHA256SUMS.txt: Dateiname der portablen EXE korrigiert sich mit dem nächsten
  Artefakt-Rebuild; Installer + Release-Manifest werden künftig aufgenommen.

## [1.0.0-rc.1] — 2026-08-25 (Pre-Release, Feature-Freeze)

> Release Candidate für externe Stabilisierung. **Kein stabiler v1.0.0-Tag.**
> GitHub Pre-Release. Keine Order-, Broker- oder Finanzberatungsfunktionen.

### Added (P1-Serie, bereits in rc integriert)
- **P1.1 Job-Queue:** In-Process-Worker, SQLite/WAL-Persistenz, Progress, Cancel.
- **P1.2 Mindestordergrößen:** `suggest_rebalance_orders()`, below_minimum-Markierung.
- **P1.3 Client-Binding:** CLI (`lml jobs`) + Desktop (F9) + Web (F9).
- **P1.4 Manifeste & Rerun:** immutable Run-Manifeste, `lml rerun`, Drift-Erkennung.

### RC-Prozess
- Externer RC-Testzyklus gestartet: `docs/v1.0-rc-test-plan.md`,
  `docs/v1.0-rc-test-report.md`, `docs/external-feedback.md`.
- Issue Templates ergänzt: Bug Report (Datenschutz-Hinweise, Pflichtfelder)
  und Feature Request (RC: Sammlung ohne Umsetzung).
- README: Installer-Abschnitt korrigiert — Installer im RC **nicht verfügbar**
  (ISCC fehlt in Build-Umgebung); portable EXE als primäres Windows-Artefakt.

### Known Limitations
Siehe `docs/v1.0-known-limitations.md` (nicht stillschweigend als gelöst markiert).

## [0.9.1] — 2026-08-24 (Stable)

### Fixed — Critical & High

- **Monte Carlo Student-t**: Innovationsvarianz war √2-fach verzerrt; jetzt
  unit-variance-standardisiert, `df > 2` erzwungen, `p01` ausgewiesen.
- **Backtest-Kosten**: Handelskosten flossen nie in die Equity-Curve; Kostenmodell
  korrigiert, Regressionstest ergänzt.
- **Stress-Tests**: Seed wurde ignoriert, run_id zufällig → deterministisch.
- **Datenqualität**: Non-monotonic-Erkennung nach erstem Duplikat deaktiviert → behoben.

### Changed — Datenadapter (Medium-Fixes)

- **Neu: gemeinsame Basisklasse** `packages/marketdata/base_adapter.py`
  (versionierter Cache-Schlüssel, Retry mit Exponential Backoff,
  Currency-Erkennung). Yahoo/AV erben davon; Provider-spezifische Logik bleibt getrennt.
- **Währungen**: Ticker-Currency-Erkennung (Suffix/Börsenplatz-Mapping, LSE in
  Pence = GBp). Unbekannte Währung bleibt explizit `unknown` — FxPolicy meldet
  fehlende Kurse als INCOMPLETE, kein stiller 1:1-Fallback.
- **Cache-Versionierung**: Schlüssel enthält Provider, Symbol, Intervall, Zeitraum,
  Währung, Adjusted-Status und Schema-Version (`schema=2`). Schemawechsel → Cache-Miss;
  korrupte Einträge werden gelöscht statt Crash; `purge_old_schema()` zum Aufräumen.
- **Alpha-Vantage-Key im Header**: Key wird nur als HTTP-Header gesendet — nie in der
  URL, nie in Logs oder Fehlermeldungen. Security-Tests ergänzt.

### Changed — Exporte & Explainability

- Alle Exporte tragen Systemversion, Seed, Run-ID, Zeitstempel und Pflicht-Disclaimer.
- CSV-Format dokumentiert: UTF-8, Komma, `# `-Metadatenkopf.
- Permutation Importance: ehrliches `splits_used`, Leakage-Richtlinie im Docstring.
- SHAP-artige Werte mit `approximation: true` und Nicht-Kausalitätshinweis.

### Known Limitations

- Rebalancing ohne Mindestordergrößen-Modellierung.
- Lange Berechnungen laufen synchron im Request (keine Job-Queue).
- WebSocket-Marktdaten sind simuliert.
- AV-Free-Tier: 25 Requests/Tag; Adapter wartet bis 12 s zwischen Requests.

### Installationshinweise

```bash
pip install local-market-lab          # aus PyPI (0.9.0)
# oder aus Source:
pip install -e ".[dev,analytics,export]"
```

Windows: Installer `LocalMarketLab-Setup-v0.9.1.exe` (enthält keine Python-Abhängigkeit).

### Breaking Changes

Keine öffentlichen API-/CLI-Änderungen. Intern: `MarketDataCache` hat neue
`*_versioned`-Methoden; alte Cache-Einträge werden bei Schema-Mismatch nicht genutzt.

## [1.0.0rc1] — 2026-08-24 (Release Candidate, Pre-Release)

### Feature-Freeze — v1.0 P1.1–P1.4 integriert
- **P1.1 Job-Queue Backend:** In-Process-Worker, SQLite/WAL, Submit→Progress→
  Result, Cancel, Artifact-Referenzen. API blockiert nicht.
- **P1.2 Mindestordergrößen:** `suggest_rebalance_orders()` mit Min-Beträgen,
  ganzzahlig/Fractional, Kosten-Nutzen-Check, `below_minimum`-Markierung.
- **P1.3 Client-Binding:** `lml jobs` + Desktop (F9) + Web-UI (F9), gemeinsames
  Statusmodell, kein Blockieren, API-Ausfall sichtbar.
- **P1.4 Manifeste & Reproduzierbarkeit:** immutable Run-Manifeste, kanonische
  Hashes (manifest_digest/parameters/data/model/environment/result_hash),
  `lml rerun` (sync/async), Drift-Erkennung, byte-identischer fachlicher Hash.
- **Release:** wheel + sdist + Windows-EXE (portable) + SBOM + SHA256SUMS.
- **Tests:** 462 passed / 6 skipped. Coverage 78% (kritisch 82–100%).
- **Bekannt:** In-Process-Queue ohne HA; Installer in Build-Env nicht
  reproduzierbar; PDF/Excel nicht garantiert byte-identisch.

### Unreleased (vor RC) — P1.1–P1.3 Vorarbeiten

## [Unreleased]

### Added — v1.0 P1.4 (Manifest & Reproducibility) — siehe oben


### Added — v1.0 P1.4 (Manifest & Reproducibility)

- **Manifest-Engine** `packages/artifacts/`: kanonische Serialisierung
  (`canonical.py`, sort_keys/allow_nan=False/Decimal/Date/Enum/Set/NaN-Inf),
  immutable Speicherung (`registry.py`, atomar, Path-Traversal-Schutz,
  SHA256-Integrität), versioniertes Schema v1 (`run_manifest.py`).
- **Hashes**: manifest_digest (Integrität), parameters/data/model/environment/
  result_hash — alle zentral über `integrity_payload()` + `stable_hash()`.
  `created_at`/`run_id`/`manifest_id` aus dem fachlichen result_hash ausgeschlossen.
- **Rerun** `packages/artifacts/rerun.py`: Load→Integrität→Drift-Check
  (system/parameter=abort, data/model=abort, environment=warn)→Re-Exec→
  Vergleich. Status: byte_identical | rerun_with_drift | failed.
- **CLI** `lml manifests list|show|compare` + `lml rerun <id> [--async|--json|
  --allow-data-drift|--allow-environment-drift]`.
- **API** `GET /api/v1/manifests`, `/{id}`, `/{id}/compare`,
  `POST /api/v1/manifests/{id}/rerun` (sync + async via Job-Queue); 404/422/409.
- **Job-Queue**: `@register("rerun")` für Async-Pfad (neue run_id, Original
  immutable, Vergleich als neuer Record).
- 27 neue Tests (24 Manifest-P1.4 + 2 Async/CLI, 1 Legacy); Suite 462 passed /
  6 skipped. Keine neuen Dependencies. Kein Breaking Change.

### Added — v1.0 P1.3 (Job-Queue Client Binding) — bereits implementiert
### Added — v1.0 P1.2 (Minimum order sizes) — bereits implementiert
### Added — v1.0 P1.1 (Job-Queue Backend) — bereits implementiert


### Added — v1.0 P1.3 (Job-Queue Client Binding)

- **CLI `lml jobs`**: list / status / cancel / wait / artifact (additiv).
  Exit-Codes: 0 succeeded, 2 timeout, 3 failed, 4 cancelled, 5 no-artifact,
  1 not_found/error. Kein künstlicher Fortschritt, keine Endlosschleifen.
- **Desktop (PyQt6) Jobs-Tab (F9)**: Submit, Live-Tabelle, Cancel,
  Artifact-Link. Eigenes Polling (`LML_JOBS_POLL_MS`, Default 2500) entkoppelt
  vom Watchlist-Timer → UI responsiv. API-Ausfall sichtbar ("last known state").
- **Web-UI Jobs-Tab (F9)**: Submit, Auto-Poll, Cancel, Artifact.
- **Gemeinsames Statusmodell** `apps/cli/jobs_client.py` (normalize_job):
  einheitlich für CLI/Desktop/Web. Keine Broker-, keine Orderpfade.
- 21 neue Tests (normalize, CLI live [skip ohne Server], Desktop-Logik);
  Suite 435 passed / 5 skipped.

### Added — v1.0 P1.2 (Minimum order sizes) — bereits implementiert
### Added — v1.0 P1.1 (Job-Queue Backend) — bereits implementiert


### Added — v1.0 P1.2 (Minimum order sizes & realistic rebalancing)

- **`suggest_rebalance_orders()`** + `OrderProposal`/`RebalanceOrdersResult`:
  per-instrument minimum order size (value based, default 50 via
  `LML_REBALANCE_DEFAULT_MIN_ORDER_VALUE`), integer vs fractional-share
  rounding with explicit `rounding_note` residual, fee/spread/min-fee
  estimation, cost-benefit gate (`worthwhile`/`marginal`/`not_worthwhile`),
  cash-before/after accounting. No execution path, no broker.
- **Rundungsstrategie** via `LML_REBALANCE_MIN_ORDER_STRATEGY`
  (skip|round_up|round_down; default skip — below-minimum orders are
  flagged, never silently rounded).
- **API**: `POST /api/v1/rebalance/orders` (stateless, explicit positions)
  and `POST /api/v1/portfolio/{name}/rebalance/orders` (from live valuation).
  Invalid params (negative min) → 422. Existing rebalance endpoints
  unchanged.
- 27 neue Unit-Tests + API-Tests; Suite 422 passed.
- Dokumentation: README, known-limitations, v1.0-roadmap, API-Endpoint
  aktualisiert.


### Added — v1.0 P1.1 + P1.3 (Job-Queue & Fortschritt)

- **In-Process Job-Queue** (`packages/jobs/`): persistenter Jobstatus in
  SQLite (WAL-Modus), Worker-Pool, kooperative Abbruch-Flag-Prüfung im
  Progress-Callback, Artifact-Ergebnisreferenzen (`results/<job_id>.json`).
  Zustandsautomat: queued → running → succeeded/failed/cancelled (+ cancelling).
- **Additive API**: `POST /api/v1/jobs`, `GET /jobs/{id}` (inkl. Result-Payload),
  `GET /jobs`, `DELETE /jobs/{id}`. Bestehende synchrone Endpunkte unverändert.
- **Built-in Job-Kinds**: monte_carlo, walk_forward, tuning, stress,
  demo_sleep (Test/UI). Nur Analyse — keine Orderausführung.
- 19 neue Tests (State-Machine, WAL, Submit→Progress→Result, Cancel-Races,
  API-Zyklus, Responsiveness-Garantie). Suite: 404 passed.

### Fixed — Release-Blocker

- **Monte Carlo Student-t (`packages/scenarios/stress.py`)**: Innovationsvarianz war
  √2-fach verzerrt (`sum` zweier Gauss-Zufallszahlen). Jetzt korrekt standardisiert
  (unit variance via `t/sqrt(df/(df-2))`), `df > 2` erzwungen, `p01` neu im Ergebnis.
- **Backtest-Kosten (`packages/backtest/engine.py`)**: Handelskosten gingen nie in die
  Equity-Curve ein (toter Code + doppelter Cash-Zweig). Kostenmodell korrigiert und
  durch `test_backtest_costs` abgesichert.
- **Stress-Tests**: Seed-Parameter wurde ignoriert (hardcoded 42); run_id zufällig.
  Jetzt deterministisch: Seed durchgereicht, reproduzierbare run_id.
- **Datenqualität (`packages/quality/checks.py`)**: Non-monotonic-Erkennung wurde nach
  dem ersten Duplikat deaktiviert; funktioniert jetzt immer.

### Changed — Reports & Explainability

- Alle Exporte (CSV/PDF/Excel) enthalten jetzt Systemversion, Seed, Run-ID, Zeitstempel
  und den Pflicht-Disclaimer. CSV-Format dokumentiert: UTF-8, Komma, `# `-Metadatenkopf.
- Permutation Importance: ehrliches `splits_used="permutation_on_eval_set"` statt
  irreführendem Walk-Forward-Label; Leakage-Richtlinie dokumentiert.
- SHAP-artige Werte tragen explizite Approximations-Kennzeichnung
  (`approximation: true`, Hinweis: deskriptiv, nicht kausal).

### Review-Dokumente

- `docs/quantitative-validation-review.md`, `docs/stress-rebalancing-production-review.md`,
  `docs/integration-review.md`, `docs/test-report.md`, `docs/security-review.md`,
  `docs/release-candidate-report.md`
- Teststand: 366 bestanden / 0 fehlgeschlagen. Reproduzierbarkeitslauf: identisch.

## [Unreleased] — 2026-08-24

### Added — Export & Explainability

- **PDF Export** (`packages/reports/export.py`): ReportLab-based PDF generation with PIL chart images, metrics tables, and trade logs. Returns `ExportResult` with `run_id`, `data_hash`, and `data_quality`.
- **Excel Export** (`packages/reports/export.py`): openpyxl-based multi-sheet workbook (Summary, Trades, Equity, Drawdown, Quality). Includes data quality sheet with run metadata.
- **CSV Export** (`packages/reports/export.py`): Unified CSV format for trades, equity curves, and scenario results. All exports include `data_quality` and `run_id`.
- **Feature Importance** (`packages/explainability/importance.py`): Permutation importance and SHAP-like approximation for LSTM/Transformer models. Results include `run_id`, `data_hash`, and `splits_used`.
- **Model Comparison** (`packages/explainability/comparison.py`): Walk-forward results aggregation and Diebold-Mariano statistical test. Returns `ModelComparison` with full metadata.
- **API Endpoints** (`apps/api/export_routes.py`):
  - `POST /api/v1/export/pdf`
  - `POST /api/v1/export/excel`
  - `POST /api/v1/export/csv`
  - `GET /api/v1/explainability/importance` (@experimental)
  - `GET /api/v1/explainability/compare` (@experimental)
- **Domain Entities** (`packages/domain/entities.py`): `ExportQuality`, `ExportResult`, `FeatureImportanceItem`, `ExplainabilityResult`, `ModelComparison`.
- **Shared Constants** (`packages/domain/constants.py`): Walk-forward windows (252/63/21), export paths, quality thresholds, source identifiers.
- **Tests** (`tests/unit/test_export.py`, `tests/unit/test_explainability.py`): 21 tests covering all export formats, permutation importance, SHAP approximation, Diebold-Mariano test, walk-forward tables, and model comparison.

### Configuration

- `LML_EXPORT_PDF_PATH` — PDF export directory (default: `./exports`)
- `LML_EXPORT_EXCEL_PATH` — Excel export directory (default: `./exports`)
- `LML_EXPORT_CSV_PATH` — CSV export directory (default: `./exports`)
- `LML_WF_TRAIN` — Walk-forward train window (default: `252`)
- `LML_WF_TEST` — Walk-forward test window (default: `63`)
- `LML_WF_STEP` — Walk-forward step size (default: `21`)

### Alignment

- Explainability uses same walk-forward splits as validation (Agent 1)
- Exports include `QualityReport` and data source info (Agent 2)
- All exports embed `data_quality` and `run_id` for traceability
