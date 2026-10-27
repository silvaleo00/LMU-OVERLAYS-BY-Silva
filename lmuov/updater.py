"""Atualizações automáticas a partir das Releases do GitHub.

1. Ao arrancar (e de 6 em 6 horas) a app pergunta ao GitHub qual é a última versão publicada.
2. Se for mais nova, o painel mostra o botão "Atualizar para vX".
3. Ao carregar: descarrega o zip da release, extrai-o para uma pasta temporária e cria um
   pequeno script que espera a app fechar, copia os ficheiros novos por cima (sem tocar no
   config.json, na pasta data nem no log) e volta a abrir a app.

Tudo corre numa thread à parte; o painel só lê o estado. Sem bibliotecas extra.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .version import UPDATE_REPO, VERSION

log = logging.getLogger("lmuov")
API = "https://api.github.com/repos/{repo}/releases/latest"
ASSET_SUFFIX = "_Windows.zip"
EXE_NAME = "LMU Overlays.exe"
KEEP = ("config.json", "lmu_overlays.log")        # ficheiros do utilizador que nunca se substituem
KEEP_DIRS = ("data",)
CHECK_EVERY = 6 * 3600


def parse_version(v: str) -> tuple:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(remote: str, local: str = VERSION) -> bool:
    a, b = parse_version(remote), parse_version(local)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def parse_release(data: dict) -> dict | None:
    """Do JSON da API do GitHub: versão, notas, página e o zip para Windows."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    asset = next((a for a in data.get("assets") or [] if str(a.get("name", "")).endswith(ASSET_SUFFIX)), None)
    if not tag or asset is None:
        return None
    return {"version": tag.lstrip("vV"), "notes": str(data.get("body") or "")[:2000],
            "url": asset.get("browser_download_url", ""), "size": int(asset.get("size") or 0),
            "page": str(data.get("html_url") or "")}


def find_app_root(folder: Path) -> Path | None:
    """Pasta (dentro do zip extraído) que tem o .exe."""
    for p in [folder, *sorted(folder.rglob("*"))]:
        if p.is_dir() and (p / EXE_NAME).exists():
            return p
    return None


def updater_env(src: Path, dest: Path, pid: int, exe: Path) -> dict:
    """As pastas vão para o script por variáveis de ambiente: assim nomes com acentos (ex.
    "Área de Trabalho", "João") passam intactos. Escritas dentro do .bat, o cmd estragava-as."""
    return {"LMU_SRC": str(src), "LMU_DEST": str(dest), "LMU_PID": str(pid), "LMU_EXE": str(exe),
            "LMU_WORK": str(src.parent)}


def updater_script(src: Path, dest: Path, pid: int, exe: Path) -> str:
    """Script .bat (só ASCII) que espera a app fechar, copia a versão nova e volta a abrir a app.
    Os caminhos vêm das variáveis de updater_env()."""
    xf = " ".join(f'"{n}"' for n in KEEP)
    xd = " ".join(f'"{n}"' for n in KEEP_DIRS)
    return "\r\n".join([
        "@echo off",
        "title LMU Overlays - a atualizar",
        "echo A atualizar o LMU Overlays... nao feches esta janela.",
        ":espera",
        'tasklist /FI "PID eq %LMU_PID%" 2>nul | find "%LMU_PID%" >nul',
        "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto espera)",
        f'robocopy "%LMU_SRC%" "%LMU_DEST%" /E /R:5 /W:1 /NFL /NDL /NJH /NJS /XF {xf} /XD {xd}',
        "if errorlevel 8 (echo A copia falhou. & pause & exit /b 1)",
        'start "" "%LMU_EXE%"',
        'rmdir /s /q "%LMU_WORK%" >nul 2>nul',
        '(goto) 2>nul & del "%~f0"',
        "",
    ])


