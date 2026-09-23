# utils/helpers.py
import os
import sys
from pathlib import Path


def clean_filename(name: str) -> str:
    invalid = '\\/*?:"<>|'
    for c in invalid:
        name = name.replace(c, "")
    return name.strip() or "unknown"


def format_number(num: int) -> str:
    return "{:,}".format(num)


def truncate_text(text: str, max_len: int = 30) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_default_download_path() -> str:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = str(Path(__file__).parent.parent)

    download_dir = os.path.join(base_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)
    return download_dir


def build_song_filename(name: str, artists: list[str], song_id: str) -> str:
    artist_str = ", ".join(artists) if artists else "Unknown"
    return clean_filename(f"{artist_str} - {name} [{song_id}]")