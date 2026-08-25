"""Bloomberg-style chart widgets for Local Market Lab.

All charts share a dark theme (black background, amber accents, monospace
labels) and are built on top of pyqtgraph / PyQt6.

Widgets
-------
- CandlestickChart : OHLC bars with crosshair
- LineChart        : Multi-series equity curves with drawdown shading
- HistogramChart   : Monte-Carlo terminal-value distribution
- DrawdownChart    : Drawdown curve over time
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

# ---------------------------------------------------------------------------
# Theme constants (Bloomberg terminal aesthetic)
# ---------------------------------------------------------------------------
BG = QColor(0, 0, 0)
GRID = QColor(40, 40, 40)
AMBER = QColor(255, 176, 0)
AMBER_DIM = QColor(180, 120, 0)
GREEN = QColor(0, 200, 80)
RED = QColor(220, 40, 40)
WHITE = QColor(230, 230, 230)
GRAY = QColor(140, 140, 140)
FONT = QFont("Consolas", 9)
FONT_BOLD = QFont("Consolas", 10, QFont.Weight.Bold)


def _apply_theme(plot: pg.PlotWidget, title: str) -> None:
    """Apply the Bloomberg dark theme to a PlotWidget."""
    plot.setBackground(BG)
    plot.showGrid(x=True, y=True, alpha=0.15)
    plot.getPlotItem().getViewBox().setBackgroundColor(BG)
    for axis_name in ("left", "bottom"):
        axis = plot.getPlotItem().getAxis(axis_name)
        axis.setPen(AMBER_DIM)
        axis.setTextPen(GRAY)
        axis.setTickFont(FONT)
    plot.setTitle(title, color=AMBER, size="11pt")


def _add_crosshair(
    plot: pg.PlotWidget,
) -> tuple[pg.InfiniteLine, pg.InfiniteLine, pg.TextItem]:
    """Attach a crosshair (vline + hline + label) that follows the cursor."""
    vb = plot.getPlotItem().getViewBox()
    vline = pg.InfiniteLine(
        angle=90, pen=pg.mkPen(AMBER, width=1, style=Qt.PenStyle.DashLine)
    )
    hline = pg.InfiniteLine(
        angle=0, pen=pg.mkPen(AMBER, width=1, style=Qt.PenStyle.DashLine)
    )
    label = pg.TextItem("", color=AMBER, anchor=(0, 1))
    label.setFont(FONT)
    label.setZValue(10)
    vline.setVisible(False)
    hline.setVisible(False)
    label.setVisible(False)
    vb.addItem(vline, ignoreBounds=True)
    vb.addItem(hline, ignoreBounds=True)
    vb.addItem(label, ignoreBounds=False)

    def _on_mouse_move(pos):
        if plot.sceneBoundingRect().contains(pos):
            mouse_pt = vb.mapSceneToView(pos)
            vline.setPos(mouse_pt.x())
            hline.setPos(mouse_pt.y())
            label.setText(f"  {mouse_pt.y():,.2f}")
            label.setPos(mouse_pt.x(), mouse_pt.y())
            vline.setVisible(True)
            hline.setVisible(True)
            label.setVisible(True)
        else:
            vline.setVisible(False)
            hline.setVisible(False)
            label.setVisible(False)

    plot.scene().sigMouseMoved.connect(_on_mouse_move)
    return vline, hline, label


# ---------------------------------------------------------------------------
# 1. CandlestickChart
# ---------------------------------------------------------------------------
class CandlestickChart(pg.PlotWidget):
    """OHLC candlestick chart with crosshair.

    Parameters
    ----------
    dates : list[float]  – x-axis positions (e.g. range index or epoch)
    open_  : list[float]
    high   : list[float]
    low    : list[float]
    close  : list[float]
    """

    def __init__(self, dates, open_, high, low, close, title: str = "PRICE"):
        super().__init__()
        _apply_theme(self, title)
        self._dates = dates
        self._open = open_
        self._high = high
        self._low = low
        self._close = close
        self._plot_candles()
        _add_crosshair(self)

    def _plot_candles(self) -> None:
        w = 0.4
        for i, (o, h, l, c) in enumerate(
            zip(self._open, self._high, self._low, self._close)
        ):
            color = GREEN if c >= o else RED
            pen = pg.mkPen(color, width=1)
            # wick (high-low)
            self.plot([i, i], [l, h], pen=pen)
            # body (open-close)
            body_low, body_high = sorted((o, c))
            bar = pg.BarGraphItem(
                x=[i],
                height=[body_high - body_low],
                width=w,
                y0=body_low,
                pen=pen,
                brush=color,
            )
            self.addItem(bar)


# ---------------------------------------------------------------------------
# 2. LineChart
# ---------------------------------------------------------------------------
class LineChart(pg.PlotWidget):
    """Multi-series line chart with legend and optional drawdown shading.

    Parameters
    ----------
    x          : list[float]            – shared x-axis
    series     : dict[str, list[float]] – label → y-values
    drawdown   : list[float] | None     – drawdown series (0 → -max_dd) for shading
    title      : str
    """

    COLORS = [
        AMBER,
        QColor(0, 180, 255),
        QColor(200, 120, 255),
        QColor(0, 220, 180),
        QColor(255, 100, 100),
    ]

    def __init__(self, x, series: dict, title: str = "EQUITY", drawdown=None):
        super().__init__()
        _apply_theme(self, title)
        self._x = x
        self._series = series
        self._drawdown = drawdown
        self._plot()
        _add_crosshair(self)

    def _plot(self) -> None:
        legend = self.addLegend(offset=(10, 10))
        legend.setFont(FONT)
        legend.setLabelTextColor(WHITE)

        # drawdown shading (fill between curve and peak)
        if self._drawdown is not None:
            peak = [0.0] * len(self._drawdown)
            bg_region = pg.FillBetweenItem(
                pg.PlotDataItem(self._x, self._drawdown, pen=pg.mkPen(RED, width=1)),
                pg.PlotDataItem(self._x, peak, pen=pg.mkPen(RED, width=0)),
                brush=pg.mkBrush(QColor(220, 40, 40, 60)),
            )
            self.addItem(bg_region)

        for idx, (label, y) in enumerate(self._series.items()):
            color = self.COLORS[idx % len(self.COLORS)]
            pen = pg.mkPen(color, width=2)
            self.plot(self._x, y, pen=pen, name=label)


# ---------------------------------------------------------------------------
# 3. HistogramChart
# ---------------------------------------------------------------------------
class HistogramChart(pg.PlotWidget):
    """Monte-Carlo terminal-value distribution histogram.

    Parameters
    ----------
    values  : list[float]  – simulated terminal values
    bins    : int          – number of histogram bins
    title   : str
    """

    def __init__(self, values, bins: int = 60, title: str = "MC DISTRIBUTION"):
        super().__init__()
        _apply_theme(self, title)
        self._values = values
        self._bins = bins
        self._plot()
        _add_crosshair(self)

    def _plot(self) -> None:
        y, x = pg.np.histogram(self._values, bins=self._bins)
        x_centers = [(x[i] + x[i + 1]) / 2 for i in range(len(x) - 1)]
        width = (x[1] - x[0]) * 0.95

        # color bars by position relative to median
        median = sorted(self._values)[len(self._values) // 2]
        for xi, yi in zip(x_centers, y):
            color = GREEN if xi >= median else RED
            bar = pg.BarGraphItem(
                x=[xi],
                height=[yi],
                width=width,
                pen=pg.mkPen(color, width=1),
                brush=color,
            )
            self.addItem(bar)

        # median line
        med_line = pg.InfiniteLine(
            angle=90,
            pos=median,
            pen=pg.mkPen(AMBER, width=2, style=Qt.PenStyle.DashLine),
        )
        self.addItem(med_line)
        med_label = pg.TextItem(f"  median: {median:,.0f}", color=AMBER, anchor=(0, 1))
        med_label.setFont(FONT_BOLD)
        med_label.setPos(median, max(y) * 0.95)
        self.addItem(med_label)


# ---------------------------------------------------------------------------
# 4. DrawdownChart
# ---------------------------------------------------------------------------
class DrawdownChart(pg.PlotWidget):
    """Drawdown curve over time with filled area.

    Parameters
    ----------
    x        : list[float]  – time axis
    drawdown : list[float]  – drawdown values (0 = peak, negative = dd)
    title    : str
    """

    def __init__(self, x, drawdown, title: str = "DRAWDOWN"):
        super().__init__()
        _apply_theme(self, title)
        self._x = x
        self._dd = drawdown
        self._plot()
        _add_crosshair(self)

    def _plot(self) -> None:
        zero_line = [0.0] * len(self._x)
        pen = pg.mkPen(RED, width=2)
        fill = pg.FillBetweenItem(
            pg.PlotDataItem(self._x, self._dd, pen=pen),
            pg.PlotDataItem(self._x, zero_line, pen=pg.mkPen(RED, width=0)),
            brush=pg.mkBrush(QColor(220, 40, 40, 80)),
        )
        self.addItem(fill)
        self.plot(self._x, self._dd, pen=pen)

        # annotate max drawdown
        min_idx = min(range(len(self._dd)), key=lambda i: self._dd[i])
        max_dd = self._dd[min_idx]
        dd_label = pg.TextItem(f"  max: {max_dd:.1%}", color=AMBER, anchor=(0, 1))
        dd_label.setFont(FONT_BOLD)
        dd_label.setPos(self._x[min_idx], max_dd)
        self.addItem(dd_label)


# ---------------------------------------------------------------------------
# Demo / smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import numpy as np
    from PyQt6.QtWidgets import QApplication, QGridLayout, QWidget

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("LML Charts — Bloomberg Style")
    window.resize(1200, 800)
    layout = QGridLayout(window)

    # --- CandlestickChart ---
    n = 60
    rng = np.random.default_rng(42)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    opens = base + rng.normal(0, 0.3, n)
    closes = base + rng.normal(0, 0.3, n)
    highs = np.maximum(opens, closes) + rng.uniform(0.5, 2.0, n)
    lows = np.minimum(opens, closes) - rng.uniform(0.5, 2.0, n)
    layout.addWidget(CandlestickChart(list(range(n)), opens, highs, lows, closes), 0, 0)

    # --- LineChart ---
    x = list(range(n))
    s1 = np.cumprod(1 + rng.normal(0.001, 0.02, n)) * 100000
    s2 = np.cumprod(1 + rng.normal(0.0005, 0.015, n)) * 100000
    peak = np.maximum.accumulate(s1)
    dd = (s1 - peak) / peak
    layout.addWidget(LineChart(x, {"Strategy": s1, "Benchmark": s2}, drawdown=dd), 0, 1)

    # --- HistogramChart ---
    mc_values = rng.normal(100000, 15000, 5000)
    layout.addWidget(HistogramChart(mc_values), 1, 0)

    # --- DrawdownChart ---
    dd_series = np.minimum.accumulate(s1 / np.maximum.accumulate(s1) - 1)
    layout.addWidget(DrawdownChart(x, dd_series), 1, 1)

    window.show()
    sys.exit(app.exec())
