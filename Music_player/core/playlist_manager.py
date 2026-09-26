# core/playlist_manager.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.helpers import get_user_data_dir


class PlaylistManager:
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or (get_user_data_dir() / "playlists.json")
        self.playlists: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        try:
            if self.data_path.exists():
                self.playlists = json.loads(self.data_path.read_text(encoding="utf-8"))
        except Exception:
            self.playlists = {}

    def save(self):
        try:
            self.data_path.write_text(
                json.dumps(self.playlists, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def create(self, name: str):
        if name not in self.playlists:
            self.playlists[name] = []
            self.save()

    def delete(self, name: str):
        if name in self.playlists:
            del self.playlists[name]
            self.save()

    def add_track(self, playlist_name: str, track: Dict[str, Any]):
        if playlist_name not in self.playlists:
            self.create(playlist_name)
        self.playlists[playlist_name].append(track)
        self.save()

    def remove_track(self, playlist_name: str, index: int):
        if playlist_name in self.playlists:
            if 0 <= index < len(self.playlists[playlist_name]):
                self.playlists[playlist_name].pop(index)
                self.save()

    def get_tracks(self, name: str) -> List[Dict[str, Any]]:
        return self.playlists.get(name, [])

    def get_all_names(self) -> List[str]:
        return list(self.playlists.keys())