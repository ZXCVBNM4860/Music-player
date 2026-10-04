# ui/local_player.py

import os
import random
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,QApplication,QComboBox,QFileDialog,QHBoxLayout,
    QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,
    QHeaderView,QInputDialog,QLabel,QLineEdit,QMainWindow,
    QMenu,QMessageBox,QPushButton,QSlider,QSplitter
)

from core.audio_engine import AudioEngine
from core.auth_manager import AuthManager
from core.config import Config
from core.local_library import LocalLibrary, read_cover
from core.playlist_manager import PlaylistManager
from core.recent_manager import RecentManager
from language import i18n
from ui.cover_widget import CoverWidget
from ui.equalizer_widget import EqualizerWidget
from ui.netease_login_dialog import NeteaseLoginDialog
from ui.playlist_widget import PlaylistWidget
from utils.helpers import get_user_data_dir


def fmt_time(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def read_bool(value, default=False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


def read_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _core_title(local: dict) -> str:
    title = (local.get("title") or "").strip()
    artist = (local.get("artist") or "").strip()

    if not title:
        return ""

    for sep in (" - ", " – ", " — "):
        if sep not in title:
            continue

        left, right = title.split(sep, 1)
        left_l = left.strip().lower()
        artist_l = artist.lower()

        if not artist or left_l == artist_l or artist_l in left_l or left_l in artist_l:
            title = right.strip()
        break

    return title.lower()


def _score_match(song_title: str, song_artist: str, local: dict) -> int:
    s_title = (song_title or "").lower().strip()
    if not s_title:
        return -1

    l_core = _core_title(local)
    if not l_core:
        return -1

    if l_core != s_title:
        return -1

    score = 1000

    s_artist = (song_artist or "").lower().strip()
    l_artist = (local.get("artist") or "").lower().strip()
    l_full = (local.get("title") or "").lower().strip()

    if s_artist:
        if l_artist and s_artist == l_artist:
            score += 500
        elif l_artist and (s_artist in l_artist or l_artist in s_artist):
            score += 200
        elif s_artist in l_full:
            score += 300

    return score


def find_local_match(song_title: str, song_artist: str, local_tracks: list) -> Optional[str]:
    best_score = -1
    best_path = None

    for local in local_tracks:
        score = _score_match(song_title, song_artist, local)
        if score > best_score:
            best_score = score
            best_path = local.get("path")

    return best_path if best_score > 0 else None


class OnlineTrackFetcher(QThread):
    cover_ready = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        api_url: str,
        song_id: str,
        cache_file: Path,
        cover_file: Optional[Path] = None,
        pic_url: str = "",
    ):
        super().__init__()
        self.api_url = api_url.rstrip("/")
        self.song_id = song_id
        self.cache_file = Path(cache_file)
        self.cover_file = Path(cover_file) if cover_file else None
        self.pic_url = pic_url
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
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
        from core.api_client import APIClient

        api = APIClient(self.api_url)

        try:
            url = api.get_download_url(self.song_id, 320000)
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

        try:
            tmp_file.replace(self.cache_file)
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
        self.api_url = api_url
        self.cache_dir = Path(cache_dir)
        self.songs = songs
        self.threads = max(1, min(threads, Config.FAST_DOWNLOAD_THREADS_MAX))
        self.local_library_path = local_library_path or ""
        self._cancelled = False
        self._local_tracks = []

    def cancel(self):
        self._cancelled = True

    def _load_local_tracks(self):
        if not self.local_library_path:
            return

        if not os.path.isdir(self.local_library_path):
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

        title = song.get("title", "")
        artist = song.get("artist", "")

        return find_local_match(title, artist, self._local_tracks) is not None

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from core.api_client import APIClient

        self._load_local_tracks()

        if self._cancelled:
            self.finished_all.emit(0, len(self.songs))
            return

        api = APIClient(self.api_url)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        covers_dir = self.cache_dir / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)

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

            cache_file = self.cache_dir / f"{song_id}.mp3"
            if cache_file.exists():
                return True

            try:
                url = api.get_download_url(song_id, 320000)
            except Exception:
                url = None

            if not url or self._cancelled:
                return False

            pic_url = song.get("pic_url", "")
            if pic_url:
                cover_file = covers_dir / f"{song_id}.jpg"
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
                return api.download_file(url, cache_file)
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


