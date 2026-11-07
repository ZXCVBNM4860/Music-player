# ui/log_panel.py

from datetime import datetime

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("logPanel")
        self.text_edit.setReadOnly(True)

        self._max_lines = 1000

        layout.addWidget(self.text_edit)

    def refresh(self):
        self.text_edit.viewport().update()
        self.text_edit.update()

        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_edit.append(f"[{timestamp}] {message}")

        doc = self.text_edit.document()
        while doc.blockCount() > self._max_lines:
            cursor = QTextCursor(doc)
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())