# Issue-Triage-Prozess — Local Market Lab

## Ablauf pro Meldung

1. **Klassifizieren:** Critical / High / Medium / Low / Feature Request / nicht reproduzierbar
2. **Umgebung erfassen:** Version, OS, Installationsweg (Wheel/sdist/EXE/Installer), Python-Version
3. **Reproduzierbarkeit prüfen** (lokal, Clean-Venv; bei Bedarf Nachfragen mit minimalen Angaben: Version, OS, exakte Fehlermeldung)
4. **Ursache analysieren** (Root Cause vor Fix — kein symptomatisches Patchen)
5. **Regressionstest ergänzen** (muss vor dem Fix rot sein)
6. **Minimalen Fix implementieren** (kein Scope-Creep)
7. **Vollständige Testsuite** (`pytest tests/ -q`) — 459+ grün
8. **Clean-Venv prüfen** (frisches venv, Wheel-Installation)
9. **E2E prüfen** (`lml demo` → `lml backtest demo`, sync + async Job-Lauf)
10. **Release-Entscheidung dokumentieren:** `v1.0.1` vs. `v1.1`

## Klassifikation

| Stufe | Kriterium | Beispiel |
|---|---|---|
| Critical | Datenverlust, Sicherheitsrisiko, falsche Kernberechnung | result_hash falsch berechnet |
| High | Standardworkflow unbrauchbar, reproduzierbarer schwerer Fehler | CASH-Backtest-Crash (rc.2) |
| Medium | wichtige Funktion eingeschränkt, Workaround existiert | Export fehlt für einen Formatkante |
| Low | kosmetisch, Dokumentation, Komfort | Tippfehler in Hilfe-Text |
| Feature Request | kein Bug | „Unterstützt ETF-X" |

## Patch-Release `v1.0.1` — nur für

- reproduzierbare Bugs
- Sicherheitsfixes
- Datenqualitätsprobleme
- falsche Berechnungen
- Installations-/Startfehler

**Nicht** in Patch-Releases: Feature-Wünsche, Refactorings, neue Adapter,
Dokument-Umfänge ohne Fehlerbezug. Diese laufen über P2 bzw. `v1.1`.

## Datenschutz in Issues

- Keine API-Keys/Tokens (Templates weisen darauf hin; bei Verstoß redigieren)
- Keine privaten Portfoliodaten; Symbole anonymisiert erlaubt
- Keine vollständigen Konfigurationsdateien mit Secrets
- Logs: nur relevanter Ausschnitt, Secrets geschwärzt

## Nicht-reproduzierbare Meldungen

Status „nicht reproduziert" + verwendete Umgebung dokumentieren
(`docs/external-feedback.md`), Issue offen lassen mit `awaiting-info`-Label,
nach 30 Tagen ohne Antwort schließen.
