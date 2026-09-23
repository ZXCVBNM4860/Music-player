# ui/netease_login_dialog.py
import base64
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QTabWidget, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap


class NeteaseLoginDialog(QDialog):
    def __init__(self, parent=None, api_url="http://localhost:3000"):
        super().__init__(parent)
        self.setWindowTitle("网易云登录")
        self.setMinimumSize(400, 500)
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.cookies = None
        self._qr_unikey = None
        self._qr_timer = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        tabs = QTabWidget()

        qr_tab = QWidget()
        qr_layout = QVBoxLayout(qr_tab)
        self.qr_label = QLabel("点击下方按钮生成二维码")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(250, 250)
        self.qr_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
                color: #888888;
            }
        """)
        qr_layout.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.btn_qr = QPushButton("生成二维码")
        self.btn_qr.clicked.connect(self._generate_qr)
        qr_layout.addWidget(self.btn_qr)
        self.qr_status = QLabel("")
        self.qr_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_status.setStyleSheet("color: #888888;")
        qr_layout.addWidget(self.qr_status)
        qr_layout.addStretch()
        tabs.addTab(qr_tab, "扫码登录")

        cookie_tab = QWidget()
        cookie_layout = QVBoxLayout(cookie_tab)
        cookie_layout.addWidget(QLabel("从浏览器复制 MUSIC_U 和 __csrf 值："))
        self.music_u_input = QLineEdit()
        self.music_u_input.setPlaceholderText("MUSIC_U")
        cookie_layout.addWidget(self.music_u_input)
        self.csrf_input = QLineEdit()
        self.csrf_input.setPlaceholderText("__csrf")
        cookie_layout.addWidget(self.csrf_input)
        btn_cookie = QPushButton("登录")
        btn_cookie.clicked.connect(self._login_cookie)
        cookie_layout.addWidget(btn_cookie)
        cookie_layout.addStretch()
        tabs.addTab(cookie_tab, "Cookie登录")

        layout.addWidget(tabs)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)

    def _generate_qr(self):
        try:
            r = self.session.get(f"{self.api_url}/login/qr/key", timeout=10)
            data = r.json()
            if data.get("code") != 200:
                self.qr_status.setText("获取二维码失败")
                return
            self._qr_unikey = data["data"]["unikey"]

            r = self.session.get(
                f"{self.api_url}/login/qr/create",
                params={"key": self._qr_unikey, "qrimg": "true"},
                timeout=10
            )
            data = r.json()
            if data.get("code") != 200:
                self.qr_status.setText("生成二维码失败")
                return

            qr_base64 = data["data"]["qrimg"].split(",")[-1]
            qr_bytes = base64.b64decode(qr_base64)
            pixmap = QPixmap()
            pixmap.loadFromData(qr_bytes)
            self.qr_label.setPixmap(pixmap.scaled(
                250, 250,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            self.qr_label.setStyleSheet("")
            self.qr_status.setText("请使用网易云音乐 App 扫码")
            self.btn_qr.setEnabled(False)
            self._qr_timer = QTimer(self)
            self._qr_timer.timeout.connect(self._check_qr_status)
            self._qr_timer.start(2000)
        except Exception as e:
            self.qr_status.setText(f"错误: {e}")

    def _check_qr_status(self):
        if not self._qr_unikey:
            return
        try:
            r = self.session.get(
                f"{self.api_url}/login/qr/check",
                params={"key": self._qr_unikey},
                timeout=10
            )
            data = r.json()
            code = data.get("code")

            if code == 800:
                self.qr_status.setText("二维码已过期，请重新生成")
                self._stop_qr_timer()
            elif code == 801:
                self.qr_status.setText("等待扫码...")
            elif code == 802:
                self.qr_status.setText("已扫码，请在手机上确认")
            elif code == 803:
                self.qr_status.setText("登录成功！")
                self._stop_qr_timer()
                self.cookies = r.cookies.get_dict()
                self.accept()
        except Exception:
            pass

    def _stop_qr_timer(self):
        if self._qr_timer:
            self._qr_timer.stop()
            self._qr_timer = None
        self.btn_qr.setEnabled(True)

    def _login_cookie(self):
        music_u = self.music_u_input.text().strip()
        csrf = self.csrf_input.text().strip()
        if not music_u or not csrf:
            QMessageBox.warning(self, "提示", "请填写完整的 Cookie")
            return
        try:
            r = self.session.get(
                f"{self.api_url}/login/status",
                cookies={"MUSIC_U": music_u, "__csrf": csrf},
                timeout=10
            )
            data = r.json()
            if data.get("data", {}).get("profile"):
                self.cookies = {"MUSIC_U": music_u, "__csrf": csrf}
                QMessageBox.information(self, "成功", "登录成功！")
                self.accept()
            else:
                QMessageBox.warning(self, "失败", "Cookie 无效或已过期")
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))

    def get_cookies(self):
        return self.cookies

    def closeEvent(self, event):
        self._stop_qr_timer()
        event.accept()