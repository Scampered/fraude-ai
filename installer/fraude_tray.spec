# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Fraude App.
# Build with: pyinstaller fraude_tray.spec
# Produces a single-folder app (faster startup than --onefile) at dist/Fraude/

import sys
from pathlib import Path

block_cipher = None
HERE = Path(__file__).parent.parent  # fraude-ai/ root

a = Analysis(
    [str(HERE / 'fraude_tray.py')],
    pathex=[str(HERE)],
    binaries=[],
    datas=[
        (str(HERE / 'fraude_automations.py'), '.'),
        (str(HERE / 'frauderepo.py'), '.'),
        (str(HERE / 'ollama_proxy.py'), '.'),
        (str(HERE / 'fraudecode.py'), '.'),
        (str(HERE / 'fraudecode_pkg'), 'fraudecode_pkg'),
        (str(HERE / 'installer' / 'icon.ico'), '.'),
    ],
    hiddenimports=[
        'pystray._win32', 'PIL._tkinter_finder',
        'pyautogui', 'pyperclip', 'psutil', 'pynput',
        'pynput.keyboard._win32', 'pynput.mouse._win32',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy.testing'],  # trim size — not needed at runtime
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
    name='Fraude',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # no console window — this is the tray app
    icon=str(HERE / 'installer' / 'icon.ico'),
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fraude',
)
