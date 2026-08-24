# Manifests (v1.0 P1.4)

Jeder relevante Analyse-Lauf erzeugt ein **immutable Run-Manifest** unter
`data/manifests/<manifest_id>.json` (konfigurierbar via `LML_MANIFEST_DIR`).

## Schema (manifest_schema_version: 1)

| Feld | Inhalt | Reproduzierbarkeitsrelevant |
|---|---|---|
| manifest_id | eindeutige ID (UUID) | nein (ausgeschlossen) |
| run_id | Lauf-ID (UUID) | nein (ausgeschlossen) |
| created_at | ISO-Zeitstempel | nein (ausgeschlossen) |
| system_version | LML-Version | ja |
| git_commit | Kurz-Hash | nein |
| job_type | backtest/scenario/... | ja |
| seed | Zufalls-Seed | ja |
| parameters / parameters_hash | kanonisch gehashte Parameter | ja |
| data[] | Quelle, Symbol, data_hash, Währung, ... | ja (data_hash) |
| features | Feature-Set-Version + Hash | ja |
| model | Name, Version, Parameter, implementation_hash | ja |
| environment / environment_hash | Python, Plattform, package_lock_hash | ja |
| result_hash | kanonischer Hash des fachlichen Ergebnisses | ja |
| manifest_digest | SHA256 des kanonischen Payloads (ohne sich selbst) | Integrität |

## Hash-Arten

- **manifest_digest** — Integrität der Datei. Basis = `integrity_payload(manifest)`
  (deepcopy, `manifest_digest` entfernt), dann `stable_hash` über kanonische
  Serialisierung. Save und Load nutzen exakt dieselbe Basis.
- **result_hash** — fachlicher Ergebnis-Hash (`stable_hash(result)`). Unabhängig
  von `created_at`/`run_id`/`manifest_id`.
- **artifact_hash** — SHA256 der gespeicherten Artefakt-Datei (bei Exporten).
  Hinweis: PDF/Excel können durch Metadaten/Zeitstempel vom byte-identischen
  Artefakt abweichen — hier wird nur der fachliche `result_hash` als
  Identitätsnachweis geführt.

## CLI

```
lml manifests list
lml manifests show <manifest_id>
lml manifests compare <manifest_id>
lml rerun <manifest_id> [--async] [--json] [--allow-data-drift] [--allow-environment-drift]
```

## Sicherheit

- Keine Secrets (api_key/token/secret/... werden beim Build auf `<REDACTED>`
  gesetzt, nie gespeichert).
- Path-Traversal-Schutz in `_safe_id`.
- Manipulation (Feld geändert ODER `manifest_digest` geändert) → `ValueError`.
- Kein Überschreiben, kein stiller Repair.
