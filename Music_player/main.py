#!/usr/bin/env python3
"""主程序入口"""

import os
import sys
import locale

import version

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont, QPalette
from ui.main_window import MainWindow
from language import i18n


def load_stylesheet(theme: str) -> str:
    """从 resources/themes/ 加载 .qss 文件"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(base_dir, "resources", "themes", f"{theme}.qss")
    
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def detect_system_theme(app: QApplication) -> str:
    """检测系统主题是暗色还是亮色"""
    pal = app.palette()
    color = pal.color(QPalette.ColorRole.Window)
    r, g, b, _ = color.getRgb()
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "dark" if luminance < 0.5 else "light"


def main():
    # 语言设置
    settings = QSettings("Music_player", "settings")
    saved_lang = settings.value("lang", "")
    if saved_lang in ("zh_cn", "en_us"):
        i18n.set_lang(saved_lang)
    else:
        system_lang = locale.getlocale()[0]
        if system_lang and ('English' in system_lang or 'en_' in system_lang):
            i18n.set_lang('en_us')
        else:
            i18n.set_lang('zh_cn')
    
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # 主题加载
    theme_pref = settings.value("theme", "system")
    if theme_pref == "system":
        actual_theme = detect_system_theme(app)
    else:
        actual_theme = theme_pref
    
    stylesheet = load_stylesheet(actual_theme)
    if stylesheet:
        app.setStyleSheet(stylesheet)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    print(version.version)
    print(version.build_date)
    main()