# core/downloader.py

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.api_client import APIClient, APIError
from core.config import Config
from language import i18n
from utils.file_manager import move_to_rejected_trial
from utils.helpers import clean_filename, format_number

try:
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class DownloadTask(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    speed_update = pyqtSignal(str)
    song_start = pyqtSignal(str, int, int)
    download_finished = pyqtSignal(bool)
    song_complete = pyqtSignal(str, bool)
    api_status = pyqtSignal(bool, str)
    byte_progress_update = pyqtSignal(int, int)
    reset_ui = pyqtSignal()

    TRIAL_DURATION_THRESHOLD = 30

    def __init__(self, api_url: str, download_path: str, bitrate=320000):
        super().__init__()

        self.api = APIClient(api_url)
        self.download_path = Path(download_path)
        self.bitrate = self._normalize_bitrate(bitrate)

        self._running = True
        self._paused = False
        self._pause_cond = threading.Condition()

        self._progress_lock = threading.Lock()
        self._completed = 0
        self._total = 0
        self._success = 0

        self._speed_lock = threading.Lock()
        self._bytes_for_speed = 0
        self._last_speed_time = time.time()

        self._byte_lock = threading.Lock()
        self._total_bytes = 0
        self._downloaded_bytes = 0

        self._downloaded_files: List[Path] = []
        self._downloaded_files_lock = threading.Lock()

        self._reset_flag = 0
        self._executor: Optional[ThreadPoolExecutor] = None

        self.task_type = 2
        self.task_id = ""

        self.reset_ui.connect(self._apply_reset)

    def set_task(self, task_type: int, task_id: str):
        self.task_type = task_type
        self.task_id = task_id

    def set_bitrate(self, bitrate):
        self.bitrate = self._normalize_bitrate(bitrate)

    def pause(self):
        self._paused = True
        self.log_message.emit(i18n.tr("paused"))

    def resume(self):
        self._paused = False
        with self._pause_cond:
            self._pause_cond.notify_all()
        self.log_message.emit(i18n.tr("resumed"))

    def stop(self):
        self._running = False
        self._paused = False

        with self._pause_cond:
            self._pause_cond.notify_all()

        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

        self.wait(2000)

    @staticmethod
    def _normalize_bitrate(bitrate):
        if str(bitrate).lower() == "flac":
            return "flac"
        return int(bitrate)

    def _wait_if_paused(self):
        while self._paused and self._running:
            with self._pause_cond:
                self._pause_cond.wait(timeout=0.5)

    def _ensure_dir(self):
        self.download_path.mkdir(parents=True, exist_ok=True)

    def _check_exists(self, name: str, ext: Optional[str] = None) -> bool:
        if ext is None:
            ext = "flac" if self.bitrate == "flac" else "mp3"
        return (self.download_path / f"{name}.{ext}").exists()

    def _update_counters(self, success: bool):
        with self._progress_lock:
            self._completed += 1
            if success:
                self._success += 1

    def _add_downloaded_bytes(self, chunk_size: int):
        with self._byte_lock:
            self._downloaded_bytes += chunk_size

        with self._speed_lock:
            self._bytes_for_speed += chunk_size
            now = time.time()
            elapsed = now - self._last_speed_time

            if elapsed >= 1.0:
                speed = self._bytes_for_speed / elapsed
                self._bytes_for_speed = 0
                self._last_speed_time = now
                self.speed_update.emit(self._fmt_speed(speed))

    @staticmethod
    def _fmt_speed(speed: float) -> str:
        if speed > 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f} MB/s"
        if speed > 1024:
            return f"{speed / 1024:.1f} KB/s"
        return f"{speed:.0f} B/s"

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size > 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
        if size > 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size > 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"

    def _get_byte_progress(self):
        with self._byte_lock:
            return self._downloaded_bytes, self._total_bytes

    @staticmethod
    def _get_audio_duration(path: Path) -> float:
        if not MUTAGEN_AVAILABLE:
            return 0

        try:
            suffix = path.suffix.lower()

            if suffix == ".mp3":
                audio = MP3(str(path))
            elif suffix == ".flac":
                audio = FLAC(str(path))
            else:
                return 0

            return audio.info.length
        except Exception:
            return 0

    def _is_trial_version(self, path: Path) -> bool:
        duration = self._get_audio_duration(path)

        if duration > 0 and duration < self.TRIAL_DURATION_THRESHOLD:
            return True

        if not MUTAGEN_AVAILABLE:
            file_size = path.stat().st_size
            suffix = path.suffix.lower()
            if suffix in (".mp3", ".flac") and file_size < 1000 * 1024:
                return True

        return False

    def _post_process_check(self):
        if not self._downloaded_files:
            return

        self.log_message.emit(i18n.tr("checking_trial_versions"))

        moved_count = 0

        for path in self._downloaded_files:
            if not path.exists():
                continue

            if not self._is_trial_version(path):
                continue

            duration = self._get_audio_duration(path)
            name = path.stem
            dest = move_to_rejected_trial(path, self.download_path)

            if dest is None:
                self.log_message.emit(f"{name} - 移动至回收站失败")
                continue

            if duration > 0:
                self.log_message.emit(
                    f"{name} - {i18n.tr('trial_moved')} "
                    f"({int(duration)}s) -> {dest.name}"
                )
            else:
                self.log_message.emit(
                    f"{name} - {i18n.tr('trial_moved')} -> {dest.name}"
                )

            moved_count += 1

            with self._progress_lock:
                self._success -= 1

        if moved_count > 0:
            self.log_message.emit(
                f"{i18n.tr('trial_check_result')} "
                f"{moved_count} {i18n.tr('trial_moved_count')}"
            )
        else:
            self.log_message.emit(i18n.tr("no_trial_versions"))

    def _get_task_items(self) -> List[Dict[str, Any]]:
        if self.task_type == 1:
            return [{"id": self.task_id, "name": None, "type": "song"}]

        if self.task_type == 3:
            return [{"id": self.task_id, "name": None, "type": "mv"}]

        self.log_message.emit(i18n.tr("fetch_playlist"))

        try:
            songs = self.api.get_playlist_detail(self.task_id)
        except APIError as exc:
            self.log_message.emit(f"{i18n.tr('playlist_fetch_fail')}: {exc}")
            return []

        if not songs:
            self.log_message.emit(i18n.tr("playlist_empty_msg"))
            return []

        return [
            {"id": str(song["id"]), "name": song["name"], "type": "song"}
            for song in songs
        ]

    def _prepare_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._wait_if_paused()

        if not self._running:
            return None

        item_id = item["id"]
        item_name = item.get("name")
        item_type = item["type"]

        try:
            if item_type == "song":
                return self._prepare_song(item_id, item_name)
            if item_type == "mv":
                return self._prepare_mv(item_id, item_name)
            return None
        except Exception as exc:
            self.log_message.emit(f"{i18n.tr('error')}: {exc}")
            return None

    def _prepare_song(
        self,
        song_id: str,
        song_name: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not song_name:
            try:
                detail = self.api.get_song_detail(song_id)
                song_name = detail["name"]
            except APIError:
                return None

        song_name = clean_filename(song_name)
        ext = "flac" if self.bitrate == "flac" else "mp3"

        if self._check_exists(song_name, ext):
            self.log_message.emit(f"{song_name} - {i18n.tr('exists_skip')}")
            return None

        url = self.api.get_download_url(song_id, self.bitrate)
        if not url:
            self.log_message.emit(f"{song_name} - {i18n.tr('no_copyright')}")
            return None

        total_size = self._probe_content_length(url)

        return {
            "id": song_id,
            "name": song_name,
            "type": "song",
            "url": url,
            "size": total_size,
            "ext": ext,
        }

    def _prepare_mv(
        self,
        mv_id: str,
        mv_name: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not mv_name:
            mv_name = mv_id

        mv_name = clean_filename(mv_name)

        if self._check_exists(mv_name, "mp4"):
            self.log_message.emit(f"{mv_name} - {i18n.tr('exists_skip')}")
            return None

        url = self.api.get_mv_download_url(mv_id)
        if not url:
            self.log_message.emit(f"{mv_name} - {i18n.tr('no_copyright')}")
            return None

        total_size = self._probe_content_length(url)

        return {
            "id": mv_id,
            "name": mv_name,
            "type": "mv",
            "url": url,
            "size": total_size,
            "ext": "mp4",
        }

    def _probe_content_length(self, url: str) -> int:
        try:
            head = self.api.session.head(url, timeout=Config.TIMEOUT_API)
            return int(head.headers.get("Content-Length", 0))
        except Exception:
            return 0

    def _download_prepared_item(
        self,
        item: Dict[str, Any],
        index: int,
        total: int,
    ) -> bool:
        self._wait_if_paused()

        if not self._running:
            return False

        try:
            if item["type"] == "song":
                return self._download_prepared_song(item, index, total)
            if item["type"] == "mv":
                return self._download_prepared_mv(item, index, total)
            return False
        except Exception as exc:
            self.log_message.emit(f"{i18n.tr('error')}: {exc}")
            return False

    def _download_prepared_song(
        self,
        item: Dict[str, Any],
        index: int,
        total: int,
    ) -> bool:
        song_name = item["name"]
        url = item["url"]
        ext = item["ext"]
        expected_size = item.get("size", 0)

        self.song_start.emit(song_name, index, total)

        final_path = self.download_path / f"{song_name}.{ext}"
        success = self._download_to_file(
            url=url,
            final_path=final_path,
            expected_size=expected_size,
        )

        if not success:
            self._log_download_failure(song_name)
            return False

        with self._downloaded_files_lock:
            self._downloaded_files.append(final_path)

        self.log_message.emit(f"{song_name} - {i18n.tr('done')}")
        return True

    def _download_prepared_mv(
        self,
        item: Dict[str, Any],
        index: int,
        total: int,
    ) -> bool:
        mv_name = item["name"]
        url = item["url"]
        expected_size = item.get("size", 0)

        self.song_start.emit(mv_name, index, total)

        final_path = self.download_path / f"{mv_name}.mp4"
        success = self._download_to_file(
            url=url,
            final_path=final_path,
            expected_size=expected_size,
        )

        if not success:
            self._log_download_failure(mv_name)
            return False

        with self._downloaded_files_lock:
            self._downloaded_files.append(final_path)

        self.log_message.emit(f"{mv_name} - {i18n.tr('done')}")
        return True

    def _download_to_file(
        self,
        url: str,
        final_path: Path,
        expected_size: int,
    ) -> bool:
        def on_chunk(chunk_size: int):
            self._add_downloaded_bytes(chunk_size)
            downloaded, total_bytes = self._get_byte_progress()
            if total_bytes > 0:
                self.byte_progress_update.emit(downloaded, total_bytes)

        def should_cancel() -> bool:
            return not self._running

        ok = self.api.download_file(
            url,
            final_path,
            progress_callback=on_chunk,
            cancel_callback=should_cancel,
        )

        if ok:
            return True

        self._cleanup_broken_file(final_path, expected_size)
        return False

    @staticmethod
    def _cleanup_broken_file(path: Path, expected_size: int):
        if not path.exists():
            return

        try:
            actual_size = path.stat().st_size
            is_broken = (
                actual_size == 0
                or (expected_size > 0 and actual_size < expected_size)
            )
            if is_broken:
                path.unlink()
        except Exception:
            pass

    def _log_download_failure(self, name: str):
        if not self._running:
            self.log_message.emit(f"{name} - {i18n.tr('stopped')}")
        else:
            self.log_message.emit(f"{name} - {i18n.tr('data_error')}")

    def run(self):
        try:
            self._reset_flag += 1

            if not self._check_api_alive():
                return

            self._ensure_dir()
            self._downloaded_files = []

            raw_items = self._get_task_items()
            if not raw_items:
                self.download_finished.emit(False)
                return

            prepared, total_size = self._prepare_all_items(raw_items)
            if prepared is None:
                return

            if not prepared:
                self.log_message.emit(i18n.tr("no_downloadable_items"))
                self.download_finished.emit(False)
                return

            self._run_downloads(prepared, total_size)

        except Exception as exc:
            self.log_message.emit(f"{i18n.tr('severe_error')}: {exc}")
            self.download_finished.emit(False)

    def _check_api_alive(self) -> bool:
        self.api_status.emit(False, i18n.tr("api_checking"))

        if self.api.check_alive():
            self.api_status.emit(True, i18n.tr("api_online"))
            return True

        self.api_status.emit(False, i18n.tr("api_offline"))
        self.log_message.emit(i18n.tr("api_not_started"))
        self.download_finished.emit(False)
        return False

    def _prepare_all_items(self, raw_items):
        """并发准备所有下载项。被停止时返回 (None, 0)。"""
        self.log_message.emit(i18n.tr("preparing_downloads"))

        prepared: List[Dict[str, Any]] = []
        total_size = 0
        prepared_lock = threading.Lock()

        self._executor = ThreadPoolExecutor(max_workers=5)

        try:
            futures = {
                self._executor.submit(self._prepare_item, item): item
                for item in raw_items
            }

            for i, future in enumerate(as_completed(futures), 1):
                self._wait_if_paused()

                if not self._running:
                    self.download_finished.emit(False)
                    return None, 0

                result = future.result()

                if result:
                    with prepared_lock:
                        prepared.append(result)
                        total_size += result["size"]

                with prepared_lock:
                    valid_count = len(prepared)

                self.log_message.emit(
                    f"{i18n.tr('preparing')} {i}/{len(raw_items)} "
                    f"({i18n.tr('valid')} {valid_count})"
                )
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

        return prepared, total_size

    def _run_downloads(self, prepared: List[Dict[str, Any]], total_size: int):
        self._total_bytes = total_size
        self._downloaded_bytes = 0
        self._total = len(prepared)
        self._completed = 0
        self._success = 0

        self.log_message.emit(
            f"{i18n.tr('ready_to_download')} "
            f"{format_number(self._total)} {i18n.tr('songs_count')}，"
            f"{i18n.tr('total_size')} {self._fmt_size(total_size)}"
        )
        self.byte_progress_update.emit(0, total_size)

        self._executor = ThreadPoolExecutor(max_workers=5)

        try:
            futures = {}

            for index, item in enumerate(prepared, 1):
                self._wait_if_paused()

                if not self._running:
                    break

                future = self._executor.submit(
                    self._download_prepared_item,
                    item,
                    index,
                    self._total,
                )
                futures[future] = item
                time.sleep(Config.DOWNLOAD_DELAY)

            for future in as_completed(futures):
                self._wait_if_paused()

                if not self._running:
                    break

                success = future.result()
                self._update_counters(success)

                with self._progress_lock:
                    self.progress_update.emit(self._completed, self._total)
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

        self._post_process_check()

        with self._progress_lock:
            self.progress_update.emit(self._total, self._total)

        self.log_message.emit(
            f"{i18n.tr('complete_result')} {self._success}/{self._total} "
            f"({i18n.tr('this_time')} {self._success}/{self._total})"
        )

        self._schedule_reset_progress()
        self.download_finished.emit(True)

    def _schedule_reset_progress(self):
        flag = self._reset_flag

        def _later():
            time.sleep(2)
            if self._reset_flag == flag:
                self.reset_ui.emit()

        threading.Thread(target=_later, daemon=True).start()

    def _apply_reset(self):
        with self._progress_lock:
            done = self._total > 0 and self._completed >= self._total

        if done and self._running:
            self.byte_progress_update.emit(0, 100)
            self.progress_update.emit(0, 100)