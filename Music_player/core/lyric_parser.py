# core/lyric_parser.py

import re
from typing import List

TIME_RE = re.compile(r"\[(\d{2,}):(\d{2})(?:\.(\d{2,3}))?\]")

class LyricLine:
    def __init__(self, time_ms: int, text: str):
        self.time_ms = time_ms
        self.text = text
        self.t_text = ""

def _parse_time(mm: str, ss: str, ms_str: str) -> int:
    ms = int(ms_str) * (10 if len(ms_str) == 2 else 1) if ms_str else 0
    return (int(mm) * 60 + int(ss)) * 1000 + ms

def parse_lrc(lrc_text: str) -> List[LyricLine]:
    lines = []
    for line in lrc_text.splitlines():
        line = line.strip()
        matches = list(TIME_RE.finditer(line))
        if not matches:
            continue
        
        text = TIME_RE.sub("", line).strip()
        if not text:
            continue
            
        for match in matches:
            time_ms = _parse_time(match.group(1), match.group(2), match.group(3))
            lines.append(LyricLine(time_ms, text))
            
    lines.sort(key=lambda x: x.time_ms)
    return lines

def parse_tlyric(tlyric_text: str, main_lines: List[LyricLine]):
    t_map = {}
    for line in tlyric_text.splitlines():
        matches = list(TIME_RE.finditer(line))
        if not matches:
            continue
        
        text = TIME_RE.sub("", line).strip()
        if not text:
            continue
            
        for match in matches:
            time_ms = _parse_time(match.group(1), match.group(2), match.group(3))
            t_map[time_ms] = text

    for line in main_lines:
        if line.time_ms in t_map:
            line.t_text = t_map[line.time_ms]