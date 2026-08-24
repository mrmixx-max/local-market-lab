# Architektur — v1.0 Zielbild

**Stand:** 2026-08-24 · Baseline: v0.9.1 (afc7948)

## Ist-Architektur (unverändert übernommen)

```
apps/
  api/        FastAPI (REST + WS), Middleware, Routen je Domäne
  cli/        Typer-CLI ("lml")
  desktop/    PyQt6-Terminal-UI
packages/
  domain/     Entities, Schemas, Konstanten (keine Abhängigkeiten)
  marketdata/ Adapter (BaseAdapter→Yahoo/AV/Synthetic), Cache, FX, Quality
  ingest/     CSV-Import, Fixtures
  validation/ Walk-Forward, Purged CV, Hyperparameter
  backtest/   Engine + Kostenmodell (fees/spread/slippage)
  metrics/    Risk-Metriken (Sharpe/Sortino/CAGR/DD/VaR/CVaR)
  explainability/ Importance (SHAP-like), Modellvergleich (DM)
  scenarios/  Stress, Krisen, MC-Fat-Tail, Forecast-Varianten
  portfolio/  Valuation, Rebalancing (proposals-only)
  reports/    Export CSV/PDF/Excel mit Metadaten
  storage/    SQLite Workspace
  artifacts/  Run-Manifeste, Data-Hashes
```

Schichtregeln: domain ← alles; packages untereinander nur "nach unten";
apps nur auf package-APIs.

## Neuerungen v1.0

### Jobs-Layer (neu: packages/jobs/)
```
POST /jobs {kind, params} → 202 {job_id}
GET  /jobs/{id} → {status, progress, result_ref}
DELETE /jobs/{id} → Abbruch
```
- In-Process Worker-Pool (N=2 default), SQLite-State (WAL).
- Job-Kinds initial: `monte_carlo`, `walk_forward`, `tuning`, `stress`.
- Ergebnis als Artifact-Referenz (Manifest-ID), nicht inline im Status.
- UI pollt oder abonniert Fortschritt; CLI blockiert optional (`--wait`).

### Model/Data Registry (Erweiterung artifacts/)
- Jeder Run schreibt ein Manifest: system_version, model_version,
  params, data_hash, seed, code_commit.
- `lml rerun <manifest_id>` reproduziert byte-identisch.

### WebSocket-Entscheidung
- Variante A: echter Provider-Stream (Lizenz+Limits prüfen) hinter dem
  bestehenden Adapter-Contract.
- Variante B: WS-Endpunkt entfernen; Polling-Endpunkt für Snapshots.
- In beiden Fällen: kein simulierter Feed in v1.0.

## Teststrategie gesamt
- Unit je Package (Bestand: 385 Tests)
- Contract-Tests für Adapter & Plugins (v1.0: Plugin-Contract vorbereiten)
- Integration: API + Jobs (Submit/Progress/Abort/Crash-Recovery)
- Determinism-Suite: Seed-42-Doppelläufe bleiben Pflicht-Gate im CI

## Sicherheitsleitplanken (unverändert gültig)
Keine Order-Ausführung · Keys nur via Env/Header · keine stillen
Datenkorrekturen/FX-Fallbacks · Input-Validierung aller neuen Endpunkte ·
Rate-Limiting am WS.
