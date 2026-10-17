# ui/cover_widget.py

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel


class CoverWidget(QLabel):
    def __init__(self, parent=None, size: int = 280):
        super().__init__(parent)

        self.setObjectName("coverWidget")
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._show_placeholder()

    def _show_placeholder(self):
        self.clear()
        self.setText("♪")
        self._set_placeholder(True)

    def set_cover(self, cover_data: bytes):
        if not cover_data:
            self._show_placeholder()
            return

        image = QImage.fromData(cover_data)
        if image.isNull():
            self._show_placeholder()
            return

        pixmap = QPixmap.fromImage(image).scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.setPixmap(pixmap)
        self._set_placeholder(False)

    def _set_placeholder(self, placeholder: bool):
        self.setProperty("placeholder", "true" if placeholder else "false")
        self.style().unpolish(self)
        self.style().polish(self)