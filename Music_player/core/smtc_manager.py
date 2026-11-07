# core/smtc_manager.py

import sys
import os
import ctypes
import winreg
import subprocess
import time
from ctypes import wintypes, CFUNCTYPE
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from utils.helpers import log_line, get_program_dir

CALLBACK_TYPE = CFUNCTYPE(None)

class SMTCManager(QObject):
    play_pause_signal = pyqtSignal()
    next_signal = pyqtSignal()
    prev_signal = pyqtSignal()

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._dll = None
        self._is_enabled = False
        self._last_timeline = 0.0
        
        if sys.platform == "win32":
            if self._shortcut_needs_refresh():
                self._register_app_shortcut()
            QTimer.singleShot(500, self._init_smtc)

    def _shortcut_path(self) -> str:
        return os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs",
            "MusicPlayer.lnk",
        )

    def _shortcut_needs_refresh(self) -> bool:
        path = self._shortcut_path()

        try:
            if not os.path.exists(path):
                return True

            return os.path.getmtime(path) < os.path.getmtime(sys.executable)
        except Exception:
            return True

    def _register_app_shortcut(self):
        try:
            app_id = "MusicPlayer.App"
            
            key_path = fr"Software\Classes\AppUserModelId\{app_id}"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "MusicPlayer")
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, sys.executable)
            winreg.CloseKey(key)

            lnk_path = self._shortcut_path()
            start_menu = os.path.dirname(lnk_path)
            
            if getattr(sys, 'frozen', False):
                args_str = ""
                work_dir = os.path.dirname(sys.executable)
                exe_path = sys.executable
            else:
                args_str = f'"{os.path.abspath(sys.argv[0])}"'
                work_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                exe_path = sys.executable

            ps_script = f'''
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{lnk_path}")
            $Shortcut.TargetPath = "{exe_path}"
            $Shortcut.WorkingDirectory = "{work_dir}"
            $Shortcut.Arguments = "{args_str}"
            $Shortcut.IconLocation = "{exe_path},0"
            $Shortcut.Save()
            
            $shell = New-Object -ComObject Shell.Application
            $folder = $shell.Namespace("{start_menu}")
            $item = $folder.ParseName("MusicPlayer.lnk")
            if ($item) {{
                $item.ExtendedProperty("System.AppUserModel.ID") = "{app_id}"
            }}
            '''
            subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script], capture_output=True, timeout=8)
            log_line("[SMTC] Forced AUMID and shortcut creation.")
        except Exception as e:
            log_line(f"[SMTC] Register shortcut failed: {e}")

    def _init_smtc(self):
        try:
            dll_path = get_program_dir() / "smtc_bridge.dll"
            if not dll_path.exists():
                dll_path = get_program_dir() / "_internal" / "smtc_bridge.dll"
                
            self._dll = ctypes.CDLL(str(dll_path))
            hwnd = int(self._window.winId())
            if not hwnd: return

            self._cb_play = CALLBACK_TYPE(self.play_pause_signal.emit)
            self._cb_next = CALLBACK_TYPE(self.next_signal.emit)
            self._cb_prev = CALLBACK_TYPE(self.prev_signal.emit)

            self._dll.InitSMTC.argtypes = [wintypes.HWND, CALLBACK_TYPE, CALLBACK_TYPE, CALLBACK_TYPE]
            self._dll.InitSMTC.restype = ctypes.c_bool

            success = self._dll.InitSMTC(hwnd, self._cb_play, self._cb_next, self._cb_prev)
            if success:
                self._is_enabled = True
                log_line("[SMTC] C++ Bridge initialized.")
            else:
                log_line("[SMTC] C++ Init failed.")
        except Exception as e:
            log_line(f"[SMTC] DLL Load failed: {e}")

    def update_metadata(self, title: str, artist: str, album: str = "", cover_path: str = ""):
        if not self._is_enabled or not self._dll: return
        self._dll.UpdateMetadata.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR]
        self._dll.UpdateMetadata.restype = None
        self._dll.UpdateMetadata(title, artist, album, cover_path if cover_path else None)

    def update_playback_status(self, is_playing: bool, is_stopped: bool = False):
        if not self._is_enabled or not self._dll: return
        status = 1 if is_playing else 0
        if is_stopped: status = 2
        self._dll.UpdatePlaybackStatus(status)

    def update_timeline(self, current_sec: float, total_sec: float):
        if not self._is_enabled or not self._dll:
            return

        if total_sec <= 0:
            return

        now = time.monotonic()

        if now - self._last_timeline < 1.0:
            return

        self._last_timeline = now

        self._dll.UpdateTimeline.argtypes = [ctypes.c_double, ctypes.c_double]
        self._dll.UpdateTimeline.restype = None
        self._dll.UpdateTimeline(float(current_sec), float(total_sec))