# Integration Review

**Datum:** 2026-08-24 · **Status: PASS MIT WARNUNGEN**

## Ablauf
1. Vier Review-Bereiche geprüft (2 per Delegation, 2 im Eigenreview nach Provider-Credit-Ausfall).
2. Findings zusammengeführt, nach Critical/High/Medium/Low sortiert.
3. Critical/High behoben (Liste unten), Medium/Low dokumentiert.
4. Vollständige Testsuite: 366 passed, 0 failed.
5. Reproduzierbarkeitslauf 2× identischer Konfiguration: PASS.
6. Exporte end-to-end verifiziert: CSV-Metadaten, Excel-Quality-Sheet, gültiges PDF.

## Behobene Critical/High-Findings (konsolidiert)

| # | Schwere | Finding | Fix |
|---|---|---|---|
| 1 | Critical | MC Student-t Innovationsvarianz √2-fach falsch → alle Fat-Tail-Metriken verzerrt | stress.py: gauss(0,1) + Standardisierung t/sqrt(df/(df-2)); df>2 erzwungen; p01 neu ausgewiesen |
| 2 | Critical | Backtest buchte Handelskosten nie in die Equity-Curve (toter Code + doppelter Cash-Zweig) | engine.py: korrekte Kosten-Deduktion, Kauf reduziert investierten Betrag; Test grün |
| 3 | High | Stress-Test: Seed-Parameter ignoriert (hardcoded 42), run_id zufällig → nicht reproduzierbar | Seed durchgereicht, deterministische run_id |
| 4 | High | Exporte ohne Systemversion/Seed/Disclaimer (Release-Blocker laut Kriterien) | report_metadata() in CSV/PDF/Excel; Disclaimer-Pflichttext eingebaut |
| 5 | High | Permutation Importance: irreführendes splits_used="walk_forward_252_63_21" ohne WF-Split | Label "permutation_on_eval_set", Leakage-Richtlinie im Docstring |
| 6 | High | SHAP-artige Ausgaben ohne Approximations-Kennzeichnung | approximation=True, method, Hinweis "nicht kausal" |
| 7 | Medium→High | check_timestamps: Non-monotonic-Check deaktiviert nach erstem Duplikat (`dupes == 0` Bedingung) | Bedingung entfernt, strikt d < prev |

## Vereinheitlichte Result-Metadaten

Alle Ergebnisobjekte tragen (wo passend): run_id, system_version, created_at, seed,
data_hash, data_quality{status, source, warnings}, warnings, limitations, disclaimer.
Nicht bestimmbare Werte bleiben leer/"unknown" — nie erfunden.

## Offene Punkte für v1.0 (Medium/Low, nicht release-blockierend)

- Currency-Hardcoding USD in beiden Adaptern (Agent-2-Fund) — vor Multi-Währung-Support fixen.
- Doppelte Adapter-Implementierungen konsolidieren (yahoo_adapter.py vs adapters.py).
- Cache ohne Schema-Versionierung; Cache-Korruption (json.loads) ohne try/except.
- Hyperparameter-Tuning nutzt letzten Drittel als Tuning-Test — Final-Holdout muss separat bleiben (dokumentiert).
- Mindestordergrößen im Rebalancing; WebSocket als "simuliert" labeln; MC-Laufzeiten dokumentieren.
- AV-API-Key in URL → Header.
