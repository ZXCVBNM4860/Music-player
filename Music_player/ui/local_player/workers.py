# ui/local_player/workers.py

import os
import time
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from core.api_client import APIClient
from core.config import Config
from core.local_library import LocalLibrary
from utils.helpers import log_line
from .utils import find_local_match, _cache_file_name


class CoverFetcher(QThread):
    cover_ready = pyqtSignal(str)

    def __init__(self, pic_url: str, cover_file: Path):
        super().__init__()
        self.pic_url = pic_url
        self.cover_file = Path(cover_file)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self.cover_file.exists():
            self.cover_ready.emit(str(self.cover_file))
            return

        try:
            self.cover_file.parent.mkdir(parents=True, exist_ok=True)
            response = requests.get(self.pic_url, timeout=10)
            if response.status_code == 200 and not self._cancelled:
                self.cover_file.write_bytes(response.content)
        except Exception:
            pass

        if self._cancelled:
            return
        if self.cover_file.exists():
            self.cover_ready.emit(str(self.cover_file))


class OnlineTrackFetcher(QThread):
    cover_ready = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        client: APIClient,
        song_id: str,
        cache_file: Path,
        cover_file: Optional[Path] = None,
        pic_url: str = "",
    ):
        super().__init__()
        self.client = client
        self.song_id = song_id
        self.cache_file = Path(cache_file)
        self.cover_file = Path(cover_file) if cover_file else None
        self.pic_url = pic_url
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._do_run()
        except PermissionError:
            self.failed.emit("cache_permission_denied")
        except Exception as exc:
            err_str = str(exc)
            if "Permission denied" in err_str:
                self.failed.emit("cache_permission_denied")
            else:
                self.failed.emit(err_str)

    def _do_run(self):
        if self.cache_file.exists():
            self._emit_cached()
            return

        if self.cover_file and self.pic_url and not self.cover_file.exists():
            self._download_cover()
            if self._cancelled:
                return

        self._download_audio()

    def _emit_cached(self):
        if self.cover_file and self.cover_file.exists():
            self.cover_ready.emit(str(self.cover_file))
        self.finished_ok.emit(str(self.cache_file))

    def _download_cover(self):
        try:
            self.cover_file.parent.mkdir(parents=True, exist_ok=True)
            response = requests.get(self.pic_url, timeout=10)
            if response.status_code == 200 and not self._cancelled:
                self.cover_file.write_bytes(response.content)
        except Exception:
            pass

        if self._cancelled:
            return
        if self.cover_file.exists():
            self.cover_ready.emit(str(self.cover_file))

    def _download_audio(self):
        try:
            url = self.client.get_download_url(self.song_id, 320000)
        except Exception:
            url = None

        if self._cancelled:
            return
        if not url:
            self.failed.emit("preview_no_url")
            return

        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.cache_file.parent / f"{self.cache_file.stem}.{id(self)}.part"

        if not self._write_stream_to(url, tmp_file):
            return
        if self._cancelled:
            self._cleanup(tmp_file)
            return

        max_retries = 5
        for attempt in range(max_retries):
            try:
                if self.cache_file.exists():
                    self._cleanup(tmp_file)
                    break
                
                tmp_file.replace(self.cache_file)
                break
            except (PermissionError, OSError):
                if attempt == max_retries - 1:
                    self._cleanup(tmp_file)
                    self.failed.emit("cache_file_occupied")
                    return
                time.sleep(0.5)
            except Exception as exc:
                self._cleanup(tmp_file)
                self.failed.emit(str(exc))
                return

        self.finished_ok.emit(str(self.cache_file))

    def _write_stream_to(self, url: str, tmp_file: Path) -> bool:
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(tmp_file, "wb") as file:
                for chunk in response.iter_content(64 * 1024):
                    if self._cancelled:
                        break
                    if chunk:
                        file.write(chunk)
        except PermissionError:
            self._cleanup(tmp_file)
            self.failed.emit("cache_permission_denied")
            return False
        except Exception as exc:
            self._cleanup(tmp_file)
            if not self._cancelled:
                self.failed.emit(str(exc))
            return False
        return True

    @staticmethod
    def _cleanup(path: Path):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


class QuickDownloadWorker(QThread):
    finished_all = pyqtSignal(int, int)

    def __init__(
        self,
        api_url: str,
        cache_dir: Path,
        songs: list,
        threads: int = 5,
        local_library_path: str = "",
    ):
        super().__init__()
        self.api = APIClient(api_url)
        self.cache_dir = Path(cache_dir)
        self.songs = songs
        self.threads = max(1, min(threads, Config.FAST_DOWNLOAD_THREADS_MAX))
        self.local_library_path = local_library_path or ""
        self._cancelled = False
        self._local_tracks = []

    def cancel(self):
        self._cancelled = True

    def _load_local_tracks(self):
        if not self.local_library_path or not os.path.isdir(self.local_library_path):
            return
        try:
            library = LocalLibrary()
            library.scan(self.local_library_path)
            self._local_tracks = library.get_all()
        except Exception:
            self._local_tracks = []

    def _has_local_match(self, song: dict) -> bool:
        if not self._local_tracks:
            return False
        return find_local_match(
            song.get("title", ""), song.get("artist", ""), self._local_tracks
        ) is not None

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self._load_local_tracks()

        if self._cancelled:
            self.finished_all.emit(0, len(self.songs))
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            log_line(f"[Cache] cannot create {self.cache_dir}: {exc}")
            self.finished_all.emit(0, len(self.songs))
            return

        covers_dir = self.cache_dir / "covers"
        try:
            covers_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        ok = 0
        total = len(self.songs)

        def download_one(song: dict) -> bool:
            if self._cancelled:
                return False
            if self._has_local_match(song):
                return True

            song_id = song.get("id")
            if not song_id:
                return False

            cache_file = self.cache_dir / _cache_file_name(str(song_id))
            if cache_file.exists():
                return True

            try:
                url = self.api.get_download_url(song_id, 320000)
            except Exception:
                url = None

            if not url or self._cancelled:
                return False

            pic_url = song.get("pic_url", "")
            if pic_url:
                cover_file = covers_dir / _cache_file_name(str(song_id), "jpg")
                if not cover_file.exists():
                    try:
                        cover_resp = requests.get(pic_url, timeout=10)
                        if cover_resp.status_code == 200 and not self._cancelled:
                            cover_file.write_bytes(cover_resp.content)
                    except Exception:
                        pass

            if self._cancelled:
                return False

            try:
                return self.api.download_file(url, cache_file)
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(download_one, song) for song in self.songs]
            for future in as_completed(futures):
                if self._cancelled:
                    break
                try:
                    if future.result():
                        ok += 1
                except Exception:
                    pass

        self.finished_all.emit(ok, total)