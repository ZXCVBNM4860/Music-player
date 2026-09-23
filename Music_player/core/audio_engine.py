# core\audio_engine.py

import threading
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
import soundfile as sf
from pedalboard import Pedalboard, PeakFilter, LowShelfFilter, HighShelfFilter


class AudioEngine:

    def __init__(self, samplerate: int = 44100, blocksize: int = 512):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = 2

        self._audio_data: Optional[np.ndarray] = None
        self._play_position = 0
        self._total_frames = 0

        self._stream: Optional[sd.OutputStream] = None
        self._playing = False
        self._paused = False
        self._lock = threading.Lock()

        self._volume = 0.7

        self._board = Pedalboard([])
        self._band_freqs = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

        self.on_position_changed: Optional[Callable[[int, int], None]] = None
        self.on_playback_finished: Optional[Callable[[], None]] = None

    def set_eq_gains(self, gains: list):
        board_effects = []
        for freq, gain in zip(self._band_freqs, gains):
            if abs(gain) < 0.1:
                continue
            if freq <= 125:
                board_effects.append(LowShelfFilter(cutoff_frequency_hz=freq, gain_db=gain))
            elif freq >= 8000:
                board_effects.append(HighShelfFilter(cutoff_frequency_hz=freq, gain_db=gain))
            else:
                board_effects.append(PeakFilter(cutoff_frequency_hz=freq, gain_db=gain, q=1.0))
        self._board = Pedalboard(board_effects)

    def load(self, path: str) -> bool:
        try:
            data, sr = sf.read(path, dtype="float32", always_2d=True)
            self._audio_data = data
            self.samplerate = sr
            self.channels = data.shape[1]
            self._total_frames = data.shape[0]
            self._play_position = 0
            return True
        except Exception as e:
            print(f"[AudioEngine] 加载失败: {e}")
            return False

    def play(self, start_frame: int = 0):
        if self._audio_data is None:
            return
        with self._lock:
            self._play_position = start_frame
            if self._stream is None or not self._stream.active:
                self._stream = sd.OutputStream(
                    samplerate=self.samplerate,
                    blocksize=self.blocksize,
                    channels=self.channels,
                    callback=self._audio_callback,
                    dtype="float32",
                )
                self._stream.start()
            self._playing = True
            self._paused = False

    def pause(self):
        with self._lock:
            self._paused = True

    def stop(self):
        with self._lock:
            self._playing = False
            self._paused = False
            self._play_position = 0
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    def seek(self, frame: int):
        with self._lock:
            self._play_position = max(0, min(frame, self._total_frames - 1))

    def set_volume(self, vol: float):
        self._volume = max(0.0, min(1.0, vol))

    @property
    def position(self) -> int:
        return self._play_position

    @property
    def duration(self) -> int:
        return self._total_frames

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            print(f"[AudioEngine] 状态: {status}")

        if not self._playing or self._paused or self._audio_data is None:
            outdata.fill(0)
            return

        with self._lock:
            pos = self._play_position
            end = pos + frames

            if pos >= self._total_frames:
                outdata.fill(0)
                self._playing = False
                if self.on_playback_finished:
                    self.on_playback_finished()
                return

            if end > self._total_frames:
                chunk = self._audio_data[pos:self._total_frames]
                pad = np.zeros((frames - chunk.shape[0], self.channels), dtype=np.float32)
                chunk = np.vstack([chunk, pad])
                self._play_position = self._total_frames
            else:
                chunk = self._audio_data[pos:end]
                self._play_position = end

        processed = self._board.process(chunk, self.samplerate)

        processed = processed * self._volume

        if processed.shape[1] < self.channels:
            processed = np.pad(processed, ((0, 0), (0, self.channels - processed.shape[1])))
        elif processed.shape[1] > self.channels:
            processed = processed[:, :self.channels]

        outdata[:] = processed

        if self.on_position_changed and (self._play_position % (frames * 10) < frames):
            self.on_position_changed(self._play_position, self._total_frames)