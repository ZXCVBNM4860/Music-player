# core\api_installer.py

import os
import sys
import time
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Callable, Optional
import requests
from utils.helpers import get_user_data_dir


NPM_MIRRORS = {
    "official": "https://registry.npmjs.org/",
    "npmmirror": "https://registry.npmmirror.com/",
}

GITHUB_MIRRORS = {
    "official": "https://codeload.github.com",
    "ghproxy": "https://ghproxy.net/https://codeload.github.com",
}

API_REPO_ZIP_PATH = "xgxdmx/NeteaseMusic-API/zip/refs/heads/main"


class APIInstaller:

    def __init__(
        self,
        npm_mirror: str = "npmmirror",
        github_mirror: str = "official",
        log: Optional[Callable[[str], None]] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
        **_ignored,
    ):
        self.npm_mirror = npm_mirror
        self.github_mirror = github_mirror
        self.log = log or (lambda msg: None)
        self.cancel_flag = cancel_flag or (lambda: False)

        self.user_dir = get_user_data_dir()
        self.api_root = self.user_dir / "API"
        self.api_dir = self.api_root / "api-enhanced"

        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MusicPlayer"}
        )

    @staticmethod
    def _which(name: str) -> Optional[str]:
        for cand in (name, name + ".cmd", name + ".exe", name + ".bat"):
            p = shutil.which(cand)
            if p:
                return p
        return None

    def _download(self, url: str, dest: Path, label: str = ""):
        self.log(f"Downloading {label or url}")
        r = self.session.get(url, stream=True, timeout=180)
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        last_pct = -1
        with open(dest, "wb") as f:
            for chunk in r.iter_content(64 * 1024):
                if self.cancel_flag():
                    raise RuntimeError("cancelled")
                f.write(chunk)
                done += len(chunk)
                if total > 0:
                    pct = int(done * 100 / total)
                    if pct != last_pct and pct % 5 == 0:
                        self.log(f"  {pct}% ({done // 1024} / {total // 1024} KB)")
                        last_pct = pct

    def _download_with_retry(self, url: str, dest: Path, label: str = "", max_retries: int = 3):
        last_err = None
        for attempt in range(max_retries):
            try:
                self._download(url, dest, label)
                return
            except Exception as e:
                last_err = e
                if self.cancel_flag():
                    raise RuntimeError("cancelled")
                if attempt < max_retries - 1:
                    self.log(f"[WARN] 下载失败（{attempt + 1}/{max_retries}）: {e}")
                    time.sleep(3)
        raise last_err

    def _extract_zip(self, zip_path: Path, dest: Path, strip_root: bool = False):
        self.log(f"Extracting {zip_path.name}")
        with zipfile.ZipFile(zip_path, "r") as z:
            if not strip_root:
                z.extractall(dest)
                return
            names = z.namelist()
            root = names[0].split("/")[0] if names else ""
            for member in z.infolist():
                if not member.filename.startswith(root + "/"):
                    continue
                rel = member.filename[len(root) + 1:]
                if not rel:
                    continue
                target = dest / rel
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)

    def _run(self, args, cwd=None, env=None) -> int:
        args = [str(a) for a in args]
        cmd_str = subprocess.list2cmdline(args)
        self.log(f"$ {cmd_str}")
        creationflags = 0x08000000
        proc = subprocess.Popen(
            cmd_str,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            env=env,
            shell=True,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self.log(f"  {line}")
        proc.wait()
        return proc.returncode

    def install(self):
        if sys.platform != "win32":
            return False, "installer_not_windows"
        try:
            self._step_check_node()
            self._step_api_enhanced()
            self._step_install_deps()
            self._step_create_launcher()
            self._step_add_to_path()
            self._step_start_api()
            return True, "install_success"
        except RuntimeError as e:
            if str(e) == "cancelled":
                return False, "install_cancelled"
            self.log(f"[XX] {e}")
            return False, "install_failed"
        except Exception as e:
            self.log(f"ERROR: {e}")
            return False, "install_failed"

    def _step_check_node(self):
        node = self._which("node")
        if not node:
            self.log("[XX] 未找到 Node.js，请先安装 Node.js 18 或更高版本")
            self.log("     下载地址: https://nodejs.org/")
            raise RuntimeError("Node.js not found")
        try:
            ver = subprocess.run(
                [node, "-v"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            ver = "?"
        self.log(f"[OK] Node.js {ver}")

        npm = self._which("npm")
        if not npm:
            self.log("[XX] 未找到 npm")
            raise RuntimeError("npm not found")
        try:
            npm_ver = subprocess.run(
                [npm, "-v"], capture_output=True, text=True, timeout=5, shell=True
            ).stdout.strip()
        except Exception:
            npm_ver = "?"
        self.log(f"[OK] npm {npm_ver}")

    def _step_api_enhanced(self):
        if (self.api_dir / "package.json").exists():
            self.log("[SKIP] api-enhanced already exists")
            return

        self.api_root.mkdir(parents=True, exist_ok=True)
        base = GITHUB_MIRRORS[self.github_mirror]
        url = f"{base}/{API_REPO_ZIP_PATH}"
        zip_path = self.api_root / "api-enhanced.zip"

        self._download_with_retry(url, zip_path, "api-enhanced")

        if self.api_dir.exists():
            shutil.rmtree(self.api_dir, ignore_errors=True)
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self._extract_zip(zip_path, self.api_dir, strip_root=True)
        zip_path.unlink(missing_ok=True)

        if not (self.api_dir / "package.json").exists():
            raise RuntimeError("解压后未找到 package.json")
        self.log("[OK] api-enhanced ready")

    def _step_install_deps(self):
        registry = NPM_MIRRORS.get(self.npm_mirror, NPM_MIRRORS["official"])
        try:
            (self.api_dir / ".npmrc").write_text(f"registry={registry}\n", encoding="utf-8")
        except Exception:
            pass

        env = os.environ.copy()
        env["HUSKY"] = "0"

        pnpm = self._which("pnpm")
        if pnpm:
            self.log(f"[OK] 使用 pnpm ({pnpm})")
            rc = self._run([pnpm, "install"], cwd=self.api_dir, env=env)
            if rc != 0:
                raise RuntimeError(f"pnpm install failed: {rc}")
        else:
            npm = self._which("npm")
            if not npm:
                raise RuntimeError("npm not found")
            self.log("[..] pnpm 未安装，使用 npm")
            rc = self._run([npm, "install"], cwd=self.api_dir, env=env)
            if rc != 0:
                raise RuntimeError(f"npm install failed: {rc}")

        if not (self.api_dir / "node_modules" / "express").exists():
            raise RuntimeError("node_modules/express missing after install")
        self.log("[OK] dependencies installed")

    def _launcher_path(self) -> Path:
        return self.api_root / "NeteaseCloudMusicAPI.bat"

    def _step_create_launcher(self):
        launcher = self._launcher_path()
        api_dir = str(self.api_dir)
        content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            f'cd /d "{api_dir}"\r\n'
            "where pnpm >nul 2>&1\r\n"
            "if %errorlevel% == 0 (\r\n"
            "    pnpm start\r\n"
            ") else (\r\n"
            "    npm start\r\n"
            ")\r\n"
            "pause >nul\r\n"
        )
        launcher.write_text(content, encoding="utf-8")
        self.log(f"[OK] launcher created: {launcher}")

    def _step_add_to_path(self):
        if sys.platform != "win32":
            return

        api_dir_str = str(self.api_root)

        try:
            import winreg
        except ImportError:
            self.log(f"[WARN] winreg 不可用，请手动添加 PATH: {api_dir_str}")
            return

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE,
            )
        except OSError as e:
            self.log(f"[WARN] 无法打开用户环境变量: {e}")
            self.log(f"       请手动添加 PATH: {api_dir_str}")
            return

        try:
            try:
                current_path, path_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path, path_type = "", winreg.REG_EXPAND_SZ

            parts = [p for p in current_path.split(";") if p.strip()]
            if any(p.strip().lower() == api_dir_str.lower() for p in parts):
                self.log(f"[SKIP] PATH 已包含: {api_dir_str}")
                return

            parts.append(api_dir_str)
            new_path = ";".join(parts)
            winreg.SetValueEx(key, "Path", 0, path_type, new_path)
            self.log(f"[OK] 已加入用户 PATH: {api_dir_str}")
            self._broadcast_env_change()
        except Exception as e:
            self.log(f"[WARN] 写入 PATH 失败: {e}")
            self.log(f"       请手动添加: {api_dir_str}")
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def _broadcast_env_change():
        try:
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_long()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                ctypes.c_wchar_p("Environment"),
                SMTO_ABORTIFHUNG,
                5000,
                ctypes.byref(result),
            )
        except Exception:
            pass

    def _step_start_api(self):
        launcher = self._launcher_path()
        if not launcher.exists():
            raise RuntimeError("launcher missing")
        self.log("Starting API server...")
        subprocess.Popen(["cmd", "/c", str(launcher)], creationflags=0x00000010)
        self.log("[OK] API server started")