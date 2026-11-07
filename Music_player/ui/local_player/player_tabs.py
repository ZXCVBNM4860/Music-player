# ui/local_player/player_tabs.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLabel, QPushButton
)

from language import i18n
from .equalizer_widget import EqualizerWidget
from .playlist_widget import PlaylistWidget


def fmt_time(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


class PlayerTabsWidget(QWidget):
    eq_changed = pyqtSignal(list)
    playlist_activated = pyqtSignal(list)
    recent_double_clicked = pyqtSignal(int)
    clear_recent_clicked = pyqtSignal()
    
    open_settings_clicked = pyqtSignal()
    toggle_desktop_lyric_clicked = pyqtSignal(bool)
    download_current_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("playerTabs")

        self.equalizer = EqualizerWidget()
        self.equalizer.eq_changed.connect(self.eq_changed.emit)
        self.tabs.addTab(self.equalizer, i18n.tr("equalizer"))

        self.playlist_widget = PlaylistWidget()
        self.playlist_widget.playlist_activated.connect(self.playlist_activated.emit)
        self.tabs.addTab(self.playlist_widget, i18n.tr("playlist_tab"))

        self.tabs.addTab(self._build_recent_tab(), i18n.tr("recent_played"))

        self.tabs.addTab(self._build_misc_tab(), i18n.tr("other"))

        layout.addWidget(self.tabs)

    def _build_recent_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.recent_list = QTableWidget()
        self.recent_list.setObjectName("recentTable")
        self.recent_list.setColumnCount(3)
        self.recent_list.setHorizontalHeaderLabels([
            i18n.tr("col_title"),
            i18n.tr("col_artist"),
            i18n.tr("col_duration"),
        ])
        header = self.recent_list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 150)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_list.doubleClicked.connect(lambda idx: self.recent_double_clicked.emit(idx.row()))
        layout.addWidget(self.recent_list)

        self.btn_clear_recent = QPushButton(i18n.tr("clear_recent"))
        self.btn_clear_recent.clicked.connect(self.clear_recent_clicked.emit)
        layout.addWidget(self.btn_clear_recent)

        return widget

    def _build_misc_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        self.btn_settings = QPushButton(i18n.tr("Settings"))
        self.btn_settings.setFixedHeight(36)
        self.btn_settings.setToolTip(i18n.tr("settings_player_title"))
        self.btn_settings.clicked.connect(self.open_settings_clicked.emit)
        layout.addWidget(self.btn_settings)

        self.btn_desktop_lyric = QPushButton(i18n.tr("desktop_lyric"))
        self.btn_desktop_lyric.setCheckable(True)
        self.btn_desktop_lyric.setFixedHeight(36)
        self.btn_desktop_lyric.clicked.connect(self.toggle_desktop_lyric_clicked.emit)
        layout.addWidget(self.btn_desktop_lyric)

        self.btn_download_now = QPushButton(i18n.tr("download_current"))
        self.btn_download_now.setFixedHeight(36)
        self.btn_download_now.clicked.connect(self.download_current_clicked.emit)
        layout.addWidget(self.btn_download_now)

        layout.addStretch()
        return widget

    def set_recent_items(self, items: list):
        self.recent_list.setRowCount(len(items))
        for row, track in enumerate(items):
            self.recent_list.setItem(row, 0, QTableWidgetItem(track.get("title", "")))
            self.recent_list.setItem(row, 1, QTableWidgetItem(track.get("artist", "")))
            self.recent_list.setItem(row, 2, QTableWidgetItem(fmt_time(track.get("duration", 0))))

    def set_desktop_lyric_checked(self, checked: bool):
        self.btn_desktop_lyric.setChecked(checked)

    def set_download_button_state(self, enabled: bool, text: str = None):
        self.btn_download_now.setEnabled(enabled)
        if text:
            self.btn_download_now.setText(text)

    def refresh_texts(self):
        self.tabs.setTabText(0, i18n.tr("equalizer"))
        self.tabs.setTabText(1, i18n.tr("playlist_tab"))
        self.tabs.setTabText(2, i18n.tr("recent_played"))
        self.tabs.setTabText(3, i18n.tr("other"))

        self.btn_clear_recent.setText(i18n.tr("clear_recent"))
        
        self.recent_list.setHorizontalHeaderLabels([
            i18n.tr("col_title"),
            i18n.tr("col_artist"),
            i18n.tr("col_duration"),
        ])

        self.btn_settings.setText(i18n.tr("Settings"))
        self.btn_settings.setToolTip(i18n.tr("settings_player_title"))
        self.btn_desktop_lyric.setText(i18n.tr("desktop_lyric"))
        self.btn_download_now.setText(i18n.tr("download_current"))
        
        self.playlist_widget.refresh_texts()
        self.equalizer.refresh_texts()