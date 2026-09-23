# utils/helpers.py
import os
import sys
from pathlib import Path


def clean_filename(name: str) -> str:
    invalid = '\\/*?:"<>|'
    for c in invalid:
        name = name.replace(c, "")
    return name.strip() or "unknown"


def format_number(num: int) -> str:
    return "{:,}".format(num)


def get_default_download_path() -> str:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = str(Path(__file__).parent.parent)

    download_dir = os.path.join(base_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)
    return download_dir