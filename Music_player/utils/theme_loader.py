# utils/theme_loader.py

import os
import sys
from pathlib import Path

from PyQt6.QtGui import QPalette


ALLOWED_THEMES = ("dark", "light")


def _resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)

    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def load_stylesheet(theme: str) -> str:
    if theme not in ALLOWED_THEMES:
        print(f"[Theme] Warning: unknown theme '{theme}', falling back to dark")
        theme = "dark"

    root = _resource_root()

    candidates = [
        root / "resources" / "themes" / f"{theme}.qss",
        root / f"{theme}.qss",
    ]

    for qss_path in candidates:
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                return f.read()

    print(f"[Theme] Warning: {theme}.qss not found under {root}")
    return ""


def detect_system_theme(app) -> str:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")

            return "light" if value else "dark"
        except Exception:
            pass

    pal = app.palette()
    lightness = pal.color(QPalette.ColorRole.Window).lightnessF()
    return "dark" if lightness < 0.5 else "light"