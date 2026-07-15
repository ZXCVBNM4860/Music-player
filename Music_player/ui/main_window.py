"""主窗口"""

import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStatusBar, QToolBar, QApplication
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QPalette
from language import i18n
import version
from ui.download_panel import DownloadPanel
from ui.api_status import APIStatusIndicator
from ui.log_panel import LogPanel
from ui.progress_bar import DownloadProgressBar
from ui.search_dialog import SearchDialog
from ui.preview_dialog import PreviewDialog
from ui.deepseek_chat import DeepSeekChat
from core.downloader import DownloadTask


def load_stylesheet(theme: str) -> str:
    #加载主题样式表
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    qss_path = os.path.join(base_dir, "resources", "themes", f"{theme}.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(i18n.tr("window_title"))
        self.setMinimumSize(900, 700)
        
        self._downloader = None
        self._ai_chat = None
        self._search_dialog = None
        self._preview_dialog = None
        self._playlist_dialog = None
        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._check_api()
    
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        self.api_status = APIStatusIndicator()
        left_layout.addWidget(self.api_status)
        
        self.download_panel = DownloadPanel()
        left_layout.addWidget(self.download_panel, stretch=1)
        
        main_layout.addWidget(left_widget, stretch=1)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        self.progress_bar = DownloadProgressBar()
        right_layout.addWidget(self.progress_bar)
        
        self.log_panel = LogPanel()
        settings = QSettings("netease_downloader", "settings")
        current = settings.value("theme", "system")
        if current == "system":
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QPalette
            pal = QApplication.instance().palette()
            color = pal.color(QPalette.ColorRole.Window)
            r, g, b, _ = color.getRgb()
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            actual = "dark" if luminance < 0.5 else "light"
        else:
            actual = current
        try:
            self.log_panel.set_theme(actual)
        except Exception:
            pass
        right_layout.addWidget(self.log_panel, stretch=1)

        main_layout.addWidget(right_widget, stretch=2)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(version.version)
    
    def _build_menu(self):
        from PyQt6.QtGui import QAction, QActionGroup
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QMenu, QToolBar, QToolButton
        menubar = self.menuBar()
        view_menu = QMenu(i18n.tr("view"), self)

        theme_menu = view_menu.addMenu(i18n.tr("theme"))

        group = QActionGroup(self)
        act_system = QAction(i18n.tr("theme_system"), self)
        act_system.setCheckable(True)
        act_dark = QAction(i18n.tr("theme_dark"), self)
        act_dark.setCheckable(True)
        act_light = QAction(i18n.tr("theme_light"), self)
        act_light.setCheckable(True)

        group.addAction(act_system)
        group.addAction(act_dark)
        group.addAction(act_light)

        theme_menu.addAction(act_system)
        theme_menu.addAction(act_dark)
        theme_menu.addAction(act_light)

        settings = QSettings("netease_downloader", "settings")
        current = settings.value("theme", "system")
        if current == "dark":
            act_dark.setChecked(True)
        elif current == "light":
            act_light.setChecked(True)
        else:
            act_system.setChecked(True)

        act_system.triggered.connect(lambda: self._on_theme_selected("system"))
        act_dark.triggered.connect(lambda: self._on_theme_selected("dark"))
        act_light.triggered.connect(lambda: self._on_theme_selected("light"))

        # 语言切换
        lang_menu = view_menu.addMenu(i18n.tr("lang"))
        lang_group = QActionGroup(self)
        act_zh = QAction(i18n.tr("lang_zh"), self)
        act_zh.setCheckable(True)
        act_en = QAction(i18n.tr("lang_en"), self)
        act_en.setCheckable(True)
        lang_group.addAction(act_zh)
        lang_group.addAction(act_en)
        lang_menu.addAction(act_zh)
        lang_menu.addAction(act_en)

        current_lang = settings.value("lang", i18n.get_lang())
        if current_lang == "en_us":
            act_en.setChecked(True)
        else:
            act_zh.setChecked(True)

        act_zh.triggered.connect(lambda: self._on_lang_selected("zh_cn"))
        act_en.triggered.connect(lambda: self._on_lang_selected("en_us"))

        # 刷新界面按钮
        act_refresh = QAction(i18n.tr("refresh_ui"), self)
        act_refresh.setShortcut("F5")
        view_menu.addSeparator()
        view_menu.addAction(act_refresh)
        act_refresh.triggered.connect(self._reload_ui)

        toolbar = QToolBar(i18n.tr("toolbar"), self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        toolbtn = QToolButton(self)
        toolbtn.setText(i18n.tr("toolbar_view"))
        toolbtn.setMenu(view_menu)
        def _show_view_menu():
            pos = toolbtn.mapToGlobal(toolbtn.rect().bottomLeft())
            pos.setY(pos.y() + 2)
            view_menu.exec(pos)
        toolbtn.clicked.connect(_show_view_menu)
        toolbar.addWidget(toolbtn)

    def _connect_signals(self):
        self.download_panel.browse_clicked.connect(self._browse_path)
        self.download_panel.start_clicked.connect(self._start_download)
        self.download_panel.pause_clicked.connect(self._pause_download)
        self.download_panel.resume_clicked.connect(self._resume_download)
        self.download_panel.stop_clicked.connect(self._stop_download)
        self.download_panel.check_api_clicked.connect(self._check_api)
        self.download_panel.search_clicked.connect(self._open_search)
        self.download_panel.ai_chat_clicked.connect(self._open_ai_chat)
    
    def _log(self, msg: str):
        self.log_panel.append(msg)
    
    def _browse_path(self):
        self.download_panel.browse_directory()
    
    def _check_api(self):
        from core.api_client import APIClient
        api = APIClient(self.download_panel.get_api_url())
        if api.check_alive():
            self.api_status.set_online(True, i18n.tr("api_online"))
            self._log(i18n.tr("api_ok"))
        else:
            self.api_status.set_online(False, i18n.tr("api_offline"))
            self._log(i18n.tr("api_fail"))
    
    def _open_search(self):
        if self._search_dialog and self._search_dialog.isVisible():
            self._search_dialog.raise_()
            self._search_dialog.activateWindow()
            return
        
        self._search_dialog = SearchDialog(None, self.download_panel.get_api_url())
        self._search_dialog.song_selected.connect(self._on_song_selected)
        self._search_dialog.playlist_selected.connect(self._on_playlist_selected)
        self._search_dialog.mv_selected.connect(self._on_mv_selected)
        self._search_dialog.preview_requested.connect(self._on_preview)
        self._search_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self._search_dialog.show()
        self._log(i18n.tr("search_window_open"))
    
    def _open_ai_chat(self):
        api_key = self.download_panel.get_ai_api_key()
        if not api_key:
            from PyQt6.QtWidgets import QMessageBox
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
    
    def _on_song_selected(self, song_id, song_name, artist):
        self.download_panel.set_task_id(song_id)
        self._log(f"{i18n.tr('selected')}: {song_name} - {artist}")
    
    def _on_mv_selected(self, mv_id, mv_name):
        self.download_panel.set_task_id(mv_id)
        self.download_panel.set_task_type(3)
        self._log(f"{i18n.tr('selected_mv')}: {mv_name}")

    def _on_preview(self, item_id, item_name, item_type):
        from core.api_client import APIClient, APIError
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QObject, pyqtSignal, QThread

        api = APIClient(self.download_panel.get_api_url())

        try:
            if item_type == "song" or item_type == "mv":
                if self._preview_dialog and self._preview_dialog.isVisible():
                    self._preview_dialog.close()

                class _Fetcher(QObject):
                    finished = pyqtSignal(object)
                    def __init__(self, api, sid, br):
                        super().__init__()
                        self.api = api
                        self.sid = sid
                        self.br = br
                    def run(self):
                        try:
                            u = self.api.get_download_url(self.sid, self.br)
                        except Exception:
                            u = None
                        self.finished.emit(u)

                self._preview_dialog = PreviewDialog(None, item_name, "", "")
                self._preview_dialog.setWindowModality(Qt.WindowModality.NonModal)

                fetcher = _Fetcher(api, item_id, 128000)
                thread = QThread(self)
                fetcher.moveToThread(thread)
                thread.started.connect(fetcher.run)

                def on_finished(u):
                    if u:
                        self._preview_dialog.set_source(u)
                    else:
                        QMessageBox.warning(self, i18n.tr("preview_fail"), i18n.tr("preview_no_url"))
                    try:
                        thread.quit()
                        thread.wait()
                    except Exception:
                        pass

                fetcher.finished.connect(on_finished)
                thread.start()

                self._preview_dialog.show()
            elif item_type == "playlist":
                self._open_playlist_dialog(item_id, item_name)
            else:
                QMessageBox.information(self, i18n.tr("notice"), i18n.tr("unsupported_type"))
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), f"{i18n.tr('preview_error')}: {e}")

    def _open_playlist_dialog(self, playlist_id, playlist_name):
        if self._playlist_dialog and self._playlist_dialog.isVisible():
            self._playlist_dialog.close()

        from ui.playlist_dialog import PlaylistDialog
        self._playlist_dialog = PlaylistDialog(None, playlist_id, playlist_name, self.download_panel.get_api_url())
        self._playlist_dialog.song_selected.connect(self._on_song_selected)
        self._playlist_dialog.preview_requested.connect(self._on_preview)
        self._playlist_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self._playlist_dialog.show()

    def _on_playlist_selected(self, playlist_id, playlist_name):
        self._open_playlist_dialog(playlist_id, playlist_name)
    
    def _start_download(self):
        task_id = self.download_panel.get_task_id()
        if not task_id:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("enter_id"))
            return
        
        task_type = self.download_panel.get_task_type()
        api_url = self.download_panel.get_api_url()
        path = self.download_panel.get_download_path()
        bitrate = self.download_panel.get_bitrate()
        
        self._downloader = DownloadTask(api_url, path, bitrate)
        self._downloader.set_task(task_type, task_id)
        
        self._downloader.log_message.connect(self._log)
        self._downloader.progress_update.connect(self._update_progress)
        self._downloader.byte_progress_update.connect(self._update_byte_progress)
        self._downloader.speed_update.connect(self._update_speed)
        self._downloader.song_start.connect(self._on_song_start)
        self._downloader.song_complete.connect(self._on_song_complete)
        self._downloader.download_finished.connect(self._on_finished)
        self._downloader.api_status.connect(self._on_api_status)
        
        self.download_panel.set_downloading_state(True)
        self.progress_bar.reset()
        
        self._downloader.start()
        type_names = {1: i18n.tr("single"), 2: i18n.tr("playlist"), 3: i18n.tr("mv")}
        self._log(f"{i18n.tr('started')} {type_names.get(task_type, '')}: {task_id}")
    
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
    
    def _on_lang_selected(self, lang: str):
        from PyQt6.QtCore import QSettings
        i18n.set_lang(lang)
        settings = QSettings("netease_downloader", "settings")
        settings.setValue("lang", lang)
        self._log(i18n.tr("lang_switched"))
        self._reload_ui()

    def _on_theme_selected(self, theme: str):
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPalette
        settings = QSettings("netease_downloader", "settings")
        settings.setValue("theme", theme)
        app = QApplication.instance()
        if theme == "system":
            pal = app.palette()
            color = pal.color(QPalette.ColorRole.Window)
            r, g, b, _ = color.getRgb()
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            actual = "dark" if luminance < 0.5 else "light"
        else:
            actual = theme
        
        stylesheet = load_stylesheet(actual)
        if stylesheet:
            app.setStyleSheet(stylesheet)
        try:
            self.log_panel.set_theme(actual)
        except Exception:
            pass

    def _reload_ui(self):
        for tb in self.findChildren(QToolBar):
            self.removeToolBar(tb)
            tb.deleteLater()
        self._build_menu()
        self.setWindowTitle(i18n.tr("window_title"))
        self.download_panel.refresh_texts()
        self.progress_bar.refresh_texts()
        self.api_status.refresh_texts()

        settings = QSettings("netease_downloader", "settings")
        theme = settings.value("theme", "system")

        if theme == "system":
            pal = QApplication.instance().palette()
            color = pal.color(QPalette.ColorRole.Window)
            r, g, b, _ = color.getRgb()
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            actual_theme = "dark" if luminance < 0.5 else "light"
        else:
            actual_theme = theme

        stylesheet = load_stylesheet(actual_theme)
        if stylesheet:
            QApplication.instance().setStyleSheet(stylesheet)

        try:
            self.log_panel.set_theme(actual_theme)
            self.log_panel.refresh()
        except AttributeError:
            pass

        try:
            self.status_bar.showMessage(i18n.tr("ui_refreshed"), 2000)
        except AttributeError:
            pass

        QTimer.singleShot(0, self._check_api)

    def _on_api_status(self, online: bool, msg: str):
        self.api_status.set_online(online, msg)
    
    def closeEvent(self, event):
        if self._downloader and self._downloader.isRunning():
            self._downloader.stop()
        if self._ai_chat:
            self._ai_chat.close()
        if self._search_dialog:
            self._search_dialog.close()
        if self._preview_dialog:
            self._preview_dialog.close()
        if self._playlist_dialog:
            self._playlist_dialog.close()
        event.accept()