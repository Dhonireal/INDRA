# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for VisionPilot Desktop AI Agent.
Builds a production one-folder distribution for Windows (Snapdragon X / x64 Prism).
"""
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

project_root = Path(SPECPATH).resolve().parent.parent

# Collect all app submodules
app_submodules = collect_submodules('app')

# Explicit hidden imports for Win32, WinRT, and AI pipelines
hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'win32com',
    'win32com.client',
    'win32gui',
    'win32con',
    'win32process',
    'win32api',
    'comtypes',
    'comtypes.client',
    'uiautomation',
    'winrt',
    'winrt.windows.foundation',
    'winrt.windows.foundation.collections',
    'winrt.windows.graphics.imaging',
    'winrt.windows.media.ocr',
    'winrt.windows.storage.streams',
    'winrt.windows.globalization',
    'speech_recognition',
    'audioop_lts',
    'cv2',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'pypdf',
    'sqlite3',
] + app_submodules

# Data files to bundle
datas = [
    (str(project_root / 'assets'), 'assets'),
]

a = Analysis(
    [str(project_root / 'app' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'unittest'],
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
    [],
    exclude_binaries=True,
    name='VisionPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed desktop application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'icons' / 'visionpilot.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VisionPilot',
)
