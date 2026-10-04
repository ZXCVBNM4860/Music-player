# ui/playlist_dialog.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,QHBoxLayout,
    QVBoxLayout,QPushButton,
    QHeaderView,QMessageBox,
    QTableWidget,QTableWidgetItem,
)

from core.api_client import APIClient, APIError
from language import i18n


class PlaylistDialog(QDialog):
    song_selected = pyqtSignal(str, str, str)
    preview_requested = pyqtSignal(str, str, str)

    def __init__(self, parent=None, playlist_id="", playlist_name="", api_url="http://localhost:3000"):
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle(f"{i18n.tr('playlist_title')} - {playlist_name}")
        self.setMinimumSize(600, 500)

        self.api = APIClient(api_url)
        self.playlist_id = playlist_id

        self._build_ui()
        self._load_tracks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([i18n.tr("col_id"), i18n.tr("col_name")])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        bottom.addStretch()

        self.btn_download = QPushButton(i18n.tr("download_selected"))
        self.btn_download.clicked.connect(self._on_download)
        bottom.addWidget(self.btn_download)

        self.btn_preview = QPushButton(i18n.tr("preview"))
        self.btn_preview.clicked.connect(self._on_preview)
        bottom.addWidget(self.btn_preview)

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)

        layout.addLayout(bottom)

    def _load_tracks(self):
        try:
            tracks = self.api.get_playlist_detail(self.playlist_id)
        except APIError as exc:
            QMessageBox.warning(
                self,
                i18n.tr("error"),
                f"{i18n.tr('playlist_fetch_fail')}: {exc}",
            )
            return

        if not tracks:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr("playlist_empty_msg")
            )
            return

        self.table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            self.table.setItem(row, 0, QTableWidgetItem(str(track.get("id"))))
            self.table.setItem(row, 1, QTableWidgetItem(track.get("name", "")))

    def _selected_row(self):
        selected = self.table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        return (
            self.table.item(row, 0).text(),
            self.table.item(row, 1).text(),
        )

    def _on_download(self):
        selected = self._selected_row()
        if selected is None:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr("select_song")
            )
            return

        song_id, song_name = selected
        self.song_selected.emit(song_id, song_name, "")
        self.accept()

    def _on_preview(self):
        selected = self._selected_row()
        if selected is None:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr("select_song")
            )
            return

        song_id, song_name = selected
        self.preview_requested.emit(song_id, song_name, "song")

    def _on_double_click(self, index):
        row = index.row()
        song_id = self.table.item(row, 0).text()
        song_name = self.table.item(row, 1).text()
        self.song_selected.emit(song_id, song_name, "")
        self.accept()