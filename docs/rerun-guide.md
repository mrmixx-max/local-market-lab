# Rerun Guide (v1.0 P1.4)

## Synchron

```bash
lml rerun man_20260824abcd_12345678
```

Lädt Manifest → prüft Integrität → System/Parameter/Environment-Drift →
führt den Lauf über den registrierten Executor aus → vergleicht `result_hash`.

Ausgabe:
```
Manifest: man_...
Original Result Hash: sha256:...
Rerun Result Hash:    sha256:...
Data Hash:    MATCH
Parameters:   MATCH
Model:        MATCH
Environment:  MATCH
Result: BYTE-IDENTICAL
```

Exit-Codes: `0` byte_identical · `2` Drift-Abbruch · `3` sonstiger Fehler ·
`1` Manifest nicht gefunden.

## Asynchron (Job-Queue)

```bash
lml rerun man_... --async
# -> rerun queued as job <job_id>
lml jobs wait <job_id>
```

Das ursprüngliche Manifest bleibt **immutable**; ein neuer Record
(`<id>__rerun_<n>`) speichert den Vergleich. Cancel via `lml jobs cancel`.

## Drift erlauben (transparent)

```bash
lml rerun man_... --allow-data-drift
lml rerun man_... --allow-environment-drift
```

Ergebnis wird **nie** als `byte_identical` ausgewiesen, sondern als
`rerun_with_drift` mit entsprechenden Warnungen.

## API

```
GET  /api/v1/manifests
GET  /api/v1/manifests/{id}
GET  /api/v1/manifests/{id}/compare
POST /api/v1/manifests/{id}/rerun           # ?background=true -> Job-Queue
```

404 bei unbekannter ID, 422 bei ungültigen Optionen, 409 bei Drift-Abbruch.
