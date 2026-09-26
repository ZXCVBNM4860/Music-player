import json
from pathlib import Path
from typing import Optional, Dict, Any
from utils.helpers import get_user_data_dir


class AuthManager:
    def __init__(self):
        self.data_path = get_user_data_dir() / "auth.json"
        self.cookies: Optional[Dict[str, str]] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.load()

    def load(self):
        try:
            if self.data_path.exists():
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.cookies = data.get("cookies")
                self.user_info = data.get("user_info")
        except Exception:
            self.cookies = None
            self.user_info = None

    def save(self, cookies, user_info):
        self.cookies = cookies
        self.user_info = user_info
        try:
            self.data_path.write_text(
                json.dumps(
                    {"cookies": cookies, "user_info": user_info},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def clear(self):
        self.cookies = None
        self.user_info = None
        try:
            if self.data_path.exists():
                self.data_path.unlink()
        except Exception:
            pass