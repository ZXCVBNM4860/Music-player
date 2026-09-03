"""主题加载与系统主题检测工具"""

import os
import sys
from pathlib import Path
from PyQt6.QtGui import QPalette


def load_stylesheet(theme: str) -> str:
    """加载指定主题的 QSS 样式表"""
    # 确定基础目录
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
        qss_path = os.path.join(base_dir, "resources", "themes", f"{theme}.qss")
    else:
        # 开发环境：从项目根目录查找
        base_dir = Path(__file__).parent.parent
        qss_path = base_dir / f"{theme}.qss"
        if not qss_path.exists():
            # 后备：尝试 resources/themes/ 目录
            qss_path = base_dir / "resources" / "themes" / f"{theme}.qss"
        qss_path = str(qss_path)
    
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    
    print(f"[Theme] Warning: {qss_path} not found")
    return ""


def detect_system_theme(app) -> str:
    """检测系统主题是暗色还是亮色"""
    pal = app.palette()
    # 使用 lightnessF() 直接获取亮度值（0.0 ~ 1.0）
    lightness = pal.color(QPalette.ColorRole.Window).lightnessF()
    return "dark" if lightness < 0.5 else "light"
