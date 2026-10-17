# ui/api_status.py

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from language import i18n


class APIStatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._online = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.dot = QLabel("●")
        self.dot.setObjectName("apiDot")
        layout.addWidget(self.dot)

        self.text = QLabel()
        self.text.setObjectName("apiText")
        layout.addWidget(self.text)

        layout.addStretch()

        self._apply_state(False)

    def set_online(self, online: bool, message: str = ""):
        self._online = online
        self._apply_state(online, message)

    def refresh_texts(self):
        default = i18n.tr("api_online") if self._online else i18n.tr("api_offline")
        self.text.setText(default)

    def _apply_state(self, online: bool, message: str = ""):
        state = "online" if online else "offline"

        for widget in (self.dot, self.text):
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        default = i18n.tr("api_online") if online else i18n.tr("api_offline")
        self.text.setText(message or default)