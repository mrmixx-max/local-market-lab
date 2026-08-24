"""Local Market Lab — Windows App Entry Point."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API_URL = "http://127.0.0.1:8322"


def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.WindowText, QColor(255, 160, 40))
    p.setColor(QPalette.ColorRole.Base, QColor(10, 10, 10))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(20, 20, 20))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 160, 40))
    p.setColor(QPalette.ColorRole.Text, QColor(255, 160, 40))
    p.setColor(QPalette.ColorRole.Button, QColor(30, 30, 30))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(255, 160, 40))
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link, QColor(255, 160, 40))
    p.setColor(QPalette.ColorRole.Highlight, QColor(255, 160, 40))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    return p


def _check_api() -> bool:
    """Check if the API is reachable."""
    try:
        import requests
        r = requests.get(f"{API_URL}/api/v1/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def main():
    app = QApplication(sys.argv)
    app.setPalette(_dark_palette())
    app.setFont(QFont("Consolas", 10))
    app.setStyleSheet("""
        QMainWindow, QDialog { background: #000; color: #FFA028; }
        QTabWidget::pane { border: 1px solid #333; }
        QTabBar::tab { background: #1a1a1a; color: #8a5a1a; padding: 8px 16px; }
        QTabBar::tab:selected { background: #000; color: #FFA028; border-bottom: 2px solid #FFA028; }
        QTableWidget { background: #0a0a0a; gridline-color: #222; }
        QHeaderView::section { background: #141414; color: #FFA028; padding: 4px; }
        QPushButton { background: #1a1a1a; border: 1px solid #333; padding: 6px 12px; }
        QPushButton:hover { border-color: #FFA028; }
        QComboBox, QSpinBox { background: #000; border: 1px solid #333; padding: 4px; }
        QStatusBar { background: #141414; color: #8a5a1a; }
    """)

    # splash
    splash_widget = QWidget()
    splash_widget.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
    splash_widget.setStyleSheet("background: #000;")
    layout = QVBoxLayout(splash_widget)
    label = QLabel("◆ LOCAL MARKET LAB")
    label.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
    label.setStyleSheet("color: #FFA028;")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    sub = QLabel("Loading...")
    sub.setFont(QFont("Consolas", 12))
    sub.setStyleSheet("color: #8a5a1a;")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(sub)
    splash_widget.setFixedSize(400, 200)
    splash_widget.show()
    app.processEvents()

    api_ok = _check_api()

    from windows.src.main_window import MainWindow
    window = MainWindow(api_online=api_ok)
    window.show()
    splash_widget.close()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
