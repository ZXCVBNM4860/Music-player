# ui/search_dialog.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,QDialog,
    QHBoxLayout,QHeaderView,QLineEdit,
    QMessageBox,QPushButton,QTableWidget,
    QTableWidgetItem,QTabWidget,QVBoxLayout
)

from core.api_client import APIClient, APIError
from language import i18n


class SearchDialog(QDialog):
    song_selected = pyqtSignal(str, str, str)
    playlist_selected = pyqtSignal(str, str)
    mv_selected = pyqtSignal(str, str)
    preview_requested = pyqtSignal(str, str, str)

    _TAB_TYPES = ("song", "playlist", "mv")

    def __init__(self, parent=None, api_url="http://localhost:3000"):
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle(i18n.tr("search_title"))
        self.setMinimumSize(700, 500)

        self.api = APIClient(api_url)
        self._build_ui()

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
        self.song_table.doubleClicked.connect(
            lambda index: self._preview_row(self.song_table, index, "song")
        )
        self.tabs.addTab(self.song_table, i18n.tr("tab_song"))

        self.playlist_table = self._create_table()
        self.playlist_table.doubleClicked.connect(self._on_playlist_double_click)
        self.tabs.addTab(self.playlist_table, i18n.tr("tab_playlist"))

        self.mv_table = self._create_table()
        self.mv_table.doubleClicked.connect(
            lambda index: self._preview_row(self.mv_table, index, "mv")
        )
        self.tabs.addTab(self.mv_table, i18n.tr("tab_mv"))

        layout.addWidget(self.tabs)

        bottom = QHBoxLayout()
        bottom.addStretch()

        self.btn_ok = QPushButton(i18n.tr("download_selected"))
        self.btn_ok.clicked.connect(self._confirm_selection)
        bottom.addWidget(self.btn_ok)

        self.btn_preview = QPushButton(i18n.tr("preview"))
        self.btn_preview.clicked.connect(self._preview_current_tab)
        bottom.addWidget(self.btn_preview)

        self.btn_cancel = QPushButton(i18n.tr("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(self.btn_cancel)

        layout.addLayout(bottom)

    def _create_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([i18n.tr("col_id"), i18n.tr("col_name")])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _search_songs(self):
        self._run_search(self.api.search_songs, self.song_table, 0)

    def _search_playlists(self):
        self._run_search(self.api.search_playlists, self.playlist_table, 1)

    def _search_mvs(self):
        self._run_search(self.api.search_mvs, self.mv_table, 2)

    def _run_search(self, fetch, table: QTableWidget, tab_index: int):
        keywords = self.search_input.text().strip()
        if not keywords:
            return

        try:
            items = fetch(keywords)
        except APIError as exc:
            QMessageBox.warning(self, i18n.tr("error"), str(exc))
            return

        table.setRowCount(len(items))
        for row, item in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(str(item["id"])))
            table.setItem(row, 1, QTableWidgetItem(item["name"]))

        self.tabs.setCurrentIndex(tab_index)

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

    def _on_playlist_double_click(self, index):
        row = index.row()
        playlist_id = self.playlist_table.item(row, 0).text()
        playlist_name = self.playlist_table.item(row, 1).text()
        self.playlist_selected.emit(playlist_id, playlist_name)

    def _preview_row(self, table: QTableWidget, index, item_type: str):
        row = index.row()
        item_id = table.item(row, 0).text()
        item_name = table.item(row, 1).text()
        self.preview_requested.emit(item_id, item_name, item_type)

    def _preview_current_tab(self):
        selected = self._selected_id_name(self._current_table())
        if selected is None:
            return

        item_id, item_name = selected
        self.preview_requested.emit(item_id, item_name, self._current_item_type())

    def _confirm_selection(self):
        selected = self._selected_id_name(self._current_table())
        if selected is None:
            return

        item_id, item_name = selected
        item_type = self._current_item_type()

        if item_type == "song":
            self.song_selected.emit(item_id, item_name, "")
        elif item_type == "playlist":
            self.playlist_selected.emit(item_id, item_name)
        else:
            self.mv_selected.emit(item_id, item_name)

        self.accept()