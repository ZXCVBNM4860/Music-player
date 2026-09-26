from pathlib import Path
import random
import requests
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox,
    QLineEdit, QSplitter, QTabWidget, QMenu, QInputDialog, QComboBox,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, QSettings, pyqtSignal
from core.local_library import LocalLibrary, read_cover
from core.playlist_manager import PlaylistManager
from core.recent_manager import RecentManager
from core.audio_engine import AudioEngine
from core.auth_manager import AuthManager
from ui.cover_widget import CoverWidget
from ui.equalizer_widget import EqualizerWidget
from ui.playlist_widget import PlaylistWidget
from ui.netease_login_dialog import NeteaseLoginDialog
from ui.random_settings_dialog import RandomSettingsDialog
from utils.helpers import get_user_data_dir
from language import i18n


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


class LocalPlayerWindow(QMainWindow):
    _position_signal = pyqtSignal(int, int)
    _finished_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("local_player_title"))
        self.setMinimumSize(1100, 700)
        self.setStyleSheet("QMainWindow { background-color: #1e1e1e; }")

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
        try:
            self.random_seed = int(self._settings.value("random_seed", 0))
        except Exception:
            self.random_seed = 0

        self._shuffle_order = []
        self._shuffle_pos = 0

        self._engine = AudioEngine()
        self._position_signal.connect(self._on_engine_position)
        self._finished_signal.connect(self._handle_playback_finished)
        self._engine.on_position_changed = self._position_signal.emit
        self._engine.on_playback_finished = self._finished_signal.emit

        self._build_ui()

        if self.cookies:
            self._update_login_state()

        if self.library.load_cache():
            self._set_tracks(self.library.get_all())

    def _set_tracks(self, tracks):
        self._all_tracks = list(tracks)
        self.current_tracks = list(tracks)
        self._refresh_table()
        self._reset_shuffle()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

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
        main_layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_track_context_menu)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #141414;
                color: #eaeaea;
                border: 1px solid #333333;
                gridline-color: #2a2a2a;
            }
            QHeaderView::section {
                background-color: #1a1a1a;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #333333;
            }
        """)
        left_layout.addWidget(self.table, stretch=1)

        info = QHBoxLayout()
        self.now_label = QLabel(i18n.tr("not_playing"))
        self.now_label.setStyleSheet("color: #eaeaea; font-size: 11pt; font-weight: bold;")
        info.addWidget(self.now_label, stretch=1)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #888888; font-family: monospace;")
        info.addWidget(self.time_label)
        left_layout.addLayout(info)

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.progress.sliderReleased.connect(self._on_seek)
        self.progress.sliderMoved.connect(self._on_slider_move)
        self._dragging = False
        left_layout.addWidget(self.progress)

        ctrl = QHBoxLayout()

        self.btn_settings = QPushButton(i18n.tr("Settings"))
        self.btn_settings.setFixedSize(60, 36)
        self.btn_settings.setToolTip(i18n.tr("random_settings_title"))
        self.btn_settings.clicked.connect(self._open_random_settings)
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

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(i18n.tr("mode_seq"), "seq")
        self.mode_combo.addItem(i18n.tr("mode_shuffle"), "shuffle")
        self.mode_combo.addItem(i18n.tr("mode_repeat_one"), "repeat_one")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ctrl.addWidget(self.mode_combo)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setFixedWidth(120)
        self.volume.valueChanged.connect(self._on_volume)
        ctrl.addWidget(QLabel(i18n.tr("volume")))
        ctrl.addWidget(self.volume)
        left_layout.addLayout(ctrl)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(8)

        self.cover = CoverWidget(size=280)
        right_layout.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignCenter)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #141414;
                color: #aaaaaa;
                padding: 6px 12px;
                border: 1px solid #333333;
            }
            QTabBar::tab:selected {
                background-color: #2a2a2a;
                color: #ffffff;
            }
        """)

        self.equalizer = EqualizerWidget()
        self.equalizer.eq_changed.connect(self._on_eq_changed)
        tabs.addTab(self.equalizer, i18n.tr("equalizer"))

        self.playlist_widget = PlaylistWidget()
        self.playlist_widget.playlist_activated.connect(self._on_playlist_activated)
        tabs.addTab(self.playlist_widget, i18n.tr("playlist_tab"))

        recent_widget = QWidget()
        recent_layout = QVBoxLayout(recent_widget)
        self.recent_list = QTableWidget()
        self.recent_list.setColumnCount(2)
        self.recent_list.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        self.recent_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.recent_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_list.doubleClicked.connect(self._on_recent_double_click)
        self.recent_list.setStyleSheet("""
            QTableWidget {
                background-color: #141414;
                color: #eaeaea;
                border: 1px solid #333333;
                gridline-color: #2a2a2a;
            }
            QHeaderView::section {
                background-color: #1a1a1a;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #333333;
            }
        """)
        recent_layout.addWidget(self.recent_list)
        self.btn_clear_recent = QPushButton(i18n.tr("clear_recent"))
        self.btn_clear_recent.clicked.connect(self._clear_recent)
        recent_layout.addWidget(self.btn_clear_recent)
        tabs.addTab(recent_widget, i18n.tr("recent_played"))
        right_layout.addWidget(tabs, stretch=1)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        self._refresh_recent()

    def refresh_texts(self):
        self.setWindowTitle(i18n.tr("local_player_title"))
        self.btn_scan.setText(i18n.tr("scan_folder"))
        self.search_box.setPlaceholderText(i18n.tr("search_placeholder"))
        if not self.cookies:
            self.btn_netease.setText(i18n.tr("netease_login"))
        else:
            self._update_login_state()
        self.table.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        if not self.cookies and not self.current_tracks:
            self.now_label.setText(i18n.tr("not_playing"))
        self.mode_combo.setItemText(0, i18n.tr("mode_seq"))
        self.mode_combo.setItemText(1, i18n.tr("mode_shuffle"))
        self.mode_combo.setItemText(2, i18n.tr("mode_repeat_one"))
        self.recent_list.setHorizontalHeaderLabels([i18n.tr("col_title"), i18n.tr("col_duration")])
        self.btn_clear_recent.setText(i18n.tr("clear_recent"))
        self.btn_settings.setToolTip(i18n.tr("random_settings_title"))

    def _refresh_table(self):
        tracks = self.current_tracks
        self.table.setRowCount(len(tracks))
        for i, t in enumerate(tracks):
            self.table.setItem(i, 0, QTableWidgetItem(t.get("title", "")))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_time(t.get("duration", 0))))

    def _scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, i18n.tr("choose_music_folder"))
        if not folder:
            return

        def _progress(i, total):
            self.setWindowTitle(f"{i18n.tr('scanning')} {i}/{total}")

        count = self.library.scan(folder, progress_callback=_progress)
        self.library.save_cache()
        self.setWindowTitle(i18n.tr("local_player_title"))
        self._current_playlist_id = None
        self._set_tracks(self.library.get_all())
        QMessageBox.information(
            self, i18n.tr("scan_done"),
            i18n.tr("scan_found").format(count=count)
        )

    def _on_search(self, text):
        text = text.strip()
        if not text:
            self.current_tracks = list(self._all_tracks)
        else:
            kw = text.lower()
            self.current_tracks = [
                t for t in self._all_tracks
                if kw in str(t.get("title", "")).lower()
                or kw in str(t.get("artist", "")).lower()
                or kw in str(t.get("album", "")).lower()
            ]
        self._refresh_table()
        self._reset_shuffle()

    def _on_double_click(self, index):
        row = index.row()
        tracks = self.current_tracks
        if not tracks:
            return
        if row < 0 or row >= len(tracks):
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
        if path.startswith("netease://"):
            self._play_online(track)
            return

        self._play_file(path)

        artist = track.get("artist") or i18n.tr("unknown_artist")
        self.now_label.setText(f"{track['title']} - {artist}")
        self.table.selectRow(row)

        cover_data = read_cover(Path(path))
        self.cover.set_cover(cover_data)

        self.recent_manager.add(track)
        self._refresh_recent()

    def _play_file(self, path: str):
        if not self._engine.load(path):
            QMessageBox.warning(self, i18n.tr("error"), f"{i18n.tr('play_fail')}:\n{path}")
            return
        self._engine.set_eq_gains(self.equalizer.get_gains())
        self._engine.set_volume(self.volume.value() / 100)
        self._engine.play()
        self.btn_play.setText("⏸")

    def _play_online(self, track: dict):
        from core.api_client import APIClient
        from core.config import Config

        song_id = track["id"]
        cache_dir = get_user_data_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{song_id}.mp3"

        pic_url = track.get("pic_url", "")
        if pic_url:
            cover_dir = cache_dir / "covers"
            cover_dir.mkdir(parents=True, exist_ok=True)
            cover_file = cover_dir / f"{song_id}.jpg"
            if not cover_file.exists():
                try:
                    rc = requests.get(pic_url, timeout=10)
                    if rc.status_code == 200:
                        cover_file.write_bytes(rc.content)
                except Exception:
                    pass
            if cover_file.exists():
                try:
                    self.cover.set_cover(cover_file.read_bytes())
                except Exception:
                    pass

        if not cache_file.exists():
            self.now_label.setText(f"{track['title']} - {i18n.tr('buffering')}")
            self.btn_play.setText("...")
            self.btn_play.setEnabled(False)
            QApplication.processEvents()

            api = APIClient(Config.DEFAULT_API_URL)
            try:
                url = api.get_download_url(song_id, 320000)
            except Exception:
                url = None

            if not url:
                self.now_label.setText(i18n.tr("not_playing"))
                self.btn_play.setText("▶")
                self.btn_play.setEnabled(True)
                QMessageBox.warning(self, i18n.tr("error"), i18n.tr("preview_no_url"))
                return

            try:
                r = requests.get(url, stream=True, timeout=30)
                with open(cache_file, "wb") as f:
                    for chunk in r.iter_content(64 * 1024):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                if cache_file.exists():
                    try:
                        cache_file.unlink()
                    except Exception:
                        pass
                self.now_label.setText(i18n.tr("not_playing"))
                self.btn_play.setText("▶")
                self.btn_play.setEnabled(True)
                QMessageBox.warning(self, i18n.tr("error"), str(e))
                return

            self.btn_play.setEnabled(True)

        self._play_file(str(cache_file))

        artist = track.get("artist") or i18n.tr("unknown_artist")
        self.now_label.setText(f"{track['title']} - {artist}")
        self.table.selectRow(self.current_index)

        self.recent_manager.add(track)
        self._refresh_recent()

    def _toggle_play(self):
        if self._engine.is_playing:
            self._engine.pause()
            self.btn_play.setText("▶")
        else:
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
            if not self._shuffle_order or len(self._shuffle_order) != len(tracks):
                self._rebuild_shuffle_order(tracks)
            self._shuffle_pos = (self._shuffle_pos - 1) % len(self._shuffle_order)
            idx = self._shuffle_order[self._shuffle_pos]
        else:
            idx = (self.current_index - 1) % len(tracks)
        self._play_index(idx)

    def _play_next(self):
        tracks = self.current_tracks
        if not tracks:
            return
        if self.play_mode == "shuffle":
            if not self._shuffle_order or len(self._shuffle_order) != len(tracks):
                self._rebuild_shuffle_order(tracks)
            self._shuffle_pos = (self._shuffle_pos + 1) % len(self._shuffle_order)
            idx = self._shuffle_order[self._shuffle_pos]
        else:
            idx = (self.current_index + 1) % len(tracks)
        self._play_index(idx)

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
        n = len(tracks)
        if n == 0:
            self._shuffle_order = []
            self._shuffle_pos = 0
            return
        rng = random.Random(self.random_seed)
        order = list(range(n))
        rng.shuffle(order)
        self._shuffle_order = order
        self._shuffle_pos = 0

    def _reset_shuffle(self):
        self._shuffle_order = []
        self._shuffle_pos = 0
        if self.play_mode == "shuffle":
            self._rebuild_shuffle_order(self.current_tracks)

    def _open_random_settings(self):
        dlg = RandomSettingsDialog(self, self.random_seed)
        if dlg.exec():
            self.random_seed = dlg.get_seed()
            self._settings.setValue("random_seed", self.random_seed)
            self._rebuild_shuffle_order(self.current_tracks)

    def _on_volume(self, value):
        self._engine.set_volume(value / 100)

    def _on_slider_move(self, value):
        if self._engine.duration > 0:
            pos = int(value / 1000 * self._engine.duration)
            self._update_time_label(pos / self._engine.samplerate,
                                    self._engine.duration / self._engine.samplerate)

    def _on_seek(self):
        self._dragging = False
        if self._engine.duration > 0:
            frame = int(self.progress.value() / 1000 * self._engine.duration)
            self._engine.seek(frame)

    def _update_time_label(self, pos_sec, dur_sec):
        self.time_label.setText(f"{fmt_time(pos_sec)} / {fmt_time(dur_sec)}")

    def _on_engine_position(self, pos: int, total: int):
        if self._dragging or total <= 0:
            return
        self.progress.setValue(int(pos / total * 1000))
        self._update_time_label(pos / self._engine.samplerate,
                                total / self._engine.samplerate)

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
        for i, t in enumerate(items):
            self.recent_list.setItem(i, 0, QTableWidgetItem(t.get("title", "")))
            self.recent_list.setItem(i, 1, QTableWidgetItem(fmt_time(t.get("duration", 0))))

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
        menu.addAction(i18n.tr("add_to_playlist_menu"), lambda: self._add_to_playlist(track))
        menu.exec(self.table.mapToGlobal(pos))

    def _add_to_playlist(self, track: dict):
        names = self.playlist_manager.get_all_names()
        if not names:
            name, ok = QInputDialog.getText(self, i18n.tr("new_playlist"),
                                            i18n.tr("playlist_name_label"))
            if ok and name.strip():
                self.playlist_manager.create(name.strip())
                self.playlist_manager.add_track(name.strip(), track)
                self.playlist_widget.refresh()
            return

        name, ok = QInputDialog.getItem(self, i18n.tr("add_to_playlist_menu"),
                                        i18n.tr("select_existing"), names, 0, False)
        if ok and name:
            self.playlist_manager.add_track(name, track)
            self.playlist_widget.refresh()
            QMessageBox.information(self, i18n.tr("success_title"),
                                    i18n.tr("added_to_playlist").format(name=name))

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
            self.btn_netease.setText(i18n.tr("netease_logged_in_as").format(name=nickname))
        else:
            self.btn_netease.setText(i18n.tr("netease_logged_in"))
        self.btn_netease.setEnabled(True)

    def _on_netease_btn_clicked(self):
        if self.cookies:
            from ui.netease_playlist_dialog import NeteasePlaylistDialog
            from core.config import Config
            uid = self.user_info.get("userId") if self.user_info else None
            nickname = self.user_info.get("nickname", "") if self.user_info else ""

            current_song_id = None
            if 0 <= self.current_index < len(self.current_tracks):
                current_song_id = self.current_tracks[self.current_index].get("id")

            dlg = NeteasePlaylistDialog(
                self,
                api_url=Config.DEFAULT_API_URL,
                cookies=self.cookies,
                uid=uid,
                nickname=nickname,
                current_song_id=current_song_id,
                current_playlist_id=self._current_playlist_id,
            )
            dlg.playlist_songs_ready.connect(self._on_online_songs_ready)
            dlg.exec()
        else:
            self._open_netease_login()

    def _on_online_songs_ready(self, songs: list, playlist_id=None):
        if not songs:
            return
        self._current_playlist_id = playlist_id
        tracks = []
        for s in songs:
            tracks.append({
                "id": s["id"],
                "title": s["title"],
                "artist": s.get("artist", ""),
                "album": "",
                "duration": s.get("duration", 0),
                "pic_url": s.get("pic_url", ""),
                "path": f"netease://{s['id']}",
            })
        self._set_tracks(tracks)

    def closeEvent(self, event):
        try:
            self._engine.stop()
        except Exception:
            pass
        try:
            import shutil
            cache_dir = get_user_data_dir() / "cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
        except Exception:
            pass
        event.accept()