# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# -----------------------------------------------------------------------------
# PYINSTALLER SPEC FILE FOR CROWDVISION
# -----------------------------------------------------------------------------
# Usage: pyinstaller packaging/crowdvision-linux.spec
# Must be run on the target OS (Linux) to produce a Linux executable.
# -----------------------------------------------------------------------------

block_cipher = None

# --- COLLECT HIDDEN IMPORTS AND DATA ---
# Collect Ultralytics (YOLO) which has many dynamic components
ultra_datas, ultra_binaries, ultra_hiddenimports = collect_all('ultralytics')

# Additional hidden imports for libraries that use dynamic loading
hiddenimports = [
    # ASGI / API
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'engineio.async_drivers.aiohttp',
    
    # ML / Scientific
    'scipy.special.cython_special',
    'sklearn.utils._typedefs',
    'sklearn.neighbors._partition_nodes',
    'pandas._libs.tslibs.base',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.timedeltas',
    
    # DB
    'motor.motor_asyncio',
]

hiddenimports += ultra_hiddenimports

# --- DEFINE DATA FILES ---
# Provide tuple (source_path, dest_path_in_bundle)
datas = [
    ('yolov8s.pt', '.'),  # Bundle YOLO model at root of bundle
    ('data/weights/SHA_model.pth', 'data/weights'), # Bundle PET weights
    ('config', 'config'), # Bundle config folder (if needed for templates etc, though we rely on code)
    ('api', 'api'), # Bundle API code explicitly if analysis misses it (unlikely but safe)
    # Add any other static asset dirs here if needed (e.g. schema files)
]

datas += ultra_datas

# --- BINARIES ---
binaries = []
binaries += ultra_binaries

# --- ANALYSIS ---
# Point to the entry point. We assume running strict from project root
# So api/main.py is the path.
a = Analysis(
    ['api/main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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

# --- ONE FILE EXECUTABLE ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='crowdvision',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Compress if UPX is available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # Run with console attached (so logs go to journalctl/stdout)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements=None,
)
