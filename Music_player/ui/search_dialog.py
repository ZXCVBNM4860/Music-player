# ui/search_dialog.py

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog,
    QFrame, QHBoxLayout, QHeaderView, QLineEdit,
    QMessageBox, QPushButton, QSlider, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QLabel,
)

from core.api_client import APIClient
from language import i18n
from ui.workers import run_async


def _fetch_preview_url(api, item_id, is_mv):
    try:
        if is_mv:
            return api.get_mv_download_url(item_id)
        return api.get_download_url(item_id, 128000)
    except Exception:
        return None


class SearchDialog(QDialog):
    songs_ready = pyqtSignal(list)
    direct_download = pyqtSignal(str, str)

    _TAB_TYPES = ("song", "playlist", "mv")

    def __init__(self, parent=None, api_url="http://localhost:3000"):
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle(i18n.tr("search_title"))
        self.setMinimumSize(820, 560)

        self.api = APIClient(api_url)
        self._current_url = ""
        self._current_row = -1
        self._song_results = []
        self._pending_preview_name = ""
        self._pending_preview_row = -1
        self._build_ui()
        self._setup_player()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        search_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(i18n.tr("search_placeholder"))
        self.search_input.returnPressed.connect(self._search_songs)
        search_row.addWidget(self.search_input, stretch=1)

        self.btn_search_song = QPushButton(i18n.tr("search_song"))
        self.btn_search_song.clicked.connect(self._search_songs)
        search_row.addWidget(self.btn_search_song)

        self.btn_search_playlist = QPushButton(i18n.tr("search_playlist"))
        self.btn_search_playlist.clicked.connect(self._search_playlists)
        search_row.addWidget(self.btn_search_playlist)

        self.btn_search_mv = QPushButton(i18n.tr("search_mv"))
        self.btn_search_mv.clicked.connect(self._search_mvs)
        search_row.addWidget(self.btn_search_mv)

        layout.addLayout(search_row)

        self.tabs = QTabWidget()

        self.song_table = self._create_table()
        self.song_table.doubleClicked.connect(self._on_song_double_click)
        self.tabs.addTab(self.song_table, i18n.tr("tab_song"))

        self.playlist_table = self._create_table()
        self.playlist_table.doubleClicked.connect(self._on_playlist_double_click)
        self.tabs.addTab(self.playlist_table, i18n.tr("tab_playlist"))

        self.mv_table = self._create_table()
        self.mv_table.doubleClicked.connect(self._on_mv_double_click)
        self.tabs.addTab(self.mv_table, i18n.tr("tab_mv"))

        layout.addWidget(self.tabs)
        layout.addWidget(self._build_preview_bar())

        bottom = QHBoxLayout()
        bottom.addStretch()

        self.btn_send = QPushButton(i18n.tr("search_send_to_player"))
        self.btn_send.clicked.connect(self._send_current_tab_to_player)
        bottom.addWidget(self.btn_send)

        self.btn_download = QPushButton(i18n.tr("search_download_direct"))
        self.btn_download.clicked.connect(self._on_download_clicked)
        bottom.addWidget(self.btn_download)

        self.btn_cancel = QPushButton(i18n.tr("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(self.btn_cancel)

        layout.addLayout(bottom)

    def _build_preview_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("searchPreviewBar")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        self.preview_label = QLabel(i18n.tr("not_playing"))
        self.preview_label.setObjectName("searchPreviewLabel")
        layout.addWidget(self.preview_label, stretch=1)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.clicked.connect(self._toggle_play)
        layout.addWidget(self.btn_play)

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 100)
        self.progress.sliderReleased.connect(self._seek_preview)
        layout.addWidget(self.progress, stretch=2)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("searchPreviewTime")
        layout.addWidget(self.time_label)

        return frame

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.7)

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.mediaStatusChanged.connect(self._on_status)

    def _create_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            i18n.tr("col_id"),
            i18n.tr("col_name"),
            i18n.tr("col_artist"),
            i18n.tr("col_provider"),
        ])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _search_songs(self):
        self._run_search("song", self.song_table, 0)

    def _search_playlists(self):
        self._run_search("playlist", self.playlist_table, 1)

    def _search_mvs(self):
        self._run_search("mv", self.mv_table, 2)

    def _run_search(self, kind: str, table: QTableWidget, tab_index: int):
        keywords = self.search_input.text().strip()
        if not keywords:
            return

        run_async(
            self._search_worker,
            args=(kind, keywords, table, tab_index),
            on_success=self._on_search_result,
            on_error=self._on_search_failed,
        )

    def _search_worker(self, kind: str, keywords: str, table: QTableWidget, tab_index: int):
        if kind == "song":
            items = self.api.search_songs(keywords)
        elif kind == "playlist":
            items = self.api.search_playlists(keywords)
        else:
            items = self.api.search_mvs(keywords)
        return items, table, tab_index

    def _on_search_result(self, result):
        items, table, tab_index = result

        if tab_index == 0:
            self._song_results = items

        table.setRowCount(len(items))
        for row, item in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(str(item.get("id", ""))))
            table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))

            if tab_index == 0:
                artists = item.get("artists") or []
                artist_text = ", ".join(artists) if isinstance(artists, list) else str(artists)
            elif tab_index == 1:
                artist_text = item.get("creator", "") or ""
            else:
                artist_text = item.get("artist", "") or ""
            table.setItem(row, 2, QTableWidgetItem(artist_text))

            table.setItem(row, 3, QTableWidgetItem(i18n.tr("provider_netease")))

        self.tabs.setCurrentIndex(tab_index)

    def _on_search_failed(self, message):
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _current_table(self) -> QTableWidget:
        tables = (self.song_table, self.playlist_table, self.mv_table)
        return tables[self.tabs.currentIndex()]

    def _current_item_type(self) -> str:
        return self._TAB_TYPES[self.tabs.currentIndex()]

    def _selected_id_name(self, table: QTableWidget):
        selected = table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        return table.item(row, 0).text(), table.item(row, 1).text()

    def _on_song_double_click(self, index):
        row = index.row()
        song_id = self.song_table.item(row, 0).text()
        song_name = self.song_table.item(row, 1).text()
        self._start_preview(song_id, song_name, row)

    def _on_mv_double_click(self, index):
        row = index.row()
        mv_id = self.mv_table.item(row, 0).text()
        mv_name = self.mv_table.item(row, 1).text()
        self._start_preview(mv_id, mv_name, row, is_mv=True)

    def _on_playlist_double_click(self, index):
        row = index.row()
        playlist_id = self.playlist_table.item(row, 0).text()
        playlist_name = self.playlist_table.item(row, 1).text()
        self._send_playlist_to_player(playlist_id, playlist_name)

    def _start_preview(self, item_id, item_name, row, is_mv=False):
        self._pending_preview_name = item_name
        self._pending_preview_row = row

        run_async(
            _fetch_preview_url,
            args=(self.api, item_id, is_mv),
            on_success=self._on_preview_url,
            on_error=self._on_preview_failed,
        )

    def _on_preview_url(self, url):
        if not url:
            self._show_preview_error()
            return

        self._current_url = url
        self._current_row = self._pending_preview_row

        self.player.setSource(QUrl(url))
        self.player.play()

        self.btn_play.setText("⏸")
        self.preview_label.setText(
            f"{i18n.tr('search_now_playing')}: {self._pending_preview_name}"
        )

    def _on_preview_failed(self, message):
        self._show_preview_error()

    def _show_preview_error(self):
        QMessageBox.warning(
            self, i18n.tr("preview_fail"), i18n.tr("preview_no_url")
        )

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶")
        else:
            self.player.play()
            self.btn_play.setText("⏸")

    def _seek_preview(self):
        if self.player.duration() > 0:
            pos = int(self.progress.value() / 100 * self.player.duration())
            self.player.setPosition(pos)

    def _on_position(self, pos):
        if self.player.duration() > 0:
            self.progress.setValue(int(pos / self.player.duration() * 100))
            self._update_time_label(pos, self.player.duration())

    def _on_duration(self, dur):
        self._update_time_label(self.player.position(), dur)

    def _update_time_label(self, pos, dur):
        if dur <= 0:
            self.time_label.setText("00:00 / 00:00")
            return
        pm, ps = divmod(pos // 1000, 60)
        dm, ds = divmod(dur // 1000, 60)
        self.time_label.setText(f"{pm:02d}:{ps:02d} / {dm:02d}:{ds:02d}")

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.btn_play.setText("▶")

    def _collect_songs_from_table(self) -> list:
        songs = []
        for item in self._song_results:
            duration_ms = item.get("duration", 0) or 0
            songs.append({
                "id": str(item["id"]),
                "title": item["name"],
                "artist": ", ".join(item.get("artists", [])),
                "duration": duration_ms / 1000,
                "pic_url": item.get("pic_url", ""),
                "path": f"netease://{item['id']}",
            })
        return songs

    def _send_current_tab_to_player(self):
        if self.tabs.currentIndex() == 0:
            songs = self._collect_songs_from_table()
            if songs:
                self.songs_ready.emit(songs)
        elif self.tabs.currentIndex() == 1:
            selected = self._selected_id_name(self.playlist_table)
            if selected:
                self._send_playlist_to_player(selected[0], selected[1])
        else:
            selected = self._selected_id_name(self.mv_table)
            if selected:
                self.direct_download.emit(selected[0], "mv")

    def _send_playlist_to_player(self, playlist_id, playlist_name):
        run_async(
            self.api.get_playlist_detail,
            args=(playlist_id,),
            on_success=self._on_playlist_tracks,
            on_error=self._on_playlist_failed,
        )

    def _on_playlist_tracks(self, tracks):
        songs = [
            {
                "id": str(track.get("id")),
                "title": track.get("name", ""),
                "artist": ", ".join(track.get("artists", [])),
                "duration": 0,
                "pic_url": track.get("pic_url", ""),
                "path": f"netease://{track.get('id')}",
            }
            for track in tracks
        ]

        if songs:
            self.songs_ready.emit(songs)

    def _on_playlist_failed(self, message):
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _on_download_clicked(self):
        table = self._current_table()
        selected = self._selected_id_name(table)
        if selected is None:
            return
        item_id, _ = selected
        self.direct_download.emit(item_id, self._current_item_type())

    def closeEvent(self, event):
        try:
            self.player.stop()
        except Exception:
            pass
        event.accept()