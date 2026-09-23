# recent_manager.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


class RecentManager:
    def __init__(self, data_path: Optional[Path] = None, max_items: int = 500):
        self.data_path = data_path or Path("./recent_played.json")
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        try:
            if self.data_path.exists():
                self.items = json.loads(self.data_path.read_text(encoding="utf-8"))
        except Exception:
            self.items = []

    def save(self):
        try:
            self.data_path.write_text(
                json.dumps(self.items, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def add(self, track: Dict[str, Any]):
        path = track.get("path", "")
        self.items = [i for i in self.items if i.get("path") != path]
        self.items.insert(0, track)
        if len(self.items) > self.max_items:
            self.items = self.items[:self.max_items]
        self.save()

    def get_all(self) -> List[Dict[str, Any]]:
        return self.items

    def clear(self):
        self.items = []
        self.save()