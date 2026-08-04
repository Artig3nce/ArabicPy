# -*- mode: python ; coding: utf-8 -*-

import glob
import os


engine_binaries = [
    (path, 'ai-engine')
    for path in glob.glob('vendor/llama.cpp/*')
    if os.path.isfile(path)
]
app_binaries = [('dist/AlBaaAIHost.exe', '.')] + engine_binaries


a = Analysis(
    ['launch_ide.py'],
    pathex=[],
    binaries=app_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AlBaa',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/albaa.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AlBaa',
)
