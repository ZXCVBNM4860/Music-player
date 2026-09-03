"""国际化翻译模块"""

import json
import os
import sys
from typing import Dict, Optional


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包后"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # 使用本文件所在目录的父级作为根目录，避免启动目录变化导致路径错误
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


class Translator:
    def __init__(self):
        self._strings: Dict[str, str] = {}
        self._lang = "zh_cn"
        self._missing_warned: set[str] = set()
        self._load_lang(self._lang)

    def _load_lang(self, lang: str):
        path = resource_path(os.path.join("language", f"{lang}.json"))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._strings = json.load(f)
            # 切换语言时清空警告缓存，避免新语言下缺失的 key 被静默忽略
            self._missing_warned.clear()
        else:
            self._strings = {}
            print(f"[i18n] Warning: Language file not found: {path}")

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


# 全局单例
_translator = Translator()


def tr(key: str, default: Optional[str] = None) -> str:
    return _translator.tr(key, default)


def set_lang(lang: str):
    _translator.set_lang(lang)


def get_lang() -> str:
    return _translator.get_lang()


def get_all_keys() -> Dict[str, str]:
    return _translator.get_all_keys()
