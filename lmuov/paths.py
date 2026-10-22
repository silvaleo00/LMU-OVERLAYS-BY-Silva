"""Onde ficam os ficheiros, tanto a correr com Python como empacotado em .exe (PyInstaller)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "LMU Overlays"
FROZEN = bool(getattr(sys, "frozen", False))


def _writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("ok", "utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


_APP_DIR: Path | None = None


def app_dir() -> Path:
    """Pasta para as definições, data/ e o log.

    No .exe: %APPDATA%\\LMU Overlays (escondida do utilizador, que só mexe na app pelo painel).
    Se havia definições ao lado do .exe (versões antigas), passam para lá na primeira vez.
    A correr com Python: a pasta do projeto.
    """
    global _APP_DIR
    if _APP_DIR is not None:
        return _APP_DIR
    if not FROZEN:
        _APP_DIR = Path(__file__).resolve().parents[1]
        return _APP_DIR
    alt = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    if not _writable(alt):
        alt = Path(sys.executable).resolve().parent
    else:
        _migrate(Path(sys.executable).resolve().parent, alt)
    _APP_DIR = alt
    return alt


def _migrate(old: Path, new: Path) -> None:
    """Move config.json e data/ de ao lado do .exe para a pasta escondida (uma vez)."""
    import shutil
    try:
        if (old / "config.json").exists() and not (new / "config.json").exists():
            shutil.move(str(old / "config.json"), str(new / "config.json"))
        if (old / "data").is_dir() and not (new / "data").exists():
            shutil.move(str(old / "data"), str(new / "data"))
    except OSError:
        pass


def resource(rel: str) -> Path:
    """Ficheiros que vão dentro do pacote (ícone, etc.)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / rel
