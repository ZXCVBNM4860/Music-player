"""API"""
import time
from typing import Optional, Any, Union
from pathlib import Path
import requests
from core.config import Config


class APIError(Exception):
    pass


def retry_on_error(max_retries: int = Config.MAX_RETRY, delay: float = 1.0):
    # 重试装饰器
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise last_exception
            return None
        return wrapper
    return decorator


class APIClient:
    def __init__(self, base_url: str = Config.DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://music.163.com/"
        })
    
    def set_base_url(self, url: str):
        self.base_url = url.rstrip("/")
    
    @retry_on_error(max_retries=Config.MAX_RETRY, delay=0.5)
    def check_alive(self) -> bool:
        try:
            r = self.session.get(f"{self.base_url}/login/status", timeout=5)
            return r.status_code == 200
        except Exception:
            return False
    
    @retry_on_error(max_retries=Config.MAX_RETRY, delay=0.5)
    def search_playlists(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        # 搜索歌单
        url = f"{self.base_url}/search"
        params = {"keywords": keywords, "limit": limit, "type": 1000}
        r = self.session.get(url, params=params, timeout=Config.TIMEOUT_API)
        data = r.json()
        if data.get("code") == 200 and data.get("result"):
            playlists = data["result"].get("playlists", [])
            return [{
                "id": p["id"],
                "name": p["name"],
                "creator": p.get("creator", {}).get("nickname", ""),
                "track_count": p.get("trackCount", 0),
                "play_count": p.get("playCount", 0)
            } for p in playlists]
        return []
    
    @retry_on_error(max_retries=Config.MAX_RETRY, delay=0.5)
    def search_songs(self, keywords: str, limit: int = 30) -> list[dict[str, Any]]:
        # 搜索歌曲
        url = f"{self.base_url}/search"
        params = {"keywords": keywords, "limit": limit, "type": 1}
        r = self.session.get(url, params=params, timeout=Config.TIMEOUT_API)
        data = r.json()
        if data.get("code") == 200 and data.get("result"):
            songs = data["result"].get("songs", [])
            return [{
                "id": s["id"],
                "name": s["name"],
                "artists": [a["name"] for a in s.get("ar", [])],
                "album": s.get("al", {}).get("name", ""),
                "duration": s.get("dt", 0)
            } for s in songs]
        return []
    
    @retry_on_error(max_retries=Config.MAX_RETRY, delay=0.5)
    def search_mvs(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        # 搜索MV
        url = f"{self.base_url}/search"
        params = {"keywords": keywords, "limit": limit, "type": 1004}
        r = self.session.get(url, params=params, timeout=Config.TIMEOUT_API)
        data = r.json()
        if data.get("code") == 200 and data.get("result"):
            mvs = data["result"].get("mvs", [])
            return [{
                "id": m["id"],
                "name": m["name"],
                "artist": m.get("artistName", ""),
                "duration": m.get("duration", 0)
            } for m in mvs]
        return []
    
    @retry_on_error(max_retries=Config.MAX_RETRY, delay=0.5)
    def get_song_detail(self, song_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/song/detail?ids={song_id}"
        r = self.session.get(url, timeout=Config.TIMEOUT_API)
        data = r.json()
        if data.get("code") == 200 and data.get("songs"):
            return {
                "id": song_id,
                "name": data["songs"][0]["name"],
                "artists": [a["name"] for a in data["songs"][0].get("ar", [])],
                "album": data["songs"][0].get("al", {}).get("name", "")
            }
        raise APIError(f"获取失败: {data}")
    
    @retry_on_error(max_retries=Config.MAX_RETRY, delay=0.5)
    def get_playlist_detail(self, playlist_id: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/playlist/detail?id={playlist_id}"
        r = self.session.get(url, timeout=Config.TIMEOUT_API)
        data = r.json()
        if data.get("code") == 200 and data.get("playlist"):
            tracks = data["playlist"].get("tracks", [])
            return [{
                "id": t["id"],
                "name": t["name"],
                "artists": [a["name"] for a in t.get("ar", [])],
                "album": t.get("al", {}).get("name", "")
            } for t in tracks]
        raise APIError(f"获取失败: {data}")
    
    def get_download_url(self, song_id: str, br: Union[int, str] = 320000) -> Optional[str]:
        # 获取下载链接
        br_param = 999000 if br == "flac" else br
        url = f"{self.base_url}/song/url?id={song_id}&br={br_param}"
        try:
            r = self.session.get(url, timeout=Config.TIMEOUT_API)
            data = r.json()
            if data.get("code") == 200 and data.get("data"):
                return data["data"][0].get("url")
            return None
        except Exception:
            return None
    
    def download_file(self, url: str, output_path: Path, progress_callback=None) -> bool:
        # stream 分块下载到文件，返回是否成功。progress_callback(bytes_written)
        try:
            r = self.session.get(url, stream=True, timeout=Config.TIMEOUT_DOWNLOAD)
            if r.status_code != 200:
                return False
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    if progress_callback:
                        progress_callback(len(chunk))
            return True
        except Exception:
            return False
    
    def get_mv_download_url(self, mv_id: str) -> Optional[str]:
        # 获取MV下载链接
        url = f"{self.base_url}/mv/url?id={mv_id}"
        try:
            r = self.session.get(url, timeout=Config.TIMEOUT_API)
            data = r.json()
            if data.get("code") == 200 and data.get("data"):
                return data["data"].get("url")
            return None
        except Exception:
            return None