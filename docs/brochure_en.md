# Local Market Lab

## Your private market analytics. Local. Secure. Reproducible.

**Version 0.8.0 — The open-source alternative to Bloomberg Terminal**

---

## Executive Summary

**Local Market Lab** (LML) is a locally-running, privacy-focused workbench for portfolio analytics, backtesting, scenario simulation, and AI-powered market prediction — all on your own machine, no cloud, no data sharing.

### The Three Promises

| Promise | Implementation |
|---------|----------------|
| **Privacy First** | No telemetry, no external services, local SQLite |
| **Institutional Methodology** | CAGR, Sharpe, VaR, CVaR, Monte Carlo — professionally documented |
| **Reproducibility** | Every run has seed, timestamp, data hash |

---

## The Problem

Modern market analysis has three weaknesses:

1. **Privacy**: Most tools send your portfolio data to cloud servers. Your investment strategy becomes the product.

2. **Black-Box Models**: AI-powered predictions don't explain how they work. No control, no transparency.

3. **Complexity**: Professional tools (Bloomberg, Refinitiv) cost thousands of euros per month and require months of training.

**LML solves all three.**

---

## The Solution

Local Market Lab combines six tools into one application:

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL MARKET LAB                         │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│  Portfolio  │  Backtest   │  Scenarios  │  AI Prediction      │
│  Analytics  │  Engine     │  Engine     │  15+ Models         │
├─────────────┼─────────────┼─────────────┼─────────────────────┤
│  Trading    │  Risk       │  Ollama     │  Bank-Ready         │
│  Game       │  Dashboard  │  Chat       │  Compliance          │
└─────────────┴─────────────┴─────────────┴─────────────────────┘
```

### Portfolio Analytics
- Real-time valuation with Decimal accuracy (no float errors)
- FX Policy with `incomplete` state (never silent 1:1 conversion)
- Corporate Actions: Splits, dividends, chronologically correct
- Benchmark comparison with Beta, Alpha, Tracking Error

### Backtest Engine
- Event loop over aligned price series
- Strategies: Buy & Hold, Momentum, Mean Reversion, Periodic Rebalance
- Configurable fees and slippage
- Reproducibility manifests with seed and data hash

### Scenarios
- Monte Carlo, Block-Bootstrap, Historical-Replay
- Percentiles (P05–P95), loss probability
- Explicit: **No forecast, only scenarios**

### AI Prediction (15+ Models)
- **Basic Models**: Linear, Holt's ExpSmooth, ARIMA-like, Ensemble
- **Advanced**: Regime-Switching, Bayesian, Online Ensemble, Cross-Asset
- **Deep Learning**: LSTM, GRU with Backpropagation Through Time
- **Reinforcement Learning**: Q-Learning, DQN, REINFORCE
- **Genetic Optimization**: Feature Selection, Differential Evolution, NSGA-II

### Trading Game
- Paper trading with virtual capital
- 6 Challenges (Beat Market, Low Volatility, Income Generator, ...)
- Leaderboard, equity curves, automatic mode

### Risk Dashboard
- VaR, CVaR, Rolling Sharpe, Drawdown Series
- Performance Attribution, Correlation Matrix
- Correlation-Regime Detection

---

## Technology

| Component | Technology | Why |
|-----------|-----------|-------|
| **Backend** | Python 3.11, FastAPI | Readability, ecosystem |
| **Database** | SQLite | Zero-config, portable |
| **Web UI** | HTML/Canvas (Bloomberg Style) | No dependencies |
| **Desktop** | PyQt6 + pyqtgraph | Native performance |
| **Charts** | Canvas 2D / pyqtgraph | Real-time, interactive |
| **AI** | 100% numpy | No GPU, no CUDA |
| **Tests** | pytest | 90+ tests, green |
| **CI/CD** | GitHub Actions, Docker | Automated |

---

## Use Cases

### Retail Investors
- Understand portfolio development
- Quantify risks (VaR, Max Drawdown)
- Test strategies **before** real deployment

### Traders
- Backtests with realistic costs
- Scenarios for different market phases
- Paper trading for strategy validation

### Education
- Experience financial mathematics practically
- Understand AI/ML models (no black box)
- Learn privacy and reproducibility

### Research
- Openly documented methodology
- All calculations reproducible
- Local data, no API dependency

---

## Comparison

| Feature | Local Market Lab | Bloomberg Terminal | Online Broker |
|---------|------------------|-------------------|---------------|
| **Cost** | Free (Open Source) | ~€2,000/month | €0 |
| **Privacy** | 100% local | Cloud | Cloud |
| **Methodology** | Openly documented | Proprietary | Proprietary |
| **AI Models** | 15+, local | External, black-box | None |
| **Backtest** | Fees, slippage, benchmark | Yes, but expensive | Limited |
| **Reproducibility** | Seed, hash, manifest | No | No |
| **Offline capable** | Yes | No | No |
| **Windows App** | Yes (PyQt6) | Yes (Native) | Web |

---

## Security & Compliance

### Bank-Ready
- **Audit Logger**: Append-only, SHA-256 checksums
- **Data Integrity**: Automatic checksums for critical tables
- **GDPR Export**: JSON export of all user data
- **GDPR Deletion**: Anonymization with aggregate preservation
- **Compliance Report**: BaFin-compliant JSON

### Security Principles
- No external API calls (except optional: Ollama)
- Rate Limiting (100 requests/minute/IP)
- Request ID for traceability
- Graceful shutdown with DB close

---

## Roadmap

| Version | Features |
|---------|----------|
| **0.9** | Walk-Forward Validation, Hyperparameter Tuning |
| **1.0** | Real market data (Yahoo Finance, Alpha Vantage) |
| **1.1** | Multiplayer Lobby, Team Challenges |
| **1.2** | Export: PDF, Excel, CSV Reports |
| **2.0** | Mobile App (iOS/Android) |

---

## Team

**Erik Gieske** — Author, Developer
- GitHub: [github.com/mrmixx-max](https://github.com/mrmixx-max)
- Email: erikgieske@gmail.com

---

## Call-to-Action

**Start now — free, no registration, no cloud.**

```bash
git clone https://github.com/mrmixx-max/local-market-lab.git
cd local-market-lab
pip install -e ".[dev]"
python -m apps.api
```

**Or**: Download the Windows installer from [GitHub Releases](https://github.com/mrmixx-max/local-market-lab/releases).

---

*Private first. No cloud. No compromises.*

**LML v0.8.0 — The open-source alternative for privacy-focused market analytics.**
