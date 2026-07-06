"""日志面板"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from datetime import datetime


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self._max_lines = 1000
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #eaeaea;
                color: #000000;
                border: 1px solid #cccccc;
                font-family: Consolas;
                font-size: 9pt;
                padding: 8px;
                selection-background-color: #007acc;
                selection-color: #eaeaea;
            }
        """)
        layout.addWidget(self.text_edit)

    def set_theme(self, theme: str):
        """Apply 'dark' or 'light' theme to the log panel."""
        if theme == "dark":
            sheet = '''
            QTextEdit {
                background-color: #1a1a1a;
                color: #eaeaea;
                border: 1px solid #333333;
                font-family: Consolas;
                font-size: 9pt;
                padding: 8px;
                selection-background-color: #2d2d2d;
                selection-color: #eaeaea;
            }
            '''
        else:
            sheet = '''
            QTextEdit {
                background-color: #eaeaea;
                color: #000000;
                border: 1px solid #cccccc;
                font-family: Consolas;
                font-size: 9pt;
                padding: 8px;
                selection-background-color: #007acc;
                selection-color: #eaeaea;
            }
            '''
        self.text_edit.setStyleSheet(sheet)
        self.text_edit.viewport().update()  # 强制视口重绘
    
    def refresh(self):
        """强制刷新日志面板（重绘 + 滚动到底部）"""
        self.text_edit.viewport().update()
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def append(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_edit.append(f"[{timestamp}] {message}")
    
        doc = self.text_edit.document()
        if doc.blockCount() > self._max_lines:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
    
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    
    def clear(self):
        self.text_edit.clear()
    
    def get_text(self) -> str:
        return self.text_edit.toPlainText()