# -*- mode: python ; coding: utf-8 -*-

import glob
import os


engine_binaries = [
    (path, 'ai-engine')
    for path in glob.glob('vendor/llama.cpp/*')
    if os.path.isfile(path)
]

a = Analysis(
    ['launch_ai_server.py'], pathex=[], binaries=engine_binaries, datas=[], hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='AlBaaAIHost',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, icon='assets/albaa.ico',
)
