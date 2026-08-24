"""Local Market Lab — Windows Desktop Main Window."""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pyqtgraph as pg
import requests
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtGui import QColor, QIcon, QPen
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

API_BASE = "http://127.0.0.1:8322"
API_TIMEOUT = 5
POLL_MS = 3000
C_BG, C_AMBER, C_DIM = "#000000", "#FFA028", "#555555"
C_GREEN, C_RED, C_WHITE = "#00CC66", "#FF3344", "#EEEEEE"
FONT = "Consolas"

STYLESHEET = f"""
QMainWindow {{ background: {C_BG}; color: {C_WHITE}; }}
QWidget {{ background: {C_BG}; color: {C_WHITE}; font-family: "{FONT}"; font-size: 16px; }}
QTabWidget::pane {{ border: 1px solid {C_DIM}; }}
QTabBar::tab {{ background: #111; color: {C_DIM}; padding: 12px 24px; font-size: 16px;
               border: 1px solid {C_DIM}; border-bottom: none; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {C_BG}; color: {C_AMBER}; border-color: {C_AMBER}; }}
QTableWidget {{ background: #0A0A0A; color: {C_WHITE}; gridline-color: #222; font-size: 15px;
               border: none; font-family: "{FONT}"; }}
QTableWidget::item:selected {{ background: #1a1a00; color: {C_AMBER}; }}
QHeaderView::section {{ background: #111; color: {C_AMBER}; border: 1px solid {C_DIM};
                       padding: 8px; font-weight: bold; font-size: 15px; }}
QStatusBar {{ background: #080808; color: {C_DIM}; font-size: 14px; }}
QPushButton {{ background: #111; color: {C_AMBER}; border: 1px solid {C_AMBER};
              padding: 10px 22px; font-size: 16px; font-weight: bold; }}
QPushButton:hover {{ background: #221100; }}
QPushButton:pressed {{ background: {C_AMBER}; color: {C_BG}; }}
QComboBox {{ background: #111; color: {C_WHITE}; padding: 8px; font-size: 15px; border: 1px solid #333; }}
QTextEdit {{ background: #0a0a0a; color: {C_WHITE}; font-size: 15px; border: 1px solid #333; }}
"""


