# core/metadata_matcher.py

import time
import requests
from pathlib import Path
from utils.helpers import log_line
from core.api_client import APIClient

try:
    from mutagen.id3 import ID3, APIC, USLT
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC, Picture
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class MetadataMatcher:
    def __init__(self, api_url: str):
        self.api = APIClient(api_url)

    def match_and_embed(self, file_path: str, title: str, artist: str) -> bool:
        if not MUTAGEN_AVAILABLE:
            return False

        path = Path(file_path)
        if not path.exists():
            return False

        keyword = f"{title} {artist}".strip()
        if not keyword:
            return False

        try:
            results = self.api.search_songs(keyword, limit=1)
            if not results:
                return False
            song = results[0]
            song_id = song["id"]
            pic_url = song.get("pic_url")
        except Exception as e:
            log_line(f"[Matcher] Search failed for {keyword}: {e}")
            return False

        try:
            lyric_data = self.api.get_lyric(song_id)
        except Exception as e:
            log_line(f"[Matcher] Fetch lyric failed for {song_id}: {e}")
            return False

        cover_data = None
        if pic_url:
            try:
                resp = requests.get(pic_url, timeout=10)
                if resp.status_code == 200:
                    cover_data = resp.content
            except Exception:
                pass

        lrc_text = lyric_data.get("lrc", "")

        max_retries = 5
        for attempt in range(max_retries):
            try:
                ext = path.suffix.lower()
                if ext == ".mp3":
                    audio = MP3(path, ID3=ID3)
                    if audio.tags is None:
                        audio.add_tags()
                    if cover_data:
                        audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data))
                    if lrc_text:
                        audio.tags.add(USLT(encoding=3, lang="eng", desc="desc", text=lrc_text))
                    audio.save()
                    return True
                    
                elif ext == ".flac":
                    audio = FLAC(path)
                    if cover_data:
                        audio.clear_pictures()
                        pic = Picture()
                        pic.type = 3
                        pic.mime = "image/jpeg"
                        pic.data = cover_data
                        audio.add_picture(pic)
                    if lrc_text:
                        audio["lyrics"] = lrc_text
                    audio.save()
                    return True
                    
                elif ext == ".m4a":
                    audio = MP4(path)
                    if cover_data:
                        audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                    if lrc_text:
                        audio["\xa9lyr"] = lrc_text
                    audio.save()
                    return True
                    
                return False
                
            except PermissionError:
                if attempt == max_retries - 1:
                    log_line(f"[Matcher] Permission denied after {max_retries} attempts for {path.name}")
                    return False
                time.sleep(0.5)
            except Exception as e:
                log_line(f"[Matcher] Embed failed for {path.name}: {e}")
                return False

        return False