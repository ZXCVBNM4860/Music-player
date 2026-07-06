"""下载历史管理"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class DownloadHistory:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # 放在用户数据目录
            app_data = Path.home() / ".Music_player"
            app_data.mkdir(parents=True, exist_ok=True)
            db_path = app_data / "history.db"
        self.db_path = str(db_path)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    item_name TEXT,
                    item_type TEXT NOT NULL,
                    task_id TEXT,
                    status TEXT NOT NULL,
                    path TEXT,
                    bitrate TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_item ON downloads(item_id, item_type, task_id)
            """)
            conn.commit()
    
    def record(self, item_id: str, item_name: str, item_type: str, 
               status: str, task_id: str = "", path: str = "", bitrate: str = ""):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            # 先删除同一 item 的旧记录
            conn.execute(
                "DELETE FROM downloads WHERE item_id = ? AND item_type = ? AND task_id = ?",
                (item_id, item_type, task_id)
            )
            conn.execute(
                """INSERT INTO downloads (item_id, item_name, item_type, task_id, status, path, bitrate, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, item_name, item_type, task_id, status, path, bitrate, now, now)
            )
            conn.commit()
    
    def is_completed(self, item_id: str, item_type: str, task_id: str = "") -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM downloads WHERE item_id = ? AND item_type = ? AND task_id = ? ORDER BY updated_at DESC LIMIT 1",
                (item_id, item_type, task_id)
            )
            row = cursor.fetchone()
            return row is not None and row[0] == "completed"
    
    def get_pending_items(self, task_id: str, item_type: str = "song") -> List[Dict[str, Any]]:
        #获取歌单中未完成的项
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT item_id, item_name, status FROM downloads WHERE task_id = ? AND item_type = ?",
                (task_id, item_type)
            )
            return [{"item_id": r[0], "item_name": r[1], "status": r[2]} for r in cursor.fetchall()]
    
    def get_stats(self, task_id: str) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM downloads WHERE task_id = ? GROUP BY status",
                (task_id,)
            )
            stats = {"completed": 0, "failed": 0, "pending": 0, "skipped": 0}
            for row in cursor.fetchall():
                stats[row[0]] = row[1]
            return stats
