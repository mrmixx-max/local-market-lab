# Stress-Tests, Rebalancing und Produktionsreife — Review

**Status: PASS MIT WARNUNGEN** (nach Fixes)
**Geprüft:** packages/scenarios/stress.py, crisis.py, portfolio/rebalancing.py, portfolio/engine.py, apps/api/main.py, middleware.py
**Datum:** 2026-08-24 · **Reviewer:** ox-alpha

## Krisenszenarien

- Historisch: 2008 (−57% Equity), 2020 (−34%), 2022 (−25% Equity / −18% Gov-Bonds) —
  plausible kumulative Multiplikatoren je Assetklasse; Parameter im Code sichtbar und
  in `available_scenarios()` ausweisbar.
- Hypothetisch: crash_30pct, volatility_spike, rates_300bp.
- Grenzen sind als `limitations` im Ergebnis enthalten ("approximate shocks",
  "Recovery = 2% monthly compounding assumption"). Reproduzierbar via Seed.

## Student-t-Monte-Carlo

- **[FIXED — Critical]** Innovationsvarianz war √2-fach verzerrt; jetzt unit-variance
  standardisiert, `df > 2` erzwungen. Empirische std verifiziert: 1.000–1.004.
- Annahmen dokumentiert: konstante Vol/Drift, Single-Factor, keine Rebalancing-Logik
  innerhalb des Horizonts.
- Hinweis zur Geometrie: mit Standardisierung ist das moderate Quantil (p05) bei kleinem
  df NICHT monotone — die Masse wandert jenseits von p05 in den Extremtail. Neu:
  `p01` wird ausgewiesen; Fat-Tail-Tests prüfen auf p01.

## Rebalancing-Assistent

- Erzeugt ausschließlich `RebalancingProposal`-Objekte. Keine Broker-Anbindung,
  keine Orderfunktion im Code-Pfad (`grep` über packages/portfolio: keine Ausführung).
- Kosten: `abs(change) * bps / 10000`; Benefit-Modell: drift × tages-bps × Halteperiode;
  Vorschlag nur bei net>0 oder drift > 2× threshold — konservativ, plausibel.
- **WARN (Medium)**: Mindestordergrößen werden nicht modelliert — kleine Depots erhalten
  Vorschläge unter Ausführungsgranularität. Für v1.0 dokumentieren oder Mindestschwelle ergänzen.
- TLH-Hinweise sind informativ gekennzeichnet ("Consider selling...") — keine Anweisung.

## API & Produktionsreife

- Rate Limiting: 100 req/min/IP, sliding window, 429 + Retry-After. PASS.
- Request-ID-Tracing + strukturierte JSON-Logs. Exception-Middleware gibt keine
  internen Details an Clients. PASS.
- Symbol-Eingaben gegen `^[A-Za-z0-9.\-^=]{1,20}$` validiert (Injection-Schutz). PASS.
- CORS default localhost-only, erweiterbar via LML_CORS_ORIGINS. PASS.
- Sauberes Herunterfahren: atexit + SIGTERM/SIGINT schließen SQLite. PASS.
- WebSocket `/ws/market`: simulierter Feed (rng.gauss), kein echter Marktanschluss —
  Doku muss "simuliert" ausweisen. **WARN (Medium)**: README sagt "live tick feed".

## Performance (grobe Messung)

- Backtest 3 Symbole × 5 Jahre: < 50 ms. Monte Carlo 5000 Runs × 252 Tage: ~3–5 s
  (pure Python; für v1.0 akzeptabel, numpy-Vektorisierung als Backlog).
- Lange Jobs laufen synchron im Request — Stress/MC > 5 s blockieren den Event-Loop-
  Worker. **WARN (Medium)**: für v1.0 Dokumentation der Laufzeiten; Background-Job-Queue
  als Backlog.

## Status: PASS MIT WARNUNGEN

Kein Handelsausführungspfad, Szenarien reproduzierbar, Grenzen ausgewiesen.
Offene Mediums: Mindestordergrößen, WS-Labeling, synchrone Langläufer.
