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
    QApplication, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

API_BASE = "http://127.0.0.1:8322"
API_TIMEOUT = 8
POLL_MS = 3000
C_BG, C_AMBER, C_DIM = "#000000", "#FFA028", "#555555"
C_GREEN, C_RED, C_WHITE = "#00CC66", "#FF3344", "#EEEEEE"
FONT = "Consolas"

STYLESHEET = f"""
QMainWindow {{ background: {C_BG}; color: {C_WHITE}; }}
QWidget {{ background: {C_BG}; color: {C_WHITE}; font-family: "{FONT}"; font-size: 16px; }}
QTabWidget::pane {{ border: 1px solid {C_DIM}; }}
QTabBar::tab {{ background: #111; color: {C_DIM}; padding: 10px 20px; font-size: 15px;
               border: 1px solid {C_DIM}; border-bottom: none; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {C_BG}; color: {C_AMBER}; border-color: {C_AMBER}; }}
QTableWidget {{ background: #0A0A0A; color: {C_WHITE}; gridline-color: #222; font-size: 14px;
               border: none; font-family: "{FONT}"; }}
QTableWidget::item:selected {{ background: #1a1a00; color: {C_AMBER}; }}
QHeaderView::section {{ background: #111; color: {C_AMBER}; border: 1px solid {C_DIM};
                       padding: 6px; font-weight: bold; font-size: 14px; }}
QStatusBar {{ background: #080808; color: {C_DIM}; font-size: 13px; }}
QPushButton {{ background: #111; color: {C_AMBER}; border: 1px solid {C_AMBER};
              padding: 8px 18px; font-size: 14px; font-weight: bold; }}
QPushButton:hover {{ background: #221100; }}
QPushButton:pressed {{ background: {C_AMBER}; color: {C_BG}; }}
QComboBox {{ background: #111; color: {C_WHITE}; padding: 6px; font-size: 14px; border: 1px solid #333; }}
QLineEdit {{ background: #111; color: {C_WHITE}; padding: 6px; font-size: 14px; border: 1px solid #333; }}
QTextEdit {{ background: #0a0a0a; color: {C_WHITE}; font-size: 14px; border: 1px solid #333; }}
QDoubleSpinBox {{ background: #111; color: {C_WHITE}; padding: 4px; border: 1px solid #333; }}
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
        self.tabs.addTab(self._build_validation_tab(), "Validation")
        self.tabs.addTab(self._build_explainability_tab(), "Explainability")
        self.tabs.addTab(self._build_rebalancing_tab(), "Rebalancing")
        self.tabs.addTab(self._build_export_tab(), "Export")
        self.tabs.addTab(self._build_risk_tab(), "Risk")
        self.tabs.addTab(self._build_ollama_tab(), "Ollama")
        self.tabs.addTab(self._build_game_tab(), "Game")
        main.addWidget(self.tabs, 1)
        root.addLayout(main, 1)
        self.setStatusBar(self._build_statusbar())

    def _build_topbar(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: #080808; border-bottom: 1px solid {C_DIM};")
        lo = QHBoxLayout(w)
        lo.setContentsMargins(12, 8, 12, 8)
        brand = QLabel("◆ LOCAL MARKET LAB")
        brand.setStyleSheet(f"color: {C_AMBER}; font-size: 18px; font-weight: bold;")
        lo.addWidget(brand)
        lo.addStretch()
        self.conn_label = QLabel("● DISCONNECTED")
        self.conn_label.setStyleSheet(f"color: {C_RED};")
        lo.addWidget(self.conn_label)
        lo.addSpacing(20)
        self.clock_label = QLabel("--:--:--")
        self.clock_label.setStyleSheet(f"color: {C_DIM};")
        lo.addWidget(self.clock_label)
        return w

    def _build_sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(320)
        frame.setStyleSheet(f"background: #0a0a0a; border-right: 1px solid {C_DIM};")
        lo = QVBoxLayout(frame)
        lo.setContentsMargins(8, 8, 8, 8)
        lbl = QLabel("WATCHLIST")
        lbl.setStyleSheet(f"color: {C_AMBER}; font-weight: bold; font-size: 14px;")
        lo.addWidget(lbl)
        self.watchlist = QTableWidget(0, 3)
        self.watchlist.setHorizontalHeaderLabels(["Symbol", "Last", "Chg%"])
        self.watchlist.setStyleSheet("border: none;")
        self.watchlist.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lo.addWidget(self.watchlist, 1)
        add_row = QHBoxLayout()
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("Symbol...")
        self.symbol_input.returnPressed.connect(self._add_symbol)
        add_row.addWidget(self.symbol_input)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(40)
        add_btn.clicked.connect(self._add_symbol)
        add_row.addWidget(add_btn)
        lo.addLayout(add_row)
        return frame

    def _build_statusbar(self) -> QStatusBar:
        sb = QStatusBar()
        sb.showMessage("Keine Finanzberatung. Keine Kauf- oder Verkaufsempfehlung.")
        return sb

    # ─── Tab Builders ───────────────────────────────────────────────

    def _build_markets_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.mk_symbol = QComboBox()
        self.mk_symbol.addItems(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"])
        self.mk_symbol.currentTextChanged.connect(self._load_market_data)
        top.addWidget(self.mk_symbol)
        top.addStretch()
        self.mk_price = QLabel("--")
        self.mk_price.setStyleSheet(f"color: {C_AMBER}; font-size: 18px; font-weight: bold;")
        top.addWidget(self.mk_price)
        self.mk_chg = QLabel("--")
        top.addWidget(self.mk_chg)
        lo.addLayout(top)
        self.mk_chart = pg.PlotWidget()
        self.mk_chart.setBackground(C_BG)
        self.mk_chart.showGrid(x=True, y=True, alpha=0.2)
        lo.addWidget(self.mk_chart, 1)
        btns = QHBoxLayout()
        for name in ["SMA", "EMA", "RSI", "MACD", "Bollinger"]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, n=name: self._load_indicator(n.lower()))
            btns.addWidget(btn)
        btns.addStretch()
        lo.addLayout(btns)
        return w

    def _build_backtest_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.bt_symbol = QComboBox()
        self.bt_symbol.addItems(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"])
        top.addWidget(self.bt_symbol)
        top.addWidget(QLabel("Strategie:"))
        self.bt_strategy = QComboBox()
        self.bt_strategy.addItems(["buy_and_hold", "periodic_rebalance_63", "momentum_20", "mean_reversion_20"])
        top.addWidget(self.bt_strategy)
        top.addWidget(QLabel("Fees:"))
        self.bt_fees = QDoubleSpinBox()
        self.bt_fees.setRange(0, 100)
        self.bt_fees.setValue(10)
        top.addWidget(self.bt_fees)
        top.addWidget(QLabel("Slippage:"))
        self.bt_slip = QDoubleSpinBox()
        self.bt_slip.setRange(0, 100)
        self.bt_slip.setValue(5)
        top.addWidget(self.bt_slip)
        top.addStretch()
        run_btn = QPushButton("▶ Run")
        run_btn.clicked.connect(self._run_backtest)
        top.addWidget(run_btn)
        lo.addLayout(top)
        self.bt_result = QTableWidget(0, 2)
        self.bt_result.setHorizontalHeaderLabels(["Metric", "Value"])
        lo.addWidget(self.bt_result)
        self.bt_chart = pg.PlotWidget()
        self.bt_chart.setBackground(C_BG)
        self.bt_chart.showGrid(x=True, y=True, alpha=0.2)
        lo.addWidget(self.bt_chart, 1)
        return w

    def _build_scenarios_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.sc_symbol = QComboBox()
        self.sc_symbol.addItems(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"])
        top.addWidget(self.sc_symbol)
        top.addWidget(QLabel("Methode:"))
        self.sc_method = QComboBox()
        self.sc_method.addItems(["crash_30pct", "covid_crash", "2008_financial_crisis", "monte_carlo", "block_bootstrap"])
        top.addWidget(self.sc_method)
        top.addStretch()
        run_btn = QPushButton("▶ Run")
        run_btn.clicked.connect(self._run_scenario)
        top.addWidget(run_btn)
        lo.addLayout(top)
        self.sc_result = QTableWidget(0, 2)
        self.sc_result.setHorizontalHeaderLabels(["Perzentil", "Wert"])
        lo.addWidget(self.sc_result)
        self.sc_chart = pg.PlotWidget()
        self.sc_chart.setBackground(C_BG)
        self.sc_chart.showGrid(x=True, y=True, alpha=0.2)
        lo.addWidget(self.sc_chart, 1)
        return w

    def _build_validation_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.val_symbol = QComboBox()
        self.val_symbol.addItems(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"])
        top.addWidget(self.val_symbol)
        top.addWidget(QLabel("Train:"))
        self.val_train = QLineEdit("100")
        self.val_train.setFixedWidth(60)
        top.addWidget(self.val_train)
        top.addWidget(QLabel("Test:"))
        self.val_test = QLineEdit("25")
        self.val_test.setFixedWidth(60)
        top.addWidget(self.val_test)
        top.addWidget(QLabel("Step:"))
        self.val_step = QLineEdit("10")
        self.val_step.setFixedWidth(50)
        top.addWidget(self.val_step)
        top.addStretch()
        wf_btn = QPushButton("Walk-Forward")
        wf_btn.clicked.connect(self._run_walk_forward)
        top.addWidget(wf_btn)
        hp_btn = QPushButton("Hyperparameter")
        hp_btn.clicked.connect(self._run_hyperparameter)
        top.addWidget(hp_btn)
        lo.addLayout(top)
        self.val_result = QTableWidget(0, 2)
        self.val_result.setHorizontalHeaderLabels(["Metric", "Value"])
        lo.addWidget(self.val_result)
        return w

    def _build_explainability_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.ex_symbol = QComboBox()
        self.ex_symbol.addItems(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"])
        top.addWidget(self.ex_symbol)
        top.addStretch()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_explainability)
        top.addWidget(load_btn)
        lo.addLayout(top)
        self.ex_result = QTableWidget(0, 3)
        self.ex_result.setHorizontalHeaderLabels(["Feature", "Importance", "Std"])
        lo.addWidget(self.ex_result)
        return w

    def _build_rebalancing_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Portfolio:"))
        self.rb_portfolio = QComboBox()
        self.rb_portfolio.addItems(["demo"])
        top.addWidget(self.rb_portfolio)
        top.addStretch()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_rebalancing)
        top.addWidget(load_btn)
        lo.addLayout(top)
        self.rb_result = QTableWidget(0, 6)
        self.rb_result.setHorizontalHeaderLabels(["Symbol", "Current%", "Target%", "Drift%", "Action", "Est. Cost"])
        lo.addWidget(self.rb_result)
        note = QLabel("⚠ NUR VORSCHLÄG — keine Ausführung!")
        note.setStyleSheet(f"color: {C_AMBER};")
        lo.addWidget(note)
        return w

    def _build_export_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Symbol:"))
        self.ex_port = QComboBox()
        self.ex_port.addItems(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"])
        top.addWidget(self.ex_port)
        top.addStretch()
        pdf_btn = QPushButton("PDF")
        pdf_btn.clicked.connect(lambda: self._run_export("pdf"))
        top.addWidget(pdf_btn)
        excel_btn = QPushButton("Excel")
        excel_btn.clicked.connect(lambda: self._run_export("excel"))
        top.addWidget(excel_btn)
        csv_btn = QPushButton("CSV")
        csv_btn.clicked.connect(lambda: self._run_export("csv"))
        top.addWidget(csv_btn)
        lo.addLayout(top)
        self.export_status = QLabel("")
        lo.addWidget(self.export_status)
        lo.addStretch()
        return w

    def _build_risk_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Portfolio:"))
        self.risk_portfolio = QComboBox()
        self.risk_portfolio.addItems(["demo"])
        top.addWidget(self.risk_portfolio)
        top.addStretch()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_risk)
        top.addWidget(load_btn)
        lo.addLayout(top)
        self.risk_result = QTableWidget(0, 2)
        self.risk_result.setHorizontalHeaderLabels(["Metric", "Value"])
        lo.addWidget(self.risk_result)
        self.risk_chart = pg.PlotWidget()
        self.risk_chart.setBackground(C_BG)
        self.risk_chart.showGrid(x=True, y=True, alpha=0.2)
        lo.addWidget(self.risk_chart, 1)
        return w

    def _build_ollama_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Modell:"))
        self.ol_model = QComboBox()
        self.ol_model.setMinimumWidth(300)
        top.addWidget(self.ol_model)
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(40)
        refresh_btn.clicked.connect(self._load_ollama_models)
        top.addWidget(refresh_btn)
        top.addStretch()
        lo.addLayout(top)
        self.ol_chat = QTextEdit()
        self.ol_chat.setReadOnly(True)
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

    def _build_game_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Challenge:"))
        self.game_challenge = QComboBox()
        self.game_challenge.addItems(["beat_market", "low_volatility", "income_generator", "max_sharpe", "min_volatility", "beat_benchmark_by_5pct"])
        top.addWidget(self.game_challenge)
        top.addStretch()
        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self._create_game)
        top.addWidget(create_btn)
        lb_btn = QPushButton("Leaderboard")
        lb_btn.clicked.connect(self._load_leaderboard)
        top.addWidget(lb_btn)
        lo.addLayout(top)
        self.game_result = QTableWidget(0, 4)
        self.game_result.setHorizontalHeaderLabels(["Rank", "Player", "Score", "Challenge"])
        lo.addWidget(self.game_result)
        return w

    # ─── Actions ─────────────────────────────────────────────────────

    def _load_market_data(self, symbol: str) -> None:
        if not symbol:
            return
        data = self.api.get(f"/api/v1/market/data/{symbol}?source=yahoo&interval=1d&years=2")
        if not data or "bars" not in data:
            return
        bars = data["bars"]
        if not bars:
            return
        self.mk_chart.clear()
        closes = [b["close"] for b in bars]
        dates = list(range(len(closes)))
        # Candlesticks
        for i, bar in enumerate(bars):
            o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
            color = C_GREEN if c >= o else C_RED
            self.mk_chart.plot([i, i], [l, h], pen=pg.mkPen(color=color, width=1))
            self.mk_chart.plot([i-0.3, i+0.3], [o, o], pen=pg.mkPen(color=color, width=2))
            self.mk_chart.plot([i-0.3, i+0.3], [c, c], pen=pg.mkPen(color=color, width=2))
        # Price display
        last = closes[-1]
        prev = closes[-2] if len(closes) > 1 else last
        chg = ((last - prev) / prev * 100) if prev else 0
        self.mk_price.setText(f"${last:,.2f}")
        self.mk_chg.setText(f"{chg:+.2f}%")
        self.mk_chg.setStyleSheet(f"color: {C_GREEN if chg >= 0 else C_RED};")

    def _load_indicator(self, name: str) -> None:
        symbol = self.mk_symbol.currentText()
        if not symbol:
            return
        data = self.api.post(f"/api/v1/market/indicators/{symbol}", {"indicator": name, "period": 20})
        if not data:
            return
        # Overlay on chart
        self.mk_chart.clear()
        self._load_market_data(symbol)
        values = data.get("values", [])
        if values:
            self.mk_chart.plot(list(range(len(values))), values, pen=pg.mkPen(color=C_AMBER, width=2))

    def _run_backtest(self) -> None:
        symbol = self.bt_symbol.currentText()
        strategy = self.bt_strategy.currentText()
        fees = self.bt_fees.value()
        slip = self.bt_slip.value()
        data = self.api.post(f"/api/v1/backtest", {
            "symbol": symbol,
            "strategy": strategy,
            "fees_bps": fees,
            "slippage_bps": slip,
            "spread_bps": 2,
            "seed": 42
        })
        if not data:
            return
        self.bt_result.setRowCount(0)
        for key in ["cagr", "max_drawdown", "sharpe", "sortino", "trades"]:
            row = self.bt_result.rowCount()
            self.bt_result.insertRow(row)
            self.bt_result.setItem(row, 0, QTableWidgetItem(key.upper()))
            val = data.get(key, "N/A")
            self.bt_result.setItem(row, 1, QTableWidgetItem(str(val)))
        # Equity curve
        curve = data.get("equity_curve", [])
        if curve:
            self.bt_chart.clear()
            self.bt_chart.plot(list(range(len(curve))), curve, pen=pg.mkPen(color=C_AMBER, width=2))

    def _run_scenario(self) -> None:
        symbol = self.sc_symbol.currentText()
        method = self.sc_method.currentText()
        if method in ["crash_30pct", "covid_crash", "2008_financial_crisis"]:
            data = self.api.post(f"/api/v1/scenario/stress", {"symbol": symbol, "source": "yahoo", "scenario": method, "seed": 42})
        else:
            data = self.api.post(f"/api/v1/scenario", {"symbol": symbol, "method": method, "n_sims": 1000, "seed": 42})
        if not data:
            return
        self.sc_result.setRowCount(0)
        metrics = data.get("metrics", {})
        for key, val in metrics.items():
            row = self.sc_result.rowCount()
            self.sc_result.insertRow(row)
            self.sc_result.setItem(row, 0, QTableWidgetItem(key))
            self.sc_result.setItem(row, 1, QTableWidgetItem(str(val)))
        # Histogram
        timeline = data.get("timeline", [])
        if timeline:
            self.sc_chart.clear()
            y, x = np.histogram(timeline, bins=30)
            self.sc_chart.plot(x[:-1], y, stepMode=True, fillLevel=0, brush=(255, 160, 40, 80))

    def _run_walk_forward(self) -> None:
        symbol = self.val_symbol.currentText()
        try:
            train = int(self.val_train.text())
            test = int(self.val_test.text())
            step = int(self.val_step.text())
        except ValueError:
            return
        data = self.api.post(f"/api/v1/validation/walk-forward", {
            "symbol": symbol, "source": "yahoo",
            "train_window": train, "test_window": test, "step": step, "seed": 42
        })
        if not data:
            return
        self.val_result.setRowCount(0)
        for key in ["n_folds", "avg_sharpe", "oos_sharpe", "avg_return"]:
            row = self.val_result.rowCount()
            self.val_result.insertRow(row)
            self.val_result.setItem(row, 0, QTableWidgetItem(key))
            self.val_result.setItem(row, 1, QTableWidgetItem(str(data.get(key, "N/A"))))

    def _run_hyperparameter(self) -> None:
        symbol = self.val_symbol.currentText()
        data = self.api.post(f"/api/v1/validation/hyperparameter", {
            "symbol": symbol, "source": "yahoo", "metric": "sharpe", "n_trials": 10, "seed": 42
        })
        if not data:
            return
        self.val_result.setRowCount(0)
        for key in ["best_score", "best_params"]:
            row = self.val_result.rowCount()
            self.val_result.insertRow(row)
            self.val_result.setItem(row, 0, QTableWidgetItem(key))
            self.val_result.setItem(row, 1, QTableWidgetItem(str(data.get(key, "N/A"))))

    def _load_explainability(self) -> None:
        symbol = self.ex_symbol.currentText()
        data = self.api.get(f"/api/v1/explainability/importance?symbol={symbol}&source=yahoo")
        if not data:
            return
        self.ex_result.setRowCount(0)
        for f in data.get("feature_importance", []):
            row = self.ex_result.rowCount()
            self.ex_result.insertRow(row)
            self.ex_result.setItem(row, 0, QTableWidgetItem(f.get("feature", "")))
            self.ex_result.setItem(row, 1, QTableWidgetItem(str(f.get("importance", ""))))
            self.ex_result.setItem(row, 2, QTableWidgetItem(str(f.get("std", ""))))

    def _load_rebalancing(self) -> None:
        portfolio = self.rb_portfolio.currentText()
        data = self.api.get(f"/api/v1/portfolio/{portfolio}/rebalancing")
        if not data:
            return
        self.rb_result.setRowCount(0)
        for p in data.get("proposals", []):
            row = self.rb_result.rowCount()
            self.rb_result.insertRow(row)
            self.rb_result.setItem(row, 0, QTableWidgetItem(p.get("symbol", "")))
            self.rb_result.setItem(row, 1, QTableWidgetItem(f"{p.get('current_weight', 0):.2%}"))
            self.rb_result.setItem(row, 2, QTableWidgetItem(f"{p.get('target_weight', 0):.2%}"))
            self.rb_result.setItem(row, 3, QTableWidgetItem(f"{p.get('drift', 0):.2%}"))
            self.rb_result.setItem(row, 4, QTableWidgetItem(p.get("action", "")))
            self.rb_result.setItem(row, 5, QTableWidgetItem(str(p.get("estimated_cost", ""))))

    def _run_export(self, kind: str) -> None:
        symbol = self.ex_port.currentText()
        data = self.api.post(f"/api/v1/export/{kind}", {"symbol": symbol, "source": "yahoo"})
        if not data:
            self.export_status.setText(f"❌ Export {kind} fehlgeschlagen")
            return
        path = data.get("file_path", "")
        self.export_status.setText(f"✅ Export: {path}")

    def _load_risk(self) -> None:
        portfolio = self.risk_portfolio.currentText()
        data = self.api.get(f"/api/v1/portfolio/{portfolio}?include_analytics=true")
        if not data:
            return
        self.risk_result.setRowCount(0)
        analytics = data.get("analytics", {})
        for key, val in analytics.items():
            row = self.risk_result.rowCount()
            self.risk_result.insertRow(row)
            self.risk_result.setItem(row, 0, QTableWidgetItem(key))
            self.risk_result.setItem(row, 1, QTableWidgetItem(str(val)))
        # Drawdown chart
        dd = data.get("drawdown_series", [])
        if dd:
            self.risk_chart.clear()
            self.risk_chart.plot(list(range(len(dd))), dd, pen=pg.mkPen(color=C_RED, width=2))

    def _send_chat(self) -> None:
        text = self.ol_input.text().strip()
        if not text:
            return
        model = self.ol_model.currentData() or self.ol_model.currentText()
        self.ol_chat.append(f"<b>Du:</b> {text}")
        self.ol_input.clear()
        result = self.api.post("/api/v1/ollama/chat", {"model": model, "messages": [{"role": "user", "content": text}]})
        if result:
            self.ol_chat.append(f"<b>KI:</b> {result.get('content', result.get('response', 'Keine Antwort'))}")

    def _create_game(self) -> None:
        challenge = self.game_challenge.currentText()
        data = self.api.post(f"/api/v1/game/create", {"challenge": challenge})
        if not data:
            return
        self.game_result.setRowCount(0)
        row = self.game_result.rowCount()
        self.game_result.insertRow(row)
        self.game_result.setItem(row, 0, QTableWidgetItem("1"))
        self.game_result.setItem(row, 1, QTableWidgetItem(data.get("player", "You")))
        self.game_result.setItem(row, 2, QTableWidgetItem(str(data.get("score", ""))))
        self.game_result.setItem(row, 3, QTableWidgetItem(challenge))

    def _load_leaderboard(self) -> None:
        data = self.api.get(f"/api/v1/game/leaderboard")
        if not data:
            return
        self.game_result.setRowCount(0)
        for i, entry in enumerate(data.get("entries", [])):
            row = self.game_result.rowCount()
            self.game_result.insertRow(row)
            self.game_result.setItem(row, 0, QTableWidgetItem(str(i + 1)))
            self.game_result.setItem(row, 1, QTableWidgetItem(entry.get("player", "")))
            self.game_result.setItem(row, 2, QTableWidgetItem(str(entry.get("score", ""))))
            self.game_result.setItem(row, 3, QTableWidgetItem(entry.get("challenge", "")))

    # ─── Watchlist & Timers ──────────────────────────────────────────

    def _init_watchlist(self) -> None:
        defaults = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BTC-USD", "ETH-USD", "SPY", "QQQ", "IWDA"]
        for symbol in defaults:
            if symbol not in self._symbols:
                self._symbols.append(symbol)
                row = self.watchlist.rowCount()
                self.watchlist.insertRow(row)
                self.watchlist.setItem(row, 0, QTableWidgetItem(symbol))
                self.watchlist.setItem(row, 1, QTableWidgetItem("--"))
                self.watchlist.setItem(row, 2, QTableWidgetItem("0.00%"))

    def _add_symbol(self) -> None:
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

    def _load_ollama_models(self) -> None:
        self.ol_model.clear()
        models = self.api.get("/api/v1/ollama/models")
        if models and isinstance(models, dict):
            for m in models.get("models", []):
                name = m.get("model", "")
                if name:
                    size = m.get("size_gb", "?")
                    self.ol_model.addItem(f"{name} ({size}GB)", name)

    def _build_timers(self) -> None:
        self.timer = QTimer()
        self.timer.timeout.connect(self._poll)
        self.timer.start(POLL_MS)
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._poll()

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
                yahoo = self.api.get(f"/api/v1/market/yahoo/{symbol}")
                if yahoo and yahoo.get("price"):
                    last = yahoo["price"]
                    prev = yahoo.get("prev_close", last)
                    chg = ((last - prev) / prev * 100) if prev else 0
                    self.watchlist.item(row, 1).setText(f"{last:.2f}")
                    self.watchlist.item(row, 2).setText(f"{chg:+.2f}%")
                    color = C_GREEN if chg >= 0 else C_RED
                    self.watchlist.item(row, 2).setForeground(QColor(color))

    def _update_clock(self) -> None:
        self.clock_label.setText(QTime.currentTime().toString("hh:mm:ss"))


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
