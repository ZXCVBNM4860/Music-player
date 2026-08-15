"""API 客户端（异常处理重构 + Session 线程安全版）"""

import os
import sys
import threading
import time
from typing import Optional, Any, Union, Callable
from pathlib import Path
import requests
from core.config import Config


class APIError(Exception):
    """API 通用异常（网络/服务器错误）"""
    pass


class APINotFoundError(APIError):
    """资源不存在（404 或返回空数据）"""
    pass


def retry_on_error(max_retries: int = Config.MAX_RETRY, delay: float = 1.0):
    """
    重试装饰器，仅对网络/IO 异常生效。
    代码逻辑错误（TypeError、KeyError 等）不会触发重试，直接抛出。
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, ConnectionError, TimeoutError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise APIError(f"请求失败（已重试 {max_retries} 次）: {e}") from e
                except Exception as e:
                    raise
            return None
        return wrapper
    return decorator


class APIClient:
    def __init__(self, base_url: str = Config.DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")
        self._local = threading.local()

    @property
    def session(self) -> requests.Session:
        """每个线程独立的 Session 实例"""
        if not hasattr(self._local, 'session'):
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://music.163.com/"
            })
            self._local.session = s
        return self._local.session

    def set_base_url(self, url: str):
        self.base_url = url.rstrip("/")

    # ==================== 内部请求封装 ====================

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", Config.TIMEOUT_API)

        try:
            r = self.session.request(method, url, timeout=timeout, **kwargs)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise APIError(f"请求 {endpoint} 失败: {e}") from e

        try:
            data = r.json()
        except ValueError as e:
            raise APIError(f"响应非 JSON 格式: {e}") from e

        if data.get("code") != 200:
            raise APIError(f"API 返回错误码 {data.get('code')}: {data.get('msg', '未知错误')}")

        return data

    # ==================== 公开 API ====================

    @retry_on_error()
    def check_alive(self) -> bool:
        try:
            self._request("GET", "login/status", timeout=5)
            return True
        except APIError:
            return False

    @retry_on_error()
    def search_playlists(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request("GET", "search", params={"keywords": keywords, "limit": limit, "type": 1000})
        playlists = data.get("result", {}).get("playlists", [])
        return [{
            "id": p["id"],
            "name": p["name"],
            "creator": p.get("creator", {}).get("nickname", ""),
            "track_count": p.get("trackCount", 0),
            "play_count": p.get("playCount", 0)
        } for p in playlists]

    @retry_on_error()
    def search_songs(self, keywords: str, limit: int = 30) -> list[dict[str, Any]]:
        data = self._request("GET", "search", params={"keywords": keywords, "limit": limit, "type": 1})
        songs = data.get("result", {}).get("songs", [])
        return [{
            "id": s["id"],
            "name": s["name"],
            "artists": [a["name"] for a in s.get("ar", [])],
            "album": s.get("al", {}).get("name", ""),
            "duration": s.get("dt", 0)
        } for s in songs]

    @retry_on_error()
    def search_mvs(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request("GET", "search", params={"keywords": keywords, "limit": limit, "type": 1004})
        mvs = data.get("result", {}).get("mvs", [])
        return [{
            "id": m["id"],
            "name": m["name"],
            "artist": m.get("artistName", ""),
            "duration": m.get("duration", 0)
        } for m in mvs]

    @retry_on_error()
    def get_song_detail(self, song_id: str) -> dict[str, Any]:
        data = self._request("GET", "song/detail", params={"ids": song_id})
        songs = data.get("songs", [])
        if not songs:
            raise APINotFoundError(f"歌曲 {song_id} 不存在")
        s = songs[0]
        return {
            "id": song_id,
            "name": s["name"],
            "artists": [a["name"] for a in s.get("ar", [])],
            "album": s.get("al", {}).get("name", "")
        }

    @retry_on_error()
    def get_playlist_detail(self, playlist_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", "playlist/detail", params={"id": playlist_id})
        playlist = data.get("playlist", {})
        if not playlist:
            raise APINotFoundError(f"歌单 {playlist_id} 不存在")
        tracks = playlist.get("tracks", [])
        return [{
            "id": t["id"],
            "name": t["name"],
            "artists": [a["name"] for a in t.get("ar", [])],
            "album": t.get("al", {}).get("name", "")
        } for t in tracks]

    def get_download_url(self, song_id: str, br: Union[int, str] = 320000) -> Optional[str]:
        br_param = 999000 if br == "flac" else br
        try:
            data = self._request("GET", "song/url", params={"id": song_id, "br": br_param})
            url_list = data.get("data", [])
            if not url_list:
                return None
            return url_list[0].get("url")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"获取下载链接异常: {e}") from e

    def get_mv_download_url(self, mv_id: str) -> Optional[str]:
        try:
            data = self._request("GET", "mv/url", params={"id": mv_id})
            url_data = data.get("data", {})
            if not url_data:
                return None
            return url_data.get("url")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"获取 MV 链接异常: {e}") from e

    def download_file(
        self,
        url: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> bool:
        try:
            r = self.session.get(url, stream=True, timeout=Config.TIMEOUT_DOWNLOAD)
            if r.status_code != 200:
                return False

            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if cancel_callback and cancel_callback():
                        return False
                    if not chunk:
                        continue
                    f.write(chunk)
                    if progress_callback:
                        progress_callback(len(chunk))
            return True
        except Exception:
            return False