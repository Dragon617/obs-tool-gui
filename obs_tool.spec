# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# Get paths
src_dir = Path(SPECPATH)
logo_png = str(src_dir / 'logo.png')
logo_ico = str(src_dir / 'logo.ico')

# Collect Pillow for icon display
import PIL
pil_path = Path(PIL.__file__).parent

a = Analysis(
    ['obs_tool_gui.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        (logo_png, '.'),
        (logo_ico, '.'),
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'wmi',
        'pythoncom',
        'win32com',
        'win32com.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'ttkbootstrap',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='影视匠OBS管理工具箱',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=logo_ico,
)
