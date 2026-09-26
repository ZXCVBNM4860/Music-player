import re
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from language import i18n


class NeteasePlaylistDialog(QDialog):
    playlist_songs_ready = pyqtSignal(list, object)

    def __init__(self, parent=None, api_url="http://localhost:3000",
                 cookies=None, uid=None, nickname="",
                 current_song_id=None, current_playlist_id=None):
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

        header = QLabel(i18n.tr("netease_playlist_header").format(name=self.nickname or ""))
        header.setStyleSheet("font-size: 11pt; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        quick_layout = QHBoxLayout()

        self.btn_daily = QPushButton(i18n.tr("netease_daily_recommend"))
        self.btn_daily.clicked.connect(self._load_daily_recommend)
        quick_layout.addWidget(self.btn_daily)

        self.btn_heart = QPushButton(i18n.tr("netease_heart_mode"))
        self.btn_heart.clicked.connect(self._load_heart_mode)
        quick_layout.addWidget(self.btn_heart)

        self.btn_radar = QPushButton(i18n.tr("netease_private_radar"))
        self.btn_radar.clicked.connect(self._load_private_radar)
        quick_layout.addWidget(self.btn_radar)

        layout.addLayout(quick_layout)

        hint = QLabel(i18n.tr("netease_playlist_double_click_hint"))
        hint.setStyleSheet("color: #888888; padding: 2px 4px;")
        layout.addWidget(hint)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_playlist_double_clicked)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #141414;
                color: #eaeaea;
                border: 1px solid #333333;
            }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background-color: #2a2a2a; }
        """)
        layout.addWidget(self.list_widget, stretch=1)

        btn_layout = QHBoxLayout()

        self.btn_create = QPushButton(i18n.tr("netease_playlist_create"))
        self.btn_create.clicked.connect(self._create_playlist)
        btn_layout.addWidget(self.btn_create)

        self.btn_subscribe = QPushButton(i18n.tr("netease_playlist_subscribe"))
        self.btn_subscribe.clicked.connect(self._subscribe_playlist)
        btn_layout.addWidget(self.btn_subscribe)

        self.btn_refresh = QPushButton(i18n.tr("netease_playlist_refresh"))
        self.btn_refresh.clicked.connect(self._load_playlists)
        btn_layout.addWidget(self.btn_refresh)

        btn_layout.addStretch()

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _load_playlists(self):
        if not self.uid:
            QMessageBox.warning(self, i18n.tr("error"), i18n.tr("netease_playlist_no_uid"))
            return
        try:
            r = self.session.get(
                f"{self.api_url}/user/playlist",
                params={"uid": self.uid, "limit": 1000},
                timeout=10
            )
            data = r.json()
            if data.get("code") == 200:
                self.playlists = data.get("playlist", [])
                self._refresh_list()
            else:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))

    def _refresh_list(self):
        self.list_widget.clear()
        for p in self.playlists:
            name = p.get("name", "")
            count = p.get("trackCount", 0)
            creator = (p.get("creator") or {}).get("nickname", "")
            is_own = p.get("userId") == self.uid
            text = f"{name}  ({i18n.tr('netease_playlist_track_count').format(count=count)})"
            if not is_own and creator:
                text += f"  - {creator}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(item)

    def _on_playlist_double_clicked(self, item):
        p = item.data(Qt.ItemDataRole.UserRole)
        if not p:
            return
        pid = p.get("id")
        if not pid:
            return
        self._fetch_playlist_tracks(pid)

    def _fetch_playlist_tracks(self, pid):
        try:
            r = self.session.get(
                f"{self.api_url}/playlist/track/all",
                params={"id": pid, "limit": 1000},
                timeout=15
            )
            data = r.json()
            if data.get("code") != 200:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
                return
            self._emit_songs(data.get("songs", []), playlist_id=pid)
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))

    def _load_daily_recommend(self):
        try:
            r = self.session.get(
                f"{self.api_url}/recommend/songs",
                timeout=10
            )
            data = r.json()
            if data.get("code") != 200:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
                return
            songs = (data.get("data") or {}).get("dailySongs", [])
            self._emit_songs(songs)
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))

    def _load_heart_mode(self):
        if not self.current_song_id or not self.current_playlist_id:
            QMessageBox.warning(
                self, i18n.tr("notice"),
                i18n.tr("netease_heart_mode_need_playing")
            )
            return
        try:
            r = self.session.get(
                f"{self.api_url}/playmode/intelligence/list",
                params={
                    "id": self.current_song_id,
                    "pid": self.current_playlist_id,
                },
                timeout=10
            )
            data = r.json()
            if data.get("code") != 200:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
                return
            songs = data.get("data", [])
            self._emit_songs(songs)
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))

    def _load_private_radar(self):
        try:
            r = self.session.get(
                f"{self.api_url}/personalized",
                params={"limit": 1},
                timeout=10
            )
            data = r.json()
            if data.get("code") != 200:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
                return
            result = data.get("result", [])
            if not result:
                QMessageBox.information(self, i18n.tr("notice"), i18n.tr("netease_playlist_empty_msg"))
                return
            radar_id = result[0].get("id")
            if not radar_id:
                QMessageBox.warning(self, i18n.tr("error"), i18n.tr("netease_playlist_invalid_id"))
                return
            self._fetch_playlist_tracks(radar_id)
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))

    def _emit_songs(self, songs, playlist_id=None):
        if not songs:
            QMessageBox.information(self, i18n.tr("notice"), i18n.tr("netease_playlist_empty_msg"))
            return
        result = []
        for s in songs:
            artists = [a.get("name", "") for a in s.get("ar", [])]
            al = s.get("al") or {}
            result.append({
                "id": str(s.get("id")),
                "title": s.get("name", ""),
                "artist": ", ".join(artists),
                "duration": s.get("dt", 0) / 1000,
                "pic_url": al.get("picUrl", ""),
            })
        self.playlist_songs_ready.emit(result, playlist_id)
        QMessageBox.information(
            self, i18n.tr("success_title"),
            i18n.tr("netease_playlist_loaded").format(count=len(result))
        )

    def _create_playlist(self):
        name, ok = QInputDialog.getText(
            self, i18n.tr("netease_playlist_create"),
            i18n.tr("playlist_name_label")
        )
        if not ok or not name.strip():
            return
        try:
            r = self.session.post(
                f"{self.api_url}/playlist/create",
                data={"name": name.strip()},
                timeout=10
            )
            data = r.json()
            if data.get("code") == 200:
                QMessageBox.information(
                    self, i18n.tr("success_title"),
                    i18n.tr("netease_playlist_create_success")
                )
                self._load_playlists()
            else:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))

    def _subscribe_playlist(self):
        text, ok = QInputDialog.getText(
            self, i18n.tr("netease_playlist_subscribe"),
            i18n.tr("netease_playlist_subscribe_prompt")
        )
        if not ok or not text.strip():
            return
        text = text.strip()
        m = re.search(r"[?&]id=(\d+)", text)
        if m:
            pid = m.group(1)
        elif text.isdigit():
            pid = text
        else:
            QMessageBox.warning(
                self, i18n.tr("error"),
                i18n.tr("netease_playlist_invalid_id")
            )
            return
        try:
            r = self.session.post(
                f"{self.api_url}/playlist/subscribe",
                data={"id": pid, "t": 1},
                timeout=10
            )
            data = r.json()
            if data.get("code") == 200:
                QMessageBox.information(
                    self, i18n.tr("success_title"),
                    i18n.tr("netease_playlist_subscribe_success")
                )
                self._load_playlists()
            else:
                QMessageBox.warning(self, i18n.tr("error"), str(data))
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("error"), str(e))