"""配置"""

class Config:
    DEFAULT_API_URL = "http://localhost:3000"
    DEFAULT_DOWNLOAD_PATH = "D:/音乐"
    TIMEOUT_API = 10
    TIMEOUT_DOWNLOAD = (5, 60)
    DOWNLOAD_DELAY = 0.8
    MAX_RETRY = 3
    UI_REFRESH_INTERVAL = 100
    MAX_LOG_LINES = 1000


class ThemeColors:
    BG_PRIMARY = "#0a0a0a"
    BG_SECONDARY = "#141414"
    BG_TERTIARY = "#1a1a1a"
    FG_PRIMARY = "#ffffff"
    FG_SECONDARY = "#e0e0e0"
    BORDER = "#333333"
    BORDER_HOVER = "#555555"
    ACCENT = "#ffffff"
    ERROR = "#ff4444"
    WARNING = "#ffaa00"
    SUCCESS = "#00ff88"