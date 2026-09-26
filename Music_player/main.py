# main.py
#!/usr/bin/env python3
import os
import sys
import locale

print("[DEBUG] step 1: start", flush=True)

import version
print("[DEBUG] step 2: version imported", flush=True)

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")
print("[DEBUG] step 3: env set", flush=True)

from PyQt6.QtWidgets import QApplication
print("[DEBUG] step 4: QApplication imported", flush=True)

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont
print("[DEBUG] step 5: QtCore/QtGui imported", flush=True)

from language import i18n
print("[DEBUG] step 6: i18n imported", flush=True)

from utils.theme_loader import load_stylesheet, detect_system_theme
print("[DEBUG] step 7: theme_loader imported", flush=True)


def main():
    print("[DEBUG] step 8: main() entered", flush=True)

    settings = QSettings("netease_downloader", "settings")
    saved_lang = settings.value("lang", "")
    if saved_lang in ("zh_cn", "en_us"):
        i18n.set_lang(saved_lang)
    else:
        system_lang = locale.getlocale()[0]
        if system_lang and ('English' in system_lang or 'en_' in system_lang):
            i18n.set_lang('en_us')
        else:
            i18n.set_lang('zh_cn')
    print("[DEBUG] step 9: lang set", flush=True)

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    print("[DEBUG] step 10: AA_ShareOpenGLContexts set", flush=True)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    print("[DEBUG] step 11: highdpi set", flush=True)

    app = QApplication(sys.argv)
    print("[DEBUG] step 12: QApplication created", flush=True)

    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    print("[DEBUG] step 13: font set", flush=True)

    theme_pref = settings.value("theme", "system")
    if theme_pref == "system":
        actual_theme = detect_system_theme(app)
    else:
        actual_theme = theme_pref
    print(f"[DEBUG] step 14: theme detected = {actual_theme}", flush=True)

    stylesheet = load_stylesheet(actual_theme)
    if stylesheet:
        app.setStyleSheet(stylesheet)
        print(f"[DEBUG] step 15: stylesheet loaded", flush=True)

    from ui.main_window import MainWindow
    print("[DEBUG] step 16: MainWindow imported", flush=True)

    window = MainWindow()
    print("[DEBUG] step 17: MainWindow created", flush=True)

    window.show()
    print("[DEBUG] step 18: window shown", flush=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    print(version.version, flush=True)
    print(version.build_date, flush=True)
    main()