@echo off
chcp 65001 >nul

D:
cd D:\Python\Music_player
cls

rd /s /q "__pycache__"
rd /s /q "core\__pycache__"
rd /s /q "language\__pycache__"
rd /s /q "ui\__pycache__"
rd /s /q "utils\__pycache__"
rd /s /q "downloads"
rd /s /q "config"
rd /s /q "build"
rd /s /q "dist"
del /q "MusicPlayer.spec"
cls

pyinstaller --onedir --windowed --noconfirm --name "MusicPlayer" main.py --hidden-import PyQt6.QtWebEngineCore --hidden-import PyQt6.QtWebEngineWidgets --hidden-import PyQt6.QtWebChannel --hidden-import sounddevice --collect-all imageio_ffmpeg --collect-all pedalboard --collect-submodules ui --collect-submodules core --add-data "language;language" --add-data "resources;resources" --exclude-module PyQt6.Qt3DAnimation --exclude-module PyQt6.Qt3DCore --exclude-module PyQt6.Qt3DExtras --exclude-module PyQt6.Qt3DInput --exclude-module PyQt6.Qt3DLogic --exclude-module PyQt6.Qt3DRender --exclude-module PyQt6.QtBluetooth --exclude-module PyQt6.QtCharts --exclude-module PyQt6.QtDataVisualization --exclude-module PyQt6.QtDBus --exclude-module PyQt6.QtDesigner --exclude-module PyQt6.QtHelp --exclude-module PyQt6.QtLocation --exclude-module PyQt6.QtNfc --exclude-module PyQt6.QtOpenGL --exclude-module PyQt6.QtOpenGLWidgets --exclude-module PyQt6.QtPdf --exclude-module PyQt6.QtPdfWidgets --exclude-module PyQt6.QtPositioning --exclude-module PyQt6.QtQml --exclude-module PyQt6.QtQuick --exclude-module PyQt6.QtQuick3D --exclude-module PyQt6.QtQuickWidgets --exclude-module PyQt6.QtRemoteObjects --exclude-module PyQt6.QtScxml --exclude-module PyQt6.QtSensors --exclude-module PyQt6.QtSerialPort --exclude-module PyQt6.QtSpatialAudio --exclude-module PyQt6.QtSql --exclude-module PyQt6.QtStateMachine --exclude-module PyQt6.QtTest --exclude-module PyQt6.QtTextToSpeech --exclude-module PyQt6.QtWebEngineQuick --exclude-module PyQt6.QtWebSockets --exclude-module PyQt6.QtXml

copy /y "smtc_bridge.dll" "dist\MusicPlayer\"

rd /s /q "__pycache__"
rd /s /q "core\__pycache__"
rd /s /q "language\__pycache__"
rd /s /q "ui\__pycache__"
rd /s /q "utils\__pycache__"
rd /s /q "downloads"
rd /s /q "build"
del /q "MusicPlayer.spec"

pause
