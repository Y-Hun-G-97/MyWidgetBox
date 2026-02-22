# -*- mode: python ; coding: utf-8 -*-

hiddenimports = [
    'pythoncom',
    'pywintypes',
    'win32com',
    'win32com.client',
    'PyQt6.QtMultimediaWidgets',
]

binaries = [
    ('C:\\\\ffmpeg\\\\bin\\\\ffmpeg.exe', '.'),
    ('C:\\\\ffmpeg\\\\bin\\\\ffprobe.exe', '.'),
]

datas = []


a = Analysis(
    ['MyCanvas.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='MyCanvas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['MyCanvas.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MyCanvas',
)
