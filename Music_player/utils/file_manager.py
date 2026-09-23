# utils/file_manager.py
from pathlib import Path
from typing import Optional


def move_to_rejected_trial(file_path: Path, base_download_path: Path) -> Optional[Path]:
    if not file_path.exists():
        return None

    rejected_dir = base_download_path / "rejected_trial"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    dest = rejected_dir / file_path.name
    counter = 1

    while dest.exists():
        dest = rejected_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
        counter += 1

    try:
        file_path.rename(dest)
        return dest
    except Exception:
        return None