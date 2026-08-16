"""工具函数"""

import os
import sys


def clean_filename(name: str) -> str:
    # 清理文件名
    invalid = '\\/*?:"<>|'
    for c in invalid:
        name = name.replace(c, "")
    return name.strip() or "unknown"


def format_number(num: int) -> str:
    # 格式化数字
    return "{:,}".format(num)


def truncate_text(text: str, max_len: int = 30) -> str:
    # 截断文本
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def format_time(seconds: float) -> str:
    # 格式化时间
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_default_download_path() -> str:
    """
    获取默认下载路径。
    - 源码运行：项目根目录下的 downloads/
    - PyInstaller 打包后：exe 同级目录下的 downloads/
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        base_dir = os.path.dirname(sys.executable)
    else:
        # 源码运行，helpers.py 位于 utils/，项目根目录是其父目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    download_dir = os.path.join(base_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)
    return download_dir


def build_song_filename(name: str, artists: list[str], song_id: str) -> str:
    """
    构建歌曲文件名：艺术家 - 歌曲名 [ID]
    例如：周杰伦 - Intro [12345678]
    """
    artist_str = ", ".join(artists) if artists else "Unknown"
    raw = f"{artist_str} - {name} [{song_id}]"
    return clean_filename(raw)