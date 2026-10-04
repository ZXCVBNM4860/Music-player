# core/api_client.py

import functools
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional, Union

import requests

from core.config import Config
from language.i18n import tr


class APIError(Exception):
    pass

class RetryableAPIError(APIError):
    pass

class APINotFoundError(APIError):
    pass

def retry_on_error(max_retries: int = Config.MAX_RETRY, delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error: Optional[Exception] = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, RetryableAPIError) as exc:
                    last_error = exc
                    is_last_attempt = attempt == max_retries - 1

                    if not is_last_attempt:
                        time.sleep(delay * (attempt + 1))

            raise APIError(
                tr("api_request_failed").format(
                    max_retries=max_retries,
                    last=last_error,
                )
            ) from last_error

        return wrapper

    return decorator


class APIClient:
    def __init__(self, base_url: str = Config.DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")
        self._local = threading.local()

    @property
    def session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                ),
                "Referer": "https://music.163.com/",
            })
            self._local.session = session

        return self._local.session

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", Config.TIMEOUT_API)

        try:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RetryableAPIError(
                tr("api_request_endpoint_failed").format(
                    endpoint=endpoint,
                    e=exc,
                )
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RetryableAPIError(
                tr("api_invalid_json").format(e=exc)
            ) from exc

        code = data.get("code")

        if code == 200:
            return data

        message = data.get("msg", tr("api_unknown_error"))

        if isinstance(code, int) and 500 <= code < 600:
            raise RetryableAPIError(
                tr("api_server_error").format(code=code, msg=message)
            )

        if code == 404:
            raise APINotFoundError(
                tr("api_not_found_error").format(code=code, msg=message)
            )

        raise APIError(
            tr("api_error_code").format(code=code, msg=message)
        )

    def check_alive(self) -> bool:
        try:
            self._request(
                "GET",
                "search",
                params={"keywords": "test", "limit": 1},
                timeout=5,
            )
            return True
        except APIError:
            return False

    @retry_on_error()
    def search_playlists(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            "search",
            params={
                "keywords": keywords,
                "limit": limit,
                "type": 1000,
            },
        )

        playlists = data.get("result", {}).get("playlists", [])
        result = []

        for playlist in playlists:
            creator = playlist.get("creator") or {}

            result.append({
                "id": playlist["id"],
                "name": playlist["name"],
                "creator": creator.get("nickname", ""),
                "track_count": playlist.get("trackCount", 0),
                "play_count": playlist.get("playCount", 0),
            })

        return result

    @retry_on_error()
    def search_songs(self, keywords: str, limit: int = 30) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            "search",
            params={
                "keywords": keywords,
                "limit": limit,
                "type": 1,
            },
        )

        songs = data.get("result", {}).get("songs", [])
        result = []

        for song in songs:
            artists = [artist["name"] for artist in song.get("ar", [])]
            album = song.get("al") or {}

            result.append({
                "id": song["id"],
                "name": song["name"],
                "artists": artists,
                "album": album.get("name", ""),
                "duration": song.get("dt", 0),
                "pic_url": album.get("picUrl", ""),
            })

        return self._fill_missing_song_fields(result)

    def _fill_missing_song_fields(self, songs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not songs:
            return songs

        missing = [
            song for song in songs
            if not song.get("artists") or not song.get("duration") or not song.get("pic_url")
        ]
        if not missing:
            return songs

        ids = [str(song["id"]) for song in missing if song.get("id")]
        if not ids:
            return songs

        detail_map: dict[str, dict[str, Any]] = {}
        chunk_size = 200

        for i in range(0, len(ids), chunk_size):
            chunk = ids[i:i + chunk_size]

            try:
                detail = self._request(
                    "GET",
                    "song/detail",
                    params={"ids": ",".join(chunk)},
                )
            except APIError:
                continue

            for s in detail.get("songs", []):
                album = s.get("al") or {}
                detail_map[str(s.get("id"))] = {
                    "artists": [a.get("name", "") for a in s.get("ar", [])],
                    "album": album.get("name", ""),
                    "duration": s.get("dt", 0),
                    "pic_url": album.get("picUrl", ""),
                }

        for song in songs:
            info = detail_map.get(str(song.get("id")))
            if not info:
                continue

            if not song.get("artists"):
                song["artists"] = info["artists"]
            if not song.get("album"):
                song["album"] = info["album"]
            if not song.get("duration"):
                song["duration"] = info["duration"]
            if not song.get("pic_url"):
                song["pic_url"] = info["pic_url"]

        return songs

    @retry_on_error()
    def search_mvs(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            "search",
            params={
                "keywords": keywords,
                "limit": limit,
                "type": 1004,
            },
        )

        mvs = data.get("result", {}).get("mvs", [])
        result = []

        for mv in mvs:
            result.append({
                "id": mv["id"],
                "name": mv["name"],
                "artist": mv.get("artistName", ""),
                "duration": mv.get("duration", 0),
            })

        return result

    @retry_on_error()
    def get_song_detail(self, song_id: str) -> dict[str, Any]:
        data = self._request("GET", "song/detail", params={"ids": song_id})
        songs = data.get("songs", [])

        if not songs:
            raise APINotFoundError(
                tr("api_song_not_found").format(song_id=song_id)
            )

        song = songs[0]
        album = song.get("al") or {}

        return {
            "id": song_id,
            "name": song["name"],
            "artists": [artist["name"] for artist in song.get("ar", [])],
            "album": album.get("name", ""),
            "pic_url": album.get("picUrl", ""),
        }

    @retry_on_error()
    def get_playlist_detail(self, playlist_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", "playlist/detail", params={"id": playlist_id})
        playlist = data.get("playlist") or {}

        if not playlist:
            raise APINotFoundError(
                tr("api_playlist_not_found").format(playlist_id=playlist_id)
            )

        tracks = playlist.get("tracks", [])
        result = []

        for track in tracks:
            album = track.get("al") or {}

            result.append({
                "id": track["id"],
                "name": track["name"],
                "artists": [artist["name"] for artist in track.get("ar", [])],
                "album": album.get("name", ""),
                "pic_url": album.get("picUrl", ""),
            })

        return result

    @retry_on_error()
    def get_download_url(
        self,
        song_id: str,
        br: Union[int, str] = 320000,
    ) -> Optional[str]:
        br_param = 999000 if br == "flac" else br

        data = self._request(
            "GET",
            "song/url",
            params={
                "id": song_id,
                "br": br_param,
            },
        )

        url_list = data.get("data", [])

        if not url_list:
            return None

        return url_list[0].get("url")

    @retry_on_error()
    def get_mv_download_url(self, mv_id: str) -> Optional[str]:
        data = self._request("GET", "mv/url", params={"id": mv_id})
        url_data = data.get("data") or {}

        if not url_data:
            return None

        return url_data.get("url")

    def download_file(
        self,
        url: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
        max_retries: int = Config.MAX_RETRY,
    ) -> bool:
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url,
                    stream=True,
                    timeout=Config.TIMEOUT_DOWNLOAD,
                )

                if response.status_code != 200:
                    can_retry = 500 <= response.status_code < 600
                    is_last_attempt = attempt == max_retries - 1

                    if can_retry and not is_last_attempt:
                        time.sleep(1.0 * (attempt + 1))
                        continue

                    return False

                with open(output_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if cancel_callback and cancel_callback():
                            return False

                        if not chunk:
                            continue

                        file.write(chunk)

                        if progress_callback:
                            progress_callback(len(chunk))

                return True

            except (
                requests.exceptions.RequestException,
                ConnectionError,
                TimeoutError,
            ):
                is_last_attempt = attempt == max_retries - 1

                if is_last_attempt:
                    return False

                time.sleep(1.0 * (attempt + 1))

            except Exception:
                return False

        return False