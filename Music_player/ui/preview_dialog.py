"""预览播放弹窗（改进版：时间标签 + 拖动跳转 + closeEvent 保护）"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from language import i18n


class PreviewDialog(QDialog):
    def __init__(self, parent=None, song_name="", artist="", url=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle(f"{i18n.tr('preview_title')} - {song_name}")
        self.setMinimumSize(400, 180)
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: #eaeaea;
            }
            QLabel {
                color: #eaeaea;
            }
            QPushButton {
                background-color: #242424;
                color: #eaeaea;
                border: 1px solid #2a2a2a;
                padding: 8px;
                min-width: 60px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2d2d2d;
            }
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                background: #2d2d2d;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #eaeaea;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #a0a0a0;
                border-radius: 3px;
            }
        """)
        
        self.url = url
        self.is_playing = False
        self._loaded = False
        self._loop = False
        self._muted = False
        self._is_dragging = False  # 是否正在拖动滑块
        
        self._build_ui(song_name, artist)
        self._setup_player()
    
    def _build_ui(self, song_name, artist):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # 歌曲信息
        info_layout = QHBoxLayout()
        self.name_label = QLabel(f"♪ {song_name}")
        self.name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.name_label)

        self.artist_label = QLabel(artist)
        self.artist_label.setStyleSheet("color: #666666;")
        info_layout.addWidget(self.artist_label)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 进度条 + 时间标签
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved_preview)
        self.progress_slider.sliderPressed.connect(lambda: setattr(self, '_is_dragging', True))
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self.progress_slider)
        
        # 时间标签（居中）
        time_layout = QHBoxLayout()
        time_layout.addStretch()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #888888; font-size: 10px; font-family: monospace;")
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        # 控制按钮
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)

        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setFixedSize(36, 36)
        self.btn_mute.clicked.connect(self._toggle_mute)
        self.btn_mute.setStyleSheet("font-size:14px;")
        ctrl_layout.addWidget(self.btn_mute)

        ctrl_layout.addStretch()

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedSize(48, 48)
        self.btn_prev.clicked.connect(self._prev)
        self.btn_prev.setStyleSheet("font-size:16px;")
        ctrl_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(64, 64)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_play.setStyleSheet("font-size:20px; border-radius:32px; background-color:#1a1a1a; color:#ffffff;")
        ctrl_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(48, 48)
        self.btn_next.clicked.connect(self._next)
        self.btn_next.setStyleSheet("font-size:16px;")
        ctrl_layout.addWidget(self.btn_next)

        self.btn_repeat = QPushButton("↻")
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.setFixedSize(36, 36)
        self.btn_repeat.clicked.connect(self._toggle_loop)
        self.btn_repeat.setStyleSheet("font-size:14px;")
        ctrl_layout.addWidget(self.btn_repeat)

        layout.addLayout(ctrl_layout)
    
    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        if self.url:
            try:
                self.player.setSource(QUrl(self.url))
                self._loaded = True
            except Exception:
                self._loaded = False
        
        self.player.positionChanged.connect(self._update_position)
        self.player.durationChanged.connect(self._update_duration)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_position)
        self.timer.start(100)

    def set_source(self, url: str):
        if not url:
            return
        self.url = url
        try:
            self.player.setSource(QUrl(url))
            self._loaded = True
            self.player.play()
            self.is_playing = True
            self.btn_play.setText("⏸")
        except Exception:
            self._loaded = False

    def _toggle_play(self):
        if self.is_playing:
            self.player.pause()
            self.btn_play.setText("▶")
            self.is_playing = False
        else:
            if not self._loaded and self.url:
                try:
                    self.player.setSource(QUrl(self.url))
                    self._loaded = True
                except Exception:
                    pass
            self.player.play()
            self.btn_play.setText("⏸")
            self.is_playing = True

    def _toggle_mute(self):
        try:
            self._muted = not self._muted
            self.audio_output.setMuted(self._muted)
            self.btn_mute.setText("🔇" if self._muted else "🔊")
        except Exception:
            pass

    def _toggle_loop(self):
        self._loop = not self._loop
        self.btn_repeat.setChecked(self._loop)

    def _prev(self):
        try:
            pos = max(0, self.player.position() - 10000)
            self.player.setPosition(pos)
        except Exception:
            pass

    def _next(self):
        try:
            dur = self.player.duration() or 0
            pos = min(dur, self.player.position() + 10000)
            self.player.setPosition(pos)
        except Exception:
            pass
    
    def _on_slider_moved_preview(self, value):
        """拖动时预览时间，不实际跳转"""
        if self.player.duration() > 0:
            pos = int((value / 100) * self.player.duration())
            self._update_time_label(pos, self.player.duration())
    
    def _on_slider_released(self):
        """释放滑块时才真正跳转"""
        self._is_dragging = False
        if self.player.duration() > 0:
            value = self.progress_slider.value()
            pos = int((value / 100) * self.player.duration())
            self.player.setPosition(pos)
            self._update_time_label(pos, self.player.duration())
    
    def _update_time_label(self, position, duration):
        """格式化并更新时间标签"""
        if duration <= 0:
            self.time_label.setText("00:00 / 00:00")
            return
        pos_m, pos_s = divmod(position // 1000, 60)
        dur_m, dur_s = divmod(duration // 1000, 60)
        self.time_label.setText(f"{pos_m:02d}:{pos_s:02d} / {dur_m:02d}:{dur_s:02d}")
    
    def _update_position(self, position):
        if not self._is_dragging and self.player.duration() > 0:
            percent = int((position / self.player.duration()) * 100)
            self.progress_slider.setValue(percent)
            self._update_time_label(position, self.player.duration())
    
    def _update_duration(self, duration):
        # 更新总时长
        if duration > 0:
            self._update_time_label(self.player.position(), duration)
    
    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._loop:
            self.player.setPosition(0)
            self.player.play()
    
    def _check_position(self):
        if self.player.duration() > 0 and not self._is_dragging:
            self.progress_slider.setValue(
                int((self.player.position() / self.player.duration()) * 100)
            )

    def closeEvent(self, event):
        """关闭时安全停止播放器（异常保护）"""
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            self.timer.stop()
        except Exception:
            pass
        event.accept()