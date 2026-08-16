"""文件管理工具"""

from pathlib import Path
from typing import Optional


def move_to_rejected_trial(file_path: Path, base_download_path: Path) -> Optional[Path]:
    """
    将疑似试听版文件移至回收站目录。
    
    Args:
        file_path: 源文件路径
        base_download_path: 下载根目录（在其下创建 rejected_trial/）
    
    Returns:
        移动后的目标路径，失败返回 None
    """
    if not file_path.exists():
        return None
    
    rejected_dir = base_download_path / "rejected_trial"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    
    # 处理同名冲突
    dest = rejected_dir / file_path.name
    counter = 1
    while dest.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        dest = rejected_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    
    try:
        file_path.rename(dest)
        return dest
    except Exception:
        return None