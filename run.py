"""LMU Overlays: overlays para o Le Mans Ultimate.

    python run.py            ligar ao jogo (memória partilhada LMU_Data)
    python run.py --demo     dados simulados, para testar e posicionar sem o jogo
    python run.py --preview  gera imagens PNG dos overlays em ./previews (não abre janelas)

Empacotado (LMU Overlays.exe) aceita as mesmas opções.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if "__compiled__" in globals():          # compilado para código nativo (Nuitka): conta como .exe
    sys.frozen = True
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from lmuov.paths import FROZEN, app_dir  # noqa: E402

_mutex = None  # mantém o mutex vivo enquanto a app corre


def _already_running() -> bool:
    """Impede abrir a app duas vezes (overlays duplicados)."""
    global _mutex
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        _mutex = k32.CreateMutexW(None, False, "Local\\LMUOverlays.SingleInstance")
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.user32.MessageBoxW(None, "O LMU Overlays já está aberto.\n"
                                             "Procura o ícone na bandeja do Windows (junto ao relógio).",
                                             "LMU Overlays", 0x40)
            return True
    except Exception:
        pass
    return False


def _selftest(out: str) -> int:
    """Confirma que o .exe compilado tem tudo: módulos, overlays, fontes e ícone. Não abre janelas."""
    lines, ok = [], True
    try:
        import importlib
        for m in ("lmuov.qt_app", "lmuov.panel", "lmuov.source_lmu", "lmuov.source_iracing", "lmuov.source_demo",
                  "lmuov.lmu_rest", "lmuov.updater", "lmuov.overlays.damage_designs", "lmuov.overlays.compact",
                  "pyLMUSharedMemory.lmu_data", "PySide6.QtWidgets"):
            importlib.import_module(m)
        from lmuov.overlays import ALL
        from lmuov.paths import resource
        lines.append(f"overlays {len(ALL)}")
        for rel in ("assets/icon.ico", "assets/fonts"):
            if not resource(rel).exists():
                ok = False
                lines.append(f"falta {rel}")
        lines.append(f"frozen {getattr(sys, 'frozen', False)}")
    except Exception as exc:  # pragma: no cover
        import traceback
        ok = False
        lines.append(traceback.format_exc())
    lines.append("SELFTEST OK" if ok else "SELFTEST FALHOU")
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Overlays para o Le Mans Ultimate")
    ap.add_argument("--demo", action="store_true", help="usar dados simulados")
    ap.add_argument("--preview", action="store_true", help="gerar PNGs em ./previews (precisa de Pillow)")
    ap.add_argument("--selftest", metavar="FICHEIRO", help="verifica o .exe (usado na compilação) e sai")
    args = ap.parse_args()
    if args.selftest:
        return _selftest(args.selftest)

    root = app_dir()
    logging.basicConfig(filename=root / "lmu_overlays.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    logging.getLogger("lmuov").info("arranque (exe=%s, pasta=%s)", FROZEN, root)

    if args.preview:
        try:
            from lmuov.preview import main as preview_main
        except ImportError:
            print("--preview precisa do Pillow e não está disponível na versão .exe.")
            return 1
        preview_main(str(root / "previews"))
        return 0

    if _already_running():
        return 0

    try:
        from lmuov.qt_app import main as qt_main
    except ImportError as exc:
        print("Falta o PySide6. Corre:  py -m pip install -r requirements.txt")
        print(f"({exc})")
        return 1
    try:
        return qt_main(root, demo=args.demo)
    except Exception:
        logging.getLogger("lmuov").exception("a app terminou com um erro")
        raise


if __name__ == "__main__":
    sys.exit(main())
