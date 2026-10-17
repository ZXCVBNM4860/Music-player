# language/i18n.py

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional


def _resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)

    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def resource_path(relative_path: str) -> str:
    return str(_resource_root() / relative_path)


class Translator:
    def __init__(self):
        self._strings: Dict[str, str] = {}
        self._lang = "zh_cn"
        self._missing_warned: set[str] = set()
        self._load_lang(self._lang)

    def _load_lang(self, lang: str):
        path = resource_path(os.path.join("language", f"{lang}.json"))

        if not os.path.exists(path):
            self._strings = {}
            print(f"[i18n] Warning: Language file not found: {path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self._strings = {}
            print(f"[i18n] Warning: Failed to load {path}: {exc}")
            return

        if not isinstance(data, dict):
            self._strings = {}
            print(f"[i18n] Warning: {path} is not a key/value object")
            return

        self._strings = data
        self._missing_warned.clear()

    def set_lang(self, lang: str):
        self._lang = lang
        self._load_lang(lang)

    def get_lang(self) -> str:
        return self._lang

    def tr(self, key: str, default: Optional[str] = None) -> str:
        if key not in self._strings:
            if key not in self._missing_warned:
                self._missing_warned.add(key)
                print(f"[i18n] Warning: Missing translation key: '{key}'")
            return default or key
        return self._strings[key]

    def get_all_keys(self) -> Dict[str, str]:
        return self._strings.copy()


_translator = Translator()


def tr(key: str, default: Optional[str] = None) -> str:
    return _translator.tr(key, default)


def set_lang(lang: str):
    _translator.set_lang(lang)


def get_lang() -> str:
    return _translator.get_lang()


def get_all_keys() -> Dict[str, str]:
    return _translator.get_all_keys()