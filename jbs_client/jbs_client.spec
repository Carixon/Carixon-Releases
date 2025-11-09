# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None


def collect_i18n():
    base = Path(__file__).parent / "i18n_files"
    return [(str(path), f"i18n_files/{path.name}") for path in base.glob("*.json")]


a = Analysis(
    ['app.py'],
    pathex=[str(Path(__file__).parent.resolve())],
    binaries=[],
    datas=collect_i18n() + [(str(Path(__file__).parent / "public.pem"), "public.pem")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JBS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JBS',
)
