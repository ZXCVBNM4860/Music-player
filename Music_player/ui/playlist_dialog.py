"""歌单内容查看对话框"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from core.api_client import APIClient, APIError
from language import i18n


class PlaylistDialog(QDialog):
    song_selected = pyqtSignal(str, str, str)      # id, name, artist
    preview_requested = pyqtSignal(str, str, str) # id, name, type

    def __init__(self, parent=None, playlist_id="", playlist_name="", api_url="http://localhost:3000"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle(f"{i18n.tr('playlist_title')} - {playlist_name}")
        self.setMinimumSize(700, 500)
        # 样式交由应用级 QSS 主题控制，不再硬编码暗色
        self.api = APIClient(api_url)
        self.playlist_id = playlist_id
        self._build_ui()
        self._load_tracks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            i18n.tr("col_id"),
            i18n.tr("col_name"),
            i18n.tr("col_artist")
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_download = QPushButton(i18n.tr("download_selected"))
        self.btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(self.btn_download)

        self.btn_preview = QPushButton(i18n.tr("preview"))
        self.btn_preview.clicked.connect(self._on_preview)
        btn_layout.addWidget(self.btn_preview)

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self.table.doubleClicked.connect(self._on_double_click)

    def _load_tracks(self):
        try:
            tracks = self.api.get_playlist_detail(self.playlist_id)
        except APIError as e:
            QMessageBox.warning(self, i18n.tr("error"), f"{i18n.tr('playlist_fetch_fail')}: {e}")
            return
        if not tracks:
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr("playlist_empty_msg"))
            return
        self.table.setRowCount(len(tracks))
        for i, t in enumerate(tracks):
            self.table.setItem(i, 0, QTableWidgetItem(str(t.get("id"))))
            self.table.setItem(i, 1, QTableWidgetItem(t.get("name", "")))
            self.table.setItem(i, 2, QTableWidgetItem(", ".join(t.get("artists", []))))

    def _get_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        sid = self.table.item(row, 0).text()
        name = self.table.item(row, 1).text()
        artist = self.table.item(row, 2).text()
        return sid, name, artist

    def _on_download(self):
        sel = self._get_selected()
        if not sel:
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr("select_song"))
            return
        sid, name, artist = sel
        self.song_selected.emit(sid, name, artist)
        self.accept()

    def _on_preview(self):
        sel = self._get_selected()
        if not sel:
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr("select_song"))
            return
        sid, name, artist = sel
        self.preview_requested.emit(sid, name, "song")

    def _on_double_click(self, index):
        row = index.row()
        sid = self.table.item(row, 0).text()
        name = self.table.item(row, 1).text()
        artist = self.table.item(row, 2).text()
        self.song_selected.emit(sid, name, artist)
        self.accept()