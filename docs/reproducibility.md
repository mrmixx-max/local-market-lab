# Reproducibility (v1.0 P1.4)

## Garantie

Bei **identischen Voraussetzungen** (Parameter, Seed, Daten-Quelle + data_hash,
Modell-Version, System-Version, Environment-Hash) liefert ein Re-Run einen
**byte-identischen fachlichen Result-Hash**.

## Was „identisch" bedeutet

| Dimension | geprüft via | bei Drift |
|---|---|---|
| System-Version | `system_version` | **Abbruch** (DriftError) |
| Parameter | `parameters_hash` | **Abbruch** |
| Daten | `data[].data_hash` | Abbruch (oder `--allow-data-drift`) |
| Modell | `model.*` + `implementation_hash` | Abbruch (oder `--allow-data-drift`) |
| Environment | `environment_hash` | **Warnung** + `rerun_with_drift` (oder `--allow-environment-drift`) |

`created_at`, `run_id`, `manifest_id` sind aus dem fachlichen `result_hash`
**ausgeschlossen** (Hash-Policy in `run_manifest._NON_RESULT_KEYS`). Ein neuer
Lauf erzeugt neue `run_id`/`created_at`, ohne den Vergleich zu brechen.

## Rehydration-Priorität

1. Gespeichertes lokales Input-Artifact
2. Cache
3. Datenquelle erneut abrufen + data_hash vergleichen
4. Bei Abweichung: Abbruch (oder explizite `--allow-data-drift`)

## Einschränkungen

- **PDF / Excel**: durch interne IDs/Zeitstempel oft NICHT byte-identisch als
  Datei. Deshalb wird der fachliche `result_hash` als Identitätsnachweis
  geführt; `artifact_hash` ist separates Feld.
- **CSV / JSON / NumPy**: bei gleichen Inputs byte-identisch möglich.
- Keine Hochverfügbarkeit: API-Prozess-Absturz verliert laufende Jobs (Status
  in SQLite, nicht fortgesetzt).

## Befehle

```
lml rerun <id>              # synchron, Vergleichsreport
lml rerun <id> --async      # via Job-Queue (neue run_id, Original immutable)
lml rerun <id> --json       # strukturierter Report
```
