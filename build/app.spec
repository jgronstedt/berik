# PyInstaller spec for Berik — build on a Windows runner (cannot cross-build from macOS).
#   pyinstaller build/app.spec --noconfirm
# Produces dist/Berik/ (onedir) — zip and ship the folder. onedir is chosen over onefile
# so there is no per-launch temp extraction (faster start, fewer Defender/SmartScreen flags).
import pathlib
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = pathlib.Path(SPECPATH).parent          # project root (build/ is one level down)

# ifcopenshell ships a SWIG wrapper (.pyd) + EXPRESS schema data that PyInstaller misses.
ic_datas, ic_bin, ic_hidden = collect_all("ifcopenshell")
it_datas, it_bin, it_hidden = collect_all("ifctester")     # IDS gate (optional feature)

# pywebview's Windows backend loads the UI through WinForms via pythonnet, whose
# native .NET loader (Python.Runtime.dll + clr_loader's shim DLLs) PyInstaller's
# import analysis does not reliably collect. Pull them in fully so the .NET loader
# path is deterministic on every machine, not just the build runner.
pn_datas, pn_bin, pn_hidden = collect_all("pythonnet")
cl_datas, cl_bin, cl_hidden = collect_all("clr_loader")

datas = ic_datas + it_datas + pn_datas + cl_datas + collect_data_files("lark") + [
    (str(ROOT / "berik" / "ui"), "berik/ui"),               # the HTML/CSS/JS + logo assets
]
binaries = ic_bin + it_bin + pn_bin + cl_bin
hiddenimports = ic_hidden + it_hidden + pn_hidden + cl_hidden + [
    "ifcopenshell_wrapper", "lark",
    "openpyxl", "openpyxl.cell._writer",
    "clr", "clr_loader", "pythonnet",
]

block_cipher = None

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide6", "pytest"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Berik",
    debug=False,
    strip=False,
    upx=False,                       # UPX trips antivirus heuristics — leave off
    console=False,                   # GUI app, no console window
    icon=str(ROOT / "build" / "berik.ico") if (ROOT / "build" / "berik.ico").exists() else None,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, name="Berik",
)
