# ui/playlist_widget.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,QInputDialog,QListWidget,
    QListWidgetItem,QMenu,QMessageBox,
    QPushButton,QVBoxLayout,QWidget
)

from core.playlist_manager import PlaylistManager
from language import i18n


class PlaylistWidget(QWidget):
    playlist_activated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.manager = PlaylistManager()
        self._build_ui()

        self.refresh_texts()
        self._reload_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        buttons = QHBoxLayout()

        self.btn_new = QPushButton()
        self.btn_new.clicked.connect(self._create_playlist)
        buttons.addWidget(self.btn_new)

        self.btn_delete = QPushButton()
        self.btn_delete.clicked.connect(lambda: self._delete_playlist())
        buttons.addWidget(self.btn_delete)

        buttons.addStretch()
        layout.addLayout(buttons)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("playlistList")
        self.list_widget.itemDoubleClicked.connect(self._on_playlist_activated)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

    def refresh(self):
        self._reload_list()

    def _reload_list(self):
        current_item = self.list_widget.currentItem()
        current_name = (
            current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        )

        self.list_widget.clear()

        for name in self.manager.get_all_names():
            track_count = len(self.manager.get_tracks(name))

            item = QListWidgetItem(f"{name} ({track_count})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)

            if name == current_name:
                self.list_widget.setCurrentItem(item)

    def _create_playlist(self):
        name, ok = QInputDialog.getText(
            self,
            i18n.tr("new_playlist"),
            i18n.tr("playlist_name_label"),
        )

        if ok and name.strip():
            self.manager.create(name.strip())
            self._reload_list()

    def _delete_playlist(self, item: QListWidgetItem = None):
        item = item or self.list_widget.currentItem()
        if not item:
            return

        name = item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self,
            i18n.tr("confirm"),
            i18n.tr("confirm_delete_playlist").format(name=name),
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete(name)
            self._reload_list()

    def _rename_playlist(self, item: QListWidgetItem):
        old_name = item.data(Qt.ItemDataRole.UserRole)

        new_name, ok = QInputDialog.getText(
            self,
            i18n.tr("rename"),
            i18n.tr("playlist_name_label"),
            text=old_name,
        )
        new_name = new_name.strip()

        if not ok or not new_name or new_name == old_name:
            return

        if new_name in self.manager.get_all_names():
            QMessageBox.warning(
                self,
                i18n.tr("error"),
                i18n.tr("playlist_already_exists").format(name=new_name),
            )
            return

        self._move_playlist(old_name, new_name)
        self._reload_list()

    def _move_playlist(self, old_name: str, new_name: str):
        tracks = self.manager.get_tracks(old_name)

        self.manager.delete(old_name)
        self.manager.create(new_name)

        for track in tracks:
            self.manager.add_track(new_name, track)

    def _on_playlist_activated(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        tracks = self.manager.get_tracks(name)

        if tracks:
            self.playlist_activated.emit(tracks)
        else:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr("playlist_empty")
            )

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.addAction(
            i18n.tr("play_menu"),
            lambda: self._on_playlist_activated(item),
        )
        menu.addAction(
            i18n.tr("delete"),
            lambda: self._delete_playlist(item),
        )
        menu.addAction(
            i18n.tr("rename"),
            lambda: self._rename_playlist(item),
        )
        menu.exec(self.list_widget.mapToGlobal(pos))

    def refresh_texts(self):
        self.btn_new.setText(f"+ {i18n.tr('new_playlist_short')}")
        self.btn_delete.setText(f"- {i18n.tr('delete_playlist_short')}")