class LocalPlayerWindow(QMainWindow):
    _position_signal = pyqtSignal(int, int)
    _finished_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("localPlayer")
        self.setWindowTitle(i18n.tr("local_player_title"))
        self.setMinimumSize(1100, 700)

        self.library = LocalLibrary()
        self.playlist_manager = PlaylistManager()
        self.recent_manager = RecentManager()

        self.auth_manager = AuthManager()
        self.cookies = self.auth_manager.cookies
        self.user_info = self.auth_manager.user_info

        self.current_index = -1
        self._all_tracks = []
        self.current_tracks = []
        self._current_playlist_id = None
        self.play_mode = "seq"

        self._settings = QSettings("netease_downloader", "settings")
        self.random_seed = self._load_random_seed()

        self._shuffle_order = []
        self._shuffle_pos = 0

        self._online_fetcher: Optional[OnlineTrackFetcher] = None
        self._online_fetchers_pending = []
        self._quick_worker: Optional[QuickDownloadWorker] = None

        self._engine = AudioEngine()
        self._position_signal.connect(self._on_engine_position)
        self._finished_signal.connect(self._handle_playback_finished)
        self._engine.on_position_changed = self._position_signal.emit
        self._engine.on_playback_finished = self._finished_signal.emit

        self._build_ui()

        self._reload_settings()
        self._load_local_library_cache()

        if self.cookies:
            self._update_login_state()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        main_layout.addLayout(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        self._refresh_recent()

    def _build_top_bar(self) -> QHBoxLayout:
        top = QHBoxLayout()

        self.btn_scan = QPushButton(i18n.tr("scan_folder"))
        self.btn_scan.clicked.connect(self._scan_folder)
        top.addWidget(self.btn_scan)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(i18n.tr("search_placeholder"))
        self.search_box.textChanged.connect(self._on_search)
        top.addWidget(self.search_box, stretch=1)

        self.btn_netease = QPushButton(i18n.tr("netease_login"))
        self.btn_netease.clicked.connect(self._on_netease_btn_clicked)
        top.addWidget(self.btn_netease)

        return top

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.table = self._create_track_table()
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_track_context_menu)
        layout.addWidget(self.table, stretch=1)

        info = QHBoxLayout()

        self.now_label = QLabel(i18n.tr("not_playing"))
        self.now_label.setObjectName("nowPlaying")
        info.addWidget(self.now_label, stretch=1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("playerTime")
        info.addWidget(self.time_label)

        layout.addLayout(info)

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(self._on_slider_pressed)
        self.progress.sliderReleased.connect(self._on_seek)
        self.progress.sliderMoved.connect(self._on_slider_move)
        self._dragging = False
        layout.addWidget(self.progress)

        layout.addLayout(self._build_playback_controls())
        return panel

    def _create_track_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setObjectName("playerTable")
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _build_playback_controls(self) -> QHBoxLayout:
        ctrl = QHBoxLayout()

        self.btn_settings = QPushButton(i18n.tr("Settings"))
        self.btn_settings.setFixedSize(60, 36)
        self.btn_settings.setToolTip(i18n.tr("settings_player_title"))
        self.btn_settings.clicked.connect(self._open_settings)
        ctrl.addWidget(self.btn_settings)

        ctrl.addStretch()

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedSize(48, 48)
        self.btn_prev.clicked.connect(self._play_prev)
        ctrl.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(64, 64)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_play.setStyleSheet("font-size: 20px; border-radius: 32px;")
        ctrl.addWidget(self.btn_play)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(48, 48)
        self.btn_next.clicked.connect(self._play_next)
        ctrl.addWidget(self.btn_next)

        ctrl.addStretch()

        self.btn_favorite = QPushButton(i18n.tr("favorite"))
        self.btn_favorite.setFixedHeight(36)
        self.btn_favorite.setMinimumWidth(56)
        self.btn_favorite.setToolTip(i18n.tr("favorite"))
        self.btn_favorite.clicked.connect(self._favorite_current)
        ctrl.addWidget(self.btn_favorite)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(i18n.tr("mode_seq"), "seq")
        self.mode_combo.addItem(i18n.tr("mode_shuffle"), "shuffle")
        self.mode_combo.addItem(i18n.tr("mode_repeat_one"), "repeat_one")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ctrl.addWidget(self.mode_combo)

        ctrl.addWidget(QLabel(i18n.tr("volume")))

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setFixedWidth(120)
        self.volume.valueChanged.connect(self._on_volume)
        ctrl.addWidget(self.volume)

        return ctrl

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(8)

        self.cover = CoverWidget(size=280)
        layout.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignCenter)

        tabs = QTabWidget()
        tabs.setObjectName("playerTabs")

        self.equalizer = EqualizerWidget()
        self.equalizer.eq_changed.connect(self._on_eq_changed)
        tabs.addTab(self.equalizer, i18n.tr("equalizer"))

        self.playlist_widget = PlaylistWidget()
        self.playlist_widget.playlist_activated.connect(self._on_playlist_activated)
        tabs.addTab(self.playlist_widget, i18n.tr("playlist_tab"))

        tabs.addTab(self._build_recent_tab(), i18n.tr("recent_played"))

        layout.addWidget(tabs, stretch=1)
        return panel

    def _build_recent_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.recent_list = QTableWidget()
        self.recent_list.setObjectName("playerTable")
        self.recent_list.setColumnCount(2)
        self.recent_list.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        self.recent_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.recent_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_list.doubleClicked.connect(self._on_recent_double_click)
        layout.addWidget(self.recent_list)

        self.btn_clear_recent = QPushButton(i18n.tr("clear_recent"))
        self.btn_clear_recent.clicked.connect(self._clear_recent)
        layout.addWidget(self.btn_clear_recent)

        return widget

    def refresh_texts(self):
        self.setWindowTitle(i18n.tr("local_player_title"))
        self.btn_scan.setText(i18n.tr("scan_folder"))
        self.search_box.setPlaceholderText(i18n.tr("search_placeholder"))

        if self.cookies:
            self._update_login_state()
        else:
            self.btn_netease.setText(i18n.tr("netease_login"))

        self.table.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])

        if not self.cookies and not self.current_tracks:
            self.now_label.setText(i18n.tr("not_playing"))

        self.mode_combo.setItemText(0, i18n.tr("mode_seq"))
        self.mode_combo.setItemText(1, i18n.tr("mode_shuffle"))
        self.mode_combo.setItemText(2, i18n.tr("mode_repeat_one"))

        self.recent_list.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        self.btn_clear_recent.setText(i18n.tr("clear_recent"))
        self.btn_settings.setText(i18n.tr("Settings"))
        self.btn_settings.setToolTip(i18n.tr("settings_player_title"))
        self.btn_favorite.setText(i18n.tr("favorite"))
        self.btn_favorite.setToolTip(i18n.tr("favorite"))

    def _reload_settings(self):
        self._auto_scan_local = read_bool(
            self._settings.value("auto_scan_local", Config.DEFAULT_AUTO_SCAN)
        )
        self._local_library_path = self._settings.value(
            "local_library_path", Config.DEFAULT_LOCAL_LIBRARY_PATH
        ) or ""
        self._fast_download = read_bool(
            self._settings.value("fast_download", Config.DEFAULT_FAST_DOWNLOAD)
        )
        self._fast_download_threads = read_int(
            self._settings.value("fast_download_threads", Config.DEFAULT_FAST_DOWNLOAD_THREADS),
            Config.DEFAULT_FAST_DOWNLOAD_THREADS,
        )
        self._cache_max_mb = read_int(
            self._settings.value("cache_max_mb", Config.DEFAULT_CACHE_MAX_MB),
            Config.DEFAULT_CACHE_MAX_MB,
        )

    def _load_local_library_cache(self):
        if self.library.load_cache():
            self._set_tracks(self.library.get_all())

    def _open_settings(self):
        from ui.player_settings_dialog import PlayerSettingsDialog

        dialog = PlayerSettingsDialog(self)
        if not dialog.exec():
            return

        self._reload_settings()

        self.random_seed = dialog.get_random_seed()
        self._rebuild_shuffle_order(self.current_tracks)

    def _set_tracks(self, tracks):
        self._all_tracks = list(tracks)
        self.current_tracks = list(tracks)
        self._refresh_table()
        self._reset_shuffle()

    def set_online_tracks(self, songs: list):
        if not songs:
            return

        tracks = [
            {
                "id": song["id"],
                "title": song["title"],
                "artist": song.get("artist", ""),
                "album": "",
                "duration": song.get("duration", 0),
                "pic_url": song.get("pic_url", ""),
                "path": song.get("path") or f"netease://{song['id']}",
            }
            for song in songs
        ]

        self._set_tracks(tracks)

        if self._fast_download:
            self._start_quick_download(tracks)

    def _start_quick_download(self, tracks):
        if not tracks:
            return

        if self._quick_worker and self._quick_worker.isRunning():
            self._quick_worker.cancel()
            self._quick_worker.wait(1500)

        cache_dir = get_user_data_dir() / "cache"

        self._quick_worker = QuickDownloadWorker(
            api_url=Config.DEFAULT_API_URL,
            cache_dir=cache_dir,
            songs=tracks,
            threads=self._fast_download_threads,
            local_library_path=self._local_library_path,
        )
        self._quick_worker.start()

    def _refresh_table(self):
        tracks = self.current_tracks
        self.table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            self.table.setItem(row, 0, QTableWidgetItem(track.get("title", "")))
            self.table.setItem(row, 1, QTableWidgetItem(fmt_time(track.get("duration", 0))))

    def _scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, i18n.tr("choose_music_folder"))
        if not folder:
            return

        def on_progress(current, total):
            self.setWindowTitle(f"{i18n.tr('scanning')} {current}/{total}")

        count = self.library.scan(folder, progress_callback=on_progress)
        self.library.save_cache()

        self.setWindowTitle(i18n.tr("local_player_title"))
        self._current_playlist_id = None
        self._set_tracks(self.library.get_all())

        QMessageBox.information(
            self,
            i18n.tr("scan_done"),
            i18n.tr("scan_found").format(count=count),
        )

    def _on_search(self, text):
        text = text.strip()

        if not text:
            self.current_tracks = list(self._all_tracks)
        else:
            keyword = text.lower()
            self.current_tracks = [
                track
                for track in self._all_tracks
                if keyword in str(track.get("title", "")).lower()
                or keyword in str(track.get("artist", "")).lower()
                or keyword in str(track.get("album", "")).lower()
            ]

        self._refresh_table()
        self._reset_shuffle()

    def _on_double_click(self, index):
        row = index.row()
        tracks = self.current_tracks

        if not tracks or row < 0 or row >= len(tracks):
            return

        if self.play_mode == "shuffle" and self._shuffle_order:
            try:
                self._shuffle_pos = self._shuffle_order.index(row)
            except ValueError:
                self._shuffle_pos = 0

        self._play_index(row)

    def _play_index(self, row: int):
        tracks = self.current_tracks

        if row < 0 or row >= len(tracks):
            return

        self.current_index = row
        track = tracks[row]
        path = str(track.get("path", ""))

        if self._auto_scan_local and self._local_library_path:
            local_path = self._find_local_match(track)
            if local_path:
                path = local_path

        if path.startswith("netease://"):
            self._play_online(track)
            return

        self._play_local_track(track, path)

    def _find_local_match(self, track: dict) -> Optional[str]:
        title = track.get("title", "")
        artist = track.get("artist", "")

        path = find_local_match(title, artist, self.library.get_all())

        if path:
            return path

        if self._local_library_path and os.path.isdir(self._local_library_path):
            try:
                temp = LocalLibrary()
                temp.scan(self._local_library_path)
                return find_local_match(title, artist, temp.get_all())
            except Exception:
                return None

        return None

    def _play_local_track(self, track: dict, path: str):
        self._play_file(path)

        artist = track.get("artist") or i18n.tr("unknown_artist")
        self.now_label.setText(f"{track['title']} - {artist}")
        self.table.selectRow(self.current_index)

        cover_data = read_cover(Path(path))
        self.cover.set_cover(cover_data)

        self.recent_manager.add(track)
        self._refresh_recent()

    def _play_file(self, path: str):
        if not self._engine.load(path):
            QMessageBox.warning(
                self,
                i18n.tr("error"),
                f"{i18n.tr('play_fail')}:\n{path}",
            )
            return

        self._engine.set_eq_gains(self.equalizer.get_gains())
        self._engine.set_volume(self.volume.value() / 100)
        self._engine.play()
        self.btn_play.setText("⏸")

    def _play_online(self, track: dict):
        song_id = track["id"]
        cache_dir = get_user_data_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_file = cache_dir / f"{song_id}.mp3"
        pic_url = track.get("pic_url", "")
        cover_file = cache_dir / "covers" / f"{song_id}.jpg" if pic_url else None

        if cache_file.exists():
            self._play_cached_online(track, cache_file, cover_file)
            return

        self._start_online_fetch(track, song_id, cache_file, cover_file, pic_url)

    def _play_cached_online(self, track: dict, cache_file: Path, cover_file):
        if cover_file and cover_file.exists():
            try:
                self.cover.set_cover(cover_file.read_bytes())
            except Exception:
                pass

        self._play_file(str(cache_file))

        artist = track.get("artist") or i18n.tr("unknown_artist")
        self.now_label.setText(f"{track['title']} - {artist}")
        self.table.selectRow(self.current_index)

        self.recent_manager.add(track)
        self._refresh_recent()

    def _start_online_fetch(
        self,
        track: dict,
        song_id: str,
        cache_file: Path,
        cover_file,
        pic_url: str,
    ):
        self._cancel_online_fetcher()

        self.now_label.setText(f"{track['title']} - {i18n.tr('buffering')}")
        self.btn_play.setText("...")
        self.btn_play.setEnabled(False)

        fetcher = OnlineTrackFetcher(
            api_url=Config.DEFAULT_API_URL,
            song_id=song_id,
            cache_file=cache_file,
            cover_file=cover_file,
            pic_url=pic_url,
        )
        self._online_fetcher = fetcher

        fetcher.cover_ready.connect(lambda path: self._on_online_cover(fetcher, path))
        fetcher.finished_ok.connect(lambda path: self._on_online_ok(fetcher, track, path))
        fetcher.failed.connect(lambda err: self._on_online_failed(fetcher, err))
        fetcher.start()

    def _on_online_cover(self, fetcher, path):
        if self._online_fetcher is not fetcher:
            return
        try:
            self.cover.set_cover(Path(path).read_bytes())
        except Exception:
            pass

    def _on_online_ok(self, fetcher, track: dict, path: str):
        if self._online_fetcher is not fetcher:
            return

        self._online_fetcher = None
        self.btn_play.setEnabled(True)
        self._play_file(path)

        artist = track.get("artist") or i18n.tr("unknown_artist")
        self.now_label.setText(f"{track['title']} - {artist}")
        self.table.selectRow(self.current_index)

        self.recent_manager.add(track)
        self._refresh_recent()

    def _on_online_failed(self, fetcher, err):
        if self._online_fetcher is not fetcher:
            return

        self._online_fetcher = None
        self.btn_play.setEnabled(True)
        self.btn_play.setText("▶")
        self.now_label.setText(i18n.tr("not_playing"))

        message = i18n.tr("preview_no_url") if err == "preview_no_url" else str(err)
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _cancel_online_fetcher(self):
        fetcher = self._online_fetcher
        self._online_fetcher = None

        if fetcher is not None:
            fetcher.cancel()
            self._online_fetchers_pending.append(fetcher)

        self._online_fetchers_pending = [
            f for f in self._online_fetchers_pending if f.isRunning()
        ]

    def _enforce_cache_limit(self):
        if self._cache_max_mb <= 0:
            return

        try:
            cache_dir = get_user_data_dir() / "cache"
            if not cache_dir.exists():
                return

            limit_bytes = self._cache_max_mb * 1024 * 1024
            total = 0
            files = []

            for path in cache_dir.rglob("*"):
                if not path.is_file():
                    continue
                size = path.stat().st_size
                total += size
                files.append((path.stat().st_mtime, size, path))

            if total <= limit_bytes:
                return

            files.sort()
            for _, size, path in files:
                if total <= limit_bytes:
                    break
                try:
                    path.unlink()
                    total -= size
                except Exception:
                    pass
        except Exception:
            pass

    def _toggle_play(self):
        if self._engine.is_playing:
            self._engine.pause()
            self.btn_play.setText("▶")
            return

        if self.current_index < 0 and self.current_tracks:
            self._play_index(0)
        else:
            self._engine.play(self._engine.position)
            self.btn_play.setText("⏸")

    def _play_prev(self):
        tracks = self.current_tracks
        if not tracks:
            return

        if self.play_mode == "shuffle":
            index = self._step_shuffle(-1)
        else:
            index = (self.current_index - 1) % len(tracks)

        self._play_index(index)

    def _play_next(self):
        tracks = self.current_tracks
        if not tracks:
            return

        if self.play_mode == "shuffle":
            index = self._step_shuffle(1)
        else:
            index = (self.current_index + 1) % len(tracks)

        self._play_index(index)

    def _step_shuffle(self, delta: int) -> int:
        tracks = self.current_tracks

        if not self._shuffle_order or len(self._shuffle_order) != len(tracks):
            self._rebuild_shuffle_order(tracks)

        self._shuffle_pos = (self._shuffle_pos + delta) % len(self._shuffle_order)
        return self._shuffle_order[self._shuffle_pos]

    def _on_mode_changed(self, index: int):
        data = self.mode_combo.itemData(index)
        if not data:
            return

        self.play_mode = data

        if data == "shuffle":
            self._rebuild_shuffle_order(self.current_tracks)

            if self.current_index >= 0 and self._shuffle_order:
                try:
                    self._shuffle_pos = self._shuffle_order.index(self.current_index)
                except ValueError:
                    self._shuffle_pos = 0

    def _rebuild_shuffle_order(self, tracks):
        count = len(tracks)

        if count == 0:
            self._shuffle_order = []
            self._shuffle_pos = 0
            return

        rng = random.Random(self.random_seed)
        order = list(range(count))
        rng.shuffle(order)

        self._shuffle_order = order
        self._shuffle_pos = 0

    def _reset_shuffle(self):
        self._shuffle_order = []
        self._shuffle_pos = 0

        if self.play_mode == "shuffle":
            self._rebuild_shuffle_order(self.current_tracks)

    def _load_random_seed(self) -> int:
        try:
            return int(self._settings.value("random_seed", 0))
        except Exception:
            return 0

    def _on_volume(self, value):
        self._engine.set_volume(value / 100)

    def _on_slider_pressed(self):
        self._dragging = True

    def _on_slider_move(self, value):
        if self._engine.duration <= 0:
            return

        pos = int(value / 1000 * self._engine.duration)
        self._update_time_label(
            pos / self._engine.samplerate,
            self._engine.duration / self._engine.samplerate,
        )

    def _on_seek(self):
        self._dragging = False

        if self._engine.duration <= 0:
            return

        frame = int(self.progress.value() / 1000 * self._engine.duration)
        self._engine.seek(frame)

    def _update_time_label(self, pos_sec, dur_sec):
        self.time_label.setText(f"{fmt_time(pos_sec)} / {fmt_time(dur_sec)}")

    def _on_engine_position(self, pos: int, total: int):
        if self._dragging or total <= 0:
            return

        self.progress.setValue(int(pos / total * 1000))
        self._update_time_label(
            pos / self._engine.samplerate,
            total / self._engine.samplerate,
        )

    def _handle_playback_finished(self):
        if self.play_mode == "repeat_one":
            self._engine.play(0)
            self.btn_play.setText("⏸")
        else:
            self._play_next()

    def _on_eq_changed(self, gains: list):
        self._engine.set_eq_gains(gains)

    def _on_playlist_activated(self, tracks: list):
        if not tracks:
            return

        self._current_playlist_id = None
        self._set_tracks(tracks)

    def _refresh_recent(self):
        items = self.recent_manager.get_all()
        self.recent_list.setRowCount(len(items))

        for row, track in enumerate(items):
            self.recent_list.setItem(row, 0, QTableWidgetItem(track.get("title", "")))
            self.recent_list.setItem(row, 1, QTableWidgetItem(fmt_time(track.get("duration", 0))))

    def _on_recent_double_click(self, index):
        items = self.recent_manager.get_all()
        row = index.row()

        if 0 <= row < len(items):
            self._current_playlist_id = None
            self._set_tracks(items)
            self._play_index(row)

    def _clear_recent(self):
        self.recent_manager.clear()
        self._refresh_recent()

    def _show_track_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        tracks = self.current_tracks

        if row >= len(tracks):
            return

        track = tracks[row]

        menu = QMenu(self)
        menu.addAction(i18n.tr("play_menu"), lambda: self._play_index(row))
        menu.addSeparator()
        menu.addAction(i18n.tr("copy_song_name"), lambda: self._copy_song_name(track))
        menu.addAction(i18n.tr("add_to_playlist_menu"), lambda: self._add_to_playlist(track))
        menu.exec(self.table.mapToGlobal(pos))

    def _copy_song_name(self, track: dict):
        title = track.get("title", "")
        if title:
            QApplication.clipboard().setText(title)

    def _add_to_playlist(self, track: dict):
        names = self.playlist_manager.get_all_names()

        if not names:
            self._create_playlist_with_track(track)
            return

        name, ok = QInputDialog.getItem(
            self,
            i18n.tr("add_to_playlist_menu"),
            i18n.tr("select_existing"),
            names,
            0,
            False,
        )

        if ok and name:
            self.playlist_manager.add_track(name, track)
            self.playlist_widget.refresh()
            QMessageBox.information(
                self,
                i18n.tr("success_title"),
                i18n.tr("added_to_playlist").format(name=name),
            )

    def _create_playlist_with_track(self, track: dict):
        name, ok = QInputDialog.getText(
            self,
            i18n.tr("new_playlist"),
            i18n.tr("playlist_name_label"),
        )

        if ok and name.strip():
            name = name.strip()
            self.playlist_manager.create(name)
            self.playlist_manager.add_track(name, track)
            self.playlist_widget.refresh()

    def _favorite_current(self):
        if not self.cookies:
            QMessageBox.warning(
                self, i18n.tr("notice"), i18n.tr("favorite_need_login")
            )
            return

        tracks = self.current_tracks
        if not (0 <= self.current_index < len(tracks)):
            return

        track = tracks[self.current_index]
        song_id = track.get("id")
        if not song_id:
            return

        try:
            session = requests.Session()
            session.cookies.update(self.cookies)
            response = session.get(
                f"{Config.DEFAULT_API_URL}/like",
                params={"id": song_id, "like": "true"},
                timeout=10,
            )
            data = response.json()
            if data.get("code") == 200:
                QMessageBox.information(
                    self, i18n.tr("success_title"), i18n.tr("favorite_added")
                )
            else:
                QMessageBox.warning(
                    self, i18n.tr("error"), i18n.tr("favorite_failed")
                )
        except Exception:
            QMessageBox.warning(
                self, i18n.tr("error"), i18n.tr("favorite_failed")
            )

    def _open_netease_login(self):
        dialog = NeteaseLoginDialog(self)

        if dialog.exec():
            self.cookies = dialog.get_cookies()
            self.user_info = dialog.get_user_info()

            if self.cookies:
                self.auth_manager.save(self.cookies, self.user_info)
                self._update_login_state()

    def _update_login_state(self):
        if not self.cookies:
            return

        nickname = ""
        if self.user_info:
            nickname = self.user_info.get("nickname", "") or ""

        if nickname:
            self.btn_netease.setText(
                i18n.tr("netease_logged_in_as").format(name=nickname)
            )
        else:
            self.btn_netease.setText(i18n.tr("netease_logged_in"))

        self.btn_netease.setEnabled(True)

    def _on_netease_btn_clicked(self):
        if not self.cookies:
            self._open_netease_login()
            return

        from ui.netease_playlist_dialog import NeteasePlaylistDialog

        uid = self.user_info.get("userId") if self.user_info else None
        nickname = self.user_info.get("nickname", "") if self.user_info else ""

        dialog = NeteasePlaylistDialog(
            self,
            api_url=Config.DEFAULT_API_URL,
            cookies=self.cookies,
            uid=uid,
            nickname=nickname,
        )
        dialog.playlist_songs_ready.connect(self._on_online_songs_ready)
        dialog.exec()

    def _on_online_songs_ready(self, songs: list, playlist_id=None):
        if not songs:
            return

        self._current_playlist_id = playlist_id
        self.set_online_tracks(songs)

    def closeEvent(self, event):
        self._shutdown_online_fetchers()
        self._shutdown_quick_worker()
        self._shutdown_engine()
        self._enforce_cache_limit()
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

    def _shutdown_quick_worker(self):
        if self._quick_worker and self._quick_worker.isRunning():
            self._quick_worker.cancel()
            self._quick_worker.wait(1500)

    def _shutdown_engine(self):
        try:
            self._engine.stop()
        except Exception:
            pass