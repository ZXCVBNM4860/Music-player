# ui/local_player/window/playback_mixin.py

import threading
import time
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.config import Config
from language import i18n
from ui.workers import run_async
from utils.helpers import get_cache_dir, log_line, clean_filename

from ..utils import fmt_time, find_local_match, _cache_file_name
from ..workers import CoverFetcher, OnlineTrackFetcher, QuickDownloadWorker

class PlaybackMixin:
    def _online_cache_file(self, song_id: str) -> Path:
        return get_cache_dir() / _cache_file_name(song_id)

    def _online_cover_file(self, song_id: str) -> Path:
        return get_cache_dir() / "covers" / _cache_file_name(song_id, "jpg")

    def _play_index(self, row: int):
        tracks = self.current_tracks
        if row < 0 or row >= len(tracks):
            return
        self.current_index = row
        track = tracks[row]
        path = str(track.get("path", ""))

        if self._auto_scan_local and self._local_library_path:
            local_path = self._find_local_match(track)
            if local_path:
                path = local_path

        if path.startswith("netease://"):
            self._play_online(track)
            return

        self._play_local_track(track, path)

    def _find_local_match(self, track: dict) -> Optional[str]:
        return find_local_match(
            track.get("title", ""), track.get("artist", ""), self.library.get_all()
        )

    def _set_now_playing(self, track: dict):
        title = track.get("title", "")
        artist = (track.get("artist", "") or "").strip()
        if artist:
            self.now_label.setText(f"{title} - {artist}")
        else:
            self.now_label.setText(title)
            
        if hasattr(self, "smtc"):
            self.smtc.update_metadata(title, artist, track.get("album", ""))

    def _play_local_track(self, track: dict, path: str):
        self._play_file(path)
        self._set_now_playing(track)
        self.table.selectRow(self.current_index)
        self._fetch_lyric(track)

        run_async(
            self._read_cover_worker,
            args=(path, track),
            on_success=self._on_local_cover,
            on_error=self._on_local_cover_failed,
        )

        self.recent_manager.add(track)
        self._refresh_recent()

    def _read_cover_worker(self, path: str, track: dict):
        from core.local_library import read_cover
        return read_cover(Path(path)), track

    def _on_local_cover(self, result):
        cover_data, track = result
        if not (0 <= self.current_index < len(self.current_tracks)):
            return
        current = self.current_tracks[self.current_index]
        if str(current.get("id", "")) != str(track.get("id", "")):
            return
        if cover_data:
            self.cover.set_cover(cover_data)
        else:
            self._show_track_cover(track)

    def _on_local_cover_failed(self, message):
        log_line(f"[Cover] {message}")

    def _play_file(self, path: str):
        if not self.player.load_and_play(path):
            err_key = self.player.last_error
            if err_key in ("ffmpeg_not_found", "ffmpeg_probe_timeout", "ffmpeg_parse_error"):
                err_msg = i18n.tr(err_key)
            else:
                err_msg = err_key

            QMessageBox.warning(
                self, i18n.tr("error"),
                f"{i18n.tr('play_fail')}:\n{path}\n{err_msg}",
            )
            return
        self.player.set_eq(self.player_tabs.equalizer.get_gains())
        self.player.set_volume(self.volume.value() / 100)
        
        speed = self.speed_slider.value() / 100.0
        self.player.set_speed(speed)
        
        self.btn_play.setText("⏸")
        
        if hasattr(self, "smtc"):
            self.smtc.update_playback_status(is_playing=True)

    def _play_online(self, track: dict):
        song_id = track["id"]
        cache_file = self._online_cache_file(str(song_id))
        pic_url = track.get("pic_url", "")
        cover_file = self._online_cover_file(str(song_id)) if pic_url else None

        if cache_file.exists():
            self._play_cached_online(track, cache_file)
            return

        self._start_online_fetch(track, song_id, cache_file, cover_file, pic_url)

    def _play_cached_online(self, track: dict, cache_file: Path):
        self._show_track_cover(track)
        self._play_file(str(cache_file))
        self._set_now_playing(track)
        self.table.selectRow(self.current_index)
        self._fetch_lyric(track)
        self.recent_manager.add(track)
        self._refresh_recent()

    def _show_track_cover(self, track: dict):
        song_id = track.get("id")
        pic_url = track.get("pic_url", "")
        if not song_id or not pic_url:
            self.cover.set_cover(b"")
            return

        cover_file = self._online_cover_file(str(song_id))

        if cover_file.exists():
            try:
                self.cover.set_cover(cover_file.read_bytes())
                return
            except Exception:
                pass

        self._start_cover_fetch(pic_url, cover_file)

    def _start_cover_fetch(self, pic_url: str, cover_file: Path):
        fetcher = CoverFetcher(pic_url, cover_file)
        self._cover_fetchers.append(fetcher)

        def _on_ready(path):
            if fetcher in self._cover_fetchers:
                self._cover_fetchers.remove(fetcher)
            if not (0 <= self.current_index < len(self.current_tracks)):
                return
            current = self.current_tracks[self.current_index]
            expected = self._online_cover_file(str(current.get("id", "")))
            if str(expected) != str(path):
                return
            try:
                self.cover.set_cover(Path(path).read_bytes())
            except Exception:
                pass

        fetcher.cover_ready.connect(_on_ready)
        fetcher.start()

    def _start_online_fetch(
        self, track: dict, song_id: str, cache_file: Path,
        cover_file, pic_url: str,
    ):
        self._cancel_online_fetcher()
        self.now_label.setText(f"{track['title']} - {i18n.tr('buffering')}")
        self.btn_play.setText("...")
        self.btn_play.setEnabled(False)

        fetcher = OnlineTrackFetcher(
            client=self.netease.client,
            song_id=str(song_id),
            cache_file=cache_file,
            cover_file=cover_file,
            pic_url=pic_url,
        )
        self._online_fetcher = fetcher

        fetcher.cover_ready.connect(lambda path: self._on_online_cover(fetcher, path))
        fetcher.finished_ok.connect(lambda path: self._on_online_ok(fetcher, track, path))
        fetcher.failed.connect(lambda err: self._on_online_failed(fetcher, err))
        fetcher.start()

    def _on_online_cover(self, fetcher, path):
        if self._online_fetcher is not fetcher:
            return
        try:
            self.cover.set_cover(Path(path).read_bytes())
        except Exception:
            pass

    def _on_online_ok(self, fetcher, track: dict, path: str):
        if self._online_fetcher is not fetcher:
            return
        self._online_fetcher = None
        self.btn_play.setEnabled(True)
        self._play_file(path)
        self._set_now_playing(track)
        self.table.selectRow(self.current_index)
        self._fetch_lyric(track)
        self.recent_manager.add(track)
        self._refresh_recent()

    def _on_online_failed(self, fetcher, err):
        if self._online_fetcher is not fetcher:
            return
        self._online_fetcher = None
        self.btn_play.setEnabled(True)
        self.btn_play.setText("▶")
        self.now_label.setText(i18n.tr("not_playing"))
        
        if err in ("cache_permission_denied", "cache_file_occupied"):
            message = i18n.tr(err)
        elif "Errno 13" in str(err) or "Permission denied" in str(err):
            message = i18n.tr("cache_permission_denied")
        elif err == "preview_no_url":
            message = i18n.tr("preview_no_url")
        else:
            message = str(err)
            
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _cancel_online_fetcher(self):
        fetcher = self._online_fetcher
        self._online_fetcher = None
        if fetcher is not None:
            fetcher.cancel()
            self._online_fetchers_pending.append(fetcher)
        self._online_fetchers_pending = [
            f for f in self._online_fetchers_pending if f.isRunning()
        ]

    def _enforce_cache_limit(self):
        if self._cache_max_mb <= 0:
            return
        try:
            cache_dir = get_cache_dir()
            if not cache_dir.exists():
                return
            limit_bytes = self._cache_max_mb * 1024 * 1024
            total = 0
            files = []
            for path in cache_dir.rglob("*"):
                if not path.is_file():
                    continue
                size = path.stat().st_size
                total += size
                files.append((path.stat().st_mtime, size, path))
            if total <= limit_bytes:
                return
            files.sort()
            for _, size, path in files:
                if total <= limit_bytes:
                    break
                try:
                    path.unlink()
                    total -= size
                except Exception:
                    pass
        except Exception:
            pass

    def _on_speed_changed(self, value):
        speed = value / 100.0
        self.speed_label.setText(f"{speed:.1f}x")
        self.player.set_speed(speed)

    def _download_current_song(self):
        if not (0 <= self.current_index < len(self.current_tracks)):
            return
        track = self.current_tracks[self.current_index]
        song_id = track.get("id")
        path = track.get("path", "")
        
        if path and not path.startswith("netease://"):
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr("already_local"))
            return
            
        if not song_id or not str(song_id).isdigit():
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr("already_local"))
            return

        try:
            url = self.netease.client.get_download_url(str(song_id), 320000)
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))
            return

        if not url:
            QMessageBox.warning(self, i18n.tr("error"), i18n.tr("no_copyright"))
            return

        save_dir = self._settings.value("default_download_path", Config.DEFAULT_DOWNLOAD_PATH)
        save_path = Path(save_dir) / f"{clean_filename(track.get('title', str(song_id)))}.mp3"
        
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self.player_tabs.set_download_button_state(False, "...")
        
        def _do_download():
            try:
                resp = requests.get(url, stream=True, timeout=30)
                resp.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(64 * 1024):
                        if chunk:
                            f.write(chunk)
                return str(save_path)
            except Exception as e:
                raise Exception(str(e))

        def _on_ok(path_str):
            self.player_tabs.set_download_button_state(True, i18n.tr("download_current"))
            QMessageBox.information(self, i18n.tr("success_title"), i18n.tr("download_success").format(name=save_path.name))
            
        def _on_err(msg):
            self.player_tabs.set_download_button_state(True, i18n.tr("download_current"))
            QMessageBox.warning(self, i18n.tr("error"), f"{i18n.tr('download_failed')}\n{msg}")

        run_async(_do_download, on_success=_on_ok, on_error=_on_err)

    def _toggle_play(self):
        if self.player.is_playing:
            self.player.pause()
            self.btn_play.setText("▶")
            if hasattr(self, "smtc"):
                self.smtc.update_playback_status(is_playing=False)
            return
        if self.current_index < 0 and self.current_tracks:
            self._play_index(0)
        else:
            self.player.play()
            self.btn_play.setText("⏸")
            if hasattr(self, "smtc"):
                self.smtc.update_playback_status(is_playing=True)

    def _play_prev(self):
        tracks = self.current_tracks
        if not tracks:
            return
        if self.play_mode == "shuffle":
            index = self._step_shuffle(-1)
        else:
            index = (self.current_index - 1) % len(tracks)
        self._play_index(index)

    def _play_next(self):
        tracks = self.current_tracks
        if not tracks:
            return
        if self.play_mode == "shuffle":
            index = self._step_shuffle(1)
        else:
            index = (self.current_index + 1) % len(tracks)
        self._play_index(index)

    def _step_shuffle(self, delta: int) -> int:
        tracks = self.current_tracks
        if not self._shuffle_order or len(self._shuffle_order) != len(tracks):
            self._rebuild_shuffle_order(tracks)
        self._shuffle_pos = (self._shuffle_pos + delta) % len(self._shuffle_order)
        return self._shuffle_order[self._shuffle_pos]

    def _on_mode_changed(self, index: int):
        data = self.mode_combo.itemData(index)
        if not data:
            return
        self.play_mode = data
        if data == "shuffle":
            self._rebuild_shuffle_order(self.current_tracks)
            if self.current_index >= 0 and self._shuffle_order:
                try:
                    self._shuffle_pos = self._shuffle_order.index(self.current_index)
                except ValueError:
                    self._shuffle_pos = 0

    def _rebuild_shuffle_order(self, tracks):
        import random
        count = len(tracks)
        if count == 0:
            self._shuffle_order = []
            self._shuffle_pos = 0
            return
        rng = random.Random(self.random_seed)
        order = list(range(count))
        rng.shuffle(order)
        self._shuffle_order = order
        self._shuffle_pos = 0

    def _reset_shuffle(self):
        self._shuffle_order = []
        self._shuffle_pos = 0
        if self.play_mode == "shuffle":
            self._rebuild_shuffle_order(self.current_tracks)

    def _on_volume(self, value):
        self.player.set_volume(value / 100)

    def _on_slider_pressed(self):
        self._dragging = True

    def _on_slider_move(self, value):
        if self.player.engine.duration <= 0:
            return
        pos_ms = int(value / 1000 * (self.player.engine.duration / self.player.engine.samplerate * 1000))
        self._update_time_label(pos_ms / 1000, self.player.engine.duration / self.player.engine.samplerate)

    def _on_seek(self):
        self._dragging = False
        if self.player.engine.duration <= 0:
            return
        total_ms = int(self.player.engine.duration / self.player.engine.samplerate * 1000)
        target_ms = int(self.progress.value() / 1000 * total_ms)
        self.player.seek(target_ms)

    def _update_time_label(self, pos_sec, dur_sec):
        self.time_label.setText(f"{fmt_time(pos_sec)} / {fmt_time(dur_sec)}")

    def _on_engine_position(self, pos_ms: int, total_ms: int):
        if self._dragging or total_ms <= 0:
            return
        self.progress.setValue(int(pos_ms / total_ms * 1000))
        self._update_time_label(pos_ms / 1000, total_ms / 1000)
        self.lyric_widget.update_position(pos_ms)
        
        if hasattr(self, "desktop_lyric") and self.desktop_lyric.isVisible():
            self.desktop_lyric.update_position(pos_ms)

    def _handle_playback_finished(self):
        if self.play_mode == "repeat_one":
            self.player.seek(0)
            self.player.play()
            self.btn_play.setText("⏸")
        else:
            self._play_next()

    def _on_eq_changed(self, gains: list):
        self.player.set_eq(gains)

    def _start_quick_download(self, tracks):
        if not tracks:
            return
        if self._quick_worker and self._quick_worker.isRunning():
            self._quick_worker.cancel()
            self._quick_worker.wait(1500)

        try:
            cache_dir = get_cache_dir()
        except Exception as exc:
            log_line(f"[QuickDownload] cannot get cache dir: {exc}")
            return

        self._quick_worker = QuickDownloadWorker(
            api_url=self.api_url,
            cache_dir=cache_dir,
            songs=tracks,
            threads=self._fast_download_threads,
            local_library_path=self._local_library_path,
        )
        self._quick_worker.start()