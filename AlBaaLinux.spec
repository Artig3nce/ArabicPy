# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Linux .deb build. Unlike AlBaaIDE.spec, this does
# not bundle AlBaaAIHost.exe -- that binary only exists to auto-start the
# Ollama LAN bridge via the Windows registry Run key; on Linux the same
# bridge (arabicpy/ai_server.py) runs in-process instead.

a = Analysis(
    ['launch_ide.py'],
    pathex=[],
    binaries=[],
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
    name='albaa',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='albaa',
)
