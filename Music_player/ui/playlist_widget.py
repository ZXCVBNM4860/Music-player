# ui/playlist_widget.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QInputDialog, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.playlist_manager import PlaylistManager
from language import i18n


class PlaylistWidget(QWidget):
    playlist_activated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = PlaylistManager()
        self._build_ui()
        self.refresh_texts()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton()
        self.btn_new.clicked.connect(self._create_playlist)
        btn_layout.addWidget(self.btn_new)

        self.btn_delete = QPushButton()
        self.btn_delete.clicked.connect(self._delete_playlist)
        btn_layout.addWidget(self.btn_delete)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_playlist_double_click)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #141414;
                color: #eaeaea;
                border: 1px solid #333333;
                border-radius: 4px;
            }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background-color: #2a2a2a; }
        """)
        layout.addWidget(self.list_widget)

    def _refresh(self):
        self.list_widget.clear()
        for name in self.manager.get_all_names():
            count = len(self.manager.get_tracks(name))
            item = QListWidgetItem(f"{name} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)

    def _create_playlist(self):
        name, ok = QInputDialog.getText(self, "新建播放列表", "名称:")
        if ok and name.strip():
            self.manager.create(name.strip())
            self._refresh()

    def _delete_playlist(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "确认", f"删除播放列表「{name}」？")
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete(name)
            self._refresh()

    def _on_playlist_double_click(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        tracks = self.manager.get_tracks(name)
        if tracks:
            self.playlist_activated.emit(tracks)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction("播放", lambda: self._on_playlist_double_click(item))
        menu.addAction("删除", self._delete_playlist)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def refresh(self):
        self._refresh()

    def refresh_texts(self):
        self.btn_new.setText(f"+ {i18n.tr('new_playlist_short')}")
        self.btn_delete.setText(f"- {i18n.tr('delete_playlist_short')}")