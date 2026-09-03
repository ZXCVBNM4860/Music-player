"""下载器"""

import time
import threading
from pathlib import Path
from typing import Optional, Any, List, Dict, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from core.api_client import APIClient, APIError
from core.config import Config
from utils.helpers import clean_filename, format_number, build_song_filename
from utils.file_manager import move_to_rejected_trial
from language import i18n

try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class DownloadTask(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    speed_update = pyqtSignal(str)
    song_start = pyqtSignal(str, int, int)
    song_complete = pyqtSignal(str, bool)
    download_finished = pyqtSignal(bool)
    api_status = pyqtSignal(bool, str)
    byte_progress_update = pyqtSignal(int, int)

    TRIAL_DURATION_THRESHOLD = 30

    def __init__(self, api_url: str, download_path: str, bitrate=320000):
        super().__init__()
        self.api = APIClient(api_url)
        self.download_path = Path(download_path)
        self.bitrate = "flac" if str(bitrate).lower() == "flac" else int(bitrate)

        self._running = True
        self._paused = False
        self._pause_lock = threading.Condition()
        self._progress_lock = threading.Lock()  # 替代 QMutex

        self._completed = 0
        self._total = 0
        self._success = 0

        # 速度统计
        self._bytes_for_speed = 0
        self._speed_lock = threading.Lock()
        self._last_speed_time = time.time()

        # 字节进度
        self._total_bytes = 0
        self._downloaded_bytes = 0
        self._byte_lock = threading.Lock()

        self._downloaded_files: List[Path] = []
        self._downloaded_files_lock = threading.Lock()

        self._reset_flag = 0
        self._executor: Optional[ThreadPoolExecutor] = None

        self.task_type = 2
        self.task_id = ""

    # ---------- 控制接口保持不变 ----------
    def set_task(self, task_type: int, task_id: str):
        self.task_type = task_type
        self.task_id = task_id

    def set_bitrate(self, bitrate):
        self.bitrate = "flac" if str(bitrate).lower() == "flac" else int(bitrate)

    def pause(self):
        self._paused = True
        self.log_message.emit(i18n.tr("paused"))

    def resume(self):
        self._paused = False
        with self._pause_lock:
            self._pause_lock.notify_all()
        self.log_message.emit(i18n.tr("resumed"))

    def stop(self):
        self._running = False
        self._paused = False
        with self._pause_lock:
            self._pause_lock.notify_all()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self.wait(2000)

    def _wait_if_paused(self):
        while self._paused and self._running:
            with self._pause_lock:
                self._pause_lock.wait(timeout=0.5)

    # ---------- 工具函数微调 ----------
    def _ensure_dir(self):
        self.download_path.mkdir(parents=True, exist_ok=True)

    def _check_exists(self, name: str, ext: str = None) -> bool:
        if ext is None:
            ext = "flac" if self.bitrate == "flac" else "mp3"
        return (self.download_path / f"{name}.{ext}").exists()

    def _update_counters(self, success: bool):
        with self._progress_lock:
            self._completed += 1
            if success:
                self._success += 1

    def _add_downloaded_bytes(self, n: int):
        # 更新字节进度
        with self._byte_lock:
            self._downloaded_bytes += n

        # 速度统计（顺便在这里做主动上报，不再需要单独的 Timer 线程）
        with self._speed_lock:
            self._bytes_for_speed += n
            now = time.time()
            if now - self._last_speed_time >= 1.0:
                elapsed = now - self._last_speed_time
                speed = self._bytes_for_speed / elapsed
                self._bytes_for_speed = 0
                self._last_speed_time = now
                # 直接发射速度信号（跨线程安全）
                self.speed_update.emit(self._fmt_speed(speed))

    @staticmethod
    def _fmt_speed(speed: float) -> str:
        if speed > 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f} MB/s"
        elif speed > 1024:
            return f"{speed / 1024:.1f} KB/s"
        else:
            return f"{speed:.0f} B/s"

    def _get_byte_progress(self) -> tuple[int, int]:
        with self._byte_lock:
            return self._downloaded_bytes, self._total_bytes

    # ---------- 试听检测逻辑完全保留 ----------
    @staticmethod
    def _get_audio_duration(path: Path) -> float:
        if not MUTAGEN_AVAILABLE:
            return 0
        try:
            ext = path.suffix.lower()
            if ext == ".mp3":
                audio = MP3(str(path))
            elif ext == ".flac":
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
            ext = path.suffix.lower()
            if ext in (".mp3", ".flac") and file_size < 1000 * 1024:
                return True
        return False

    def _post_process_check(self):
        if not self._downloaded_files:
            return
        self.log_message.emit(i18n.tr("checking_trial_versions"))
        moved = 0
        for path in self._downloaded_files:
            if not path.exists():
                continue
            if self._is_trial_version(path):
                duration = self._get_audio_duration(path)
                name = path.stem
                dest = move_to_rejected_trial(path, self.download_path)
                if dest is None:
                    self.log_message.emit(f"{name} - 移动至回收站失败")
                    continue
                if duration > 0:
                    self.log_message.emit(f"{name} - {i18n.tr('trial_moved')} ({int(duration)}s) -> {dest.name}")
                else:
                    self.log_message.emit(f"{name} - {i18n.tr('trial_moved')} -> {dest.name}")
                moved += 1
                with self._progress_lock:
                    self._success -= 1
        if moved > 0:
            self.log_message.emit(f"{i18n.tr('trial_check_result')} {moved} {i18n.tr('trial_moved_count')}")
        else:
            self.log_message.emit(i18n.tr("no_trial_versions"))

    # ---------- 预取和下载逻辑（只改锁名，逻辑不动） ----------
    def _get_task_items(self) -> List[Dict[str, Any]]:
        if self.task_type == 1:
            return [{"id": self.task_id, "name": None, "type": "song"}]
        if self.task_type == 3:
            return [{"id": self.task_id, "name": None, "type": "mv"}]
        self.log_message.emit(i18n.tr("fetch_playlist"))
        try:
            songs = self.api.get_playlist_detail(self.task_id)
        except APIError as e:
            self.log_message.emit(f"{i18n.tr('playlist_fetch_fail')}: {e}")
            return []
        if not songs:
            self.log_message.emit(i18n.tr("playlist_empty_msg"))
            return []
        return [{"id": str(s["id"]), "name": s["name"], "type": "song"} for s in songs]

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
            elif item_type == "mv":
                return self._prepare_mv(item_id, item_name)
            return None
        except Exception as e:
            self.log_message.emit(f"{i18n.tr('error')}: {e}")
            return None

    def _prepare_song(self, song_id: str, song_name: Optional[str]) -> Optional[Dict[str, Any]]:
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
        total_size = 0
        try:
            head = self.api.session.head(url, timeout=Config.TIMEOUT_API)
            total_size = int(head.headers.get("Content-Length", 0))
        except Exception:
            pass
        return {"id": song_id, "name": song_name, "type": "song", "url": url, "size": total_size, "ext": ext}

    def _prepare_mv(self, mv_id: str, mv_name: Optional[str]) -> Optional[Dict[str, Any]]:
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
        total_size = 0
        try:
            head = self.api.session.head(url, timeout=Config.TIMEOUT_API)
            total_size = int(head.headers.get("Content-Length", 0))
        except Exception:
            pass
        return {"id": mv_id, "name": mv_name, "type": "mv", "url": url, "size": total_size, "ext": "mp4"}

    def _download_prepared_item(self, item: Dict[str, Any], index: int, total: int) -> bool:
        self._wait_if_paused()
        if not self._running:
            return False
        item_type = item["type"]
        try:
            if item_type == "song":
                return self._download_prepared_song(item, index, total)
            elif item_type == "mv":
                return self._download_prepared_mv(item, index, total)
            return False
        except Exception as e:
            self.log_message.emit(f"{i18n.tr('error')}: {e}")
            return False

    def _download_prepared_song(self, item: Dict[str, Any], index: int, total: int) -> bool:
        song_name = item["name"]
        url = item["url"]
        ext = item["ext"]
        expected_size = item.get("size", 0)
        self.song_start.emit(song_name, index, total)
        final_path = self.download_path / f"{song_name}.{ext}"

        def _on_chunk(chunk_size: int):
            self._add_downloaded_bytes(chunk_size)
            downloaded, total_bytes = self._get_byte_progress()
            if total_bytes > 0:
                self.byte_progress_update.emit(downloaded, total_bytes)

        def _cancel_check() -> bool:
            return not self._running

        if not self.api.download_file(url, final_path, progress_callback=_on_chunk, cancel_callback=_cancel_check):
            if final_path.exists():
                try:
                    actual_size = final_path.stat().st_size
                    if actual_size == 0 or (expected_size > 0 and actual_size < expected_size):
                        final_path.unlink()
                except Exception:
                    pass
            if not self._running:
                self.log_message.emit(f"{song_name} - {i18n.tr('stopped')}")
            else:
                self.log_message.emit(f"{song_name} - {i18n.tr('data_error')}")
            return False
        with self._downloaded_files_lock:
            self._downloaded_files.append(final_path)
        self.log_message.emit(f"{song_name} - {i18n.tr('done')}")
        return True

    def _download_prepared_mv(self, item: Dict[str, Any], index: int, total: int) -> bool:
        mv_name = item["name"]
        url = item["url"]
        expected_size = item.get("size", 0)
        self.song_start.emit(mv_name, index, total)
        final_path = self.download_path / f"{mv_name}.mp4"

        def _on_chunk(chunk_size: int):
            self._add_downloaded_bytes(chunk_size)
            downloaded, total_bytes = self._get_byte_progress()
            if total_bytes > 0:
                self.byte_progress_update.emit(downloaded, total_bytes)

        def _cancel_check() -> bool:
            return not self._running

        if not self.api.download_file(url, final_path, progress_callback=_on_chunk, cancel_callback=_cancel_check):
            if final_path.exists():
                try:
                    actual_size = final_path.stat().st_size
                    if actual_size == 0 or (expected_size > 0 and actual_size < expected_size):
                        final_path.unlink()
                except Exception:
                    pass
            if not self._running:
                self.log_message.emit(f"{mv_name} - {i18n.tr('stopped')}")
            else:
                self.log_message.emit(f"{mv_name} - {i18n.tr('data_error')}")
            return False
        with self._downloaded_files_lock:
            self._downloaded_files.append(final_path)
        self.log_message.emit(f"{mv_name} - {i18n.tr('done')}")
        return True

    # ---------- 核心 run ----------
    def run(self):
        try:
            self._reset_flag += 1
            self.api_status.emit(False, i18n.tr("api_checking"))
            if not self.api.check_alive():
                self.api_status.emit(False, i18n.tr("api_offline"))
                self.log_message.emit(i18n.tr("api_not_started"))
                self.download_finished.emit(False)
                return

            self.api_status.emit(True, i18n.tr("api_online"))
            self._ensure_dir()
            self._downloaded_files = []

            raw_items = self._get_task_items()
            if not raw_items:
                self.download_finished.emit(False)
                return

            self.log_message.emit(i18n.tr("preparing_downloads"))
            prepared = []
            total_size = 0
            prepared_lock = threading.Lock()

            self._executor = ThreadPoolExecutor(max_workers=5)
            try:
                futures = {self._executor.submit(self._prepare_item, item): item for item in raw_items}
                for i, future in enumerate(as_completed(futures), 1):
                    self._wait_if_paused()
                    if not self._running:
                        self.download_finished.emit(False)
                        return
                    result = future.result()
                    if result:
                        with prepared_lock:
                            prepared.append(result)
                            total_size += result["size"]
                    with prepared_lock:
                        valid_count = len(prepared)
                    self.log_message.emit(f"{i18n.tr('preparing')} {i}/{len(raw_items)} ({i18n.tr('valid')} {valid_count})")
            finally:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None

            if not prepared:
                self.log_message.emit(i18n.tr("no_downloadable_items"))
                self.download_finished.emit(False)
                return

            self._total_bytes = total_size
            self._downloaded_bytes = 0
            self._total = len(prepared)
            self._completed = 0
            self._success = 0

            self.log_message.emit(
                f"{i18n.tr('ready_to_download')} {format_number(self._total)} {i18n.tr('songs_count')}，"
                f"{i18n.tr('total_size')} {self._fmt_size(total_size)}"
            )
            self.byte_progress_update.emit(0, total_size)


            self._executor = ThreadPoolExecutor(max_workers=5)
            try:
                futures = {}
                for i, item in enumerate(prepared, 1):
                    self._wait_if_paused()
                    if not self._running:
                        break
                    future = self._executor.submit(self._download_prepared_item, item, i, self._total)
                    futures[future] = item
                    time.sleep(Config.DOWNLOAD_DELAY)

                for future in as_completed(futures):
                    self._wait_if_paused()
                    if not self._running:
                        break
                    success = future.result()
                    self._update_counters(success)
                    # 更新进度条（每完成一首）
                    with self._progress_lock:
                        self.progress_update.emit(self._completed, self._total)
            finally:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None

            # 后处理
            self._post_process_check()

            # 最终完成进度
            with self._progress_lock:
                self.progress_update.emit(self._total, self._total)
            self.log_message.emit(
                f"{i18n.tr('complete_result')} {self._success}/{self._total} "
                f"({i18n.tr('this_time')} {self._success}/{self._total})"
            )

            self._schedule_reset_progress()

            self.download_finished.emit(True)

        except Exception as e:
            self.log_message.emit(f"{i18n.tr('severe_error')}: {e}")
            self.download_finished.emit(False)

    def _schedule_reset_progress(self):
        flag = self._reset_flag
        # 注意：这个函数运行在子线程，QTimer.singleShot 会确保回调在主线程执行（因为 self 属于主线程）
        def reset():
            # 此时在主线程，但为了防止主线程 UI 操作时变量冲突，读锁即可
            with self._progress_lock:
                is_finished = (self._completed >= self._total)
            if is_finished and self._running and self._reset_flag == flag:
                self.byte_progress_update.emit(0, 100)
                self.progress_update.emit(0, 100)
        QTimer.singleShot(2000, reset)

    @staticmethod
    def _fmt_size(n: int) -> str:
        if n > 1024 * 1024 * 1024:
            return f"{n / (1024*1024*1024):.2f} GB"
        elif n > 1024 * 1024:
            return f"{n / (1024*1024):.1f} MB"
        elif n > 1024:
            return f"{n / 1024:.1f} KB"
        else:
            return f"{n} B"
