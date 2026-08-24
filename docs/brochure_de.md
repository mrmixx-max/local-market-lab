# Local Market Lab

## Deine private Marktanalyse. Lokal. Sicher. Reproduzierbar.

**Version 0.8.0 — Die Open-Source-Alternative zu Bloomberg Terminal**

---

## Executive Summary

**Local Market Lab** (LML) ist eine lokal arbeitende, datenschutzorientierte Workbench für Portfolioanalyse, Backtesting, Szenariosimulation und KI-gestützte Marktvorhersage — alles auf deinem eigenen Rechner, ohne Cloud, ohne Datenweitergabe.

### Die drei Versprechen

| Verspreis | Umsetzung |
|-----------|-----------|
| **Privacy First** | Keine Telemetrie, keine externen Services, SQLite lokal |
| **Institutionelle Methodik** | CAGR, Sharpe, VaR, CVaR, Monte-Carlo — professionell dokumentiert |
| **Reproduzierbarkeit** | Jeder Run mit Seed, Timestamp, Data-Hash |

---

## Das Problem

Moderne Marktanalyse hat drei Schwachstellen:

1. **Datenschutz**: Die meisten Tools senden deine Portfolio-Daten an Cloud-Server. Deine AnlageStrategie wird zum Produkt.

2. **Black-Box-Modelle**: KI-gestützte Vorhersagen erklären nicht, wie sie kommen. Keine Kontrolle, keine Transparenz.

3. **Komplexität**: Professionelle Tools (Bloomberg, Refinitiv) kosten tausende Euro pro Monat und erfordern monatelange Schulung.

**LML löst alle drei.**

---

## Die Lösung

