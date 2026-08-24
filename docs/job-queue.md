# Job Queue — Client Binding (v1.0 P1.1 + P1.3)

## Architektur

- **In-process** worker thread (kein externer Broker, keine Cloud-Queue).
- Persistente Status-DB: SQLite im WAL-Modus (`~/.local-market-lab/jobs.db`).
- Worker läuft im API-Prozess; Web-UI und Desktop-App sind reine Clients.

## Gemeinsames Statusmodell (CLI / Desktop / Web)

```json
{ "job_id", "job_type", "status", "progress", "phase", "processed",
  "total", "message", "created_at", "started_at", "finished_at",
  "cancel_requested", "run_id", "artifact_id", "error_code",
  "error_message", "warnings" }
```

Statuswerte: `queued`, `running`, `cancelling`, `cancelled`, `succeeded`, `failed`.

## CLI

```
lml jobs list [--json]            # id, type, status, progress, phase, runtime
lml jobs status <job_id> [--json] # vollstaendiger Status
lml jobs cancel <job_id>          # idempotent
lml jobs wait   <job_id> [--timeout S]  # pollt; Exit 0 = succeeded
lml jobs artifact <job_id> [--json]      # nur bei succeeded
```

Exit-Codes: `0` succeeded · `2` timeout · `3` failed · `4` cancelled ·
`5` artifact nicht verfügbar · `1` not_found/Fehler.

## Desktop (PyQt6)

- Tab **Jobs** (F9): Submit, Tabelle, Cancel, Refresh.
- Eigenes Polling-Intervall (`LML_JOBS_POLL_MS`, Default 2500 ms),
  entkoppelt vom Watchlist-Timer → UI bleibt responsiv.
- API-Ausfall: "API unreachable — last known state" statt erfundener Werte.
- Artifact nur bei `succeeded` abrufbar.

## Web (index.html)

- Tab **Jobs** (F9): Submit, Tabelle (auto-poll 2500 ms wenn sichtbar),
  Cancel via Doppelklick → Artifact-Anzeige.

## Cancellation & Timeout

- `cancel` ist idempotent (terminal → No-op).
- `wait` hat hartes Timeout-Default (300 s), kein Endlos-Loop.
- Keine künstlichen Fortschrittswerte; `progress` kommt 1:1 aus dem Backend.

## Betrieb

- Keine Hochverfügbarkeit: bei API-Prozess-Absturz sind laufende Jobs
  verloren (Status bleibt in SQLite, wird aber nicht fortgesetzt).
- Neustart der App zeigt den letzten bekannten Status aus der DB — keine
  stillschweigend falschen "running"-Zustände (Worker ist nach Restart leer).
