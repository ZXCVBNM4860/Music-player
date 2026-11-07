# core/smtc_manager.py

import sys
from PyQt6.QtCore import QObject, pyqtSignal
from utils.helpers import log_line

try:
    from winrt.windows.media import (
        SystemMediaTransportControls, 
        SystemMediaTransportControlsPlaybackStatus, 
        MediaPlaybackType,
        SystemMediaTransportControlsButton
    )
    HAS_WINRT = True
except ImportError:
    HAS_WINRT = False


class SMTCManager(QObject):
    play_pause_signal = pyqtSignal()
    next_signal = pyqtSignal()
    prev_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.smtc = None
        if sys.platform == "win32" and HAS_WINRT:
            self._init_smtc()

    def _init_smtc(self):
        try:
            self.smtc = SystemMediaTransportControls.get_for_current_view()
            self.smtc.is_enabled = True
            self.smtc.is_play_enabled = True
            self.smtc.is_pause_enabled = True
            self.smtc.is_next_enabled = True
            self.smtc.is_previous_enabled = True
            self.smtc.is_stop_enabled = True

            self.smtc.add_button_pressed(self._on_button_pressed)
            log_line("[SMTC] Initialized successfully with winrt.")
        except Exception as e:
            log_line(f"[SMTC] Init failed: {e}")
            self.smtc = None

    def _on_button_pressed(self, sender, args):
        button = args.button
        if button == SystemMediaTransportControlsButton.PLAY:
            self.play_pause_signal.emit()
        elif button == SystemMediaTransportControlsButton.PAUSE:
            self.play_pause_signal.emit()
        elif button == SystemMediaTransportControlsButton.NEXT:
            self.next_signal.emit()
        elif button == SystemMediaTransportControlsButton.PREVIOUS:
            self.prev_signal.emit()

    def update_metadata(self, title: str, artist: str, album: str = ""):
        if not self.smtc:
            return
        try:
            updater = self.smtc.display_updater
            updater.type = MediaPlaybackType.MUSIC
            updater.music_properties.title = title
            updater.music_properties.artist = artist
            updater.music_properties.album_title = album
            updater.update()
        except Exception as e:
            log_line(f"[SMTC] Update metadata failed: {e}")

    def update_playback_status(self, is_playing: bool, is_stopped: bool = False):
        if not self.smtc:
            return
        try:
            if is_stopped:
                self.smtc.playback_status = SystemMediaTransportControlsPlaybackStatus.STOPPED
            elif is_playing:
                self.smtc.playback_status = SystemMediaTransportControlsPlaybackStatus.PLAYING
            else:
                self.smtc.playback_status = SystemMediaTransportControlsPlaybackStatus.PAUSED
        except Exception as e:
            log_line(f"[SMTC] Update status failed: {e}")