# Local Market Lab v0.9.1 (Stable)

Stabile Version nach erfolgreichem RC- und Beta-Zyklus (12/12 Beta-Tests, 385/385 Regressionstests).

## Features
- Walk-Forward-Validation, Purged K-Fold / Time-Series-CV, Hyperparameter-Tuning — durch dedizierte Tests auf Look-ahead-Bias geprüft
- Yahoo-Finance- und Alpha-Vantage-Adapter auf gemeinsamer BaseAdapter-Schicht (Retry/Backoff, versionierte Cache-Keys, Currency-Erkennung)
- FX-Policy: fehlende Wechselkurse erscheinen als INCOMPLETE — kein stiller 1:1-Fallback
- Datenqualitätslayer: Lücken, Duplikate, Splits, Outliers, stale data — nichts stillschweigend korrigiert
- PDF-, Excel- und CSV-Export mit Systemversion, Seed, Run-ID und Disclaimer
- Explainability: Permutation Importance, SHAP-like Approximation (explizit gekennzeichnet), Diebold-Mariano-Modellvergleich
- Krisenszenarien (2008/2020/2022 + hypothetisch) und Student-t-Monte-Carlo mit unit-variance-Innovationen
- Rebalancing-Assistent: ausschließlich Vorschläge, keine Ausführungspfade

## Qualität
- 385 bestandene Tests, 0 Fehler
- Clean-Venv-Installation geprüft
- Reproduzierbare End-to-End-Läufe (Seed 42, identischer Data-Hash, byte-identische Ergebnisse)
- SBOM (CycloneDX 1.4): artifacts/sbom-v0.9.1.json

## Datenschutz
Standardmäßig lokal; optionale Marktdaten-Adapter benötigen Netzwerkzugriff. Keine Telemetrie.

## Bekannte Einschränkungen
Siehe docs/known-limitations.md — u. a. keine Mindestordergrößen im Rebalancing, synchrone Langläufer, simulierter WebSocket-Feed.

## Links
- Beta-Report: docs/beta-test-report.md
- Release-Audit: docs/release-audit-v0.9.1.md

Dieses Ergebnis dient ausschließlich der Analyse, Forschung und Bildung. Es stellt keine Finanzberatung und keine Kauf- oder Verkaufsempfehlung dar.
