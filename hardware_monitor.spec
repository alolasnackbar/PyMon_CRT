# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect ttkbootstrap themes and data
ttkbootstrap_datas = collect_data_files('ttkbootstrap')

block_cipher = None

# GUI Application Configuration
gui_analysis = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('nohead_test.ico', '.'),
        ('nohead_test.png', '.'),
        ('README.md', '.'),  # For patch notes
    ] + ttkbootstrap_datas,
    hiddenimports=[
        'ttkbootstrap',
        'ttkbootstrap.themes',
        'screeninfo',
        'PIL',
        'PIL._tkinter_finder',
        'psutil',  # Likely used by monitor_core
        'pynvml',  # If you're monitoring NVIDIA GPUs
        'constants', 
        'crt_graphics', 
        'metrics_layout', 
        'startup_loader', 
        'monitor_core', 
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Startup Setup Application Configuration
startup_analysis = Analysis(
    ['startup_set.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('nohead_test.ico', '.'),
        ('nohead_test.png', '.'),
        ('README.md', '.'),
        ('debug_core.py', '.'),
    ] + ttkbootstrap_datas,
    hiddenimports=[
        'ttkbootstrap',
        'ttkbootstrap.themes',
        'screeninfo',
        'PIL',
        'PIL._tkinter_finder',
        'constants', 
        'crt_graphics', 
        'metrics_layout', 
        'startup_loader', 
        'monitor_core',
        'debug_core.py', 
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# GUI PYZ and EXE
gui_pyz = PYZ(gui_analysis.pure, gui_analysis.zipped_data, cipher=block_cipher)

gui_exe = EXE(
    gui_pyz,
    gui_analysis.scripts,
    [],
    exclude_binaries=True,
    name='gui',
    debug=True,  # Enable console for debugging
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='nohead_test.ico',
)

# Startup Setup PYZ and EXE
startup_pyz = PYZ(startup_analysis.pure, startup_analysis.zipped_data, cipher=block_cipher)

startup_exe = EXE(
    startup_pyz,
    startup_analysis.scripts,
    [],
    exclude_binaries=True,
    name='startup_set',
    debug=True,  # Enable console for debugging
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='nohead_test.ico',
)

# Collect everything into one directory
coll = COLLECT(
    gui_exe,
    gui_analysis.binaries,
    gui_analysis.zipfiles,
    gui_analysis.datas,
    startup_exe,
    startup_analysis.binaries,
    startup_analysis.zipfiles,
    startup_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HardwareMonitor',
)