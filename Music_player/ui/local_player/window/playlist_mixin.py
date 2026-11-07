# ui/local_player/window/playlist_mixin.py

from PyQt6.QtWidgets import (
    QMessageBox, QInputDialog, QApplication, QFileDialog, QMenu, QTableWidgetItem
)
from PyQt6.QtCore import Qt

from core.config import Config
from core.local_library import LocalLibrary
from language import i18n
from ..comment_dialog import CommentDialog
from ui.workers import run_async
from utils.helpers import log_line

from ..utils import fmt_time, read_bool, read_int

class PlaylistMixin:
    def _reload_settings(self):
        self._auto_scan_local = read_bool(
            self._settings.value("auto_scan_local", Config.DEFAULT_AUTO_SCAN)
        )
        self._local_library_path = self._settings.value(
            "local_library_path", Config.DEFAULT_LOCAL_LIBRARY_PATH
        ) or ""
        self._fast_download = read_bool(
            self._settings.value("fast_download", Config.DEFAULT_FAST_DOWNLOAD)
        )
        self._fast_download_threads = read_int(
            self._settings.value("fast_download_threads", Config.DEFAULT_FAST_DOWNLOAD_THREADS),
            Config.DEFAULT_FAST_DOWNLOAD_THREADS,
        )
        self._cache_max_mb = read_int(
            self._settings.value("cache_max_mb", Config.DEFAULT_CACHE_MAX_MB),
            Config.DEFAULT_CACHE_MAX_MB,
        )
        self._translate_settings = {
            "enabled": read_bool(self._settings.value("translate_enabled", False)),
            "source": str(self._settings.value("translate_source", "auto") or "auto"),
            "target": str(self._settings.value("translate_target", "en") or "en"),
        }

    def _load_local_library_cache(self):
        if self.library.load_cache():
            self._set_tracks(self.library.get_all())

    def _open_settings(self):
        from ..player_settings_dialog import PlayerSettingsDialog
        dialog = PlayerSettingsDialog(self)
        if not dialog.exec():
            return
        self._reload_settings()
        self._translate_settings = dialog.get_translate_settings()
        self.random_seed = dialog.get_random_seed()
        self._rebuild_shuffle_order(self.current_tracks)

    def _set_tracks(self, tracks):
        self._all_tracks = list(tracks)
        self.current_tracks = list(tracks)
        self._refresh_table()
        self._reset_shuffle()

    def set_online_tracks(self, songs: list):
        if not songs:
            return

        tracks = []
        for song in songs:
            path = song.get("path") or f"netease://{song['id']}"
            tracks.append({
                "id": song["id"],
                "title": song["title"],
                "artist": song.get("artist", ""),
                "album": "",
                "duration": song.get("duration", 0),
                "pic_url": song.get("pic_url", ""),
                "path": path,
            })

        self._set_tracks(tracks)
        if self._fast_download:
            self._start_quick_download(tracks)

    def _refresh_table(self):
        tracks = self.current_tracks
        self.table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            self.table.setItem(row, 0, QTableWidgetItem(track.get("title", "")))
            self.table.setItem(row, 1, QTableWidgetItem(track.get("artist", "")))
            self.table.setItem(row, 2, QTableWidgetItem(fmt_time(track.get("duration", 0))))

    def _scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, i18n.tr("choose_music_folder"))
        if not folder:
            return
        self.setWindowTitle(f"{i18n.tr('scanning')} 0/0")
        run_async(
            self._scan_worker,
            args=(folder,),
            on_success=self._on_scan_finished,
            on_error=self._on_scan_failed,
        )

    def _on_scan_progress(self, current, total):
        self.setWindowTitle(f"{i18n.tr('scanning')} {current}/{total}")

    def _on_scan_finished(self, library):
        self.library = library
        self.setWindowTitle(i18n.tr("local_player_title"))
        self._current_playlist_id = None
        self._set_tracks(library.get_all())
        QMessageBox.information(
            self, i18n.tr("scan_done"),
            i18n.tr("scan_found").format(count=len(library.get_all())),
        )

    def _on_scan_failed(self, message):
        self.setWindowTitle(i18n.tr("local_player_title"))
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _on_search(self, text):
        text = text.strip()
        if not text:
            self.current_tracks = list(self._all_tracks)
        else:
            keyword = text.lower()
            self.current_tracks = [
                track for track in self._all_tracks
                if keyword in str(track.get("title", "")).lower()
                or keyword in str(track.get("artist", "")).lower()
                or keyword in str(track.get("album", "")).lower()
            ]
        self._refresh_table()
        self._reset_shuffle()

    def _on_double_click(self, index):
        row = index.row()
        tracks = self.current_tracks
        if not tracks or row < 0 or row >= len(tracks):
            return
        if self.play_mode == "shuffle" and self._shuffle_order:
            try:
                self._shuffle_pos = self._shuffle_order.index(row)
            except ValueError:
                self._shuffle_pos = 0
        self._play_index(row)

    def _on_playlist_activated(self, tracks: list):
        if not tracks:
            return
        self._current_playlist_id = None
        self._set_tracks(tracks)

    def _refresh_recent(self):
        items = self.recent_manager.get_all()
        self.player_tabs.set_recent_items(items)

    def _on_recent_double_click(self, row: int):
        items = self.recent_manager.get_all()
        if 0 <= row < len(items):
            self._current_playlist_id = None
            self._set_tracks(items)
            self._play_index(row)

    def _clear_recent(self):
        self.recent_manager.clear()
        self._refresh_recent()

    def _show_track_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        tracks = self.current_tracks
        if row >= len(tracks):
            return
        track = tracks[row]

        menu = QMenu(self)
        menu.addAction(i18n.tr("play_menu"), lambda: self._play_index(row))
        menu.addSeparator()
        menu.addAction(i18n.tr("copy_song_name"), lambda: self._copy_song_name(track))
        menu.addAction(i18n.tr("add_to_playlist_menu"), lambda: self._add_to_playlist(track))
        menu.exec(self.table.mapToGlobal(pos))

    def _copy_song_name(self, track: dict):
        title = track.get("title", "")
        if title:
            QApplication.clipboard().setText(title)

    def _add_to_playlist(self, track: dict):
        self.playlist_manager.reload()
        names = self.playlist_manager.get_all_names()
        if not names:
            self._create_playlist_with_track(track)
            return

        name, ok = QInputDialog.getItem(
            self, i18n.tr("add_to_playlist_menu"),
            i18n.tr("select_existing"), names, 0, False,
        )
        if ok and name:
            self.playlist_manager.add_track(name, track)
            self.player_tabs.playlist_widget.refresh()
            QMessageBox.information(
                self, i18n.tr("success_title"),
                i18n.tr("added_to_playlist").format(name=name),
            )

    def _create_playlist_with_track(self, track: dict):
        name, ok = QInputDialog.getText(
            self, i18n.tr("new_playlist"), i18n.tr("playlist_name_label"),
        )
        if ok and name.strip():
            name = name.strip()
            self.playlist_manager.create(name)
            self.playlist_manager.add_track(name, track)
            self.player_tabs.playlist_widget.refresh()

    def _open_comments(self):
        tracks = self.current_tracks
        if not (0 <= self.current_index < len(tracks)):
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("favorite_need_song"))
            return

        track = tracks[self.current_index]
        song_id = track.get("id")
        if not song_id:
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("comment_no_song"))
            return

        if self._comment_dialog is not None:
            self._comment_dialog.close()

        dialog = CommentDialog(
            self.api_url,
            str(song_id),
            track.get("title", ""),
            cookies=self.cookies or {},
            translate_enabled=self._translate_settings.get("enabled", False),
            translate_source=self._translate_settings.get("source", "auto"),
            translate_target=self._translate_settings.get("target", "en"),
            parent=self,
        )
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.show()
        self._comment_dialog = dialog

    def _favorite_current(self):
        if not self.cookies:
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("favorite_need_login"))
            return

        tracks = self.current_tracks
        if not (0 <= self.current_index < len(tracks)):
            QMessageBox.warning(self, i18n.tr("notice"), i18n.tr("favorite_need_song"))
            return

        track = tracks[self.current_index]
        song_id = track.get("id")
        if not song_id:
            return

        uid = self.user_info.get("userId") if self.user_info else None
        if not uid:
            QMessageBox.warning(
                self, i18n.tr("error"), i18n.tr("netease_playlist_no_uid")
            )
            return

        self._pending_song_id = song_id
        run_async(
            self.netease.fetch_user_playlists,
            args=(uid,),
            on_success=self._on_playlists_fetched,
            on_error=self._on_favorite_failed,
        )

    def _on_playlists_fetched(self, playlists):
        song_id = self._pending_song_id
        if not song_id:
            return
        if not playlists:
            self._favorite_create_and_add(song_id)
            return
        if len(playlists) == 1:
            target = playlists[0]
            self._add_song_to_playlist(target["id"], song_id, target["name"])
            return

        names = [p["name"] for p in playlists]
        choice, ok = QInputDialog.getItem(
            self, i18n.tr("favorite_select_playlist"),
            i18n.tr("favorite_select_playlist"), names, 0, False,
        )
        if not ok or not choice:
            return

        for playlist in playlists:
            if playlist["name"] == choice:
                self._add_song_to_playlist(playlist["id"], song_id, playlist["name"])
                return

    def _on_favorite_failed(self, message):
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _favorite_create_and_add(self, song_id):
        reply = QMessageBox.question(
            self, i18n.tr("notice"), i18n.tr("favorite_no_playlist_hint"),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        name, ok = QInputDialog.getText(
            self, i18n.tr("favorite_create_playlist_title"),
            i18n.tr("playlist_name_label"),
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        self._pending_song_id = song_id
        self._pending_playlist_name = name
        run_async(
            self.netease.create_playlist,
            args=(name,),
            on_success=self._on_playlist_created,
            on_error=self._on_playlist_create_failed,
        )

    def _on_playlist_created(self, pid):
        song_id = self._pending_song_id
        if not pid or not song_id:
            return
        self._add_song_to_playlist(pid, song_id, self._pending_playlist_name)

    def _on_playlist_create_failed(self, message):
        QMessageBox.warning(
            self, i18n.tr("error"),
            f"{i18n.tr('favorite_create_failed')}\n{message}",
        )

    def _add_song_to_playlist(self, pid, song_id, playlist_name: str):
        self._pending_playlist_name = playlist_name
        run_async(
            self.netease.add_song_to_playlist,
            args=(pid, song_id),
            on_success=self._on_song_added,
            on_error=self._on_add_song_failed,
        )

    def _on_song_added(self, _result):
        QMessageBox.information(
            self, i18n.tr("success_title"),
            i18n.tr("favorite_added_to_named").format(
                name=self._pending_playlist_name
            ),
        )

    def _on_add_song_failed(self, message):
        QMessageBox.warning(self, i18n.tr("error"), message)

    def _update_login_state(self):
        if self.cookies:
            nickname = ""
            if self.user_info:
                nickname = self.user_info.get("nickname", "") or ""

            if nickname:
                self.btn_netease.setText(
                    i18n.tr("logged_in_as").format(name=nickname)
                )
            else:
                self.btn_netease.setText(i18n.tr("logged_in"))
            self.btn_netease.setEnabled(True)
        else:
            self.btn_netease.setText(i18n.tr("login"))
            self.btn_netease.setEnabled(True)

    def _on_netease_btn_clicked(self):
        if not self.cookies:
            self._open_netease_login()
            return

        from ..netease_playlist_dialog import NeteasePlaylistDialog
        uid = self.user_info.get("userId") if self.user_info else None
        nickname = self.user_info.get("nickname", "") if self.user_info else ""

        dialog = NeteasePlaylistDialog(
            self, api_url=self.api_url, cookies=self.cookies,
            uid=uid, nickname=nickname,
        )
        dialog.playlist_songs_ready.connect(self._on_online_songs_ready)
        dialog.exec()

    def _open_netease_login(self):
        from ..netease_login_dialog import NeteaseLoginDialog

        dialog = NeteaseLoginDialog(self, api_url=self.api_url)
        if dialog.exec():
            self.cookies = dialog.get_cookies()
            self.user_info = dialog.get_user_info()
            if self.cookies:
                self.netease.save_login(self.cookies, self.user_info)
                self._update_login_state()

    def _on_online_songs_ready(self, songs: list, playlist_id=None):
        if not songs:
            return
        self._current_playlist_id = playlist_id
        self.set_online_tracks(songs)