# utils/helpers.py

import os
import re
import shutil
import sys
from pathlib import Path


LEGACY_DATA_FILES = (
    "auth.json",
    "playlists.json",
    "recent_played.json",
    "library_cache.json",
)

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
    name = name.rstrip(". ")
    return name or "unknown"


def format_number(num: int) -> str:
    return "{:}".format(num)


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def get_program_dir() -> Path:
    if _is_frozen():
        if sys.argv and sys.argv[0]:
            candidate = Path(sys.argv[0])
            try:
                resolved = candidate.resolve()
                if resolved.exists() and resolved.suffix.lower() in (".exe", ".bin", ""):
                    return resolved.parent
            except Exception:
                pass

        exe = Path(sys.executable).resolve()
        return exe.parent

    return Path(__file__).resolve().parent.parent


def _test_dir_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        test_file = directory / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True
    except Exception as exc:
        log_line(f"[Helpers] Directory not writable {directory}: {exc}")
        return False


def get_default_download_path() -> str:
    candidates = (
        get_program_dir() / "downloads",
        _app_data_root() / "downloads",
        Path.home() / "Downloads" / "MusicPlayer",
    )

    for candidate in candidates:
        if _test_dir_writable(candidate):
            return str(candidate)

    return str(candidates[-1])


def _app_data_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    if base:
        return Path(base) / "MusicPlayer"

    return Path(os.environ.get("TEMP") or os.path.expanduser("~")) / "MusicPlayer"


def _migrate_legacy_data(target: Path):
    legacy = _app_data_root()
    if not legacy.is_dir() or legacy == target:
        return

    for name in LEGACY_DATA_FILES:
        source = legacy / name
        destination = target / name
        if source.is_file() and not destination.exists():
            try:
                shutil.copy2(source, destination)
            except Exception:
                pass


def get_user_data_dir() -> Path:
    global _app_data_dir

    if _app_data_dir is not None:
        if _test_dir_writable(_app_data_dir):
            return _app_data_dir
        else:
            _app_data_dir = None

    candidates = (
        get_program_dir() / "config",
        _app_data_root(),
        Path(os.environ.get("TEMP") or os.path.expanduser("~")) / "MusicPlayer",
    )

    for candidate in candidates:
        if _test_dir_writable(candidate):
            if candidate == candidates[0]:
                _migrate_legacy_data(candidate)
            _app_data_dir = candidate
            return candidate

    _app_data_dir = candidates[-1]
    return _app_data_dir


def get_cache_dir() -> Path:
    global _cache_dir

    if _cache_dir is not None:
        if _test_dir_writable(_cache_dir):
            return _cache_dir
        else:
            _cache_dir = None

    candidates = (
        get_user_data_dir() / "cache",
        Path(os.environ.get("TEMP") or os.path.expanduser("~")) / "MusicPlayer_cache",
    )

    for candidate in candidates:
        if _test_dir_writable(candidate):
            _cache_dir = candidate
            return candidate

    raise PermissionError("cache_permission_denied")


def build_song_filename(name: str, artists: list[str]) -> str:
    artist_str = ", ".join(artists) if artists else "Unknown"
    return clean_filename(f"{artist_str} - {name}")