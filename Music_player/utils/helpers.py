"""工具函数"""
import re


def clean_filename(name: str) -> str:
    """清理文件名"""
    invalid = '\\/*?:"<>|'
    for c in invalid:
        name = name.replace(c, "")
    return name.strip() or "unknown"


def format_number(num: int) -> str:
    """格式化数字"""
    return "{:,}".format(num)


def truncate_text(text: str, max_len: int = 30) -> str:
    """截断文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def format_time(seconds: float) -> str:
    """格式化时间"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
