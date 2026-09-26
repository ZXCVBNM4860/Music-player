# ui/cover_widget.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt


class CoverWidget(QLabel):
    def __init__(self, parent=None, size: int = 280):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_placeholder()

    def _show_placeholder(self):
        self.clear()
        self.setText("♪")
        self.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
                color: #555555;
                font-size: 48pt;
            }
        """)

    def set_cover(self, cover_data: bytes):
        if not cover_data:
            self._show_placeholder()
            return
        try:
            image = QImage.fromData(cover_data)
            if image.isNull():
                self._show_placeholder()
                return
            pixmap = QPixmap.fromImage(image).scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(pixmap)
            self.setStyleSheet("""
                QLabel {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 8px;
                }
            """)
        except Exception:
            self._show_placeholder()