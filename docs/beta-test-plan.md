# Beta-Testplan v0.9.1-rc.1

Für jeden Test: System, Version, Schritte, erwartetes Ergebnis, tatsächliches
Ergebnis, PASS/FAIL. Logs/Screenshots bei FAIL anhängen.

| # | Test | Schritte | Erwartet |
|---|---|---|---|
| 1 | Installation sauberes Windows | Setup-EXE starten, Default-Pfad | Installation ohne Admin, ohne Python |
| 2 | Start ohne Python | Startmenü/Desktop-Shortcut | Terminal-Fenster öffnet, Watchlist sichtbar |
| 3 | Eigene CSV importieren | `lml import prices FILE SYMBOL` bzw. UI | Punkte-Zahl korrekt, keine stillen Korrekturen |
| 4 | Yahoo-Verbindung | Symbol mit Yahoo-Kurs abrufen | Kursdaten + Quelle "yahoo" |
| 5 | Alpha Vantage | ALPHAVANTAGE_KEY setzen, Import | Daten laden; Key erscheint nirgends in Logs |
| 6 | Offline-Modus | Netzwerk aus, Cache abrufen | Gespeicherte Daten oder klare Fehlermeldung |
| 7 | Cache-Verhalten | zweimal gleicher Abruf | zweiter Lauf aus Cache (TTL 24 h) |
| 8 | Backtest | Demo-Portfolio backtesten | Equity-Curve; Kosten reduzieren Endwert vs. gebührenfrei |
| 9 | Validation | Walk-Forward auf eigenem Symbol | Folds dokumentiert, kein Crash bei kurzen Reihen |
| 10 | Stress-Test | 2008/2020/2022 + hypothetisch | DD-Werte plausibel, Seed reproduzierbar |
| 11 | Rebalancing | Drift > Threshold setzen | Nur Vorschläge, keine Orderfunktion |
| 12–14 | PDF-/Excel-/CSV-Export | je ein Export öffnen | Dateien lesbar; Excel Quality-Sheet; CSV-Metadatenkopf |
| 15 | Ollama (optional) | lokales Modell verbinden | Chat antwortet oder klarer Verbindungsfehler |
| 16 | Fehlermeldungen | ungültiges Symbol, fehlende Daten | verständliche Meldung, kein Stacktrace |

Feedback freiwillig und manuell — keine automatische Telemetrie.
**Keine API-Keys oder privaten Portfolio-Daten in Issues/Feedback.**
