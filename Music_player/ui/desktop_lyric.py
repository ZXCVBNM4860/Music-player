# ui/desktop_lyric.py

from PyQt6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QAbstractItemView, QApplication
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QColor


class DesktopLyricWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setStyleSheet("background: transparent; border: none; outline: none;")
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.list_widget)
        
        self._lines = []
        self._current_idx = -1
        self._font_size = 16
        self._position = "bottom"
        
        self._scroll_anim = QPropertyAnimation(self.list_widget.verticalScrollBar(), b"value")
        self._scroll_anim.setDuration(300)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_lyrics(self, lines: list):
        self._lines = lines
        self._current_idx = -1
        self._refresh_display()

    def update_position(self, pos_ms: int):
        if not self._lines:
            return
            
        idx = -1
        for i, line in enumerate(self._lines):
            if line.time_ms <= pos_ms:
                idx = i
            else:
                break
                
        if idx != self._current_idx and idx >= 0:
            self._current_idx = idx
            self._highlight(idx + 1)

    def _refresh_display(self):
        self.list_widget.clear()
        if not self._lines:
            return
            
        half_height = self.list_widget.viewport().height() // 2
        if half_height <= 0:
            half_height = 50

        top_spacer = QListWidgetItem(" ")
        top_spacer.setSizeHint(QSize(1, half_height))
        self.list_widget.addItem(top_spacer)

        for line in self._lines:
            item = QListWidgetItem(line.text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            font = item.font()
            font.setPointSize(self._font_size)
            font.setBold(True)
            item.setFont(font)
            
            self.list_widget.addItem(item)

        bottom_spacer = QListWidgetItem(" ")
        bottom_spacer.setSizeHint(QSize(1, half_height))
        self.list_widget.addItem(bottom_spacer)

        if self._current_idx >= 0:
            self._highlight(self._current_idx + 1, force=True)

    def _highlight(self, list_idx: int, force=False):
        normal_color = QColor(255, 255, 255, 150)
        active_color = QColor(0, 255, 136, 255)

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                font = item.font()
                if i == list_idx:
                    item.setForeground(active_color)
                    font.setPointSize(self._font_size + 8)
                    font.setBold(True)
                else:
                    item.setForeground(normal_color)
                    font.setPointSize(self._font_size)
                    font.setBold(False)
                item.setFont(font)

        current_item = self.list_widget.item(list_idx)
        if current_item:
            scrollbar = self.list_widget.verticalScrollBar()
            current_val = scrollbar.value()
            
            self.list_widget.scrollToItem(current_item, QAbstractItemView.ScrollHint.PositionAtCenter)
            target_val = scrollbar.value()
            
            scrollbar.setValue(current_val)
            
            if abs(current_val - target_val) < 5 and not force:
                return

            self._scroll_anim.stop()
            self._scroll_anim.setStartValue(current_val)
            self._scroll_anim.setEndValue(target_val)
            self._scroll_anim.start()

    def apply_settings(self, font_size: int, position: str):
        self._font_size = font_size
        self._position = position
        
        normal_h = int(font_size * 1.5)
        active_h = int((font_size + 8) * 1.5)
        total_height = normal_h * 2 + active_h + 20
        
        screen = QApplication.primaryScreen().geometry()
        
        self.resize(screen.width(), total_height)
        
        if self._position == "bottom":
            self.move(0, screen.height() - total_height - 80)
        elif self._position == "top":
            self.move(0, 80)
        elif self._position == "center":
            self.move(0, (screen.height() - total_height) // 2)
            
        self._refresh_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._lines:
            self._refresh_display()
            if self._current_idx >= 0:
                QTimer.singleShot(50, lambda: self._highlight(self._current_idx + 1, force=True))