@echo off
D:
cd "D:\Python\Music_player"
python main.py
rd /s /q "__pycache__"
rd /s /q "core\__pycache__"
rd /s /q "language\__pycache__"
rd /s /q "ui\__pycache__"
rd /s /q "utils\__pycache__"
rd /s /q "ui\local_player\__pycache__"
rd /s /q "ui\local_player\window\__pycache__"
rd /s /q "downloads"
rd /s /q "config"
rd /s /q "cache"