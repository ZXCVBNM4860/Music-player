"""API状态指示器"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from language import i18n


class APIStatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #ff4444; font-size: 14px;")
        layout.addWidget(self.dot)
        
        self.text = QLabel(i18n.tr("api_offline"))
        self.text.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self.text)
        
        layout.addStretch()
    
    def refresh_texts(self):
        """刷新状态文本（根据当前颜色判断在线/离线）"""
        current = self.dot.styleSheet()
        is_online = "00ff88" in current
        if is_online:
            self.text.setText(i18n.tr("api_online"))
        else:
            self.text.setText(i18n.tr("api_offline"))
    
    def set_online(self, online: bool, message: str = ""):
        if online:
            self.dot.setStyleSheet("color: #00ff88; font-size: 14px;")
            self.text.setText(message or i18n.tr("api_online"))
            self.text.setStyleSheet("color: #00ff88; font-size: 10px;")
        else:
            self.dot.setStyleSheet("color: #ff4444; font-size: 14px;")
            self.text.setText(message or i18n.tr("api_offline"))
            self.text.setStyleSheet("color: #ff4444; font-size: 10px;")
