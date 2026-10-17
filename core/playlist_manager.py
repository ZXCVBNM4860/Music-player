# core\playlist_manager.py

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.helpers import get_user_data_dir, log_line


class PlaylistManager:
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or (get_user_data_dir() / "playlists.json")
        self.playlists: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        try:
            if self.data_path.exists():
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.playlists = data if isinstance(data, dict) else {}
            else:
                self.playlists = {}
        except Exception as exc:
            log_line(f"[Playlists] load failed: {exc}")
            self.playlists = {}

    def reload(self):
        self.load()

    def save(self):
        try:
            tmp_path = self.data_path.with_name(self.data_path.name + ".tmp")
            tmp_path.write_text(
                json.dumps(self.playlists, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            os.replace(tmp_path, self.data_path)
        except Exception as exc:
            log_line(f"[Playlists] save failed: {exc}")

    def create(self, name: str):
        self.reload()

        if name and name not in self.playlists:
            self.playlists[name] = []
            self.save()

    def delete(self, name: str):
        self.reload()

        if name in self.playlists:
            del self.playlists[name]
            self.save()

    def add_track(self, playlist_name: str, track: Dict[str, Any]):
        self.reload()

        if not playlist_name:
            return

        if playlist_name not in self.playlists:
            self.playlists[playlist_name] = []
        elif self._contains(self.playlists[playlist_name], track):
            return

        self.playlists[playlist_name].append(track)
        self.save()

    @staticmethod
    def _contains(tracks: List[Dict[str, Any]], track: Dict[str, Any]) -> bool:
        path = track.get("path")

        if path:
            return any(existing.get("path") == path for existing in tracks)

        key = (track.get("title"), track.get("artist"))

        return any(
            (existing.get("title"), existing.get("artist")) == key
            for existing in tracks
        )

    def remove_track(self, playlist_name: str, index: int):
        self.reload()

        if playlist_name in self.playlists:
            if 0 <= index < len(self.playlists[playlist_name]):
                self.playlists[playlist_name].pop(index)
                self.save()

    def get_tracks(self, name: str) -> List[Dict[str, Any]]:
        return list(self.playlists.get(name, []))

    def get_all_names(self) -> List[str]:
        return list(self.playlists.keys())
