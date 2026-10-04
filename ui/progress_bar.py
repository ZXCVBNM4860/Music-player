# ui/progress_bar.py

from PyQt6.QtWidgets import (
    QProgressBar,QHBoxLayout,
    QVBoxLayout,QLabel,QWidget
)

from language import i18n


class DownloadProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.status_label = QLabel(i18n.tr("ready"))
        self.status_label.setObjectName("progressStatus")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("downloadProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)

        info = QHBoxLayout()

        self.speed_label = QLabel("")
        self.speed_label.setObjectName("progressSpeed")
        info.addWidget(self.speed_label)

        info.addStretch()

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("progressDetail")
        info.addWidget(self.detail_label)

        layout.addLayout(info)

    def set_progress(self, current: int, total: int):
        if total <= 0:
            return
        percent = int(current / total * 100)
        self._render(percent, f"{current} / {total}", f"{percent}%")

    def set_byte_progress(self, downloaded: int, total: int):
        if total <= 0:
            return
        percent = int(downloaded / total * 100)
        detail = f"{self._fmt_size(downloaded)} / {self._fmt_size(total)}"
        self._render(percent, detail, f"{percent}%")

    def set_speed(self, speed_text: str):
        self.speed_label.setText(f"{i18n.tr('speed')}: {speed_text}")

    def set_status(self, text: str):
        self.status_label.setText(text)
        self.detail_label.setText("")
        self.speed_label.setText("")

    def set_song_name(self, name: str):
        self.detail_label.setText(name)

    def reset(self):
        self.progress.setValue(0)
        self.status_label.setText(i18n.tr("ready"))
        self.detail_label.setText("")
        self.speed_label.setText("")

    def refresh_texts(self):
        current = self.status_label.text()
        if not current or current == i18n.tr("ready"):
            self.status_label.setText(i18n.tr("ready"))

    def _render(self, percent: int, status_text: str, detail_text: str):
        self.progress.setValue(percent)

        level = "high" if percent >= 48 else "normal"
        self.progress.setProperty("level", level)
        self.progress.style().unpolish(self.progress)
        self.progress.style().polish(self.progress)

        self.status_label.setText(status_text)
        self.detail_label.setText(detail_text)

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size > 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
        if size > 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size > 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"