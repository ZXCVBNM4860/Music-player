# core/audio_engine.py
import os
import re
import subprocess
import threading
import time
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
from pedalboard import Pedalboard, PeakFilter, LowShelfFilter, HighShelfFilter

try:
    import imageio_ffmpeg
    _HAS_IMAGEIO_FFMPEG = True
except ImportError:
    _HAS_IMAGEIO_FFMPEG = False


OUTPUT_SAMPLERATE = 44100
OUTPUT_CHANNELS = 2
OUTPUT_BLOCKSIZE = 512
BYTES_PER_SAMPLE = 2

_READ_CHUNK = 8192
_BUFFER_HIGH_WATER = 4 * 1024 * 1024

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _find_ffmpeg() -> str:
    if _HAS_IMAGEIO_FFMPEG:
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.exists(exe):
                return exe
        except Exception:
            pass

    import shutil
    for name in ("ffmpeg", "ffmpeg.exe"):
        path = shutil.which(name)
        if path:
            return path

    import sys
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    for base in candidates:
        for name in ("ffmpeg.exe", "ffmpeg"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p

    raise RuntimeError("找不到 ffmpeg，请安装 imageio-ffmpeg 或把 ffmpeg 放进 PATH")


class AudioEngine:

    def __init__(self, blocksize: int = OUTPUT_BLOCKSIZE):
        self.samplerate = OUTPUT_SAMPLERATE
        self.blocksize = blocksize
        self.channels = OUTPUT_CHANNELS

        self._path: Optional[str] = None
        self._duration_sec: float = 0.0
        self._total_frames: int = 0
        self._play_position: int = 0

        self._stream: Optional[sd.OutputStream] = None
        self._playing = False
        self._paused = False
        self._lock = threading.Lock()

        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._eof = False

        self._volume = 0.7
        self._board = Pedalboard([])
        self._band_freqs = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

        self._ffmpeg: Optional[str] = None

        self._last_pos_emit = 0.0

        self.on_position_changed: Optional[Callable[[int, int], None]] = None
        self.on_playback_finished: Optional[Callable[[], None]] = None

    def load(self, path: str) -> bool:
        try:
            self._ensure_ffmpeg()
        except RuntimeError as e:
            print(f"[AudioEngine] {e}")
            return False

        try:
            duration = self._probe_duration(path)
        except Exception as e:
            print(f"[AudioEngine] 读取时长失败: {e}")
            return False

        self.stop()
        self._path = path
        self._duration_sec = duration
        self._total_frames = int(duration * self.samplerate)
        self._play_position = 0
        return True

    def play(self, start_frame: int = 0):
        if self._path is None:
            return

        with self._lock:
            if self._total_frames > 0:
                start_frame = max(0, min(start_frame, self._total_frames - 1))
            else:
                start_frame = 0

            already_decoding = (
                self._proc is not None and self._proc.poll() is None
            )
            same_pos = (start_frame == self._play_position)
            is_resume = self._paused and already_decoding and same_pos

            self._play_position = start_frame
            self._paused = False
            self._playing = True
            need_restart = not is_resume

        self._ensure_stream()
        if need_restart:
            self._start_decoder(self._play_position / self.samplerate)

    def pause(self):
        with self._lock:
            self._paused = True

    def stop(self):
        with self._lock:
            self._playing = False
            self._paused = False
            self._play_position = 0

        self._kill_decoder()

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._buffer_lock:
            self._buffer.clear()
            self._eof = False

    def seek(self, frame: int):
        with self._lock:
            if self._total_frames > 0:
                frame = max(0, min(frame, self._total_frames - 1))
            else:
                frame = 0
            self._play_position = frame
            was_playing = self._playing
            self._paused = False

        if was_playing:
            self._start_decoder(frame / self.samplerate)

    def set_volume(self, vol: float):
        self._volume = max(0.0, min(1.0, vol))

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

    @property
    def position(self) -> int:
        return self._play_position

    @property
    def duration(self) -> int:
        return self._total_frames

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def _ensure_ffmpeg(self):
        if self._ffmpeg is None:
            self._ffmpeg = _find_ffmpeg()

    def _probe_duration(self, path: str) -> float:
        cmd = [self._ffmpeg, "-hide_banner", "-i", path]
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            **kwargs,
        )
        try:
            _, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("ffmpeg 探测时长超时")

        text = err.decode("utf-8", "ignore")
        m = _DURATION_RE.search(text)
        if not m:
            raise RuntimeError(f"无法解析时长:\n{text[:300]}")

        h, mm, s = m.group(1), m.group(2), m.group(3)
        return int(h) * 3600 + int(mm) * 60 + float(s)

    def _ensure_stream(self):
        if self._stream is None or not self._stream.active:
            self._stream = sd.OutputStream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                channels=self.channels,
                callback=self._audio_callback,
                dtype="float32",
            )
            self._stream.start()

    def _start_decoder(self, start_time: float):
        self._kill_decoder()

        with self._buffer_lock:
            self._buffer.clear()
            self._eof = False

        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-nostdin",
            "-ss", f"{max(start_time, 0.0):.3f}",
            "-i", self._path,
            "-vn",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", str(self.channels),
            "-ar", str(self.samplerate),
            "pipe:1",
        ]

        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            **kwargs,
        )

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _kill_decoder(self):
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass

        thread = self._reader_thread
        self._reader_thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1)

    def _reader_loop(self):
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        fd = proc.stdout.fileno()

        while self._proc is proc:
            if self._paused:
                time.sleep(0.02)
                continue

            with self._buffer_lock:
                full = len(self._buffer) >= _BUFFER_HIGH_WATER

            if full:
                time.sleep(0.02)
                continue

            try:
                data = os.read(fd, _READ_CHUNK)
            except OSError:
                break
            if not data:
                break

            with self._buffer_lock:
                self._buffer.extend(data)

        with self._buffer_lock:
            self._eof = True

    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            print(f"[AudioEngine] 状态: {status}")

        if not self._playing or self._paused:
            outdata.fill(0)
            return

        want_bytes = frames * self.channels * BYTES_PER_SAMPLE

        with self._buffer_lock:
            take = min(len(self._buffer), want_bytes)
            if take:
                raw = bytes(self._buffer[:take])
                del self._buffer[:take]
            else:
                raw = b""
            eof = self._eof and len(self._buffer) == 0

        if not raw:
            outdata.fill(0)
            if eof:
                self._playing = False
                if self.on_playback_finished:
                    threading.Thread(
                        target=self.on_playback_finished, daemon=True
                    ).start()
            return

        pcm = np.frombuffer(raw, dtype=np.int16)
        if pcm.size % self.channels != 0:
            pcm = pcm[: pcm.size - (pcm.size % self.channels)]
        samples = pcm.astype(np.float32).reshape(-1, self.channels) / 32768.0
        raw_frames = samples.shape[0]

        if raw_frames < frames:
            pad = np.zeros(
                (frames - raw_frames, self.channels), dtype=np.float32
            )
            samples = np.vstack([samples, pad])

        try:
            processed = self._board.process(samples, self.samplerate)
        except Exception:
            processed = samples

        processed = processed * self._volume

        out_ch = outdata.shape[1]
        if processed.shape[1] < out_ch:
            processed = np.pad(
                processed, ((0, 0), (0, out_ch - processed.shape[1]))
            )
        elif processed.shape[1] > out_ch:
            processed = processed[:, :out_ch]

        outdata[:] = processed

        with self._lock:
            self._play_position += raw_frames
            pos = self._play_position
            total = self._total_frames

        now = time.monotonic()
        if self.on_position_changed and (now - self._last_pos_emit) >= 0.1:
            self._last_pos_emit = now
            self.on_position_changed(pos, total)