"""主题加载与系统主题检测工具"""

import os
import sys
from PyQt6.QtGui import QPalette


def load_stylesheet(theme: str) -> str:
    """加载指定主题的 QSS 样式表"""
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    qss_path = os.path.join(base_dir, "resources", "themes", f"{theme}.qss")
    
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    
    print(f"[Theme] Warning: {qss_path} not found")
    return ""


def detect_system_theme(app) -> str:
    """检测系统主题是暗色还是亮色"""
    pal = app.palette()
    color = pal.color(QPalette.ColorRole.Window)
    r, g, b, _ = color.getRgb()
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "dark" if luminance < 0.5 else "light"