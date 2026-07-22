"""搜索弹窗"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.api_client import APIClient, APIError
from language import i18n


class SearchDialog(QDialog):
    song_selected = pyqtSignal(str, str, str)      # id, name, artist
    playlist_selected = pyqtSignal(str, str)       # id, name
    mv_selected = pyqtSignal(str, str)             # id, name
    preview_requested = pyqtSignal(str, str, str)  # id, name, type(song/mv/playlist)
    
    def __init__(self, parent=None, api_url="http://localhost:3000"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle(i18n.tr("search_title"))
        self.setMinimumSize(800, 600)
        self.api = APIClient(api_url)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(i18n.tr("search_placeholder"))
        self.search_input.returnPressed.connect(self._do_search_songs)
        search_layout.addWidget(self.search_input, stretch=1)
        
        self.btn_search_song = QPushButton(i18n.tr("search_song"))
        self.btn_search_song.clicked.connect(self._do_search_songs)
        search_layout.addWidget(self.btn_search_song)
        
        self.btn_search_playlist = QPushButton(i18n.tr("search_playlist"))
        self.btn_search_playlist.clicked.connect(self._do_search_playlists)
        search_layout.addWidget(self.btn_search_playlist)
        
        self.btn_search_mv = QPushButton(i18n.tr("search_mv"))
        self.btn_search_mv.clicked.connect(self._do_search_mvs)
        search_layout.addWidget(self.btn_search_mv)
        
        layout.addLayout(search_layout)
        
        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2a2a2a;
                background: #121212;
            }
            QTabBar::tab {
                background: #242424;
                color: #666666;
                padding: 8px 20px;
                border: 1px solid #2a2a2a;
            }
            QTabBar::tab:selected {
                background: #1a1a1a;
                color: #eaeaea;
                border-bottom: 2px solid #eaeaea;
            }
        """)
        
        # 歌曲页
        self.song_table = self._create_table(["ID", "Name", "Artist", "Album", "Duration"])
        self.song_table.doubleClicked.connect(self._on_song_double_click)
        self.tabs.addTab(self.song_table, i18n.tr("tab_song"))
        
        # 歌单页
        self.playlist_table = self._create_table(["ID", "Name", "Creator", "Track Count", "Play Count"])
        self.playlist_table.doubleClicked.connect(self._on_playlist_double_click)
        self.tabs.addTab(self.playlist_table, i18n.tr("tab_playlist"))
        
        # MV页
        self.mv_table = self._create_table(["ID", "Name", "Artist", "Duration"])
        self.mv_table.doubleClicked.connect(self._on_mv_double_click)
        self.tabs.addTab(self.mv_table, i18n.tr("tab_mv"))
        
        layout.addWidget(self.tabs)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_ok = QPushButton(i18n.tr("download_selected"))
        self.btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.btn_ok)
        
        self.btn_preview = QPushButton(i18n.tr("preview"))
        self.btn_preview.clicked.connect(self._on_preview_btn)
        btn_layout.addWidget(self.btn_preview)
        
        self.btn_cancel = QPushButton(i18n.tr("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _create_table(self, headers):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                color: #eaeaea;
                border: none;
                gridline-color: #2a2a2a;
            }
            QTableWidget::item:selected {
                background-color: #2d2d2d;
                color: #eaeaea;
            }
        """)
        return table
    
    def _do_search_songs(self):
        keywords = self.search_input.text().strip()
        if not keywords:
            return
        try:
            songs = self.api.search_songs(keywords)
            self._fill_table(self.song_table, songs, "song")
            self.tabs.setCurrentIndex(0)
        except APIError as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))
    
    def _do_search_playlists(self):
        keywords = self.search_input.text().strip()
        if not keywords:
            return
        try:
            playlists = self.api.search_playlists(keywords)
            self._fill_table(self.playlist_table, playlists, "playlist")
            self.tabs.setCurrentIndex(1)
        except APIError as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))
    
    def _do_search_mvs(self):
        keywords = self.search_input.text().strip()
        if not keywords:
            return
        try:
            mvs = self.api.search_mvs(keywords)
            self._fill_table(self.mv_table, mvs, "mv")
            self.tabs.setCurrentIndex(2)
        except APIError as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))
    
    def _fill_table(self, table, items, item_type):
        table.setRowCount(len(items))
        for i, item in enumerate(items):
            if item_type == "song":
                table.setItem(i, 0, QTableWidgetItem(str(item["id"])))
                table.setItem(i, 1, QTableWidgetItem(item["name"]))
                table.setItem(i, 2, QTableWidgetItem(", ".join(item.get("artists", []))))
                table.setItem(i, 3, QTableWidgetItem(item.get("album", "")))
                duration = item.get("duration", 0)
                mins, secs = divmod(duration // 1000, 60)
                table.setItem(i, 4, QTableWidgetItem(f"{mins}:{secs:02d}"))
            elif item_type == "playlist":
                table.setItem(i, 0, QTableWidgetItem(str(item["id"])))
                table.setItem(i, 1, QTableWidgetItem(item["name"]))
                table.setItem(i, 2, QTableWidgetItem(item.get("creator", "")))
                table.setItem(i, 3, QTableWidgetItem(str(item.get("track_count", 0))))
                play_count = item.get("play_count", 0)
                table.setItem(i, 4, QTableWidgetItem(f"{play_count:,}"))
            elif item_type == "mv":
                table.setItem(i, 0, QTableWidgetItem(str(item["id"])))
                table.setItem(i, 1, QTableWidgetItem(item["name"]))
                table.setItem(i, 2, QTableWidgetItem(item.get("artist", "")))
                duration = item.get("duration", 0)
                mins, secs = divmod(duration // 1000, 60)
                table.setItem(i, 3, QTableWidgetItem(f"{mins}:{secs:02d}"))
    
    def _on_song_double_click(self, index):
        row = index.row()
        song_id = self.song_table.item(row, 0).text()
        song_name = self.song_table.item(row, 1).text()
        artist = self.song_table.item(row, 2).text()
        self.preview_requested.emit(song_id, song_name, "song")
    
    def _on_playlist_double_click(self, index):
        row = index.row()
        playlist_id = self.playlist_table.item(row, 0).text()
        playlist_name = self.playlist_table.item(row, 1).text()
        # emit playlist_selected so parent can show playlist contents
        self.playlist_selected.emit(playlist_id, playlist_name)
    
    def _on_mv_double_click(self, index):
        row = index.row()
        mv_id = self.mv_table.item(row, 0).text()
        mv_name = self.mv_table.item(row, 1).text()
        self.preview_requested.emit(mv_id, mv_name, "mv")
    
    def _on_preview_btn(self):
        current_tab = self.tabs.currentIndex()
        tables = [self.song_table, self.playlist_table, self.mv_table]
        table = tables[current_tab]
        
        selected = table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        types = ["song", "playlist", "mv"]
        item_type = types[current_tab]
        
        if item_type == "song":
            item_id = self.song_table.item(row, 0).text()
            item_name = self.song_table.item(row, 1).text()
        elif item_type == "playlist":
            item_id = self.playlist_table.item(row, 0).text()
            item_name = self.playlist_table.item(row, 1).text()
        else:
            item_id = self.mv_table.item(row, 0).text()
            item_name = self.mv_table.item(row, 1).text()
        
        self.preview_requested.emit(item_id, item_name, item_type)
    
    def _on_ok(self):
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 0:  # 歌曲
            selected = self.song_table.selectedItems()
            if selected:
                row = selected[0].row()
                self.song_selected.emit(
                    self.song_table.item(row, 0).text(),
                    self.song_table.item(row, 1).text(),
                    self.song_table.item(row, 2).text()
                )
                self.accept()
                
        elif current_tab == 1:  # 歌单
            selected = self.playlist_table.selectedItems()
            if selected:
                row = selected[0].row()
                self.playlist_selected.emit(
                    self.playlist_table.item(row, 0).text(),
                    self.playlist_table.item(row, 1).text()
                )
                self.accept()
                
        else:  # MV
            selected = self.mv_table.selectedItems()
            if selected:
                row = selected[0].row()
                self.mv_selected.emit(
                    self.mv_table.item(row, 0).text(),
                    self.mv_table.item(row, 1).text()
                )
                self.accept()
