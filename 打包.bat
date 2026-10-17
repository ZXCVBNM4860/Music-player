@echo off
chcp 65001 >nul

pyinstaller --noconfirm --windowed --onedir --name "Music_Player" --add-data "resources/themes;resources/themes" --add-data "language;language" --collect-all PyQt6.QtWebEngineCore --collect-all _sounddevice_data --collect-all pedalboard --collect-all imageio_ffmpeg --hidden-import numpy.core._multiarray_umath main.py
cls
del /q "Music_Player.spec"
rd /s /q "build"
rd /s /q "__pycache__"
rd /s /q "core\__pycache__"
rd /s /q "language\__pycache__"
rd /s /q "ui\__pycache__"
rd /s /q "utils\__pycache__"
cls

:end
echo 按任意键退出...
pause >nul
exit /b 0
