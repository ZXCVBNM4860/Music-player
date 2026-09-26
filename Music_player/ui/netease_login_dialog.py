import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtNetwork import QNetworkCookie
from language import i18n


NETEASE_LOGIN_URL = "https://music.163.com/#/login"


class PopupWebEnginePage(QWebEnginePage):
    def createWindow(self, window_type):
        return self


class NeteaseLoginDialog(QDialog):
    def __init__(self, parent=None, api_url="http://localhost:3000"):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("netease_login_title"))
        self.setMinimumSize(900, 650)
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.cookies = None
        self.user_info = None
        self._logged_in = False

        self._build_ui()
        self._setup_cookie_monitor()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tip = QLabel(i18n.tr("netease_login_web_tip"))
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(
            "padding: 8px; background-color: #2a2a2a; color: #eaeaea; "
            "font-size: 10pt;"
        )
        layout.addWidget(tip)

        self.web_view = QWebEngineView()
        self._custom_page = PopupWebEnginePage(self.web_view)
        self.web_view.setPage(self._custom_page)

        settings = self.web_view.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True
        )

        self.web_view.setUrl(QUrl(NETEASE_LOGIN_URL))
        layout.addWidget(self.web_view, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 8, 10, 8)

        self.btn_manual = QPushButton(i18n.tr("netease_login_manual"))
        self.btn_manual.clicked.connect(self._show_manual_input)
        btn_layout.addWidget(self.btn_manual)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton(i18n.tr("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _setup_cookie_monitor(self):
        profile = self.web_view.page().profile()
        self._cookie_store = profile.cookieStore()
        self._cookie_store.cookieAdded.connect(self._on_cookie_added)

    def _on_cookie_added(self, cookie: QNetworkCookie):
        if self._logged_in:
            return
        try:
            name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        except Exception:
            return
        if name != "MUSIC_U":
            return
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        if not value:
            return

        self._logged_in = True
        self.cookies = {"MUSIC_U": value}
        QTimer.singleShot(100, self._finalize_login)

    def _finalize_login(self):
        self._fetch_user_info()
        QMessageBox.information(
            self, i18n.tr("success_title"), i18n.tr("netease_login_ok")
        )
        self.accept()

    def _fetch_user_info(self):
        try:
            r = self.session.get(
                f"{self.api_url}/login/status",
                cookies=self.cookies, timeout=10
            )
            profile = r.json().get("data", {}).get("profile") or {}
            self.user_info = {
                "nickname": profile.get("nickname", ""),
                "userId": profile.get("userId", ""),
            }
        except Exception:
            self.user_info = {"nickname": "", "userId": ""}

    def _show_manual_input(self):
        dialog = _ManualCookieDialog(self)
        if dialog.exec():
            cookies = dialog.get_cookies()
            if cookies:
                self.cookies = cookies
                self._fetch_user_info()
                QMessageBox.information(
                    self, i18n.tr("success_title"), i18n.tr("netease_login_ok")
                )
                self.accept()

    def get_cookies(self):
        return self.cookies

    def get_user_info(self):
        return self.user_info

    def closeEvent(self, event):
        try:
            self._cookie_store.cookieAdded.disconnect(self._on_cookie_added)
        except Exception:
            pass
        event.accept()


class _ManualCookieDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("netease_login_manual_title"))
        self.setMinimumSize(420, 220)
        self._cookies = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(i18n.tr("netease_login_cookie_tip")))

        self.music_u_input = QLineEdit()
        self.music_u_input.setPlaceholderText("MUSIC_U")
        layout.addWidget(self.music_u_input)

        self.csrf_input = QLineEdit()
        self.csrf_input.setPlaceholderText("__csrf")
        layout.addWidget(self.csrf_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_ok = QPushButton(i18n.tr("netease_login_btn"))
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton(i18n.tr("cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_ok(self):
        music_u = self.music_u_input.text().strip()
        csrf = self.csrf_input.text().strip()
        if not music_u:
            QMessageBox.warning(self, i18n.tr("notice"),
                                i18n.tr("netease_login_cookie_incomplete"))
            return
        self._cookies = {"MUSIC_U": music_u, "__csrf": csrf}
        self.accept()

    def get_cookies(self):
        return self._cookies