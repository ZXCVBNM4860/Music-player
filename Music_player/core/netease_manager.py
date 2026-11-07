# core/netease_manager.py

import requests
from core.api_client import APIClient
from core.auth_manager import AuthManager
from language import i18n
from utils.helpers import log_line


class NeteaseManager:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.auth = AuthManager()
        self.client = APIClient(self.api_url, cookies=self.auth.cookies)

    def refresh_client(self):
        self.client = APIClient(self.api_url, cookies=self.auth.cookies)

    def save_login(self, cookies: dict, user_info: dict):
        self.auth.save(cookies, user_info)
        self.refresh_client()

    def get_lyric(self, song_id: str) -> dict:
        return self.client.get_lyric(song_id)

    def fetch_user_playlists(self, uid: str) -> list:
        try:
            session = requests.Session()
            session.cookies.update(self.auth.cookies or {})
            response = session.get(
                f"{self.api_url}/user/playlist",
                params={"uid": uid, "limit": 1000},
                timeout=10,
            )
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"{i18n.tr('favorite_failed')}\n{exc}") from exc

        code = data.get("code")
        status = data.get("status")
        if code not in (200, None) and status not in (200, None):
            raise RuntimeError(
                f"{i18n.tr('favorite_failed')}\n"
                f"code={code} status={status} msg={data.get('msg', '')}"
            )

        uid_str = str(uid)
        playlists = (
            data.get("playlist")
            or (data.get("body") or {}).get("playlist")
            or []
        )
        return [
            {"id": p.get("id"), "name": p.get("name", "")}
            for p in playlists
            if str(p.get("userId")) == uid_str and p.get("id")
        ]

    def create_playlist(self, name: str) -> str:
        try:
            session = requests.Session()
            session.cookies.update(self.auth.cookies or {})
            response = session.post(
                f"{self.api_url}/playlist/create", data={"name": name}, timeout=10,
            )
            data = response.json()
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        code = data.get("code")
        status = data.get("status")
        if code not in (200, None) and status not in (200, None):
            raise RuntimeError(
                f"code={code} status={status} msg={data.get('msg', '')}"
            )

        pid = (
            data.get("id")
            or (data.get("playlist") or {}).get("id")
            or (data.get("body") or {}).get("id")
        )
        if not pid:
            raise RuntimeError(f"id missing: {data}")
        return str(pid)

    def add_song_to_playlist(self, pid: str, song_id: str) -> bool:
        try:
            session = requests.Session()
            session.cookies.update(self.auth.cookies or {})
            response = session.get(
                f"{self.api_url}/playlist/tracks",
                params={"op": "add", "pid": pid, "tracks": song_id},
                timeout=10,
            )
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"{i18n.tr('favorite_failed')}\n{exc}") from exc

        code = data.get("code")
        status = data.get("status")
        if code == 200 or (code is None and status in (200, None)):
            return True
        raise RuntimeError(
            f"{i18n.tr('favorite_failed')}\n"
            f"code={code} status={status} msg={data.get('msg', '')}"
        )