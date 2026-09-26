# core/api_installer.py
import os
import sys
import ctypes
import shutil
import zipfile
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

import requests

from utils.helpers import get_user_data_dir


NODE_VERSION = "v22.11.0"
NODE_ARCH = "win-x64"

NODE_MIRRORS = {
    "official": "https://nodejs.org/dist",
    "npmmirror": "https://npmmirror.com/mirrors/node",
}

NPM_MIRRORS = {
    "official": "https://registry.npmjs.org/",
    "npmmirror": "https://registry.npmmirror.com/",
}

GITHUB_MIRRORS = {
    "official": "https://github.com",
    "ghproxy": "https://ghproxy.com/https://github.com",
}


class APIInstaller:

    def __init__(
        self,
        node_mirror: str = "npmmirror",
        npm_mirror: str = "npmmirror",
        github_mirror: str = "official",
        log: Optional[Callable[[str], None]] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ):
        self.node_mirror = node_mirror
        self.npm_mirror = npm_mirror
        self.github_mirror = github_mirror
        self.log = log or (lambda msg: None)
        self.cancel_flag = cancel_flag or (lambda: False)

        self.user_dir = get_user_data_dir()
        self.node_dir = self.user_dir / "nodejs"
        self.api_dir = self.user_dir / "api-enhanced"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MusicPlayer"
        })

    def _download(self, url: str, dest: Path, label: str = ""):
        self.log(f"Downloading {label or url}")
        r = self.session.get(url, stream=True, timeout=60)
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

    def _extract_zip(self, zip_path: Path, dest: Path, strip_root: bool = False):
        self.log(f"Extracting {zip_path.name}")
        with zipfile.ZipFile(zip_path, "r") as z:
            if strip_root:
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
            else:
                z.extractall(dest)

    def install(self):
        if sys.platform != "win32":
            return False, "installer_not_windows"

        try:
            self._step_nodejs()
            self._step_api_enhanced()
            self._step_install_deps()
            self._step_create_launcher()
            self._step_copy_to_system32()
            self._step_start_api()
            return True, "install_success"
        except RuntimeError as e:
            if str(e) == "cancelled":
                return False, "install_cancelled"
            return False, "install_failed"
        except Exception as e:
            self.log(f"ERROR: {e}")
            return False, "install_failed"

    def _step_nodejs(self):
        if (self.node_dir / "node.exe").exists():
            self.log(f"[SKIP] Node.js already exists")
            return

        base_url = NODE_MIRRORS[self.node_mirror]
        filename = f"node-{NODE_VERSION}-{NODE_ARCH}.zip"
        url = f"{base_url}/{NODE_VERSION}/{filename}"
        zip_path = self.user_dir / filename

        self._download(url, zip_path, "Node.js")
        if self.node_dir.exists():
            shutil.rmtree(self.node_dir, ignore_errors=True)
        self.node_dir.mkdir(parents=True, exist_ok=True)

        self._extract_zip(zip_path, self.node_dir, strip_root=True)
        zip_path.unlink(missing_ok=True)
        self.log("[OK] Node.js ready")

    def _step_api_enhanced(self):
        if (self.api_dir / "package.json").exists():
            self.log("[SKIP] api-enhanced already exists")
            return

        gh_base = GITHUB_MIRRORS[self.github_mirror]
        url = f"{gh_base}/xgxdmx/NeteaseMusic-API/archive/refs/heads/main.zip"
        zip_path = self.user_dir / "api-enhanced.zip"

        self._download(url, zip_path, "api-enhanced")
        if self.api_dir.exists():
            shutil.rmtree(self.api_dir, ignore_errors=True)
        self.api_dir.mkdir(parents=True, exist_ok=True)

        self._extract_zip(zip_path, self.api_dir, strip_root=True)
        zip_path.unlink(missing_ok=True)

        if not (self.api_dir / "package.json").exists():
            raise RuntimeError("api-enhanced package.json missing")
        self.log("[OK] api-enhanced ready")

    def _run(self, args, cwd=None, env=None) -> int:
        self.log(f"$ {' '.join(str(a) for a in args)}")
        creationflags = 0x08000000
        proc = subprocess.Popen(
            args,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            env=env,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self.log(f"  {line}")
        proc.wait()
        return proc.returncode

    def _step_install_deps(self):
        node_exe = self.node_dir / "node.exe"
        npm_cli = self.node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"

        if not node_exe.exists() or not npm_cli.exists():
            raise RuntimeError("node.exe or npm-cli.js not found")

        registry = NPM_MIRRORS[self.npm_mirror]
        self._run([str(node_exe), str(npm_cli), "config", "set", "registry", registry])

        self.log("Installing pnpm...")
        rc = self._run([str(node_exe), str(npm_cli), "install", "-g", "pnpm"])
        if rc != 0:
            raise RuntimeError(f"pnpm install failed: {rc}")

        pnpm_cmd = self.user_dir / "nodejs" / "pnpm.cmd"

        appdata_pnpm = Path(os.environ.get("APPDATA", "")) / "npm" / "pnpm.cmd"
        if appdata_pnpm.exists():
            pnpm_cmd = appdata_pnpm
        elif not pnpm_cmd.exists():
            self.log("pnpm not found, falling back to npm")
            env = os.environ.copy()
            env["PATH"] = str(self.node_dir) + os.pathsep + env.get("PATH", "")
            rc = self._run([str(node_exe), str(npm_cli), "install"], cwd=self.api_dir, env=env)
            if rc != 0:
                raise RuntimeError(f"npm install failed: {rc}")
            self.log("[OK] dependencies installed (npm)")
            return

        env = os.environ.copy()
        env["PATH"] = str(self.node_dir) + os.pathsep + str(appdata_pnpm.parent) + os.pathsep + env.get("PATH", "")
        env["HUSKY"] = "0"
        rc = self._run([str(pnpm_cmd), "install", "--dangerously-allow-all-builds"], cwd=self.api_dir, env=env)
        if rc != 0:
            raise RuntimeError(f"pnpm install failed: {rc}")

        if not (self.api_dir / "node_modules" / "express").exists():
            raise RuntimeError("node_modules/express missing after install")

        self.log("[OK] dependencies installed")

    def _launcher_path(self) -> Path:
        return self.user_dir / "NeteaseCloudMusicAPI.bat"

    def _step_create_launcher(self):
        launcher = self._launcher_path()
        content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            f'cd /d "{self.api_dir}"\r\n'
            f'"{self.node_dir / "node.exe"}" app.js\r\n'
            "pause >nul\r\n"
        )
        launcher.write_text(content, encoding="utf-8")
        self.log(f"[OK] launcher created: {launcher}")

    def _step_copy_to_system32(self):
        if sys.platform != "win32":
            return
        source = self._launcher_path()
        target = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "NeteaseCloudMusicAPI.bat"

        if target.exists():
            self.log(f"[SKIP] {target} already exists")
            return

        self.log("Requesting admin permission to write System32...")
        ps_cmd = (
            f'Start-Process cmd.exe -ArgumentList '
            f'\'/c copy /y "{source}" "{target}"\' '
            f'-Verb RunAs -Wait'
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True,
            creationflags=0x08000000,
        )
        if not target.exists():
            self.log(f"[WARN] System32 copy failed or was cancelled")
            self.log(f"       手动复制: {source} -> {target}")
        else:
            self.log(f"[OK] launcher copied to System32")

    def _step_start_api(self):
        launcher = self._launcher_path()
        if not launcher.exists():
            raise RuntimeError("launcher missing")
        self.log("Starting API server...")
        subprocess.Popen(
            ["cmd", "/c", str(launcher)],
            creationflags=0x00000010,
        )
        self.log("[OK] API server started")