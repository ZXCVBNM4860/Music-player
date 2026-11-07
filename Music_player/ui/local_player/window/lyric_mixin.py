# ui/local_player/window/lyric_mixin.py

import re
from PyQt6.QtWidgets import QMessageBox
from language import i18n
from ui.workers import run_async
from ..lyric_widget import LyricWidget

class LyricMixin:
    def _fetch_lyric(self, track: dict):
        song_id = track.get("id")
        if not song_id or not str(song_id).isdigit():
            self.lyric_widget.set_status(i18n.tr("lyric_empty"))
            if hasattr(self, "desktop_lyric") and self.desktop_lyric.isVisible():
                self.desktop_lyric.set_lyrics([])
            return
            
        self.lyric_widget.set_status(i18n.tr("lyric_loading"))
        
        run_async(
            self.netease.get_lyric,
            args=(str(song_id),),
            on_success=self._on_lyric_loaded,
            on_error=self._on_lyric_failed
        )

    def _on_lyric_failed(self, _):
        self.lyric_widget.set_status(i18n.tr("lyric_empty"))
        if hasattr(self, "desktop_lyric") and self.desktop_lyric.isVisible():
            self.desktop_lyric.set_lyrics([])

    def _on_lyric_loaded(self, data: dict):
        lrc = data.get("lrc", "")
        tlyric = data.get("tlyric", "")
        
        if not lrc:
            self.lyric_widget.set_status(i18n.tr("lyric_empty"))
            if hasattr(self, "desktop_lyric") and self.desktop_lyric.isVisible():
                self.desktop_lyric.set_lyrics([])
            return
            
        if not tlyric and i18n.get_lang() == "en_us":
            if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]', lrc):
                self.lyric_widget.set_lyric(lrc, "", force_translate=True)
                
                run_async(
                    self._translate_lyric_worker,
                    args=(lrc,),
                    on_success=lambda res: self._apply_translated_lyric(res),
                    on_error=lambda _: self._apply_translated_lyric("")
                )
                return
                
        self.lyric_widget.set_lyric(lrc, tlyric)
        
        if hasattr(self, "desktop_lyric") and self.desktop_lyric.isVisible():
            self.desktop_lyric.set_lyrics(self.lyric_widget._lines)

    def _apply_translated_lyric(self, translated_lrc: str):
        self.lyric_widget.apply_auto_translation(translated_lrc)
        if hasattr(self, "desktop_lyric") and self.desktop_lyric.isVisible():
            self.desktop_lyric.set_lyrics(self.lyric_widget._lines)

    def _translate_lyric_worker(self, lrc: str) -> str:
        from core.translator import BingTranslator
        from core.lyric_parser import parse_lrc
        
        lines = parse_lrc(lrc)
        if not lines:
            return ""
            
        texts = [line.text for line in lines]
        translator = BingTranslator(source="auto", target="en")
        translated_list = translator.translate_many(texts)
        
        tlyric_lines = []
        for line, t in zip(lines, translated_list):
            t = t.strip()
            if t:
                m = line.time_ms // 60000
                s = (line.time_ms % 60000) // 1000
                ms = line.time_ms % 1000
                tlyric_lines.append(f"[{m:02d}:{s:02d}.{ms:03d}]{t}")
                
        return "\n".join(tlyric_lines)