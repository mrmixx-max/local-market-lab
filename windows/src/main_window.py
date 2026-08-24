"""Local Market Lab — Windows Desktop Main Window.
Bloomberg-terminal style PyQt6 GUI with tabs, sidebar watchlist,
top bar, status bar, dark theme, and live REST polling.
"""
from __future__ import annotations

import sys

import requests
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

# ------------------------------------------------------------------ constants
API_BASE = "http://127.0.0.1:8322"
API_TIMEOUT = 5
POLL_MS = 3000
C_BG, C_AMBER, C_DIM = "#000000", "#FFA028", "#555555"
C_GREEN, C_RED, C_WHITE = "#00CC66", "#FF3344", "#EEEEEE"
FONT = "Consolas"

STYLESHEET = f"""
QMainWindow {{ background: {C_BG}; color: {C_WHITE}; }}
QWidget {{ background: {C_BG}; color: {C_WHITE}; font-family: "{FONT}"; font-size: 14px; }}
QTabWidget::pane {{ border: 1px solid {C_DIM}; }}
QTabBar::tab {{ background: #111; color: {C_DIM}; padding: 10px 20px; font-size: 14px;
               border: 1px solid {C_DIM}; border-bottom: none; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {C_BG}; color: {C_AMBER}; border-color: {C_AMBER}; }}
QTableWidget {{ background: #0A0A0A; color: {C_WHITE}; gridline-color: #222; font-size: 13px;
               border: none; font-family: "{FONT}"; }}
QTableWidget::item:selected {{ background: #1a1a00; color: {C_AMBER}; }}
QHeaderView::section {{ background: #111; color: {C_AMBER}; border: 1px solid {C_DIM};
                       padding: 6px; font-weight: bold; font-size: 13px; }}
QStatusBar {{ background: #080808; color: {C_DIM}; font-size: 12px; }}
QPushButton {{ background: #111; color: {C_AMBER}; border: 1px solid {C_AMBER};
              padding: 8px 18px; font-size: 14px; font-weight: bold; }}
QPushButton:hover {{ background: #221100; }}
QPushButton:pressed {{ background: {C_AMBER}; color: {C_BG}; }}
"""


class ApiClient:
    """Thin REST client for the LML backend."""

    def __init__(self, base_url: str = API_BASE, timeout: int = API_TIMEOUT):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def get(self, path: str, **kwargs) -> dict | list | None:
        try:
            r = self.session.get(f"{self.base}{path}", timeout=self.timeout, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def health(self) -> dict | None:
        return self.get("/api/v1/health")

    def symbols(self) -> list[dict] | None:
        return self.get("/api/v1/market/symbols")

    def prices(self, symbol: str) -> dict | None:
        return self.get(f"/api/v1/market/prices/{symbol}")


class MainWindow(QMainWindow):
    """LML Windows main window — terminal-style multi-tab dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.api = ApiClient()
        self.setWindowTitle("Local Market Lab — Terminal")
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)
        self._symbols: list[str] = []
        self._last_prices: dict[str, float] = {}
        self._prev_prices: dict[str, float] = {}
        # Window Icon
        from PyQt6.QtGui import QIcon
        icon_path = str(Path(__file__).parent.parent.parent / "lml-icon.ico")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))
        self._build_ui()
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
        for label, title in [
            ("Markets — live quotes & charts", "Markets"),
            ("Backtest — strategy engine", "Backtest"),
            ("Scenarios — Monte Carlo sim", "Scenarios"),
            ("Game — trading simulator", "Game"),
            ("Ollama — local LLM assistant", "Ollama"),
            ("Risk — VaR / CVaR analytics", "Risk"),
        ]:
            self.tabs.addTab(self._placeholder(label), title)
        main.addWidget(self.tabs, 1)
        mw = QWidget()
        mw.setLayout(main)
        root.addWidget(mw, 1)
        self.setStatusBar(self._build_statusbar())

    def _build_sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(220)
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
        bar.addSpacing(10)
        self.refresh_btn = QPushButton("↻ Refresh")
        self.refresh_btn.clicked.connect(self._poll)
        bar.addWidget(self.refresh_btn)
        w = QWidget()
        w.setLayout(bar)
        w.setStyleSheet(f"QWidget {{ border-bottom: 1px solid {C_DIM}; }}")
        return w

    def _build_statusbar(self) -> QStatusBar:
        sb = QStatusBar()
        sb.showMessage(
            "⚠ FOR EDUCATIONAL PURPOSES ONLY — NOT FINANCIAL ADVICE — "
            "PAST PERFORMANCE ≠ FUTURE RESULTS"
        )
        return sb

    def _placeholder(self, text: str) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C_DIM}; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(lbl)
        return w

    def _build_timers(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(POLL_MS)
        QTimer.singleShot(0, self._poll)

    def _update_clock(self) -> None:
        self.clock_label.setText(QTime.currentTime().toString("hh:mm:ss"))

    def _poll(self) -> None:
        health = self.api.health()
        if health and health.get("status") in ("ok", "degraded"):
            self.conn_label.setText(f"● LIVE  v{health.get('version', '?')}")
            self.conn_label.setStyleSheet(f"color: {C_GREEN};")
        else:
            self.conn_label.setText("● DISCONNECTED")
            self.conn_label.setStyleSheet(f"color: {C_RED};")
        sym_data = self.api.symbols()
        if sym_data:
            self._symbols = [s["symbol"] for s in sym_data]
            self._refresh_watchlist()

    def _refresh_watchlist(self) -> None:
        self.watchlist.setRowCount(len(self._symbols))
        for row, sym in enumerate(self._symbols):
            prev = self._last_prices.get(sym)
            data = self.api.prices(sym)
            last = data["bars"][-1]["close"] if data and data.get("bars") else 0.0
            self._prev_prices[sym] = prev if prev is not None else last
            self._last_prices[sym] = last
            i_sym = QTableWidgetItem(sym)
            i_sym.setForeground(QColor(C_AMBER))
            self.watchlist.setItem(row, 0, i_sym)
            i_last = QTableWidgetItem(f"{last:,.2f}")
            i_last.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            i_last.setForeground(QColor(C_WHITE))
            self.watchlist.setItem(row, 1, i_last)
            chg_color, chg_text = C_DIM, "0.00%"
            if prev and prev > 0:
                chg = (last - prev) / prev * 100
                chg_text = f"{chg:+.2f}%"
                chg_color = C_GREEN if chg >= 0 else C_RED
            i_chg = QTableWidgetItem(chg_text)
            i_chg.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            i_chg.setForeground(QColor(chg_color))
            self.watchlist.setItem(row, 2, i_chg)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
