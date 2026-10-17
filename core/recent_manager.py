# core\recent_manager.py

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.helpers import get_user_data_dir, log_line


class RecentManager:
    def __init__(self, data_path: Optional[Path] = None, max_items: int = 500):
        self.data_path = data_path or (get_user_data_dir() / "recent_played.json")
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        try:
            if self.data_path.exists():
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.items = data if isinstance(data, list) else []
            else:
                self.items = []
        except Exception as exc:
            log_line(f"[Recent] load failed: {exc}")
            self.items = []

    def save(self):
        try:
            tmp_path = self.data_path.with_name(self.data_path.name + ".tmp")
            tmp_path.write_text(
                json.dumps(self.items, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            os.replace(tmp_path, self.data_path)
        except Exception as exc:
            log_line(f"[Recent] save failed: {exc}")

    @staticmethod
    def _key(track: Dict[str, Any]) -> tuple:
        path = track.get("path")

        if path:
            return ("path", path)

        return ("title", track.get("title"), track.get("artist"))

    def add(self, track: Dict[str, Any]):
        key = self._key(track)
        self.items = [i for i in self.items if self._key(i) != key]
        self.items.insert(0, track)

        if len(self.items) > self.max_items:
            self.items = self.items[:self.max_items]

        self.save()

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.items)

    def clear(self):
        self.items = []
        self.save()