Local Market Lab vereint sechs Werkzeuge in einer einzigen Anwendung:

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL MARKET LAB                         │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│  Portfolio  │  Backtest   │  Szenarien  │  KI-Prediction      │
│  Analytics  │  Engine     │  Engine     │  15+ Modelle        │
├─────────────┼─────────────┼─────────────┼─────────────────────┤
│  Trading    │  Risk       │  Ollama     │  Bank-Ready         │
│  Game       │  Dashboard  │  Chat       │  Compliance          │
└─────────────┴─────────────┴─────────────┴─────────────────────┘
```

### Portfolio Analytics
- Bewertung in Echtzeit mit Decimal-Genauigkeit (keine Float-Fehler)
- FX-Policy mit `incomplete`-State (nie stille 1:1-Konvertierung)
- Corporate Actions: Splits, Dividenden, chronologisch korrekt
- Benchmark-Vergleich mit Beta, Alpha, Tracking Error

### Backtest Engine
- Event-Loop über alignede Preisreihen
- Strategien: Buy & Hold, Momentum, Mean Reversion, Periodic Rebalance
- Gebühren und Slippage konfigurierbar
- Reproduzierbarkeits-Manifeste mit Seed und Data-Hash

### Szenarien
- Monte-Carlo, Block-Bootstrap, Historical-Replay
- Perzentile (P05–P95), Verlustwahrscheinlichkeit
- Explizit: **Keine Prognose, nur Szenarien**

### KI-Prediction (15+ Modelle)
- **Basismodelle**: Linear, Holt's ExpSmooth, ARIMA-like, Ensemble
- **Fortgeschritten**: Regime-Switching, Bayesian, Online Ensemble, Cross-Asset
- **Deep Learning**: LSTM, GRU mit Backpropagation Through Time
- **Reinforcement Learning**: Q-Learning, DQN, REINFORCE
- **Genetische Optimierung**: Feature-Selection, Differential Evolution, NSGA-II

### Trading Game
- Paper-Trading mit virtuellen Kapital
- 6 Challenges (Beat Market, Low Volatility, Income Generator, ...)
- Leaderboard, Equity-Curves, automatischer Modus

### Risk Dashboard
- VaR, CVaR, Rolling Sharpe, Drawdown Series
- Performance Attribution, Korrelationsmatrix
- Korrelation-Regime-Erkennung

---

## Technologie

| Komponente | Technologie | Warum |
|------------|-------------|-------|
| **Backend** | Python 3.11, FastAPI | Lesbarkeit, Ecosystem |
| **Datenbank** | SQLite | Zero-Config, portable |
| **Web UI** | HTML/Canvas (Bloomberg-Stil) | Keine Dependencies |
| **Desktop** | PyQt6 + pyqtgraph | Native Performance |
| **Charts** | Canvas 2D / pyqtgraph | Echtzeit, interaktiv |
| **KI** | 100% numpy | Kein GPU, kein CUDA |
| **Tests** | pytest | 90+ Tests, grün |
| **CI/CD** | GitHub Actions, Docker | Automatisiert |

---

## Use Cases

### Privatanleger
- Portfolio-Entwicklung verstehen
- Risiken quantifizieren (VaR, Max Drawdown)
- Strategien **vor** echten Einsatz testen

### Trader
- Backtests mit realistischen Kosten
- Szenarien für verschiedene Marktphasen
- Paper-Trading für Strategie-Validierung

### Bildung
- Finanzmathematik praktisch erleben
- KI/ML-Modelle verstehen (keine Black Box)
- Datenschutz und Reproduzierbarkeit lernen

### Forschung
- Methodik offen dokumentiert
- Alle Berechnungen reproduzierbar
- Lokale Daten, keine API-Abhängigkeit

---

## Vergleich

| Feature | Local Market Lab | Bloomberg Terminal | Online-Broker |
|---------|------------------|-------------------|---------------|
| **Kosten** | Kostenlos (Open Source) | ~2.000€/Monat | 0€ |
| **Datenschutz** | 100% lokal | Cloud | Cloud |
| **Methodik** | Offen dokumentiert | Proprietär | Proprietär |
| **KI-Modelle** | 15+, lokal | Extern, Black-Box | Keine |
| **Backtest** | Kosten, Slippage, Benchmark | Ja, aber teuer | Eingeschränkt |
| **Reproduzierbarkeit** | Seed, Hash, Manifest | Nein | Nein |
| **Offline-fähig** | Ja | Nein | Nein |
| **Windows-App** | Ja (PyQt6) | Ja (Native) | Web |

---

## Sicherheit & Compliance

### Bank-Ready
- **Audit-Logger**: Append-only, SHA-256-Prüfsummen
- **Data Integrity**: Automatische Checksummen für kritische Tabellen
- **GDPR-Export**: JSON-Export aller Nutzerdaten
- **GDPR-Löschung**: Anonymisierung mit Aggregat-Erhaltung
- **Compliance-Report**: BaFin-konformes JSON

### Sicherheitsprinzipien
- Keine externen API-Aufrufe (außer optional: Ollama)
- Rate Limiting (100 Anfragen/Minute/IP)
- Request-ID für Traceability
- Graceful Shutdown mit DB-Close

---

## Roadmap

| Version | Features |
|---------|----------|
| **0.9** | Walk-Forward-Validation, Hyperparameter-Tuning |
| **1.0** | Echte Marktdaten (Yahoo Finance, Alpha Vantage) |
| **1.1** | Multiplayer-Lobby, Team-Challenges |
| **1.2** | Export: PDF, Excel, CSV Reports |
| **2.0** | Mobile App (iOS/Android) |

---

## Team

**Erik Gieske** — Autor, Entwickler
- GitHub: [github.com/mrmixx-max](https://github.com/mrmixx-max)
- E-Mail: erikgieske@gmail.com

---

## Call-to-Action

**Starte jetzt — kostenlos, ohne Registrierung, ohne Cloud.**

```bash
git clone https://github.com/mrmixx-max/local-market-lab.git
cd local-market-lab
pip install -e ".[dev]"
python -m apps.api
```

**Oder**: Windows-Installer von [GitHub Releases](https://github.com/mrmixx-max/local-market-lab/releases) herunterladen.

---

*Lokale First. Keine Cloud. Keine Kompromisse.*

**LML v0.8.0 — Die Open-Source-Alternative für datenschutzorientierte Marktanalyse.**
