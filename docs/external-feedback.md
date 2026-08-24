# External Feedback — v1.0.0-rc.1

Laufende Sammlung externer Rückmeldungen. Jede Meldung wird klassifiziert
(Critical / High / Medium / Low / Feature Request) und mit Status geführt.

**Regeln:** Keine Änderung an P1.1–P1.4 ohne reproduzierten Fehler.
Keine API-Keys, Tokens oder privaten Portfoliodaten in Issues.

| Datum | Tester/Umgebung | Version | Klassifikation | Zusammenfassung (anonymisiert) | Issue | Status |
|---|---|---|---|---|---|---|
| 2026-08-25 | intern (Clean-Venv Wheel/sdist-Test, Windows 11, Python 3.11.15) | 1.0.0rc1 | **High** | `lml backtest demo` bricht ab: `MissingPriceError: no price data for 'CASH'` — Demo-Fixtures enthalten CASH-Deposit ohne Preisreihe; `backtest_from_workspace` filtert CASH nicht heraus (im Gegensatz zum Szenarien-Pfad). Existiert seit v0.1.0, von der Testsuite nicht abgedeckt. | Fix in release/v1.0 (`packages/backtest/engine.py`, Regressionstests `tests/unit/test_demo_backtest_cash.py`) | REPRODUZIERT & BEHOBEN |
| 2026-08-25 | Asset-Audit (GitHub API + Download-Verifikation) | 1.0.0rc1 | **Low** | SHA256SUMS.txt nennt portable EXE als `LocalMarketLab-rc1.exe`, Asset heißt `LocalMarketLab.exe` (Hash identisch); Installer-EXE und Release-Manifest fehlen in SHA256SUMS.txt. | dokumentiert, Fix mit rc.2/stable | OFFEN (dokumentiert) |

### Behobener Bug im Detail

- **Klassifikation:** High — Standardworkflow (`lml demo` gefolgt von
  `lml backtest demo`) unbrauchbar, 100 % reproduzierbar.
- **Ursache:** `backtest_from_workspace()` leitete die Symbolliste aus allen
  Transaktionen ab; die Demo-Fixtures (und jeder reale CSV-Import mit
  Einlagen) enthalten `CASH`-Buchungen ohne Preisreihe.
- **Fix:** CASH aus der Symbolmenge ausschließen (konsistent zum
  `scenarios replay`-Pfad). Keine stillsche Datenersetzung: ein wirklich
  fehlendes Kurs-Symbol löst weiterhin `MissingPriceError` (Regressionstest).
- **Verifikation:** 3 neue Regressionstests grün; Vollsuite 459 passed,
  6 skipped; CLI-E2E (`lml demo && lml backtest demo`) in Clean-Venv
  mit neu gebautem Wheel verifiziert.

## Hinweis zur Aussagekraft

```text
Externe RC-Rückmeldungen: keine eingegangen
Aussagekraft: begrenzt
Freigabegrundlage: interne Tests und dokumentierte RC-Prüfung
```
