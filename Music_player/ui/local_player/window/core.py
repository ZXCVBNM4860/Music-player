# ui/local_player/window/core.py

import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import pyqtSignal, QSettings
from PyQt6.QtWidgets import QMainWindow

from core.config import Config
from core.local_library import LocalLibrary
from core.player_controller import PlayerController
from core.netease_manager import NeteaseManager
from core.playlist_manager import PlaylistManager
from core.recent_manager import RecentManager
from core.smtc_manager import SMTCManager
from language import i18n
from ui.local_player.desktop_lyric import DesktopLyricWindow
from ui.workers import run_async
from utils.helpers import get_cache_dir

from .ui_mixin import UIMixin
from .playback_mixin import PlaybackMixin
from .lyric_mixin import LyricMixin
from .playlist_mixin import PlaylistMixin
from ..utils import _cache_file_name

class LocalPlayerWindow(UIMixin, PlaybackMixin, LyricMixin, PlaylistMixin, QMainWindow):
    _scan_progress_signal = pyqtSignal(int, int)

    def __init__(self, parent=None, api_url=None):
        super().__init__(parent)

        self.api_url = api_url or Config.DEFAULT_API_URL

        self.setObjectName("localPlayer")
        self.setWindowTitle(i18n.tr("local_player_title"))
        self.setMinimumSize(1100, 700)

        self.library = LocalLibrary()
        self.playlist_manager = PlaylistManager()
        self.recent_manager = RecentManager()

        self.netease = NeteaseManager(self.api_url)
        self.cookies = self.netease.auth.cookies
        self.user_info = self.netease.auth.user_info

        self.player = PlayerController(self)
        self.player.position_changed.connect(self._on_engine_position)
        self.player.playback_finished.connect(self._handle_playback_finished)
        
        self.smtc = SMTCManager(self)
        self.smtc.play_pause_signal.connect(self._toggle_play)
        self.smtc.next_signal.connect(self._play_next)
        self.smtc.prev_signal.connect(self._play_prev)

        self.desktop_lyric = DesktopLyricWindow()
        self.desktop_lyric.hide()

        self.current_index = -1
        self._all_tracks = []
        self.current_tracks = []
        self._current_playlist_id = None
        self.play_mode = "seq"

        self._settings = QSettings("netease_downloader", "settings")
        self.random_seed = self._load_random_seed()

        self._shuffle_order = []
        self._shuffle_pos = 0

        self._online_fetcher = None
        self._online_fetchers_pending = []
        self._cover_fetchers = []
        self._quick_worker = None

        self._pending_song_id = None
        self._pending_playlist_name = ""
        self._comment_dialog = None
        self._translate_settings = {
            "enabled": False, "source": "auto", "target": "en",
        }

        self._build_ui()
        self._reload_settings()
        self._load_local_library_cache()
        self._update_login_state()
        
        self._scan_progress_signal.connect(self._on_scan_progress)

    def _load_random_seed(self) -> int:
        try:
            return int(self._settings.value("random_seed", 0))
        except Exception:
            return 0

    def _scan_worker(self, folder):
        library = LocalLibrary()
        library.scan(folder, progress_callback=self._scan_progress_signal.emit)
        library.save_cache()
        return library

    def closeEvent(self, event):
        if self._comment_dialog is not None:
            self._comment_dialog.close()
        if hasattr(self, "desktop_lyric"):
            self.desktop_lyric.close()
        self._shutdown_online_fetchers()
        self._shutdown_cover_fetchers()
        self._shutdown_quick_worker()
        self.player.stop()
        threading.Thread(target=self._enforce_cache_limit, daemon=True).start()
        event.accept()

    def _shutdown_online_fetchers(self):
        if self._online_fetcher is not None:
            self._online_fetcher.cancel()
        pending = [self._online_fetcher] + self._online_fetchers_pending
        for fetcher in pending:
            if fetcher is not None and fetcher.isRunning():
                fetcher.wait(1500)
        self._online_fetcher = None
        self._online_fetchers_pending.clear()

    def _shutdown_cover_fetchers(self):
        for fetcher in self._cover_fetchers[:]:
            fetcher.cancel()
            if fetcher.isRunning():
                fetcher.wait(500)
        self._cover_fetchers.clear()

    def _shutdown_quick_worker(self):
        if self._quick_worker and self._quick_worker.isRunning():
            self._quick_worker.cancel()
            self._quick_worker.wait(1500)