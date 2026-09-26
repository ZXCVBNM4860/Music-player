# ui/api_installer_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTextEdit, QGroupBox, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from language import i18n
from core.api_installer import APIInstaller


class InstallerWorker(QThread):
    log_line = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, node_mirror, npm_mirror, github_mirror):
        super().__init__()
        self.node_mirror = node_mirror
        self.npm_mirror = npm_mirror
        self.github_mirror = github_mirror
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        installer = APIInstaller(
            node_mirror=self.node_mirror,
            npm_mirror=self.npm_mirror,
            github_mirror=self.github_mirror,
            log=self.log_line.emit,
            cancel_flag=lambda: self._cancelled,
        )
        ok, msg_key = installer.install()
        self.finished_signal.emit(ok, msg_key)


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

        tip = QLabel(i18n.tr("api_installer_tip"))
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #cccccc;")
        layout.addWidget(tip)

        mirror_group = QGroupBox(i18n.tr("api_installer_mirror_group"))
        mirror_layout = QVBoxLayout(mirror_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel(i18n.tr("api_installer_node_mirror")))
        self.node_mirror = QComboBox()
        self.node_mirror.addItem(i18n.tr("mirror_official"), "official")
        self.node_mirror.addItem(i18n.tr("mirror_npmmirror"), "npmmirror")
        self.node_mirror.setCurrentIndex(1)
        row1.addWidget(self.node_mirror, stretch=1)
        mirror_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(i18n.tr("api_installer_npm_mirror")))
        self.npm_mirror = QComboBox()
        self.npm_mirror.addItem(i18n.tr("mirror_official"), "official")
        self.npm_mirror.addItem(i18n.tr("mirror_npmmirror"), "npmmirror")
        self.npm_mirror.setCurrentIndex(1)
        row2.addWidget(self.npm_mirror, stretch=1)
        mirror_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel(i18n.tr("api_installer_github_mirror")))
        self.github_mirror = QComboBox()
        self.github_mirror.addItem(i18n.tr("mirror_official"), "official")
        self.github_mirror.addItem(i18n.tr("mirror_ghproxy"), "ghproxy")
        self.github_mirror.setCurrentIndex(0)
        row3.addWidget(self.github_mirror, stretch=1)
        mirror_layout.addLayout(row3)

        layout.addWidget(mirror_group)

        log_group = QGroupBox(i18n.tr("api_installer_log_group"))
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet(
            "QTextEdit {background-color: #0d1117;color: #c9d1d9;"
            "font-family: Consolas,monospace;font-size: 9pt;padding: 6px;}"
        )
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_group, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_start = QPushButton(i18n.tr("api_installer_start"))
        self.btn_start.setStyleSheet("font-weight: bold;padding: 8px 24px;")
        self.btn_start.clicked.connect(self._on_start)
        btn_layout.addWidget(self.btn_start)

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _append_log(self, msg: str):
        self.log_edit.append(msg)
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_start(self):
        if self.worker and self.worker.isRunning():
            return

        self.btn_start.setEnabled(False)
        self.log_edit.clear()
        self._append_log(i18n.tr("api_installer_begin"))

        self.worker = InstallerWorker(
            node_mirror=self.node_mirror.currentData(),
            npm_mirror=self.npm_mirror.currentData(),
            github_mirror=self.github_mirror.currentData(),
        )
        self.worker.log_line.connect(self._append_log)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, ok: bool, msg_key: str):
        self.btn_start.setEnabled(True)
        self._append_log("")
        self._append_log("=" * 40)
        self._append_log(i18n.tr(msg_key))

        if ok:
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr(msg_key))
            self.accept()
        else:
            QMessageBox.warning(self, i18n.tr("error"), i18n.tr(msg_key))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        event.accept()