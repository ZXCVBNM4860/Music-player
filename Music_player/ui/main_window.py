# ui/main_window.py

import sys

from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,QHBoxLayout,
    QLabel,QMainWindow,QMessageBox,
    QPushButton,QStatusBar,QToolBar,
    QToolButton,QVBoxLayout,QWidget
)

from core.api_client import APIClient
from core.downloader import DownloadTask
from language import i18n
from ui.api_status import APIStatusIndicator
from ui.deepseek_chat import DeepSeekChat
from ui.download_panel import DownloadPanel
from ui.log_panel import LogPanel
from ui.playlist_dialog import PlaylistDialog
from ui.progress_bar import DownloadProgressBar
from ui.search_dialog import SearchDialog
from ui.settings_dialog import SettingsDialog
from utils.theme_loader import detect_system_theme, load_stylesheet

try:
    import version
    _VERSION = getattr(version, "version", "beta")
except Exception:
    _VERSION = "beta"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(i18n.tr("window_title"))
        self.setMinimumSize(900, 750)

        self._settings = QSettings("netease_downloader", "settings")

        self._ai_chat = None
        self._downloader = None
        self._local_player = None
        self._search_dialog = None
        self._playlist_dialog = None

        self._build_ui()
        self._build_toolbar()
        self._connect_signals()
        self._check_api()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        main_layout.addWidget(self._build_left_column(), stretch=1)
        main_layout.addWidget(self._build_right_column(), stretch=2)

        self._build_status_bar()

    def _build_left_column(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.api_status = APIStatusIndicator()
        layout.addWidget(self.api_status)

        self.download_panel = DownloadPanel()
        layout.addWidget(self.download_panel, stretch=1)

        return widget

    def _build_right_column(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.progress_bar = DownloadProgressBar()
        layout.addWidget(self.progress_bar)

        self.log_panel = LogPanel()
        layout.addWidget(self.log_panel, stretch=1)

        return widget

    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self._version_label = QLabel(_VERSION)
        self.status_bar.addWidget(self._version_label)

        if sys.platform == "win32":
            self.btn_install_api = QPushButton(i18n.tr("install_api_button"))
            self.btn_install_api.setObjectName("installApiButton")
            self.btn_install_api.clicked.connect(self._open_api_installer)
            self.status_bar.addPermanentWidget(self.btn_install_api)

    def _build_toolbar(self):
        toolbar = QToolBar(i18n.tr("toolbar"), self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        self.btn_settings = QToolButton(self)
        self.btn_settings.setText(i18n.tr("settings_title"))
        self.btn_settings.clicked.connect(self._open_settings)
        toolbar.addWidget(self.btn_settings)

    def _connect_signals(self):
        panel = self.download_panel

        panel.browse_clicked.connect(self._browse_path)
        panel.start_clicked.connect(self._start_download)
        panel.pause_clicked.connect(self._pause_download)
        panel.resume_clicked.connect(self._resume_download)
        panel.stop_clicked.connect(self._stop_download)
        panel.check_api_clicked.connect(self._check_api)
        panel.search_clicked.connect(self._open_search)
        panel.ai_chat_clicked.connect(self._open_ai_chat)
        panel.local_player_clicked.connect(self._open_local_player)

    def _log(self, message: str):
        self.log_panel.append(message)

    def _browse_path(self):
        self.download_panel.browse_directory()

    def _check_api(self):
        api = APIClient(self.download_panel.get_api_url())

        if api.check_alive():
            self.api_status.set_online(True, i18n.tr("api_online"))
            self._log(i18n.tr("api_ok"))
        else:
            self.api_status.set_online(False, i18n.tr("api_offline"))
            self._log(i18n.tr("api_fail"))

    def _on_api_status(self, online: bool, message: str):
        self.api_status.set_online(online, message)

    def _open_settings(self):
        old_lang = i18n.get_lang()

        dialog = SettingsDialog(self)
        if not dialog.exec():
            return

        new_lang = dialog.get_selected_language()
        if new_lang != old_lang:
            i18n.set_lang(new_lang)
            self._reload_ui()
        else:
            self._reapply_current_theme()

    def _open_api_installer(self):
        from ui.api_installer_dialog import APIInstallerDialog

        dialog = APIInstallerDialog(self)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.show()

    def _open_local_player(self):
        from ui.local_player import LocalPlayerWindow

        if self._local_player is None:
            self._local_player = LocalPlayerWindow(None)

        self._local_player.show()
        self._local_player.raise_()
        self._local_player.activateWindow()

    def _open_search(self):
        if self._search_dialog and self._search_dialog.isVisible():
            self._search_dialog.raise_()
            self._search_dialog.activateWindow()
            return

        dialog = SearchDialog(None, self.download_panel.get_api_url())
        dialog.songs_ready.connect(self._on_search_songs_ready)
        dialog.direct_download.connect(self._on_search_direct_download)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.show()

        self._search_dialog = dialog
        self._log(i18n.tr("search_window_open"))

    def _on_search_songs_ready(self, songs: list):
        if not songs:
            return

        self._open_local_player()
        self._local_player.set_online_tracks(songs)

    def _on_search_direct_download(self, item_id: str, item_type: str):
        type_map = {"song": 1, "mv": 3}
        task_type = type_map.get(item_type)
        if not task_type:
            return

        self.download_panel.set_task_type(task_type)
        self.download_panel.set_task_id(item_id)
        self._start_download()

    def _open_ai_chat(self):
        api_key = self.download_panel.get_ai_api_key()

        if not api_key:
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("ai_key_required"))
            return

        if self._ai_chat and self._ai_chat.isVisible():
            self._ai_chat.raise_()
            self._ai_chat.activateWindow()
            return

        self._ai_chat = DeepSeekChat(api_key, parent=self)
        self._ai_chat.setWindowModality(Qt.WindowModality.NonModal)
        self._ai_chat.show()
        self._log(i18n.tr("ai_window_open"))

    def _open_playlist_dialog(self, playlist_id, playlist_name):
        if self._playlist_dialog and self._playlist_dialog.isVisible():
            self._playlist_dialog.close()

        dialog = PlaylistDialog(
            None,
            playlist_id,
            playlist_name,
            self.download_panel.get_api_url(),
        )
        dialog.song_selected.connect(self._on_song_selected)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.show()

        self._playlist_dialog = dialog

    def _on_song_selected(self, song_id, song_name, artist):
        self.download_panel.set_task_id(song_id)
        self._log(f"{i18n.tr('selected')}: {song_name} - {artist}")

    def _on_mv_selected(self, mv_id, mv_name):
        self.download_panel.set_task_id(mv_id)
        self.download_panel.set_task_type(3)
        self._log(f"{i18n.tr('selected_mv')}: {mv_name}")

    def _on_playlist_selected(self, playlist_id, playlist_name):
        self._open_playlist_dialog(playlist_id, playlist_name)

    def _start_download(self):
        task_id = self.download_panel.get_task_id()

        if not task_id:
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("enter_id"))
            return

        task_type = self.download_panel.get_task_type()
        api_url = self.download_panel.get_api_url()
        path = self.download_panel.get_download_path()
        bitrate = self.download_panel.get_bitrate()

        self._downloader = DownloadTask(api_url, path, bitrate)
        self._downloader.set_task(task_type, task_id)

        self._wire_downloader_signals()

        self.download_panel.set_downloading_state(True)
        self.progress_bar.reset()

        self._downloader.start()

        type_names = {
            1: i18n.tr("single"),
            2: i18n.tr("playlist"),
            3: i18n.tr("mv"),
        }
        self._log(
            f"{i18n.tr('started')} "
            f"{type_names.get(task_type, '')}: {task_id}"
        )

    def _wire_downloader_signals(self):
        downloader = self._downloader

        downloader.log_message.connect(self._log)
        downloader.progress_update.connect(self._update_progress)
        downloader.byte_progress_update.connect(self._update_byte_progress)
        downloader.speed_update.connect(self._update_speed)
        downloader.song_start.connect(self._on_song_start)
        downloader.song_complete.connect(self._on_song_complete)
        downloader.download_finished.connect(self._on_finished)
        downloader.api_status.connect(self._on_api_status)

    def _pause_download(self):
        if self._downloader and self._downloader.isRunning():
            self._downloader.pause()
            self._log(i18n.tr("paused"))

    def _resume_download(self):
        if self._downloader and self._downloader.isRunning():
            self._downloader.resume()
            self._log(i18n.tr("resumed"))

    def _stop_download(self):
        if self._downloader and self._downloader.isRunning():
            self._downloader.stop()
            self._log(i18n.tr("stopped"))

        self.download_panel.set_downloading_state(False)

    def _update_progress(self, current: int, total: int):
        self.progress_bar.set_progress(current, total)

    def _update_byte_progress(self, downloaded: int, total: int):
        self.progress_bar.set_byte_progress(downloaded, total)

    def _update_speed(self, speed_text: str):
        self.progress_bar.set_speed(speed_text)

    def _on_song_start(self, name: str, index: int, total: int):
        self.progress_bar.set_song_name(f"[{index}/{total}] {name}")

    def _on_song_complete(self, name: str, success: bool):
        pass

    def _on_finished(self, success: bool):
        self.download_panel.set_downloading_state(False)

        if success:
            self.progress_bar.set_status(i18n.tr("download_complete"))
            self._log(i18n.tr("all_complete"))
        else:
            self.progress_bar.set_status(i18n.tr("download_interrupted"))
            self._log(i18n.tr("not_complete"))

    def _reload_ui(self):
        self._refresh_toolbar_texts()
        self.setWindowTitle(i18n.tr("window_title"))
        self.download_panel.refresh_texts()
        self.progress_bar.refresh_texts()
        self.api_status.refresh_texts()

        if self._local_player is not None:
            self._local_player.refresh_texts()

        if hasattr(self, "btn_install_api"):
            self.btn_install_api.setText(i18n.tr("install_api_button"))

        self._reapply_current_theme()

        self.status_bar.showMessage(i18n.tr("ui_refreshed"), 2000)
        QTimer.singleShot(0, self._check_api)

    def _refresh_toolbar_texts(self):
        if hasattr(self, "btn_settings"):
            self.btn_settings.setText(i18n.tr("settings_title"))

    def _reapply_current_theme(self):
        theme = self._settings.value("theme", "system")

        if theme == "system":
            theme = detect_system_theme(QApplication.instance())

        stylesheet = load_stylesheet(theme)
        if stylesheet:
            QApplication.instance().setStyleSheet(stylesheet)

    def closeEvent(self, event):
        self._stop_running_download()
        self._close_child_windows()
        event.accept()

    def _stop_running_download(self):
        if self._downloader and self._downloader.isRunning():
            self._downloader.stop()

    def _close_child_windows(self):
        windows = [
            self._local_player,
            self._ai_chat,
            self._search_dialog,
            self._playlist_dialog,
        ]

        for window in windows:
            if window is None:
                continue
            try:
                window.close()
            except Exception:
                pass