class ApiClient:
    def __init__(self, base_url: str = API_BASE, timeout: int = API_TIMEOUT):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def get(self, path: str, **kwargs):
        try:
            r = self.session.get(f"{self.base}{path}", timeout=self.timeout, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def post(self, path: str, json: dict = None):
        try:
            r = self.session.post(f"{self.base}{path}", json=json or {}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.api = ApiClient()
        self.setWindowTitle("Local Market Lab — Terminal")
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)
        self._symbols: list[str] = []
        self._last_prices: dict[str, float] = {}
        icon_path = str(Path(__file__).parent.parent.parent / "lml-icon.ico")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))
        self._build_ui()
        self._init_watchlist()
        self._load_ollama_models()
        self._build_timers()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar(), 0)
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._build_topbar(), 0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_markets_tab(), "Markets")
        self.tabs.addTab(self._build_backtest_tab(), "Backtest")
        self.tabs.addTab(self._build_scenarios_tab(), "Scenarios")
        self.tabs.addTab(self._build_game_tab(), "Game")
        self.tabs.addTab(self._build_ollama_tab(), "Ollama")
        self.tabs.addTab(self._build_risk_tab(), "Risk")
        main.addWidget(self.tabs, 1)
        mw = QWidget()
        mw.setLayout(main)
        root.addWidget(mw, 1)
        self.setStatusBar(self._build_statusbar())

    def _build_sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(320)
        frame.setStyleSheet(f"QFrame {{ border-right: 1px solid {C_DIM}; }}")
        lo = QVBoxLayout(frame)
        lo.setContentsMargins(6, 6, 6, 6)
        title = QLabel("◆ WATCHLIST")
        title.setStyleSheet(f"color: {C_AMBER}; font-weight: bold; padding: 4px;")
        lo.addWidget(title)
        self.watchlist = QTableWidget(0, 3)
        self.watchlist.setHorizontalHeaderLabels(["Symbol", "Last", "Chg%"])
        self.watchlist.horizontalHeader().setStretchLastSection(True)
        self.watchlist.verticalHeader().setVisible(False)
        self.watchlist.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.watchlist.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lo.addWidget(self.watchlist, 1)
        add_row = QHBoxLayout()
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("Symbol hinzufügen...")
        add_row.addWidget(self.symbol_input)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(40)
        add_btn.clicked.connect(self._add_symbol)
        add_row.addWidget(add_btn)
        lo.addLayout(add_row)
        return frame

    def _build_topbar(self) -> QWidget:
        bar = QHBoxLayout()
        bar.setContentsMargins(10, 6, 10, 6)
        brand = QLabel("◆ LOCAL MARKET LAB")
        brand.setStyleSheet(f"color: {C_AMBER}; font-size: 18px; font-weight: bold;")
        bar.addWidget(brand, 1)
        self.clock_label = QLabel("--:--:--")
        bar.addWidget(self.clock_label)
        bar.addSpacing(20)
        self.conn_label = QLabel("● DISCONNECTED")
        self.conn_label.setStyleSheet(f"color: {C_RED};")
        bar.addWidget(self.conn_label)
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(40)
        refresh_btn.clicked.connect(self._poll)
        bar.addWidget(refresh_btn)
        w = QWidget()
        w.setLayout(bar)
        return w

    def _build_statusbar(self) -> QStatusBar:
        sb = QStatusBar()
        sb.showMessage("⚠ FOR EDUCATIONAL PURPOSES ONLY — NOT FINANCIAL ADVICE")
        return sb

    def _build_markets_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.mk_symbol = QComboBox()
        self.mk_symbol.setMinimumWidth(150)
        top.addWidget(self.mk_symbol)
        top.addSpacing(20)
        for name in ["SMA", "EMA", "RSI", "MACD", "Bollinger"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self._toggle_indicator(n, checked))
            top.addWidget(btn)
        top.addStretch()
        self.mk_price = QLabel("--")
        self.mk_price.setStyleSheet(f"color: {C_AMBER}; font-size: 20px; font-weight: bold;")
        top.addWidget(self.mk_price)
        self.mk_chg = QLabel("--")
        self.mk_chg.setStyleSheet(f"font-size: 16px;")
        top.addWidget(self.mk_chg)
        lo.addLayout(top)
        self.mk_chart = pg.PlotWidget()
        self.mk_chart.setBackground(C_BG)
        self.mk_chart.showGrid(x=True, y=True, alpha=0.15)
        self.mk_chart.getPlotItem().showAxis('bottom', True)
        self.mk_chart.getPlotItem().showAxis('left', True)
        lo.addWidget(self.mk_chart, 1)
        return w

    def _build_backtest_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.bt_symbol = QComboBox()
        self.bt_symbol.setMinimumWidth(150)
        top.addWidget(self.bt_symbol)
        top.addWidget(QLabel("Strategie:"))
        self.bt_strategy = QComboBox()
        self.bt_strategy.addItems(["buy_and_hold", "periodic_rebalance_63", "momentum_20", "mean_reversion_20"])
        top.addWidget(self.bt_strategy)
        run_btn = QPushButton("▶ Run")
        run_btn.clicked.connect(self._run_backtest)
        top.addWidget(run_btn)
        top.addStretch()
        lo.addLayout(top)
        self.bt_table = QTableWidget(0, 4)
        self.bt_table.setHorizontalHeaderLabels(["Metrik", "Wert", "Metrik", "Wert"])
        self.bt_table.horizontalHeader().setStretchLastSection(True)
        self.bt_table.setMaximumHeight(120)
        lo.addWidget(self.bt_table)
        self.bt_chart = pg.PlotWidget()
        self.bt_chart.setBackground(C_BG)
        self.bt_chart.showGrid(x=True, y=True, alpha=0.15)
        lo.addWidget(self.bt_chart, 1)
        return w

    def _build_scenarios_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.sc_symbol = QComboBox()
        self.sc_symbol.setMinimumWidth(150)
        top.addWidget(self.sc_symbol)
        top.addWidget(QLabel("Methode:"))
        self.sc_method = QComboBox()
        self.sc_method.addItems(["monte_carlo", "block_bootstrap", "historical_replay"])
        top.addWidget(self.sc_method)
        run_btn = QPushButton("▶ Run")
        run_btn.clicked.connect(self._run_scenario)
        top.addWidget(run_btn)
        top.addStretch()
        lo.addLayout(top)
        self.sc_table = QTableWidget(0, 2)
        self.sc_table.setHorizontalHeaderLabels(["Perzentil", "Wert"])
        self.sc_table.horizontalHeader().setStretchLastSection(True)
        self.sc_table.setMaximumHeight(150)
        lo.addWidget(self.sc_table)
        self.sc_chart = pg.PlotWidget()
        self.sc_chart.setBackground(C_BG)
        self.sc_chart.showGrid(x=True, y=True, alpha=0.15)
        lo.addWidget(self.sc_chart, 1)
        return w

    def _build_game_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Challenge:"))
        self.gm_challenge = QComboBox()
        self.gm_challenge.addItems(["beat_market", "low_volatility", "income_generator", "max_sharpe", "min_volatility", "beat_benchmark_by_5pct"])
        top.addWidget(self.gm_challenge)
        create_btn = QPushButton("▶ Create")
        create_btn.clicked.connect(self._create_game)
        top.addWidget(create_btn)
        top.addWidget(QLabel("Auto:"))
        self.gm_interval = QComboBox()
        self.gm_interval.addItems(["Off", "1s", "3s", "5s"])
        top.addWidget(self.gm_interval)
        auto_btn = QPushButton("▶ Auto")
        auto_btn.clicked.connect(self._auto_run)
        top.addWidget(auto_btn)
        top.addStretch()
        lo.addLayout(top)
        self.gm_table = QTableWidget(0, 5)
        self.gm_table.setHorizontalHeaderLabels(["Rank", "Player", "Return", "Sharpe", "Trades"])
        self.gm_table.horizontalHeader().setStretchLastSection(True)
        lo.addWidget(self.gm_table, 1)
        return w

    def _build_ollama_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Modell:"))
        self.ol_model = QComboBox()
        self.ol_model.setMinimumWidth(300)
        top.addWidget(self.ol_model)
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.clicked.connect(self._load_ollama_models)
        top.addWidget(refresh_btn)
        top.addStretch()
        lo.addLayout(top)
        self.ol_chat = QTextEdit()
        self.ol_chat.setReadOnly(True)
        self.ol_chat.setStyleSheet("background: #0a0a0a; color: #EEEEEE; font-size: 14px;")
        lo.addWidget(self.ol_chat, 1)
        inp = QHBoxLayout()
        self.ol_input = QLineEdit()
        self.ol_input.setPlaceholderText("Nachricht eingeben...")
        self.ol_input.returnPressed.connect(self._send_chat)
        inp.addWidget(self.ol_input)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send_chat)
        inp.addWidget(send_btn)
        lo.addLayout(inp)
        return w

    def _load_ollama_models(self) -> None:
        """Lade Ollama-Modelle direkt."""
        self.ol_model.clear()
        models = self.api.get("/api/v1/ollama/models")
        if models and isinstance(models, dict):
            for m in models.get("models", []):
                name = m.get("model", "")
                if name:
                    size = m.get("size_gb", "?")
                    self.ol_model.addItem(f"{name} ({size}GB)", name)

    def _build_risk_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        self.risk_table = QTableWidget(0, 4)
        self.risk_table.setHorizontalHeaderLabels(["Metrik", "Wert", "Metrik", "Wert"])
        self.risk_table.horizontalHeader().setStretchLastSection(True)
        self.risk_table.setMaximumHeight(150)
        lo.addWidget(self.risk_table)
        self.risk_chart = pg.PlotWidget()
        self.risk_chart.setBackground(C_BG)
        self.risk_chart.showGrid(x=True, y=True, alpha=0.15)
        lo.addWidget(self.risk_chart, 1)
        return w

    def _build_timers(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(POLL_MS)
        QTimer.singleShot(0, self._poll)

    def _update_clock(self) -> None:
        self.clock_label.setText(QTime.currentTime().toString("hh:mm:ss"))

    def _init_watchlist(self) -> None:
        """Initialisiere Watchlist mit Standardwerten."""
        defaults = [
            ("AAPL", "Apple Inc."),
            ("MSFT", "Microsoft Corp."),
            ("GOOGL", "Alphabet Inc."),
            ("AMZN", "Amazon.com Inc."),
            ("TSLA", "Tesla Inc."),
            ("NVDA", "NVIDIA Corp."),
            ("META", "Meta Platforms Inc."),
            ("BTC-USD", "Bitcoin"),
            ("ETH-USD", "Ethereum"),
            ("SPY", "S&P 500 ETF"),
            ("QQQ", "Nasdaq 100 ETF"),
            ("IWDA", "iShares MSCI World"),
        ]
        for symbol, name in defaults:
            if symbol not in self._symbols:
                self._symbols.append(symbol)
                row = self.watchlist.rowCount()
                self.watchlist.insertRow(row)
                self.watchlist.setItem(row, 0, QTableWidgetItem(symbol))
                self.watchlist.setItem(row, 1, QTableWidgetItem("--"))
                self.watchlist.setItem(row, 2, QTableWidgetItem("0.00%"))

    def _add_symbol(self) -> None:
        """Füge ein Symbol zur Watchlist hinzu."""
        symbol = self.symbol_input.text().strip().upper()
        if not symbol or symbol in self._symbols:
            return
        row = self.watchlist.rowCount()
        self.watchlist.insertRow(row)
        self.watchlist.setItem(row, 0, QTableWidgetItem(symbol))
        self.watchlist.setItem(row, 1, QTableWidgetItem("--"))
        self.watchlist.setItem(row, 2, QTableWidgetItem("0.00%"))
        self._symbols.append(symbol)
        self.symbol_input.clear()
        self.mk_symbol.addItem(symbol)
        self.bt_symbol.addItem(symbol)
        self.sc_symbol.addItem(symbol)

    def _toggle_indicator(self, name: str, checked: bool) -> None:
        pass

    def _run_backtest(self) -> None:
        symbol = self.bt_symbol.currentText()
        strategy = self.bt_strategy.currentText()
        if not symbol:
            return
        result = self.api.post("/api/v1/backtest", {"symbol": symbol, "strategy": strategy})
        if not result:
            return
        self.bt_table.setRowCount(0)
        metrics = [("CAGR", result.get("cagr", "--")), ("MaxDD", result.get("max_drawdown", "--")),
                   ("Sharpe", result.get("sharpe", "--")), ("Sortino", result.get("sortino", "--"))]
        for i, (k, v) in enumerate(metrics):
            self.bt_table.insertRow(i)
            self.bt_table.setItem(i, 0, QTableWidgetItem(k))
            self.bt_table.setItem(i, 1, QTableWidgetItem(str(v)))
        equity = result.get("equity_curve", [])
        if equity:
            self.bt_chart.clear()
            self.bt_chart.plot(equity, pen=pg.mkPen(C_AMBER, width=2))

    def _run_scenario(self) -> None:
        symbol = self.sc_symbol.currentText()
        method = self.sc_method.currentText()
        if not symbol:
            return
        result = self.api.post("/api/v1/scenario", {"symbol": symbol, "method": method})
        if not result:
            return
        self.sc_table.setRowCount(0)
        for i, p in enumerate(["p05", "p25", "p50", "p75", "p95"]):
            self.sc_table.insertRow(i)
            self.sc_table.setItem(i, 0, QTableWidgetItem(p.upper()))
            self.sc_table.setItem(i, 1, QTableWidgetItem(str(result.get(p, "--"))))
        hist = result.get("histogram", [])
        if hist:
            self.sc_chart.clear()
            self.sc_chart.plot(hist, pen=pg.mkPen(C_AMBER, width=2))

    def _create_game(self) -> None:
        challenge = self.gm_challenge.currentText()
        self.api.post("/api/v1/game/create", {"challenge": challenge})
        self._refresh_leaderboard()

    def _auto_run(self) -> None:
        pass

    def _refresh_leaderboard(self) -> None:
        data = self.api.get("/api/v1/game/leaderboard")
        if not data:
            return
        self.gm_table.setRowCount(0)
        for i, entry in enumerate(data[:20]):
            self.gm_table.insertRow(i)
            self.gm_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.gm_table.setItem(i, 1, QTableWidgetItem(entry.get("player", "--")))
            self.gm_table.setItem(i, 2, QTableWidgetItem(str(entry.get("return", "--"))))
            self.gm_table.setItem(i, 3, QTableWidgetItem(str(entry.get("sharpe", "--"))))
            self.gm_table.setItem(i, 4, QTableWidgetItem(str(entry.get("trades", "--"))))

    def _send_chat(self) -> None:
        text = self.ol_input.text().strip()
        if not text:
            return
        model = self.ol_model.currentData() or self.ol_model.currentText()
        self.ol_chat.append(f"<b>Du:</b> {text}")
        self.ol_input.clear()
        result = self.api.post("/api/v1/ollama/chat", {"model": model, "message": text})
        if result:
            self.ol_chat.append(f"<b>KI:</b> {result.get('content', result.get('response', 'Keine Antwort'))}")

    def _poll(self) -> None:
        health = self.api.get("/api/v1/health")
        if health:
            self.conn_label.setText("● CONNECTED")
            self.conn_label.setStyleSheet(f"color: {C_GREEN};")
        else:
            self.conn_label.setText("● DISCONNECTED")
            self.conn_label.setStyleSheet(f"color: {C_RED};")
            return
        for row in range(self.watchlist.rowCount()):
            symbol = self.watchlist.item(row, 0).text()
            prices = self.api.get(f"/api/v1/market/prices/{symbol}")
            if prices and isinstance(prices, list) and len(prices) > 0:
                last = prices[-1]
                prev = prices[-2] if len(prices) > 1 else last
                chg = ((last - prev) / prev * 100) if prev else 0
                self.watchlist.item(row, 1).setText(f"{last:.2f}")
                self.watchlist.item(row, 2).setText(f"{chg:+.2f}%")
                color = C_GREEN if chg >= 0 else C_RED
                self.watchlist.item(row, 2).setForeground(QColor(color))
            else:
                # Fallback: Yahoo Finance direkt abfragen
                yahoo = self.api.get(f"/api/v1/market/yahoo/{symbol}")
                if yahoo and yahoo.get("price"):
                    last = yahoo["price"]
                    prev = yahoo.get("prev_close", last)
                    chg = ((last - prev) / prev * 100) if prev else 0
                    self.watchlist.item(row, 1).setText(f"{last:.2f}")
                    self.watchlist.item(row, 2).setText(f"{chg:+.2f}%")
                    color = C_GREEN if chg >= 0 else C_RED
                    self.watchlist.item(row, 2).setForeground(QColor(color))
        if self.mk_symbol.count() == 0:
            syms = self.api.get("/api/v1/market/symbols")
            if syms:
                for s in syms:
                    self.mk_symbol.addItem(s.get("symbol", ""))
                    self.bt_symbol.addItem(s.get("symbol", ""))
                    self.sc_symbol.addItem(s.get("symbol", ""))
        models = self.api.get("/api/v1/ollama/models")
        if models and self.ol_model.count() == 0:
            self._load_ollama_models()
        if self.tabs.currentIndex() == 5:
            self._refresh_risk()

    def _refresh_risk(self) -> None:
        data = self.api.get("/api/v1/portfolio/demo?include_analytics=true")
        if not data:
            return
        self.risk_table.setRowCount(0)
        metrics = [("Value", data.get("total_value", "--")), ("P&L", data.get("unrealized_pl", "--")),
                   ("Positions", len(data.get("positions", []))), ("Currency", data.get("reporting_currency", "--"))]
        for i, (k, v) in enumerate(metrics):
            self.risk_table.insertRow(i)
            self.risk_table.setItem(i, 0, QTableWidgetItem(k))
            self.risk_table.setItem(i, 1, QTableWidgetItem(str(v)))
        positions = data.get("positions", [])
        if positions:
            self.risk_chart.clear()
            returns = [p.get("pl_pct", 0) for p in positions]
            labels = [p.get("symbol", "") for p in positions]
            x = range(len(returns))
            colors = [C_GREEN if r >= 0 else C_RED for r in returns]
            for xi, (r, c) in enumerate(zip(returns, colors)):
                self.risk_chart.plot([xi, xi], [0, r], pen=pg.mkPen(c, width=8))
