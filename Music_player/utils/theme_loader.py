# utils/theme_loader.py
import os
import sys
from pathlib import Path
from PyQt6.QtGui import QPalette


def load_stylesheet(theme: str) -> str:
    if getattr(sys, 'frozen', False):
        qss_path = os.path.join(sys._MEIPASS, "resources", "themes", f"{theme}.qss")
    else:
        base_dir = Path(__file__).parent.parent
        qss_path = base_dir / f"{theme}.qss"
        if not qss_path.exists():
            qss_path = base_dir / "resources" / "themes" / f"{theme}.qss"
        qss_path = str(qss_path)

    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()

    print(f"[Theme] Warning: {qss_path} not found")
    return ""


def detect_system_theme(app) -> str:
    pal = app.palette()
    lightness = pal.color(QPalette.ColorRole.Window).lightnessF()
    return "dark" if lightness < 0.5 else "light"