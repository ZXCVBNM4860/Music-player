#!/usr/bin/env python3

import locale
import os
import sys

DEBUG = os.environ.get("NETEASE_DEBUG", "").lower() in ("1", "true", "yes", "on")


def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", flush=True)


debug("step 1: start")

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")
debug("step 2: env set")

import version
debug("step 3: version imported")

from language import i18n
debug("step 4: i18n imported")

from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import QApplication
debug("step 5: PyQt6 imported")

from utils.theme_loader import load_stylesheet, detect_system_theme
debug("step 6: theme_loader imported")


def load_language(settings):
    saved = settings.value("lang", "")
    if saved in ("zh_cn", "en_us"):
        i18n.set_lang(saved)
        return

    system_lang = locale.getlocale()[0] or ""
    if system_lang.startswith("en") or "English" in system_lang:
        i18n.set_lang("en_us")
    else:
        i18n.set_lang("zh_cn")


def read_gpu_setting(settings) -> bool:
    raw = settings.value("gpu_acceleration", "true")
    return str(raw).lower() in ("1", "true", "yes", "on")


def create_application(gpu_enabled: bool):
    if gpu_enabled:
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True
        )
    else:
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True
        )

    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True
    )
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 9))
    return app


def apply_theme(app, settings):
    pref = settings.value("theme", "system")
    theme = detect_system_theme(app) if pref == "system" else pref

    stylesheet = load_stylesheet(theme)
    if stylesheet:
        app.setStyleSheet(stylesheet)

    return theme


def main():
    debug("step 7: main() entered")

    settings = QSettings("netease_downloader", "settings")
    load_language(settings)
    debug("step 8: lang set")

    gpu_enabled = read_gpu_setting(settings)
    debug(f"step 9: gpu acceleration = {gpu_enabled}")

    app = create_application(gpu_enabled)
    debug("step 10: QApplication created")

    theme = apply_theme(app, settings)
    debug(f"step 11: theme applied = {theme}")

    from ui.main_window import MainWindow
    debug("step 12: MainWindow imported")

    window = MainWindow()
    window.show()
    debug("step 13: window shown")

    sys.exit(app.exec())


if __name__ == "__main__":
    debug(f"version: {version.version}")
    debug(f"build_date: {version.build_date}")
    main()