# ui/local_player/utils.py

from typing import Optional

def fmt_time(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def read_bool(value, default=False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


def read_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _core_title(local: dict) -> str:
    title = (local.get("title") or "").strip()
    artist = (local.get("artist") or "").strip()

    if not title:
        return ""

    for sep in (" - ", " – ", " — "):
        if sep not in title:
            continue
        left, right = title.split(sep, 1)
        left_l = left.strip().lower()
        artist_l = artist.lower()
        if not artist or left_l == artist_l or artist_l in left_l or left_l in artist_l:
            title = right.strip()
        break

    return title.lower()


def _score_match(song_title: str, song_artist: str, local: dict) -> int:
    s_title = (song_title or "").lower().strip()
    if not s_title:
        return -1

    l_core = _core_title(local)
    if not l_core:
        return -1
    if l_core != s_title:
        return -1

    score = 1000

    s_artist = (song_artist or "").lower().strip()
    l_artist = (local.get("artist") or "").lower().strip()
    l_full = (local.get("title") or "").lower().strip()

    if s_artist:
        if l_artist and s_artist == l_artist:
            score += 500
        elif l_artist and (s_artist in l_artist or l_artist in s_artist):
            score += 200
        elif s_artist in l_full:
            score += 300

    return score


def find_local_match(song_title: str, song_artist: str, local_tracks: list) -> Optional[str]:
    best_score = -1
    best_path = None
    for local in local_tracks:
        score = _score_match(song_title, song_artist, local)
        if score > best_score:
            best_score = score
            best_path = local.get("path")
    return best_path if best_score > 0 else None


def _cache_file_name(song_id: str, ext: str = "mp3") -> str:
    return f"netease_{song_id}.{ext}"