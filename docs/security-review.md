# Security & Datenschutz Review

**Datum:** 2026-08-24 · **Status: PASS MIT WARNUNGEN** (keine Critical/High offen)

## Geprüfte Bereiche

| Bereich | Befund | Schwere |
|---|---|---|
| SQL Injection | Parameterized queries durchgängig (cache.py, api routes, storage). Tabellenname in bank_ready._tbl_cs ist interne Konstante, kein Userinput | PASS |
| Command Injection | Kein subprocess/os.system in Request-Pfaden | PASS |
| Path Traversal | Symbol-Regex blockt `/ \ ..`; Exportpfade aus env-Konstanten, keine User-Pfade in Dateinamen (run_id uuid) | PASS |
| Uploads/Deserialisierung | CSV-Import tolerant aber zeilenweise validiert; kein pickle/yaml.load unsafe | PASS |
| CORS | Default localhost-only; "*" möglich via env — Doku warnt | PASS |
| Rate Limiting | 100 req/min/IP, 429 + Retry-After | PASS |
| Fehlermeldungen | Exception-Middleware gibt generische Meldung + request_id, keine Stacktraces | PASS |
| Secrets | Alpha-Vantage-Key nur via env/config, nicht im Repo; **WARN**: Key steht in AV-URL (Query-String) und kann in Server-/Proxy-Logs landen | Medium |
| Logs | log_json ohne Secrets; request paths können Symbole enthalten (kein PII) | PASS |
| Externe Netzwerkzugriffe | Nur: Yahoo Finance (Adapter + Healthcheck), Alpha Vantage, Ollama (localhost). Dokumentiert in README/Doku | PASS |
| Ollama-Antworten | Werden als Text behandelt, keine Eval/Render-Pipeline; Language-Guard scannt Reports | PASS |
| Audit-Log | Append-only Tabelle + result_hash; Manipulationsschutz ist Hash-Vergleich, nicht kryptografisch verkettet | Low (dokumentiert) |
| GDPR | Export pro Portfolio + Anonymisierung vorhanden; Löschpfad anonymisiert statt löscht (Doku-Klarheit nötig) | Low |
| Dependencies | Kern: typer/fastapi/pydantic/pyyaml/dateutil — keine bekannten Critical CVEs zum Review-Zeitpunkt; dev-only pytest/httpx2 | PASS |
| Lizenz | Apache-2.0 kompatibel mit allen Deps (yfinance/reportlab/openpyxl MIT/Apache-BSD) | PASS |

## Verbleibende Maßnahmen für v1.0
1. (Medium) AV-Key aus URL in Header umziehen, wo möglich.
2. (Low) Audit-Hash-Kette (prev_hash) für Manipulationssicherheit.
3. (Low) GDPR: "anonymize" vs "delete" begrifflich trennen.
