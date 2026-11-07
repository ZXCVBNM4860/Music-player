# main.py
# #!/usr/bin/env python3

import locale
import os
import sys
import ctypes

def _ensure_std_streams():
    try:
        from utils.helpers import LOG_PATH
    except Exception:
        return

    if sys.stdout is None:
        try:
            sys.stdout = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        except Exception:
            pass

    if sys.stderr is None:
        try:
            sys.stderr = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        except Exception:
            pass

def _disable_sandbox_when_elevated():
    if sys.platform != "win32":
        return
    try:
        elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return
    if not elevated:
        return
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--no-sandbox" not in flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{flags} --no-sandbox".strip()
    try:
        from utils.helpers import log_line
        log_line("[Startup] running elevated, Chromium sandbox disabled")
    except Exception:
        pass

_ensure_std_streams()
_disable_sandbox_when_elevated()

if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MusicPlayer.App")
    except Exception:
        pass

DEBUG = os.environ.get("NETEASE_DEBUG", "").lower() in ("1", "true", "yes", "on")

def debug(msg):
    if not DEBUG:
        return
    try:
        print(f"[DEBUG] {msg}", flush=True)
    except Exception:
        pass

debug("step 1: start")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")
debug("step 2: env set")

import version
from language import i18n
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import QApplication
from utils.theme_loader import load_stylesheet, detect_system_theme

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
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    else:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
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

def run_main_app():
    debug("step 7: main_app() entered")
    settings = QSettings("netease_downloader", "settings")
    load_language(settings)
    gpu_enabled = read_gpu_setting(settings)
    app = create_application(gpu_enabled)
    apply_theme(app, settings)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

def run_standalone_player():
    api_url = "http://localhost:3000"
    for arg in sys.argv:
        if arg.startswith("--api="):
            api_url = arg.split("=", 1)[1]
            break

    settings = QSettings("netease_downloader", "settings")
    load_language(settings)
    gpu_enabled = read_gpu_setting(settings)
    app = create_application(gpu_enabled)
    apply_theme(app, settings)

    from ui.local_player import LocalPlayerWindow
    window = LocalPlayerWindow(None, api_url=api_url)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    if "--player" in sys.argv:
        run_standalone_player()
    else:
        run_main_app()