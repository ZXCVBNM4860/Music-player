# ui/netease_playlist_dialog.py

import re

import requests
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,QHBoxLayout,QInputDialog,
    QLabel,QListWidget,QListWidgetItem,
    QMessageBox,QPushButton,QVBoxLayout
)

from language import i18n


class NeteasePlaylistDialog(QDialog):
    playlist_songs_ready = pyqtSignal(list, object)

    def __init__(
        self,
        parent=None,
        api_url="http://localhost:3000",
        cookies=None,
        uid=None,
        nickname="",
        current_song_id=None,
        current_playlist_id=None,
    ):
        super().__init__(parent)

        self.setWindowTitle(i18n.tr("netease_playlist_title"))
        self.setMinimumSize(620, 560)

        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        if cookies:
            self.session.cookies.update(cookies)

        self.uid = uid
        self.nickname = nickname
        self.current_song_id = current_song_id
        self.current_playlist_id = current_playlist_id

        self.playlists = []

        self._build_ui()
        self._load_playlists()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            i18n.tr("netease_playlist_header").format(name=self.nickname or "")
        )
        header.setObjectName("npHeader")
        layout.addWidget(header)

        quick = QHBoxLayout()

        self.btn_daily = QPushButton(i18n.tr("netease_daily_recommend"))
        self.btn_daily.clicked.connect(self._load_daily_recommend)
        quick.addWidget(self.btn_daily)

        self.btn_heart = QPushButton(i18n.tr("netease_heart_mode"))
        self.btn_heart.clicked.connect(self._load_heart_mode)
        quick.addWidget(self.btn_heart)

        self.btn_radar = QPushButton(i18n.tr("netease_private_radar"))
        self.btn_radar.clicked.connect(self._load_private_radar)
        quick.addWidget(self.btn_radar)

        layout.addLayout(quick)

        hint = QLabel(i18n.tr("netease_playlist_double_click_hint"))
        hint.setObjectName("npHint")
        layout.addWidget(hint)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("npList")
        self.list_widget.itemDoubleClicked.connect(self._on_playlist_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        bottom = QHBoxLayout()

        self.btn_create = QPushButton(i18n.tr("netease_playlist_create"))
        self.btn_create.clicked.connect(self._create_playlist)
        bottom.addWidget(self.btn_create)

        self.btn_subscribe = QPushButton(i18n.tr("netease_playlist_subscribe"))
        self.btn_subscribe.clicked.connect(self._subscribe_playlist)
        bottom.addWidget(self.btn_subscribe)

        self.btn_refresh = QPushButton(i18n.tr("netease_playlist_refresh"))
        self.btn_refresh.clicked.connect(self._load_playlists)
        bottom.addWidget(self.btn_refresh)

        bottom.addStretch()

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)

        layout.addLayout(bottom)

    def _get_json(self, endpoint: str, params=None, timeout: int = 10):
        try:
            response = self.session.get(
                f"{self.api_url}/{endpoint.lstrip('/')}",
                params=params,
                timeout=timeout,
            )
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, i18n.tr("error"), str(exc))
            return None

        if data.get("code") != 200:
            QMessageBox.warning(self, i18n.tr("error"), str(data))
            return None

        return data

    def _post_json(self, endpoint: str, data, timeout: int = 10):
        try:
            response = self.session.post(
                f"{self.api_url}/{endpoint.lstrip('/')}",
                data=data,
                timeout=timeout,
            )
            result = response.json()
        except Exception as exc:
            QMessageBox.warning(self, i18n.tr("error"), str(exc))
            return None

        if result.get("code") != 200:
            QMessageBox.warning(self, i18n.tr("error"), str(result))
            return None

        return result

    def _load_playlists(self):
        if not self.uid:
            QMessageBox.warning(
                self, i18n.tr("error"), i18n.tr("netease_playlist_no_uid")
            )
            return

        data = self._get_json("user/playlist", params={"uid": self.uid, "limit": 1000})
        if data is None:
            return

        self.playlists = data.get("playlist", [])
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()

        for playlist in self.playlists:
            item = QListWidgetItem(self._format_playlist_text(playlist))
            item.setData(Qt.ItemDataRole.UserRole, playlist)
            self.list_widget.addItem(item)

    def _format_playlist_text(self, playlist: dict) -> str:
        name = playlist.get("name", "")
        count = playlist.get("trackCount", 0)

        text = (
            f"{name}  "
            f"({i18n.tr('netease_playlist_track_count').format(count=count)})"
        )

        creator = (playlist.get("creator") or {}).get("nickname", "")
        is_own = playlist.get("userId") == self.uid

        if not is_own and creator:
            text += f"  - {creator}"

        return text

    def _on_playlist_double_clicked(self, item: QListWidgetItem):
        playlist = item.data(Qt.ItemDataRole.UserRole)
        if not playlist:
            return

        playlist_id = playlist.get("id")
        if not playlist_id:
            return

        self._fetch_playlist_tracks(playlist_id)

    def _fetch_playlist_tracks(self, playlist_id):
        data = self._get_json(
            "playlist/track/all",
            params={"id": playlist_id, "limit": 1000},
            timeout=15,
        )
        if data is None:
            return

        self._emit_songs(data.get("songs", []), playlist_id=playlist_id)

    def _load_daily_recommend(self):
        data = self._get_json("recommend/songs")
        if data is None:
            return

        songs = (data.get("data") or {}).get("dailySongs", [])
        self._emit_songs(songs)

    def _load_heart_mode(self):
        if not self.current_song_id or not self.current_playlist_id:
            QMessageBox.warning(
                self,
                i18n.tr("notice"),
                i18n.tr("netease_heart_mode_need_playing"),
            )
            return

        data = self._get_json(
            "playmode/intelligence/list",
            params={
                "id": self.current_song_id,
                "pid": self.current_playlist_id,
            },
        )
        if data is None:
            return

        self._emit_songs(data.get("data", []))

    def _load_private_radar(self):
        data = self._get_json("personalized", params={"limit": 1})
        if data is None:
            return

        result = data.get("result", [])
        if not result:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr("netease_playlist_empty_msg")
            )
            return

        radar_id = result[0].get("id")
        if not radar_id:
            QMessageBox.warning(
                self, i18n.tr("error"), i18n.tr("netease_playlist_invalid_id")
            )
            return

        self._fetch_playlist_tracks(radar_id)

    def _emit_songs(self, songs, playlist_id=None):
        if not songs:
            QMessageBox.information(
                self, i18n.tr("notice"), i18n.tr("netease_playlist_empty_msg")
            )
            return

        result = [self._make_song_entry(song) for song in songs]

        self.playlist_songs_ready.emit(result, playlist_id)
        QMessageBox.information(
            self,
            i18n.tr("success_title"),
            i18n.tr("netease_playlist_loaded").format(count=len(result)),
        )

    @staticmethod
    def _make_song_entry(song: dict) -> dict:
        artists = [artist.get("name", "") for artist in song.get("ar", [])]
        album = song.get("al") or {}

        return {
            "id": str(song.get("id")),
            "title": song.get("name", ""),
            "artist": ", ".join(artists),
            "duration": song.get("dt", 0) / 1000,
            "pic_url": album.get("picUrl", ""),
        }

    def _create_playlist(self):
        name, ok = QInputDialog.getText(
            self,
            i18n.tr("netease_playlist_create"),
            i18n.tr("playlist_name_label"),
        )

        if not ok or not name.strip():
            return

        result = self._post_json("playlist/create", data={"name": name.strip()})
        if result is None:
            return

        QMessageBox.information(
            self,
            i18n.tr("success_title"),
            i18n.tr("netease_playlist_create_success"),
        )
        self._load_playlists()

    def _subscribe_playlist(self):
        text, ok = QInputDialog.getText(
            self,
            i18n.tr("netease_playlist_subscribe"),
            i18n.tr("netease_playlist_subscribe_prompt"),
        )

        if not ok or not text.strip():
            return

        playlist_id = self._parse_playlist_id(text.strip())
        if not playlist_id:
            QMessageBox.warning(
                self, i18n.tr("error"), i18n.tr("netease_playlist_invalid_id")
            )
            return

        result = self._post_json(
            "playlist/subscribe", data={"id": playlist_id, "t": 1}
        )
        if result is None:
            return

        QMessageBox.information(
            self,
            i18n.tr("success_title"),
            i18n.tr("netease_playlist_subscribe_success"),
        )
        self._load_playlists()

    @staticmethod
    def _parse_playlist_id(text: str):
        match = re.search(r"[?&]id=(\d+)", text)
        if match:
            return match.group(1)

        if text.isdigit():
            return text

        return None