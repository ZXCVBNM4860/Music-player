"""DeepSeek AI 对话组件"""

import re
import version
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from openai import OpenAI
from language import i18n


def copy_to_clipboard(text: str):
    """复制文本到剪贴板"""
    clipboard = QApplication.clipboard()
    clipboard.setText(text)


def parse_markdown(text: str):
    """解析 markdown，提取代码块和普通文本"""
    pattern = r'```(\w*)\n(.*?)```'
    parts = []
    last_end = 0
    for match in re.finditer(pattern, text, re.DOTALL):
        if match.start() > last_end:
            parts.append(('text', text[last_end:match.start()]))
        lang = match.group(1).strip()
        code = match.group(2).rstrip('\n')
        parts.append(('code', lang, code))
        last_end = match.end()
    if last_end < len(text):
        parts.append(('text', text[last_end:]))
    return parts


class AIWorker(QThread):
    response_ready = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, client, messages):
        super().__init__()
        self.client = client
        self.messages = messages
        self._running = True

    def run(self):
        try:
            response = self.client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=self.messages,
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}}
            )
            message = response.choices[0].message
            content = message.content or ""
            reasoning = getattr(message, 'reasoning_content', None) or ""
            if self._running:
                self.response_ready.emit(content, reasoning)
        except Exception as e:
            if self._running:
                self.error_occurred.emit(str(e))

    def stop(self):
        self._running = False
        self.wait(1000)


class CodeBlockWidget(QFrame):
    def __init__(self, language: str, code: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.code = code
        self._build_ui(language)

    def _build_ui(self, language: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        lang_label = QLabel(language.upper() if language else i18n.tr("code"))
        lang_label.setStyleSheet("color: #8b949e; font-size: 9pt; font-weight: bold;")
        header_layout.addWidget(lang_label)
        header_layout.addStretch()

        copy_btn = QPushButton(i18n.tr("copy"))
        copy_btn.setFixedSize(60, 28)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        copy_btn.clicked.connect(self._copy_code)
        header_layout.addWidget(copy_btn)

        layout.addWidget(header)

        code_edit = QPlainTextEdit()
        code_edit.setPlainText(self.code)
        code_edit.setReadOnly(True)
        code_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        lines = self.code.count('\n') + 1
        line_height = 18
        padding = 16
        max_height = 400
        ideal_height = lines * line_height + padding
        actual_height = min(max(ideal_height, 40), max_height)
        code_edit.setFixedHeight(actual_height)

        code_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 0 0 8px 8px;
                padding: 8px 12px;
                font-family: "Consolas", "SF Mono", "Fira Code", monospace;
                font-size: 10pt;
                line-height: 1.5;
            }
            QPlainTextEdit QScrollBar:vertical {
                background: #0d1117;
                width: 6px;
            }
            QPlainTextEdit QScrollBar::handle:vertical {
                background: #30363d;
                border-radius: 3px;
            }
        """)
        layout.addWidget(code_edit)

    def _copy_code(self):
        copy_to_clipboard(self.code)
        btn = self.sender()
        btn.setText(i18n.tr("copied"))
        btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #238636;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 9pt;
            }
        """)
        QTimer.singleShot(1500, lambda: self._reset_btn(btn))

    def _reset_btn(self, btn):
        btn.setText(i18n.tr("copy"))
        btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)


class TextBlockWidget(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build_ui(text)

    def _build_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet("""
            QLabel {
                color: #eaeaea;
                font-size: 10pt;
                line-height: 1.6;
                padding: 8px 0;
            }
        """)
        layout.addWidget(label)


class UserBubble(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build_ui(text)

    def _build_ui(self, text: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)
        layout.addStretch()

        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #1a2332;
                border: 1px solid #2a3a4a;
                border-radius: 12px 12px 4px 12px;
            }
        """)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(0)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet("color: #eaeaea; font-size: 10pt; line-height: 1.5;")
        bubble_layout.addWidget(label)

        layout.addWidget(bubble)
        layout.setStretch(0, 1)


class AIBubble(QFrame):
    def __init__(self, text: str, reasoning: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build_ui(text, reasoning)

    def _build_ui(self, text: str, reasoning: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        if reasoning:
            thinking = QFrame()
            thinking.setStyleSheet("""
                QFrame {
                    background-color: #0a0a0a;
                    border: 1px dashed #2a2a2a;
                    border-radius: 8px;
                }
            """)
            t_layout = QVBoxLayout(thinking)
            t_layout.setContentsMargins(12, 8, 12, 8)

            t_label = QLabel(f"{reasoning}")
            t_label.setWordWrap(True)
            t_label.setStyleSheet("color: #666666; font-size: 9pt; line-height: 1.5;")
            t_layout.addWidget(t_label)
            layout.addWidget(thinking)

        parts = parse_markdown(text)

        for part in parts:
            if part[0] == 'text':
                txt = part[1].strip()
                if txt:
                    tw = TextBlockWidget(txt)
                    layout.addWidget(tw)
            elif part[0] == 'code':
                lang, code = part[1], part[2]
                cw = CodeBlockWidget(lang, code)
                layout.addWidget(cw)


class DeepSeekChat(QMainWindow):
    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("deepseek_chat"))
        self.setMinimumSize(700, 600)

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant"}
        ]
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel(i18n.tr("deepseek_assistant"))
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #eaeaea;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 聊天记录
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        scroll.setWidget(self.chat_container)
        layout.addWidget(scroll, stretch=1)

        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 6, 10, 6)
        input_layout.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText(i18n.tr("input_hint"))
        self.input_box.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_box, stretch=1)

        self.send_btn = QPushButton(i18n.tr("send"))
        self.send_btn.setFixedWidth(70)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        self.clear_btn = QPushButton(i18n.tr("clear"))
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666666;
                border: 1px solid #333333;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                color: #eaeaea;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_chat)
        input_layout.addWidget(self.clear_btn)

        layout.addWidget(input_frame)

        # 状态栏
        self.status_label = QLabel(version.version)
        self.status_label.setStyleSheet("color: #555555; font-size: 9pt;")
        layout.addWidget(self.status_label)

    def _send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return

        self._add_user_message(text)
        self.input_box.clear()
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.status_label.setText(i18n.tr("thinking"))

        self.messages.append({"role": "user", "content": text})

        self.worker = AIWorker(self.client, self.messages.copy())
        self.worker.response_ready.connect(self._on_response)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _add_user_message(self, text: str):
        bubble = UserBubble(text)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _add_ai_message(self, text: str, reasoning: str = ""):
        bubble = AIBubble(text, reasoning)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        for child in self.findChildren(QScrollArea):
            vbar = child.verticalScrollBar()
            vbar.setValue(vbar.maximum())

    def _on_response(self, content, reasoning):
        self._add_ai_message(content, reasoning)
        self.messages.append({"role": "assistant", "content": content})

    def _on_error(self, error_msg):
        self._add_ai_message(f"{i18n.tr('ai_error')}: {error_msg}")

    def _on_finished(self):
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setFocus()
        self.status_label.setText(version.version)

    def _clear_chat(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant"}
        ]
        self.status_label.setText(i18n.tr("cleared"))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        event.accept()
