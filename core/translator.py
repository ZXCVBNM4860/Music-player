# core/translator.py

import re
import threading

import requests

from utils.helpers import log_line


BING_HOME = "https://www.bing.com/translator"

SOURCE_LANGUAGES = ("auto", "zh-CN", "en", "ja")

TARGET_LANGUAGES = ("zh-CN", "en", "ja")

LANGUAGE_MAP = {
    "auto": "auto-detect",
    "zh-CN": "zh-Hans",
    "en": "en",
    "ja": "ja",
}

IG_PATTERN = re.compile(r'IG:"([0-9A-Za-z]+)"')
IID_PATTERN = re.compile(r'data-iid="([^"]+)"')
TOKEN_PATTERN = re.compile(
    r'params_AbusePreventionHelper\s*=\s*\[(\d+),\s*"([^"]+)"'
)


class TranslationError(Exception):
    pass


class BingTranslator:
    def __init__(self, source: str = "auto", target: str = "en"):
        self.source = source if source in SOURCE_LANGUAGES else "auto"
        self.target = target if target in TARGET_LANGUAGES else "en"

        self._lock = threading.Lock()
        self._session = None
        self._params = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            })

        return self._session

    def _fetch_params(self) -> dict:
        response = self.session.get(BING_HOME, timeout=10)
        response.raise_for_status()

        page = response.text

        ig = IG_PATTERN.search(page)
        iid = IID_PATTERN.search(page)
        token = TOKEN_PATTERN.search(page)

        if not (ig and iid and token):
            raise TranslationError("bing_params_error")

        base = response.url.split("/translator")[0] or "https://www.bing.com"

        return {
            "base": base,
            "IG": ig.group(1),
            "IID": iid.group(1),
            "key": token.group(1),
            "token": token.group(2),
        }

    def _params_or_fetch(self) -> dict:
        with self._lock:
            if self._params is None:
                self._params = self._fetch_params()

            return self._params

    def _reset_params(self):
        with self._lock:
            self._params = None

    def translate(self, text: str) -> str:
        text = (text or "").strip()

        if not text:
            return ""

        params = self._params_or_fetch()

        response = self.session.post(
            f"{params['base']}/ttranslatev3",
            params={
                "isVertical": 1,
                "IG": params["IG"],
                "IID": params["IID"],
            },
            data={
                "fromLang": LANGUAGE_MAP[self.source],
                "text": text,
                "to": LANGUAGE_MAP[self.target],
                "token": params["token"],
                "key": params["key"],
            },
            headers={"Referer": f"{params['base']}/translator"},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list) or not data:
            raise TranslationError("bing_unexpected_response")

        translations = data[0].get("translations") or []

        if not translations:
            raise TranslationError("bing_empty_translation")

        return translations[0].get("text", "")

    def translate_many(self, texts: list) -> list:
        results = []

        for text in texts:
            try:
                results.append(self.translate(text))
            except Exception as exc:
                log_line(f"[Translate] failed: {exc}")
                self._reset_params()
                results.append("")

        return results