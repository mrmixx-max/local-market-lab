"""Dashboard-Widgets: MetricsPanel, PositionsTable, OrderEntry, GamePanel, OllamaChat."""

from __future__ import annotations
from typing import Any
import requests
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

API = "http://127.0.0.1:8322/api/v1"


def _get(path: str, **kw: Any) -> dict | list:
    try:
        r = requests.get(f"{API}{path}", timeout=5, **kw)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _post(path: str, payload: dict | None = None) -> dict:
    try:
        r = requests.post(f"{API}{path}", json=payload or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _fmt(val: float | None, suffix: str = "", digits: int = 2) -> str:
    return "—" if val is None else f"{val:,.{digits}f}{suffix}"


def _color(val: float | None):
    return (
        None
        if val is None
        else (Qt.GlobalColor.darkGreen if val >= 0 else Qt.GlobalColor.red)
    )


class MetricsPanel(QFrame):
    KEYS = [
        "total_value",
        "unrealized_pl",
        "volatility_pct",
        "max_drawdown_pct",
        "var_95",
        "sharpe",
    ]
    LABELS = [
        ("Value", " €"),
        ("P/L", " €"),
        ("Vol", "%"),
        ("MaxDD", "%"),
        ("VaR", " €"),
        ("Sharpe", ""),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tiles: dict[str, QLabel] = {}
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 8)
        grid = QGridLayout()
        for i, (lbl, _) in enumerate(self.LABELS):
            box = QGroupBox(lbl)
            bl = QVBoxLayout(box)
            vl = QLabel("—")
            vl.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
            bl.addWidget(vl)
            grid.addWidget(box, i // 3, i % 3)
            self._tiles[lbl] = vl
        lo.addLayout(grid)
        btn = QPushButton("↻ Refresh")
        btn.clicked.connect(self.refresh)
        lo.addWidget(btn)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5_000)

    def refresh(self) -> None:
        d = _get("/portfolio/default")
        if d:
            for (lbl, sfx), key in zip(self.LABELS, self.KEYS):
                self._tiles[lbl].setText(_fmt(d.get(key), sfx))


class PositionsTable(QFrame):
    HEADERS = ["Symbol", "Qty", "Avg Cost", "Last", "P/L", "P/L %"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 8)
        self._tbl = QTableWidget(0, len(self.HEADERS))
        self._tbl.setHorizontalHeaderLabels(self.HEADERS)
        self._tbl.setAlternatingRowColors(True)
        lo.addWidget(self._tbl)
        row = QHBoxLayout()
        btn = QPushButton("↻ Refresh")
        btn.clicked.connect(self.refresh)
        row.addWidget(btn)
        row.addStretch()
        lo.addLayout(row)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5_000)

    def refresh(self) -> None:
        d = _get("/portfolio/default")
        if not d:
            return
        pos = d.get("positions", [])
        self._tbl.setRowCount(len(pos))
        for r, p in enumerate(pos):
            vals = [
                p.get("symbol", ""),
                _fmt(p.get("quantity"), "", 4),
                _fmt(p.get("avg_cost"), " €"),
                _fmt(p.get("last_price"), " €"),
                _fmt(p.get("pl"), " €"),
                _fmt(p.get("pl_pct"), "%"),
            ]
            for c, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                if c in (4, 5):
                    v = p.get("pl", 0) if c == 4 else p.get("pl_pct")
                    col = _color(v)
                    if col:
                        it.setForeground(col)
                self._tbl.setItem(r, c, it)
        self._tbl.resizeColumnsToContents()


class OrderEntry(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 8)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Symbol:"))
        self._cb = QComboBox()
        self._cb.setMinimumWidth(120)
        r1.addWidget(self._cb)
        lo.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Qty:"))
        self._sp = QSpinBox()
        self._sp.setRange(1, 1_000_000)
        self._sp.setValue(10)
        r2.addWidget(self._sp)
        lo.addLayout(r2)
        r3 = QHBoxLayout()
        self._buy = QPushButton("BUY")
        self._buy.setStyleSheet("background:#2d7d2d;color:#fff;font-weight:bold;")
        self._buy.clicked.connect(lambda: self._order("buy"))
        self._sell = QPushButton("SELL")
        self._sell.setStyleSheet("background:#7d2d2d;color:#fff;font-weight:bold;")
        self._sell.clicked.connect(lambda: self._order("sell"))
        r3.addWidget(self._buy)
        r3.addWidget(self._sell)
        lo.addLayout(r3)
        self._status = QLabel("")
        lo.addWidget(self._status)
        lo.addStretch()
        syms = _get("/market/symbols")
        if isinstance(syms, list):
            for s in syms:
                self._cb.addItem(s.get("symbol", ""))

    def _order(self, side: str) -> None:
        sym = self._cb.currentText()
        if not sym:
            self._status.setText("⚠ Kein Symbol.")
            return
        self._status.setText(
            f"ℹ {side.upper()} {self._sp.value()} {sym} (Game erforderlich)"
        )


class GamePanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._game_id: str | None = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 8)
        ch = QGroupBox("Challenges")
        cl = QVBoxLayout(ch)
        self._ch_list = QListWidget()
        cl.addWidget(self._ch_list)
        lo.addWidget(ch)
        lb = QGroupBox("Leaderboard")
        ll = QVBoxLayout(lb)
        self._lb_list = QListWidget()
        ll.addWidget(self._lb_list)
        lo.addWidget(lb)
        ar = QGroupBox("Auto-Run")
        al = QHBoxLayout(ar)
        self._btn_create = QPushButton("Create Game")
        self._btn_create.clicked.connect(self._create)
        self._btn_tick = QPushButton("Tick ▶")
        self._btn_tick.clicked.connect(self._tick)
        self._btn_tick.setEnabled(False)
        self._auto = QComboBox()
        self._auto.addItems(["Off", "1s", "3s", "5s"])
        self._auto.currentTextChanged.connect(self._on_auto)
        al.addWidget(self._btn_create)
        al.addWidget(self._btn_tick)
        al.addWidget(QLabel("Auto:"))
        al.addWidget(self._auto)
        lo.addWidget(ar)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(8_000)

    def _create(self) -> None:
        r = _post(
            "/game/create",
            {
                "player": "trader",
                "symbols": ["IWDA", "EIMI", "AGGH"],
                "days": 63,
                "challenge": "beat_market",
            },
        )
        if r and "game_id" in r:
            self._game_id = r["game_id"]
            self._btn_tick.setEnabled(True)

    def _tick(self) -> None:
        if self._game_id:
            _post(f"/game/{self._game_id}/tick")

    def _on_auto(self, text: str) -> None:
        if text == "Off":
            self._timer.stop()
        else:
            self._timer.setInterval(int(text.replace("s", "")) * 1000)
            if not self._timer.isActive():
                self._timer.start()

    def refresh(self) -> None:
        self._ch_list.clear()
        chs = _get("/game/challenges")
        if isinstance(chs, list):
            for c in chs:
                self._ch_list.addItem(
                    f"{c.get('name', c.get('challenge', ''))}: {c.get('description', '')}"
                )
        self._lb_list.clear()
        lb = _get("/game/leaderboard")
        if isinstance(lb, list):
            for e in lb[:10]:
                self._lb_list.addItem(
                    f"{e.get('player', '?')}: {e.get('score', 0):.2f} ({e.get('status', '')})"
                )
        if self._game_id and self._auto.currentText() != "Off":
            self._tick()


class OllamaChat(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Model:"))
        self._cb = QComboBox()
        self._cb.setMinimumWidth(180)
        top.addWidget(self._cb)
        btn_r = QPushButton("↻")
        btn_r.setFixedWidth(30)
        btn_r.clicked.connect(self._load_models)
        top.addWidget(btn_r)
        top.addStretch()
        lo.addLayout(top)
        self._view = QTextEdit()
        self._view.setReadOnly(True)
        lo.addWidget(self._view)
        inp = QHBoxLayout()
        self._inp = QLineEdit()
        self._inp.setPlaceholderText("Nachricht …")
        self._inp.returnPressed.connect(self._send)
        inp.addWidget(self._inp)
        btn_s = QPushButton("Send")
        btn_s.clicked.connect(self._send)
        inp.addWidget(btn_s)
        lo.addLayout(inp)
        self._load_models()

    def _load_models(self) -> None:
        self._cb.clear()
        d = _get("/ollama/models")
        models = d.get("models", []) if isinstance(d, dict) else []
        for m in models:
            self._cb.addItem(
                f"{m.get('model', '')} ({m.get('size_gb', 0)} GB)", m.get("model", "")
            )
        if not models:
            self._cb.addItem("— keine Modelle —", "")

    def _send(self) -> None:
        text = self._inp.text().strip()
        model = self._cb.currentData()
        if not text or not model:
            return
        self._view.append(f"<b>Du:</b> {text}")
        self._inp.clear()
        self._view.append("<i>⏳ Denke nach …</i>")
        r = _post(
            "/ollama/chat",
            {
                "model": model,
                "messages": [{"role": "user", "content": text}],
                "temperature": 0.4,
            },
        )
        content = (
            r.get("content", "[Keine Antwort]") if isinstance(r, dict) else "[Fehler]"
        )
        self._view.append(f"<b>Ollama:</b>{content}")
        self._view.verticalScrollBar().setValue(
            self._view.verticalScrollBar().maximum()
        )


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QTabWidget

    app = QApplication(sys.argv)
    tw = QTabWidget()
    tw.addTab(MetricsPanel(), "📊 Metrics")
    tw.addTab(PositionsTable(), "📋 Positions")
    tw.addTab(OrderEntry(), "💹 Order")
    tw.addTab(GamePanel(), "🎮 Game")
    tw.addTab(OllamaChat(), "🤖 Ollama")
    tw.setWindowTitle("Local Market Lab — Dashboard")
    tw.resize(720, 520)
    tw.show()
    sys.exit(app.exec())
