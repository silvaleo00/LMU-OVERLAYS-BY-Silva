from PyInstaller.utils.hooks import collect_submodules
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: gera  dist/LMU Overlays/LMU Overlays.exe  (pasta portátil, sem precisar de Python)
#   py -m PyInstaller --noconfirm --clean lmu_overlays.spec
# Normalmente não precisas de correr isto à mão: usa criar_exe.bat.

from pathlib import Path

ROOT = Path(SPECPATH)
ICON = str(ROOT / "assets" / "icon.ico")

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (ICON, "assets"),
        (str(ROOT / "assets" / "fonts"), "assets/fonts"),   # Barlow Semi Condensed (OFL)
        (str(ROOT / "assets" / "logos"), "assets/logos"),   # logótipos das marcas (os que puseres lá)
        (str(ROOT / "pyLMUSharedMemory" / "License.txt"), "pyLMUSharedMemory"),
    ],
    # todos os módulos da app (alguns só são importados quando são precisos, ex. os designs do dano)
    hiddenimports=collect_submodules("lmuov", filter=lambda n: n != "lmuov.preview") + [
        "pyLMUSharedMemory.lmu_data",
    ],
    excludes=["tkinter", "PIL", "lmuov.preview", "numpy", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LMU Overlays",
    icon=ICON,
    console=False,          # sem janela de consola; erros vão para lmu_overlays.log
    upx=False,              # UPX aumenta os falsos positivos dos antivírus
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LMU Overlays",
)
