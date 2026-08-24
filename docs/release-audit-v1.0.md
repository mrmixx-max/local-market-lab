# Release Audit v1.0.0 — Vorbereitung (Stand: rc.1)

**Zweck:** Nachweis, dass alle Stable-Release-Kriterien erfüllt sind,
bevor `v1.0.0` getaggt wird. Kein stabiler Tag vor Abschluss des
externen RC-Testzyklus.

## Kriterien-Checkliste

| # | Kriterium | Status |
|---|---|---|
| 1 | Externer RC-Testzyklus abgeschlossen | ⬜ OFFEN — läuft; 1 reproduzierter High-Bug gefunden und behoben (CASH-Backtest-Crash) |
| 2 | Keine offenen Critical-/High-Probleme | ✅ High-Bug (CASH) behoben + Regressionstest; keine weiteren bekannt |
| 3 | Reproduzierte relevante Bugs behoben oder bewusst akzeptiert | ✅/⬜ siehe external-feedback.md |
| 4 | Relevante Tests grün (462 Tests) | ✅ PASS bei rc.1 |
| 5 | Clean-Venv funktioniert | ✅ bei rc.1 verifiziert; vor stable erneut |
| 6 | E2E funktioniert | ✅ PASS bei rc.1 |
| 7 | Rerun reproduzierbar (sync + async) | ✅ PASS bei rc.1 |
| 8 | Exporte geprüft (PDF/Excel/CSV) | ✅ bei rc.1 (PDF/Excel nicht byte-identisch, result_hash maßgeblich) |
| 9 | Security-/Secret-Scan grün | ✅ PASS bei rc.1; vor stable erneut |
| 10 | Release-Artefakte neu gebaut und geprüft (SBOM, SHA256, Manifest) | ⬜ für stable NEU bauen |
| 11 | Known Limitations vollständig und korrekt | ✅ docs/v1.0-known-limitations.md (rc-Stand) |
| 12 | Installer reproduzierbar geprüft ODER klar als nicht verfügbar markiert | ✅ Installer gebaut + Install/Uninstall/Version/SHA256 lokal verifiziert; saubere VM noch offen (RC-Zyklus) |

## Windows-Installer (Punkt 12)

Zu prüfen außerhalb der aktuellen Umgebung:
1. Inno Setup verfügbar? → sonst portable EXE als primäres Artefakt behalten.
2. Installer reproduzierbar baubar? Versionsnummer? SHA256?
3. Installiert/deinstalliert sauber? Anwendung startet?
4. Nur erwartete Dateien enthalten? Saubere Windows-VM?

Kein Installer-Claim veröffentlichen, solange nicht verifiziert.
Kein unnötiger Code ändern, um den Installer zu „retten".

## Release-Regeln

`v1.0.0-rc.2` nur bei behobenem reproduzierbarem Critical-/High-/relevantem
Medium-Bug mit Regressionstest. **Kein** rc.2 bei: keinen Meldungen, nur
Feature-Wünschen, nur bestätigten dokumentierten Limitations, nur kosmetischen
Low-Problemen.

## Keine vorzeitige Freigabe

Stable wird NICHT freigegeben, weil der RC intern funktioniert, keine Issues
eingegangen sind oder Zeitdruck besteht. Bei ausbleibenden Rückmeldungen gilt
der Block in `docs/external-feedback.md` („Aussagekraft: begrenzt").