class Updater:
    """Estado da atualização (lido pelo painel a cada segundo)."""

    def __init__(self, repo: str = UPDATE_REPO, install_dir: Path | None = None) -> None:
        self.repo = (repo or "").strip().strip("/")
        self.install_dir = install_dir or Path(sys.executable).resolve().parent
        self.state = "off" if not self.repo else "idle"   # off, idle, checking, latest, available, downloading, ready, error
        self.release: dict | None = None
        self.progress = 0.0
        self.error = ""
        self.script: Path | None = None
        self._next_check = 0.0
        self._busy = False
        self._opener = urllib.request.build_opener()
        self.frozen = bool(getattr(sys, "frozen", False))

    # ------------------------------------------------------------------ #
    def _get(self, url: str, timeout: float = 8.0):
        req = urllib.request.Request(url, headers={"User-Agent": f"LMU-Overlays/{VERSION}",
                                                   "Accept": "application/vnd.github+json"})
        return self._opener.open(req, timeout=timeout)

    def _run(self, fn) -> None:
        if self._busy:
            return
        self._busy = True

        def wrap():
            try:
                fn()
            except Exception as exc:
                self.state, self.error = "error", str(exc)[:200]
                log.warning("atualização: %s", exc)
            finally:
                self._busy = False
        threading.Thread(target=wrap, name="lmu-update", daemon=True).start()

    def poll(self, now: float) -> None:
        """Chamado pela app: verifica de vez em quando (ao arrancar e de 6 em 6 horas)."""
        if self.state in ("off", "downloading", "ready") or now < self._next_check:
            return
        self._next_check = now + CHECK_EVERY
        self.check()

    def check(self) -> None:
        if self.state == "off":
            return

        def go():
            self.state = "checking"
            with self._get(API.format(repo=self.repo)) as r:
                rel = parse_release(json.loads(r.read().decode("utf-8")))
            self.release = rel
            self.state = "available" if rel and is_newer(rel["version"]) else "latest"
        self._run(go)

    def download(self) -> None:
        """Descarrega e prepara a atualização. No fim, state = "ready" (falta só fechar e trocar)."""
        if self.state != "available" or not self.release:
            return

        def go():
            self.state, self.progress = "downloading", 0.0
            work = Path(tempfile.mkdtemp(prefix="lmu_update_"))
            zpath = work / "update.zip"
            with self._get(self.release["url"], timeout=30) as r, open(zpath, "wb") as f:
                total = int(r.headers.get("Content-Length") or self.release.get("size") or 0)
                done = 0
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.progress = min(0.99, done / total)
            self.script = self.prepare(zpath, work)
            self.progress, self.state = 1.0, "ready"
        self._run(go)

    def prepare(self, zpath: Path, work: Path) -> Path:
        """Extrai o zip, confirma que tem a app e escreve o script de troca. Devolve o script."""
        out = work / "novo"
        with zipfile.ZipFile(zpath) as z:
            for m in z.namelist():                         # não deixa sair da pasta (zip malformado)
                if m.startswith(("/", "\\")) or ".." in Path(m).parts:
                    raise ValueError("zip inválido")
            z.extractall(out)
        root = find_app_root(out)
        if root is None:
            raise ValueError(f"o zip não tem {EXE_NAME}")
        script = work / "atualizar.bat"
        exe = self.install_dir / EXE_NAME
        script.write_text(updater_script(root, self.install_dir, os.getpid(), exe), encoding="ascii")
        self.env = updater_env(root, self.install_dir, os.getpid(), exe)
        return script

    def apply(self) -> bool:
        """Lança o script (que espera a app fechar). A app deve sair logo a seguir."""
        if self.state != "ready" or not self.script or sys.platform != "win32":
            return False
        import subprocess
        env = {**os.environ, **(getattr(self, "env", None) or {})}
        subprocess.Popen(["cmd", "/c", str(self.script)], creationflags=0x00000010,   # CREATE_NEW_CONSOLE
                         close_fds=True, cwd=str(self.script.parent), env=env)
        return True

    @staticmethod
    def cleanup_old(now: float | None = None) -> None:
        """Apaga pastas temporárias de atualizações antigas que tenham ficado para trás."""
        now = now or time.time()
        for p in Path(tempfile.gettempdir()).glob("lmu_update_*"):
            try:
                if now - p.stat().st_mtime > 86400:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass
