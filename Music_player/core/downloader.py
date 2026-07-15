"""下载"""

import time
import threading
from pathlib import Path
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QTimer
from core.api_client import APIClient, APIError
from core.config import Config
from utils.helpers import clean_filename, format_number
from language import i18n


class DownloadTask(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    speed_update = pyqtSignal(str)
    song_start = pyqtSignal(str, int, int)
    song_complete = pyqtSignal(str, bool)
    download_finished = pyqtSignal(bool)
    api_status = pyqtSignal(bool, str)
    byte_progress_update = pyqtSignal(int, int)   # (downloaded_bytes, total_bytes)
    
    def __init__(self, api_url: str, download_path: str, bitrate=320000):
        super().__init__()
        self.api = APIClient(api_url)
        self.download_path = Path(download_path)
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
        
        # 字节进度追踪
        self._total_bytes = 0
        self._downloaded_bytes = 0
        self._byte_progress_mutex = QMutex()
        
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
    
    def _add_downloaded_bytes(self, n: int):
        self._byte_progress_mutex.lock()
        try:
            self._downloaded_bytes += n
        finally:
            self._byte_progress_mutex.unlock()

    def _get_byte_progress(self) -> tuple[int, int]:
        self._byte_progress_mutex.lock()
        try:
            return self._downloaded_bytes, self._total_bytes
        finally:
            self._byte_progress_mutex.unlock()
    
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
        
        items = []
        for s in songs:
            items.append({"id": str(s["id"]), "name": s["name"], "type": "song"})
        
        return items
    
    def _prepare_item(self, item: dict[str, Any]) -> Optional[dict[str, Any]]:
        """预获取单个项目的下载链接和文件大小，返回准备就绪的信息或 None"""
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
    
    def _prepare_song(self, song_id: str, song_name: Optional[str]) -> Optional[dict[str, Any]]:
        if not song_name:
            try:
                detail = self.api.get_song_detail(song_id)
                song_name = detail["name"]
            except APIError:
                return None
        
        song_name = clean_filename(song_name)
        ext = "flac" if self.bitrate == "flac" else "mp3"
        
        # 本地已存在则跳过
        if self._check_exists(song_name, ext):
            self.log_message.emit(f"{song_name} - {i18n.tr('exists_skip')}")
            return None
        
        url = self.api.get_download_url(song_id, self.bitrate)
        if not url:
            self.log_message.emit(f"{song_name} - {i18n.tr('no_copyright')}")
            return None
        
        # 获取文件大小
        total_size = 0
        try:
            head = self.api.session.head(url, timeout=Config.TIMEOUT_API)
            total_size = int(head.headers.get("Content-Length", 0))
        except Exception:
            pass
        
        return {
            "id": song_id,
            "name": song_name,
            "type": "song",
            "url": url,
            "size": total_size,
            "ext": ext
        }
    
    def _prepare_mv(self, mv_id: str, mv_name: Optional[str]) -> Optional[dict[str, Any]]:
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
        
        return {
            "id": mv_id,
            "name": mv_name,
            "type": "mv",
            "url": url,
            "size": total_size,
            "ext": "mp4"
        }
    
    def _download_prepared_item(self, item: dict[str, Any], index: int, total: int) -> bool:
        """下载已预获取的项目"""
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
    
    def _download_prepared_song(self, item: dict[str, Any], index: int, total: int) -> bool:
        song_name = item["name"]
        url = item["url"]
        ext = item["ext"]
        
        self.song_start.emit(song_name, index, total)
        final_path = self.download_path / f"{song_name}.{ext}"
        
        def _on_chunk(chunk_size: int):
            self._add_downloaded_bytes(chunk_size)
            downloaded, total_bytes = self._get_byte_progress()
            if total_bytes > 0:
                self.byte_progress_update.emit(downloaded, total_bytes)
        
        if not self.api.download_file(url, final_path, progress_callback=_on_chunk):
            self.log_message.emit(f"{song_name} - {i18n.tr('data_error')}")
            # 下载失败，如果文件存在且很小则清理
            if final_path.exists():
                final_path.unlink()
            return False
        
        # 下载完成后检测是否为试听版
        file_size = final_path.stat().st_size
        if ext in ("mp3", "flac") and file_size < 1000 * 1024:
            self.log_message.emit(f"{song_name} - {i18n.tr('trial_deleted')}")
            final_path.unlink()
            return False
        
        with self._speed_lock:
            self._bytes_downloaded += file_size
        
        self.log_message.emit(f"{song_name} - {i18n.tr('done')}")
        return True
    
    def _download_prepared_mv(self, item: dict[str, Any], index: int, total: int) -> bool:
        mv_name = item["name"]
        url = item["url"]
        
        self.song_start.emit(mv_name, index, total)
        final_path = self.download_path / f"{mv_name}.mp4"
        
        def _on_chunk(chunk_size: int):
            self._add_downloaded_bytes(chunk_size)
            downloaded, total_bytes = self._get_byte_progress()
            if total_bytes > 0:
                self.byte_progress_update.emit(downloaded, total_bytes)
        
        if not self.api.download_file(url, final_path, progress_callback=_on_chunk):
            self.log_message.emit(f"{mv_name} - {i18n.tr('data_error')}")
            if final_path.exists():
                final_path.unlink()
            return False
        
        # 下载完成后检测
        file_size = final_path.stat().st_size
        if file_size < 1024:
            self.log_message.emit(f"{mv_name} - {i18n.tr('data_error')}")
            final_path.unlink()
            return False
        
        with self._speed_lock:
            self._bytes_downloaded += file_size
        
        self.log_message.emit(f"{mv_name} - {i18n.tr('done')}")
        return True
    
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
            
            # 获取任务列表
            raw_items = self._get_task_items()
            if not raw_items:
                self.download_finished.emit(False)
                return
            
            # 预获取下载链接和文件大小
            self.log_message.emit(i18n.tr("preparing_downloads"))
            
            prepared = []
            total_size = 0
            
            # 单线程预获取，避免API限流
            for i, item in enumerate(raw_items, 1):
                self._wait_if_paused()
                if not self._running:
                    self.download_finished.emit(False)
                    return
                
                result = self._prepare_item(item)
                if result:
                    prepared.append(result)
                    total_size += result["size"]
                
                # 只发log，不更新进度条
                self.log_message.emit(
                    f"{i18n.tr('preparing')} {i}/{len(raw_items)} "
                    f"({i18n.tr('valid')} {len(prepared)})"
                )
            
            if not prepared:
                self.log_message.emit(i18n.tr("no_downloadable_items"))
                self.download_finished.emit(False)
                return
            
            self._total_bytes = total_size
            self._downloaded_bytes = 0
            
            total = len(prepared)
            self._total = total
            self._completed = 0
            self._success = 0
            
            self.log_message.emit(
                f"{i18n.tr('ready_to_download')} {format_number(total)} {i18n.tr('songs_count')}，"
                f"{i18n.tr('total_size')} {self._fmt_size(total_size)}"
            )
            
            # 预获取完成，进度条归零，准备开始字节进度
            self.byte_progress_update.emit(0, total_size)
            
            # 真正下载
            # 启动速度计时器
            speed_timer = QTimer()
            speed_timer.timeout.connect(self._emit_speed)
            speed_timer.start(1000)
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for i, item in enumerate(prepared, 1):
                    self._wait_if_paused()
                    if not self._running:
                        break
                    
                    future = executor.submit(self._download_prepared_item, item, i, total)
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