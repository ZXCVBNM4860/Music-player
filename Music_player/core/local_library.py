# local_library.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.helpers import get_user_data_dir

try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.wave import WAVE
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


SUPPORTED_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac"}


def read_metadata(path: Path) -> Dict[str, Any]:
    meta = {"title": path.stem, "artist": "", "album": "", "duration": 0}
    if not MUTAGEN_AVAILABLE:
        return meta

    try:
        ext = path.suffix.lower()
        if ext == ".mp3":
            audio = MP3(str(path))
        elif ext == ".flac":
            audio = FLAC(str(path))
        elif ext == ".wav":
            audio = WAVE(str(path))
        elif ext == ".m4a":
            audio = MP4(str(path))
        elif ext == ".ogg":
            audio = OggVorbis(str(path))
        else:
            return meta

        if audio.tags:
            title = audio.tags.get("title")
            meta["title"] = str(title[0]) if isinstance(title, list) else str(title or path.stem)
            artist = audio.tags.get("artist")
            meta["artist"] = str(artist[0]) if isinstance(artist, list) else str(artist or "")
            album = audio.tags.get("album")
            meta["album"] = str(album[0]) if isinstance(album, list) else str(album or "")

        if audio.info:
            meta["duration"] = audio.info.length
    except Exception:
        pass

    return meta


def read_cover(path: Path) -> bytes:
    if not MUTAGEN_AVAILABLE:
        return b""
    try:
        ext = path.suffix.lower()
        if ext == ".mp3":
            audio = MP3(str(path))
            if audio.tags:
                for tag in audio.tags.values():
                    if hasattr(tag, "FrameID") and tag.FrameID == "APIC":
                        return tag.data
        elif ext == ".flac":
            audio = FLAC(str(path))
            if audio.pictures:
                return audio.pictures[0].data
        elif ext == ".m4a":
            audio = MP4(str(path))
            if audio.tags:
                covers = audio.tags.get("covr")
                if covers:
                    return bytes(covers[0])
    except Exception:
        pass
    return b""


class LocalLibrary:
    def __init__(self, cache_path: Optional[Path] = None):
        self.tracks: List[Dict[str, Any]] = []
        self.cache_path = cache_path or (get_user_data_dir() / "library_cache.json")

    def scan(self, folder: str, progress_callback=None) -> int:
        root = Path(folder)
        if not root.exists():
            return 0

        files = []
        for ext in SUPPORTED_EXTS:
            files.extend(root.rglob(f"*{ext}"))

        self.tracks = []
        total = len(files)

        for i, path in enumerate(files, 1):
            meta = read_metadata(path)
            self.tracks.append({
                "path": str(path),
                "title": meta["title"],
                "artist": meta["artist"],
                "album": meta["album"],
                "duration": meta["duration"],
            })
            if progress_callback:
                progress_callback(i, total)

        return len(self.tracks)

    def get_all(self) -> List[Dict[str, Any]]:
        return self.tracks

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        kw = keyword.lower()
        return [
            t for t in self.tracks
            if kw in t["title"].lower() or kw in t["artist"].lower() or kw in t["album"].lower()
        ]

    def save_cache(self):
        try:
            self.cache_path.write_text(
                json.dumps(self.tracks, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def load_cache(self) -> bool:
        try:
            if self.cache_path.exists():
                self.tracks = json.loads(self.cache_path.read_text(encoding="utf-8"))
                return True
        except Exception:
            pass
        return False