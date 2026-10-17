# ui/deepseek_chat.py

import re

from openai import OpenAI
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,QFrame,
    QHBoxLayout,QLabel,QLineEdit,
    QScrollArea,QVBoxLayout,QWidget,
    QMainWindow,QPlainTextEdit,QPushButton
)

from language import i18n

try:
    import version
    _VERSION = getattr(version, "version", "beta")
except Exception:
    _VERSION = "beta"


def copy_to_clipboard(text: str):
    QApplication.clipboard().setText(text)


def parse_markdown(text: str):
    pattern = r"```(\w*)\n(.*?)```"

    parts = []
    last_end = 0

    for match in re.finditer(pattern, text, re.DOTALL):
        if match.start() > last_end:
            parts.append(("text", text[last_end:match.start()]))

        language = match.group(1).strip()
        code = match.group(2).rstrip("\n")
        parts.append(("code", language, code))

        last_end = match.end()

    if last_end < len(text):
        parts.append(("text", text[last_end:]))

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
                extra_body={
                    "reasoning_effort": "high",
                    "thinking": {"type": "enabled"},
                },
            )
            message = response.choices[0].message
            content = message.content or ""
            reasoning = getattr(message, "reasoning_content", None) or ""

            if self._running:
                self.response_ready.emit(content, reasoning)
        except Exception as exc:
            if self._running:
                self.error_occurred.emit(str(exc))

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
        header.setObjectName("codeBlockHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        lang_label = QLabel(language.upper() if language else i18n.tr("code"))
        lang_label.setObjectName("codeLang")
        header_layout.addWidget(lang_label)
        header_layout.addStretch()

        self.copy_btn = QPushButton(i18n.tr("copy"))
        self.copy_btn.setObjectName("codeCopyBtn")
        self.copy_btn.setFixedSize(60, 28)
        self.copy_btn.clicked.connect(self._copy_code)
        header_layout.addWidget(self.copy_btn)

        layout.addWidget(header)

        edit = QPlainTextEdit()
        edit.setObjectName("codeEdit")
        edit.setPlainText(self.code)
        edit.setReadOnly(True)
        edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        lines = self.code.count("\n") + 1
        ideal = lines * 18 + 16
        edit.setFixedHeight(min(max(ideal, 40), 400))

        layout.addWidget(edit)

    def _copy_code(self):
        copy_to_clipboard(self.code)

        self.copy_btn.setText(i18n.tr("copied"))
        self._set_copied(True)

        QTimer.singleShot(1500, self._reset_copy_button)

    def _reset_copy_button(self):
        self.copy_btn.setText(i18n.tr("copy"))
        self._set_copied(False)

    def _set_copied(self, copied: bool):
        self.copy_btn.setProperty("copied", "true" if copied else "false")
        self.copy_btn.style().unpolish(self.copy_btn)
        self.copy_btn.style().polish(self.copy_btn)


class TextBlockWidget(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        label = QLabel(text)
        label.setObjectName("textBlock")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)


class UserBubble(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)
        layout.addStretch()

        bubble = QFrame()
        bubble.setObjectName("userBubble")

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(0)

        label = QLabel(text)
        label.setObjectName("userBubbleText")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_layout.addWidget(label)

        layout.addWidget(bubble)
        layout.setStretch(0, 1)


class AIBubble(QFrame):
    def __init__(self, text: str, reasoning: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        if reasoning:
            layout.addWidget(self._build_thinking_box(reasoning))

        for part in parse_markdown(text):
            if part[0] == "text":
                content = part[1].strip()
                if content:
                    layout.addWidget(TextBlockWidget(content))
            elif part[0] == "code":
                layout.addWidget(CodeBlockWidget(part[1], part[2]))

    @staticmethod
    def _build_thinking_box(reasoning: str) -> QFrame:
        box = QFrame()
        box.setObjectName("thinkingBubble")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 8, 12, 8)

        label = QLabel(reasoning)
        label.setObjectName("thinkingText")
        label.setWordWrap(True)
        layout.addWidget(label)

        return box


class DeepSeekChat(QMainWindow):
    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)

        self.setObjectName("deepseekChat")
        self.setWindowTitle(i18n.tr("deepseek_chat"))
        self.setMinimumSize(700, 600)

        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.messages = [{"role": "system", "content": "You are a helpful assistant"}]
        self.worker = None

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(i18n.tr("deepseek_assistant"))
        title.setObjectName("chatTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addWidget(self._build_chat_area(), stretch=1)
        layout.addWidget(self._build_input_frame())

        self.status_label = QLabel(_VERSION)
        self.status_label.setObjectName("chatStatus")
        layout.addWidget(self.status_label)

    def _build_chat_area(self) -> QScrollArea:
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
        return scroll

    def _build_input_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("chatInputFrame")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText(i18n.tr("input_hint"))
        self.input_box.returnPressed.connect(self._send_message)
        layout.addWidget(self.input_box, stretch=1)

        self.send_btn = QPushButton(i18n.tr("send"))
        self.send_btn.setFixedWidth(70)
        self.send_btn.clicked.connect(self._send_message)
        layout.addWidget(self.send_btn)

        self.clear_btn = QPushButton(i18n.tr("clear"))
        self.clear_btn.setObjectName("chatClearBtn")
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.clicked.connect(self._clear_chat)
        layout.addWidget(self.clear_btn)

        return frame

    def _send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return

        self._add_user_message(text)
        self.input_box.clear()
        self._set_busy(True)

        self.messages.append({"role": "user", "content": text})

        self.worker = AIWorker(self.client, self.messages.copy())
        self.worker.response_ready.connect(self._on_response)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _set_busy(self, busy: bool):
        self.input_box.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)

        if busy:
            self.status_label.setText(i18n.tr("thinking"))
        else:
            self.status_label.setText(_VERSION)
            self.input_box.setFocus()

    def _on_response(self, content, reasoning):
        self._add_ai_message(content, reasoning)
        self.messages.append({"role": "assistant", "content": content})

    def _on_error(self, error_message):
        self._add_ai_message(f"{i18n.tr('ai_error')}: {error_message}")

    def _on_finished(self):
        self._set_busy(False)

    def _add_user_message(self, text: str):
        self.chat_layout.insertWidget(
            self.chat_layout.count() - 1, UserBubble(text)
        )
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _add_ai_message(self, text: str, reasoning: str = ""):
        self.chat_layout.insertWidget(
            self.chat_layout.count() - 1, AIBubble(text, reasoning)
        )
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        for child in self.findChildren(QScrollArea):
            scrollbar = child.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _clear_chat(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.messages = [{"role": "system", "content": "You are a helpful assistant"}]
        self.status_label.setText(i18n.tr("cleared"))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        event.accept()