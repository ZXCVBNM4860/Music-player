# core/player_controller.py

from PyQt6.QtCore import QObject, pyqtSignal
from core.audio_engine import AudioEngine

class PlayerController(QObject):
    position_changed = pyqtSignal(int, int)
    playback_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = AudioEngine()
        
        self.engine.on_position_changed = self._on_engine_pos
        self.engine.on_playback_finished = self._on_engine_finish

    def _on_engine_pos(self, pos_frames: int, total_frames: int):
        pos_ms = int(pos_frames / self.engine.samplerate * 1000)
        total_ms = int(total_frames / self.engine.samplerate * 1000)
        self.position_changed.emit(pos_ms, total_ms)

    def _on_engine_finish(self):
        self.playback_finished.emit()

    def load_and_play(self, path: str) -> bool:
        if self.engine.load(path):
            self.engine.play()
            return True
        return False

    def play(self):
        self.engine.play(self.engine.position)

    def pause(self):
        self.engine.pause()

    def stop(self):
        self.engine.stop()

    def seek(self, ms: int):
        frame = int(ms * self.engine.samplerate / 1000)
        self.engine.seek(frame)

    def set_volume(self, vol: float):
        self.engine.set_volume(vol)

    def set_eq(self, gains: list):
        self.engine.set_eq_gains(gains)

    @property
    def is_playing(self) -> bool:
        return self.engine.is_playing

    @property
    def last_error(self) -> str:
        return self.engine.last_error