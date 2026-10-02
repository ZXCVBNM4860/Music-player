# ui/api_installer_dialog.py

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,QDialog,QGroupBox,
    QHBoxLayout,QLabel,QMessageBox,
    QPushButton,QTextEdit,QVBoxLayout,
)

from core.api_installer import APIInstaller
from language import i18n


_LOG_STYLE = (
    "QTextEdit {"
    "background-color: #0d1117;"
    "color: #c9d1d9;"
    "font-family: Consolas, monospace;"
    "font-size: 9pt;"
    "padding: 6px;}"
)


class InstallerWorker(QThread):
    log_line = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, npm_mirror, github_mirror):
        super().__init__()
        self.npm_mirror = npm_mirror
        self.github_mirror = github_mirror
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        installer = APIInstaller(
            npm_mirror=self.npm_mirror,
            github_mirror=self.github_mirror,
            log=self.log_line.emit,
            cancel_flag=lambda: self._cancelled,
        )

        ok, message_key = installer.install()
        self.finished_signal.emit(ok, message_key)


class APIInstallerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(i18n.tr("api_installer_title"))
        self.setMinimumSize(680, 520)

        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        layout.addWidget(self._build_tip_label())
        layout.addWidget(self._build_mirror_group())
        layout.addWidget(self._build_log_group(), stretch=1)
        layout.addLayout(self._build_button_row())

    @staticmethod
    def _build_tip_label() -> QLabel:
        tip = QLabel(i18n.tr("api_installer_tip"))
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #cccccc;")
        return tip

    def _build_mirror_group(self) -> QGroupBox:
        group = QGroupBox(i18n.tr("api_installer_mirror_group"))
        layout = QVBoxLayout(group)

        layout.addLayout(self._build_npm_mirror_row())
        layout.addLayout(self._build_github_mirror_row())

        return group

    def _build_npm_mirror_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("api_installer_npm_mirror")))

        self.npm_mirror = QComboBox()
        self.npm_mirror.addItem(i18n.tr("mirror_official"), "official")
        self.npm_mirror.addItem(i18n.tr("mirror_npmmirror"), "npmmirror")
        self.npm_mirror.setCurrentIndex(1)
        row.addWidget(self.npm_mirror, stretch=1)

        return row

    def _build_github_mirror_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("api_installer_github_mirror")))

        self.github_mirror = QComboBox()
        self.github_mirror.addItem(i18n.tr("mirror_official"), "official")
        self.github_mirror.addItem(i18n.tr("mirror_ghproxy"), "ghproxy")
        self.github_mirror.setCurrentIndex(0)
        row.addWidget(self.github_mirror, stretch=1)

        return row

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox(i18n.tr("api_installer_log_group"))
        layout = QVBoxLayout(group)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet(_LOG_STYLE)
        layout.addWidget(self.log_edit)

        return group

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        self.btn_start = QPushButton(i18n.tr("api_installer_start"))
        self.btn_start.setStyleSheet("font-weight: bold;padding: 8px 24px;")
        self.btn_start.clicked.connect(self._on_start)
        row.addWidget(self.btn_start)

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        row.addWidget(self.btn_close)

        return row

    def _append_log(self, message: str):
        self.log_edit.append(message)

        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_start(self):
        if self.worker and self.worker.isRunning():
            return

        self.btn_start.setEnabled(False)
        self.log_edit.clear()
        self._append_log(i18n.tr("api_installer_begin"))

        self.worker = InstallerWorker(
            npm_mirror=self.npm_mirror.currentData(),
            github_mirror=self.github_mirror.currentData(),
        )
        self.worker.log_line.connect(self._append_log)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, ok: bool, message_key: str):
        self.btn_start.setEnabled(True)
        self._append_log(i18n.tr(message_key))

        if ok:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr(message_key)
            )
            self.accept()
        else:
            QMessageBox.warning(
                self, i18n.tr("error"), i18n.tr(message_key)
            )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)

        event.accept()