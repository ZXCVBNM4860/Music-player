"""下载器"""

import time
import threading
from pathlib import Path
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QTimer
from core.api_client import APIClient, APIError
from core.config import Config
from utils.helpers import clean_filename, format_number
from utils.history import DownloadHistory
from language import i18n


class DownloadTask(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    speed_update = pyqtSignal(str)
    song_start = pyqtSignal(str, int, int)
    song_complete = pyqtSignal(str, bool)
    download_finished = pyqtSignal(bool)
    api_status = pyqtSignal(bool, str)
    
    def __init__(self, api_url: str, download_path: str, bitrate=320000):
        super().__init__()
        self.api = APIClient(api_url)
        self.download_path = Path(download_path)
        self.history = DownloadHistory()
        if isinstance(bitrate, str) and bitrate.lower() == "flac":
            self.bitrate = "flac"
        else:
            try:
                self.bitrate = int(bitrate)
            except Exception:
                self.bitrate = 320000
        
        self._running = True
        self._paused = False
        self._pause_lock = threading.Condition()
        
        self._completed = 0
        self._total = 0
        self._success = 0
        self._progress_mutex = QMutex()
        
        self._bytes_downloaded = 0
        self._speed_lock = threading.Lock()
        self._last_speed_time = time.time()
        
        self.task_type = 2
        self.task_id = ""
    
    def set_task(self, task_type: int, task_id: str):
        self.task_type = task_type
        self.task_id = task_id
    
    def set_bitrate(self, bitrate):
        if isinstance(bitrate, str) and bitrate.lower() == "flac":
            self.bitrate = "flac"
        else:
            try:
                self.bitrate = int(bitrate)
            except Exception:
                self.bitrate = 320000
    
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
        self.wait(2000)
    
    def _wait_if_paused(self):
        while self._paused and self._running:
            with self._pause_lock:
                self._pause_lock.wait(timeout=0.5)
    
    def _ensure_dir(self):
        self.download_path.mkdir(parents=True, exist_ok=True)
    
    def _check_exists(self, name: str, ext: str = None) -> bool:
        if ext is None:
            ext = "flac" if self.bitrate == "flac" else "mp3"
        return (self.download_path / f"{name}.{ext}").exists()
    
    def _save_file(self, name: str, data: bytes, ext: str = None) -> bool:
        try:
            if ext is None:
                ext = "flac" if self.bitrate == "flac" else "mp3"
            path = self.download_path / f"{name}.{ext}"
            with open(path, "wb") as f:
                f.write(data)
            
            with self._speed_lock:
                self._bytes_downloaded += len(data)
            
            file_size = path.stat().st_size
            if ext in ("mp3", "flac") and file_size < 1000 * 1024:
                self.log_message.emit(f"{name} - {i18n.tr('trial_deleted')}")
                path.unlink()
                return False
            
            return True
        except Exception as e:
            self.log_message.emit(f"{i18n.tr('save_fail')}: {e}")
            return False
    
    def _update_progress_safe(self, current, total):
        self._progress_mutex.lock()
        try:
            self.progress_update.emit(current, total)
        finally:
            self._progress_mutex.unlock()
    
    def _update_counters(self, success: bool):
        self._progress_mutex.lock()
        try:
            self._completed += 1
            if success:
                self._success += 1
        finally:
            self._progress_mutex.unlock()
    
    def _get_speed(self) -> str:
        with self._speed_lock:
            elapsed = time.time() - self._last_speed_time
            if elapsed > 0:
                speed = self._bytes_downloaded / elapsed
                self._bytes_downloaded = 0
                self._last_speed_time = time.time()
                
                if speed > 1024 * 1024:
                    return f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed > 1024:
                    return f"{speed / 1024:.1f} KB/s"
                else:
                    return f"{speed:.0f} B/s"
            return "0 B/s"
    
    def _get_task_items(self) -> list[dict[str, Any]]:
        if self.task_type == 1:  # 单曲
            return [{"id": self.task_id, "name": None, "type": "song"}]
        
        if self.task_type == 3:  # MV
            return [{"id": self.task_id, "name": None, "type": "mv"}]
        
        # 歌单
        self.log_message.emit(i18n.tr("fetch_playlist"))
        try:
            songs = self.api.get_playlist_detail(self.task_id)
        except APIError as e:
            self.log_message.emit(f"{i18n.tr('playlist_fetch_fail')}: {e}")
            return []
        
        if not songs:
            self.log_message.emit(i18n.tr("playlist_empty_msg"))
            return []
        
        # 断点续传过滤
        items = []
        skipped = 0
        for s in songs:
            sid = str(s["id"])
            if not self.history.is_completed(sid, "song", self.task_id):
                items.append({"id": sid, "name": s["name"], "type": "song"})
            else:
                skipped += 1
        
        if skipped > 0:
            self.log_message.emit(f"{i18n.tr('resume_skip')} {skipped} {i18n.tr('already_downloaded')}")
        
        if not items:
            self.log_message.emit(i18n.tr("playlist_all_done"))
        
        return items
    
    def _download_item(self, item: dict[str, Any], index: int, total: int) -> bool:
        self._wait_if_paused()
        if not self._running:
            return False
        
        item_id = item["id"]
        item_name = item.get("name")
        item_type = item["type"]
        
        try:
            if item_type == "song":
                return self._download_song(item_id, item_name, index, total)
            elif item_type == "mv":
                return self._download_mv(item_id, item_name, index, total)
            return False
        except Exception as e:
            self.log_message.emit(f"{i18n.tr('error')}: {e}")
            return False
    
    def _download_song(self, song_id: str, song_name: Optional[str], index: int, total: int) -> bool:
        if not song_name:
            detail = self.api.get_song_detail(song_id)
            song_name = detail["name"]
        
        song_name = clean_filename(song_name)
        self.song_start.emit(song_name, index, total)
        
        if self.history.is_completed(song_id, "song", self.task_id):
            self.log_message.emit(f"{song_name} - {i18n.tr('history_skip')}")
            return True
        
        if self._check_exists(song_name):
            self.log_message.emit(f"{song_name} - {i18n.tr('exists_skip')}")
            self.history.record(song_id, song_name, "song", "skipped", self.task_id)
            return True
        
        url = self.api.get_download_url(song_id, self.bitrate)
        if not url:
            self.log_message.emit(f"{song_name} - {i18n.tr('no_copyright')}")
            self.history.record(song_id, song_name, "song", "failed", self.task_id)
            return False
        
        data = self.api.download_song(url)
        if not data or len(data) < 1024:
            self.log_message.emit(f"{song_name} - {i18n.tr('data_error')}")
            self.history.record(song_id, song_name, "song", "failed", self.task_id)
            return False
        
        if self._save_file(song_name, data):
            self.log_message.emit(f"{song_name} - {i18n.tr('done')}")
            self.history.record(song_id, song_name, "song", "completed", self.task_id)
            return True
        else:
            self.history.record(song_id, song_name, "song", "failed", self.task_id)
            return False
    
    def _download_mv(self, mv_id: str, mv_name: Optional[str], index: int, total: int) -> bool:
        if not mv_name:
            mv_name = mv_id
        
        mv_name = clean_filename(mv_name)
        self.song_start.emit(mv_name, index, total)
        
        if self.history.is_completed(mv_id, "mv", self.task_id):
            self.log_message.emit(f"{mv_name} - {i18n.tr('history_skip')}")
            return True
        
        if self._check_exists(mv_name, "mp4"):
            self.log_message.emit(f"{mv_name} - {i18n.tr('exists_skip')}")
            self.history.record(mv_id, mv_name, "mv", "skipped", self.task_id)
            return True
        
        url = self.api.get_mv_download_url(mv_id)
        if not url:
            self.log_message.emit(f"{mv_name} - {i18n.tr('no_copyright')}")
            self.history.record(mv_id, mv_name, "mv", "failed", self.task_id)
            return False
        
        data = self.api.download_song(url)
        if not data or len(data) < 1024:
            self.log_message.emit(f"{mv_name} - {i18n.tr('data_error')}")
            self.history.record(mv_id, mv_name, "mv", "failed", self.task_id)
            return False
        
        if self._save_file(mv_name, data, "mp4"):
            self.log_message.emit(f"{mv_name} - {i18n.tr('done')}")
            self.history.record(mv_id, mv_name, "mv", "completed", self.task_id)
            return True
        else:
            self.history.record(mv_id, mv_name, "mv", "failed", self.task_id)
            return False
    
    def run(self):
        try:
            self.api_status.emit(False, i18n.tr("api_checking"))
            if not self.api.check_alive():
                self.api_status.emit(False, i18n.tr("api_offline"))
                self.log_message.emit(i18n.tr("api_not_started"))
                self.download_finished.emit(False)
                return
            
            self.api_status.emit(True, i18n.tr("api_online"))
            self._ensure_dir()
            
            # 统一获取任务
            items = self._get_task_items()
            if not items:
                self.download_finished.emit(False)
                return
            
            total = len(items)
            self._total = total
            self._completed = 0
            self._success = 0
            
            self._update_progress_safe(0, total)
            self.log_message.emit(
                f"{i18n.tr('playlist_total')} {format_number(total)} {i18n.tr('songs_count')}，"
                f"{i18n.tr('pending')} {format_number(total)} {i18n.tr('songs_count')}"
            )
            
            # 启动速度计时器
            speed_timer = QTimer()
            speed_timer.timeout.connect(self._emit_speed)
            speed_timer.start(1000)
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for i, item in enumerate(items, 1):
                    self._wait_if_paused()
                    if not self._running:
                        break
                    
                    future = executor.submit(self._download_item, item, i, total)
                    futures[future] = item
                    time.sleep(Config.DOWNLOAD_DELAY)
                
                for future in as_completed(futures):
                    self._wait_if_paused()
                    if not self._running:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    success = future.result()
                    self._update_counters(success)
                    self._update_progress_safe(self._completed, self._total)
                    self.speed_update.emit(self._get_speed())
            
            speed_timer.stop()
            
            self._update_progress_safe(self._total, self._total)
            self.log_message.emit(
                f"{i18n.tr('complete_result')} {self._success}/{total} "
                f"({i18n.tr('this_time')} {self._success}/{self._total})"
            )
            self.download_finished.emit(True)
            
        except Exception as e:
            self.log_message.emit(f"{i18n.tr('severe_error')}: {e}")
            self.download_finished.emit(False)
    
    def _emit_speed(self):
        self.speed_update.emit(self._get_speed())