# Bekannte Einschränkungen — v0.9.1

## Methodik
- Permutation Importance wird auf dem vom Aufrufer übergebenen Auswertungsset
  berechnet (`splits_used="permutation_on_eval_set"`); kein automatischer Split.
- SHAP-artige Werte sind Sampling-Approximationen (`approximation: true`),
  deskriptiv, nicht kausal.
- Purged K-Fold: Embargo zählt Indizes, nicht Kalendertage — bei Datenlücken ist
  der effektive Embargo kleiner als nominal.
- Hyperparameter-Tuning nutzt das letzte Datendrittel als Tuning-Test; ein finales
  Holdout muss außerhalb des Tunings liegen.

## Datenadapter
- Currency-Erkennung aus Ticker-Suffix/Börsenplatz; ohne Marker bleibt die Währung
  `unknown` und FX-Konversion meldet INCOMPLETE (kein stiller Fallback).
- Yahoo: `1h`-Intervall auf 60 Tage historie limitiert (Provider-Beschränkung).
- Alpha Vantage Free-Tier: 25 Requests/Tag, Adapter-Throttling 12 s.

## Portfolio & Rebalancing
- ✅ Mindestordergrößen & Stückelung — gelöst in v1.0 P1.2:
  `suggest_rebalance_orders()` berücksichtigt Mindestordergrößen
  (Default 50 € via `LML_REBALANCE_DEFAULT_MIN_ORDER_VALUE`), Ganzzahl-
  vs. Fractional-Rundung, Gebühren/Spread und verfügbares Cash; Orders unter
  Minimum werden als `below_minimum` markiert, nie stillschweigend gerundet.
- Steuereffekte im TLH-Hinweis sind Pauschalschätzungen (25 %), keine Steuerberatung.

## Betrieb
- Lange Berechnungen (Monte Carlo >5k Runs) laufen synchron; API/UI blockieren
  währenddessen für die Dauer des Requests.
- WebSocket `/ws/market` liefert einen simulierten Feed, keine echten Kurse.
- Windows-Icon-Cache kann alte Icons zeigen bis Explorer-/Systemneustart.

## Datenschutz
- Keine Telemetrie, keine externen Calls außer den konfigurierten Marktdatenquellen
  (Yahoo, Alpha Vantage) und localhost-Ollama.
