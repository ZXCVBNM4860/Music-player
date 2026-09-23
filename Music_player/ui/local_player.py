# ui\local_player.py

from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox,
    QLineEdit, QSplitter, QTabWidget, QMenu, QInputDialog, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from core.local_library import LocalLibrary, read_cover
from core.playlist_manager import PlaylistManager
from core.recent_manager import RecentManager
from core.audio_engine import AudioEngine
from ui.cover_widget import CoverWidget
from ui.equalizer_widget import EqualizerWidget
from ui.playlist_widget import PlaylistWidget
from ui.netease_login_dialog import NeteaseLoginDialog


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


class LocalPlayerWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("本地播放器")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet("QMainWindow { background-color: #1e1e1e; }")

        self.library = LocalLibrary()
        self.playlist_manager = PlaylistManager()
        self.recent_manager = RecentManager()
        self.current_index = -1
        self.current_tracks = []
        self.cookies = None
        self.play_mode = "顺序播放"

        self._engine = AudioEngine()
        self._engine.on_position_changed = self._on_engine_position
        self._engine.on_playback_finished = self._on_engine_finished

        self._build_ui()

        if self.library.load_cache():
            self._refresh_table()
            self.current_tracks = self.library.get_all()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        top = QHBoxLayout()
        self.btn_scan = QPushButton("扫描文件夹")
        self.btn_scan.clicked.connect(self._scan_folder)
        top.addWidget(self.btn_scan)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索...")
        self.search_box.textChanged.connect(self._on_search)
        top.addWidget(self.search_box, stretch=1)

        self.btn_netease = QPushButton("网易云登录")
        self.btn_netease.clicked.connect(self._open_netease_login)
        top.addWidget(self.btn_netease)
        main_layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["歌名", "时长"])
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
        self.now_label = QLabel("未播放")
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
        self.mode_combo.addItems(["顺序播放", "随机播放", "单曲循环"])
        self.mode_combo.currentTextChanged.connect(lambda t: setattr(self, "play_mode", t))
        ctrl.addWidget(self.mode_combo)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setFixedWidth(120)
        self.volume.valueChanged.connect(self._on_volume)
        ctrl.addWidget(QLabel("音量"))
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
        tabs.addTab(self.equalizer, "均衡器")

        self.playlist_widget = PlaylistWidget()
        self.playlist_widget.playlist_activated.connect(self._on_playlist_activated)
        tabs.addTab(self.playlist_widget, "播放列表")

        recent_widget = QWidget()
        recent_layout = QVBoxLayout(recent_widget)
        self.recent_list = QTableWidget()
        self.recent_list.setColumnCount(2)
        self.recent_list.setHorizontalHeaderLabels(["歌名", "时长"])
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
        btn_clear_recent = QPushButton("清空最近播放")
        btn_clear_recent.clicked.connect(self._clear_recent)
        recent_layout.addWidget(btn_clear_recent)
        tabs.addTab(recent_widget, "最近播放")
        right_layout.addWidget(tabs, stretch=1)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        self._refresh_recent()

    def _scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if not folder:
            return

        def _progress(i, total):
            self.setWindowTitle(f"扫描中 {i}/{total}")

        count = self.library.scan(folder, progress_callback=_progress)
        self.library.save_cache()
        self.setWindowTitle("本地播放器")
        self._refresh_table()
        self.current_tracks = self.library.get_all()
        QMessageBox.information(self, "扫描完成", f"共找到 {count} 首曲目")

    def _refresh_table(self):
        tracks = self.library.get_all()
        self.table.setRowCount(len(tracks))
        for i, t in enumerate(tracks):
            self.table.setItem(i, 0, QTableWidgetItem(t["title"]))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_time(t["duration"])))

    def _on_search(self, text):
        text = text.strip()
        if not text:
            self._refresh_table()
            return
        results = self.library.search(text)
        self.table.setRowCount(len(results))
        for i, t in enumerate(results):
            self.table.setItem(i, 0, QTableWidgetItem(t["title"]))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_time(t["duration"])))

    def _on_double_click(self, index):
        self.current_tracks = self.library.get_all()
        self._play_index(index.row())

    def _play_index(self, row: int):
        tracks = self.current_tracks or self.library.get_all()
        if row < 0 or row >= len(tracks):
            return
        self.current_index = row
        track = tracks[row]

        self._play_file(track["path"])

        self.now_label.setText(f"{track['title']} - {track['artist'] or '未知艺术家'}")
        self.table.selectRow(row)

        cover_data = read_cover(Path(track["path"]))
        self.cover.set_cover(cover_data)

        self.recent_manager.add(track)
        self._refresh_recent()

    def _play_file(self, path: str):
        if not self._engine.load(path):
            QMessageBox.warning(self, "错误", f"无法加载文件:\n{path}")
            return
        self._engine.set_eq_gains(self.equalizer.get_gains())
        self._engine.set_volume(self.volume.value() / 100)
        self._engine.play()
        self.btn_play.setText("⏸")

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
        tracks = self.current_tracks or self.library.get_all()
        if not tracks:
            return
        idx = (self.current_index - 1) % len(tracks)
        self._play_index(idx)

    def _play_next(self):
        tracks = self.current_tracks or self.library.get_all()
        if not tracks:
            return
        if self.play_mode == "随机播放":
            import random
            idx = random.randint(0, len(tracks) - 1)
        else:
            idx = (self.current_index + 1) % len(tracks)
        self._play_index(idx)

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

    def _on_engine_finished(self):
        QTimer.singleShot(0, self._handle_playback_finished)

    def _handle_playback_finished(self):
        if self.play_mode == "单曲循环":
            self._engine.play(0)
            self.btn_play.setText("⏸")
        else:
            self._play_next()

    def _on_eq_changed(self, gains: list):
        self._engine.set_eq_gains(gains)

    def _on_playlist_activated(self, tracks: list):
        if not tracks:
            return
        self.current_tracks = tracks
        self._play_index(0)

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
            self.current_tracks = items
            self._play_index(row)

    def _clear_recent(self):
        self.recent_manager.clear()
        self._refresh_recent()

    def _show_track_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        tracks = self.current_tracks or self.library.get_all()
        if row >= len(tracks):
            return
        track = tracks[row]

        menu = QMenu(self)
        menu.addAction("播放", lambda: self._play_index(row))
        menu.addSeparator()
        menu.addAction("添加到播放列表...", lambda: self._add_to_playlist(track))
        menu.exec(self.table.mapToGlobal(pos))

    def _add_to_playlist(self, track: dict):
        names = self.playlist_manager.get_all_names()
        if not names:
            name, ok = QInputDialog.getText(self, "新建播放列表", "名称:")
            if ok and name.strip():
                self.playlist_manager.create(name.strip())
                self.playlist_manager.add_track(name.strip(), track)
                self.playlist_widget.refresh()
            return

        name, ok = QInputDialog.getItem(self, "添加到播放列表", "选择:", names, 0, False)
        if ok and name:
            self.playlist_manager.add_track(name, track)
            self.playlist_widget.refresh()
            QMessageBox.information(self, "成功", f"已添加到「{name}」")

    def _open_netease_login(self):
        dialog = NeteaseLoginDialog(self)
        if dialog.exec():
            self.cookies = dialog.get_cookies()
            if self.cookies:
                QMessageBox.information(self, "成功", "网易云登录成功！")

    def closeEvent(self, event):
        try:
            self._engine.stop()
        except Exception:
            pass
        event.accept()