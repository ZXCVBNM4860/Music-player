# ui/local_player/lyric_widget.py

from PyQt6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QSize, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
    QListWidget, QListWidgetItem, QAbstractItemView, QApplication
)

from core.lyric_parser import LyricLine, parse_lrc, parse_tlyric
from language import i18n


class LyricWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lyricWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        top_row = QHBoxLayout()
        top_row.addStretch()
        
        self.translate_check = QCheckBox(i18n.tr("lyric_show_translation"))
        self.translate_check.setChecked(True)
        self.translate_check.toggled.connect(self._refresh_display)
        self.translate_check.setVisible(False)
        top_row.addWidget(self.translate_check)
        layout.addLayout(top_row)
        
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("lyricList")
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setWordWrap(True)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        layout.addWidget(self.list_widget, stretch=1)
        
        self._lines: list[LyricLine] = []
        self._current_idx = -1
        self._has_translation = False

        self._scroll_anim = QPropertyAnimation(self.list_widget.verticalScrollBar(), b"value")
        self._scroll_anim.setDuration(350)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_status(self, text: str):
        self.list_widget.clear()
        self._lines = []
        item = QListWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list_widget.addItem(item)
        self.translate_check.setVisible(False)

    def set_lyric(self, lrc: str, tlyric: str, force_translate: bool = False):
        self._lines = parse_lrc(lrc)
        
        if not self._lines:
            self.set_status(i18n.tr("lyric_empty"))
            self._has_translation = False
            return

        if tlyric:
            parse_tlyric(tlyric, self._lines)
            self._has_translation = True
            self.translate_check.setVisible(True)
            self.translate_check.setEnabled(True)
            self.translate_check.setChecked(True)
        elif force_translate:
            self._has_translation = True
            self.translate_check.setVisible(True)
            self.translate_check.setEnabled(True)
            self.translate_check.setChecked(True)
        else:
            self._has_translation = False
            self.translate_check.setVisible(True)
            self.translate_check.setChecked(False)
            self.translate_check.setEnabled(False)
            
        self._current_idx = -1
        self._refresh_display()

    def apply_auto_translation(self, tlyric: str):
        if not tlyric:
            self._has_translation = False
            self.translate_check.setChecked(False)
            self.translate_check.setEnabled(False)
            self._refresh_display()
            return
            
        parse_tlyric(tlyric, self._lines)
        self._refresh_display()

    def _refresh_display(self):
        self.list_widget.clear()
        show_trans = self._has_translation and self.translate_check.isChecked()
        
        half_height = self.list_widget.viewport().height() // 2
        if half_height <= 0:
            half_height = 150 

        top_spacer = QListWidgetItem(" ")
        top_spacer.setSizeHint(QSize(1, half_height))
        self.list_widget.addItem(top_spacer)

        for line in self._lines:
            text = line.text
            if show_trans and line.t_text:
                text += f"\n{line.t_text}"
            item = QListWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setPointSize(12)
            item.setFont(font)
            self.list_widget.addItem(item)

        bottom_spacer = QListWidgetItem(" ")
        bottom_spacer.setSizeHint(QSize(1, half_height))
        self.list_widget.addItem(bottom_spacer)

        if self._current_idx >= 0:
            self._highlight(self._current_idx + 1, force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._lines:
            self._refresh_display()
            if self._current_idx >= 0:
                QTimer.singleShot(50, lambda: self._highlight(self._current_idx + 1, force=True))

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

    def _highlight(self, list_idx: int, force=False):
        is_dark = QApplication.instance().palette().window().color().lightnessF() < 0.5
        normal_color = QColor("#888888") if is_dark else QColor("#999999")
        active_color = QColor("#00ff88") if is_dark else QColor("#007acc")

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                font = item.font()
                if i == list_idx:
                    item.setForeground(active_color)
                    font.setBold(True)
                    font.setPointSize(18)
                else:
                    item.setForeground(normal_color)
                    font.setBold(False)
                    font.setPointSize(12)
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