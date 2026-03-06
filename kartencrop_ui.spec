from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH).resolve()

datas = [(str(project_root / "map_ui.py"), ".")]
binaries = []
hiddenimports = ["tkinter", "tkinter.filedialog", "PIL._tkinter_finder"]

datas += collect_data_files("kartencrop", include_py_files=False)
hiddenimports += collect_submodules("kartencrop")


def add_directory_tree(source: Path, target_root: str) -> None:
    if not source.exists():
        return
    for file_path in source.rglob("*"):
        if file_path.is_file():
            relative_parent = file_path.relative_to(source).parent
            target_dir = Path(target_root) / relative_parent
            datas.append((str(file_path), str(target_dir)))


python_tcl_root = Path(sys.base_prefix) / "tcl"
add_directory_tree(python_tcl_root / "tcl8.6", "_tcl_data")
add_directory_tree(python_tcl_root / "tk8.6", "_tk_data")

for package_name in (
    "streamlit",
    "streamlit_folium",
    "folium",
    "branca",
    "xyzservices",
    "altair",
    "pydeck",
):
    collected_datas, collected_binaries, collected_hiddenimports = collect_all(package_name)
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hiddenimports

for distribution_name in (
    "streamlit",
    "streamlit-folium",
    "folium",
    "branca",
    "xyzservices",
    "altair",
    "pydeck",
):
    datas += copy_metadata(distribution_name)


a = Analysis(
    [str(project_root / "kartencrop" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KartencropUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KartencropUI",
)
