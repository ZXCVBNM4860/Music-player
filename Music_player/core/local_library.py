# core/local_library.py

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.helpers import get_user_data_dir

try:
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    from mutagen.wave import WAVE
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

SUPPORTED_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac"}

_AUDIO_CLASSES = {}

if MUTAGEN_AVAILABLE:
    _AUDIO_CLASSES = {
        ".mp3": MP3,
        ".flac": FLAC,
        ".wav": WAVE,
        ".m4a": MP4,
        ".ogg": OggVorbis,
    }


def _open_audio(path: Path):
    if not MUTAGEN_AVAILABLE:
        return None

    audio_class = _AUDIO_CLASSES.get(path.suffix.lower())
    if audio_class is None:
        return None

    try:
        return audio_class(str(path))
    except Exception:
        return None


def _read_tag(tags, key: str) -> str:
    if not tags:
        return ""

    value = tags.get(key)
    if value is None:
        return ""

    if isinstance(value, list):
        return str(value[0]) if value else ""

    return str(value)


def read_metadata(path: Path) -> Dict[str, Any]:
    meta = {"title": path.stem, "artist": "", "album": "", "duration": 0}

    audio = _open_audio(path)
    if audio is None:
        return meta

    if audio.tags:
        meta["title"] = _read_tag(audio.tags, "title") or path.stem
        meta["artist"] = _read_tag(audio.tags, "artist")
        meta["album"] = _read_tag(audio.tags, "album")

    if audio.info:
        meta["duration"] = audio.info.length

    return meta


def read_cover(path: Path) -> bytes:
    audio = _open_audio(path)
    if audio is None:
        return b""

    try:
        suffix = path.suffix.lower()

        if suffix == ".mp3":
            return _read_mp3_cover(audio)
        if suffix == ".flac":
            return _read_flac_cover(audio)
        if suffix == ".m4a":
            return _read_mp4_cover(audio)
    except Exception:
        pass

    return b""


def _read_mp3_cover(audio) -> bytes:
    if not audio.tags:
        return b""

    for tag in audio.tags.values():
        if getattr(tag, "FrameID", None) == "APIC":
            return tag.data

    return b""


def _read_flac_cover(audio) -> bytes:
    if audio.pictures:
        return audio.pictures[0].data
    return b""


def _read_mp4_cover(audio) -> bytes:
    if not audio.tags:
        return b""

    covers = audio.tags.get("covr")
    if covers:
        return bytes(covers[0])

    return b""


class LocalLibrary:
    def __init__(self, cache_path: Optional[Path] = None):
        self.tracks: List[Dict[str, Any]] = []
        self.cache_path = cache_path or (
            get_user_data_dir() / "library_cache.json"
        )

    def scan(self, folder: str, progress_callback=None) -> int:
        root = Path(folder)
        if not root.exists():
            return 0

        files = self._collect_audio_files(root)
        self.tracks = []

        total = len(files)

        for index, path in enumerate(files, 1):
            self.tracks.append(self._make_track_entry(path))

            if progress_callback:
                progress_callback(index, total)

        return len(self.tracks)

    @staticmethod
    def _collect_audio_files(root: Path) -> List[Path]:
        files: List[Path] = []

        for ext in SUPPORTED_EXTS:
            files.extend(root.rglob(f"*{ext}"))

        return files

    @staticmethod
    def _make_track_entry(path: Path) -> Dict[str, Any]:
        meta = read_metadata(path)

        return {
            "path": str(path),
            "title": meta["title"],
            "artist": meta["artist"],
            "album": meta["album"],
            "duration": meta["duration"],
        }

    def get_all(self) -> List[Dict[str, Any]]:
        return self.tracks

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        keyword = keyword.lower()

        return [
            track
            for track in self.tracks
            if keyword in track["title"].lower()
            or keyword in track["artist"].lower()
            or keyword in track["album"].lower()
        ]

    def save_cache(self):
        try:
            self.cache_path.write_text(
                json.dumps(self.tracks, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load_cache(self) -> bool:
        try:
            if not self.cache_path.exists():
                return False

            self.tracks = json.loads(
                self.cache_path.read_text(encoding="utf-8")
            )
            return True
        except Exception:
            return False