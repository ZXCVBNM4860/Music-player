# utils/helpers.py

import os
import re
import sys
from pathlib import Path

LOG_PATH = os.path.join(
    os.environ.get("TEMP") or os.environ.get("TMP") or os.path.expanduser("~"),
    "MusicPlayer.log",
)

_app_data_dir = None
_cache_dir = None

_INVALID_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|\x00-\x1f]')


def log_line(message: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")
    except Exception:
        pass


def reset_log():
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass


def clean_filename(name: str) -> str:
    if not name:
        return "unknown"
    name = _INVALID_FILENAME_CHARS.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.rstrip(". ") or "unknown"


def format_number(num: int) -> str:
    return "{:}".format(num)


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_program_dir() -> Path:
    if bool(getattr(sys, "frozen", False)) or "__compiled__" in globals():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _app_data_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    if base:
        return Path(base) / "MusicPlayer"
    return Path(os.environ.get("TEMP") or os.path.expanduser("~")) / "MusicPlayer"


def _test_dir_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        test_file = directory / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True
    except Exception as exc:
        log_line(f"[Helpers] Directory NOT writable: {directory} | Reason: {exc}")
        return False


def get_user_data_dir() -> Path:
    global _app_data_dir

    if _app_data_dir is not None:
        return _app_data_dir

    target = get_program_dir() / "config"
    if _test_dir_writable(target):
        _app_data_dir = target
    else:
        fallback = _app_data_root()
        if _test_dir_writable(fallback):
            _app_data_dir = fallback
        else:
            _app_data_dir = Path(os.environ.get("TEMP") or os.path.expanduser("~")) / "MusicPlayer"
            _test_dir_writable(_app_data_dir)

    return _app_data_dir


def get_cache_dir() -> Path:
    global _cache_dir

    if _cache_dir is not None:
        return _cache_dir

    target = get_program_dir() / "cache"
    if _test_dir_writable(target):
        _cache_dir = target
    else:
        _cache_dir = get_user_data_dir() / "cache"
        _test_dir_writable(_cache_dir)

    return _cache_dir


def get_default_download_path() -> str:
    target = get_program_dir() / "downloads"
    if _test_dir_writable(target):
        return str(target)
    return str(Path.home() / "Downloads" / "MusicPlayer")


def build_song_filename(name: str, artists: list[str]) -> str:
    artist_str = ", ".join(artists) if artists else "Unknown"
    return clean_filename(f"{artist_str} - {name}")