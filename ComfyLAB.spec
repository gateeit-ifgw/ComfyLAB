# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Define files to collect
added_files = [
    ('frontend/dist', 'frontend/dist'),
    ('backend/adjectives.txt', 'backend'),
    ('backend/nouns.txt', 'backend'),
]

for src_path, dst_path in [
    ('comfylab/examples', 'comfylab/examples'),
    ('comfylab/clusters', 'comfylab/clusters'),
]:
    if os.path.exists(src_path):
        added_files.append((src_path, dst_path))

if os.path.exists('VERSION'):
    added_files.append(('VERSION', '.'))

# Collect data files for packages that require them at runtime
for pkg in ['pyvisa_py', 'scipy', 'pandas', 'pyarrow', 'fastparquet', 'PIL', 'cv2']:
    try:
        added_files += collect_data_files(pkg)
    except Exception:
        pass

hidden_imports = [
    'pyvisa',
    'pyvisa_py',
    'usb',
    'usb.core',
    'usb.backend',
    'usb.backend.libusb1',
    'usb.backend.libusb0',
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
    'gpib_ctypes',
    'zeroconf',
    'psutil',
    'uvicorn',
    'fastapi',
    'websockets',
    'httpx',
    'cryptography',
    'multipart',
    'python_multipart',
    'numpy',
    'pydantic',
    'scipy',
    'scipy.optimize',
    'scipy.signal',
    'scipy.fft',
    'scipy.interpolate',
    'scipy.stats',
    'pandas',
    'pyarrow',
    'fastparquet',
    'PIL',
    'PIL.Image',
    'cv2',
    'backend.auth',
    'backend.main',
    'backend.manager',
    'backend.ratelimit',
    'backend.workspace',
    'backend.routers.execution',
    'backend.routers.settings',
    'backend.routers.diagnostics',
    'backend.routers.workspace',
    'backend.routers.packages',
    'backend.routers.updates',
    'backend.routers.store',
    'comfylab.engine.config',
    'comfylab.engine.executor',
    'comfylab.engine.lock_manager',
    'comfylab.engine.locks',
    'comfylab.engine.logging',
    'comfylab.engine.models',
    'comfylab.engine.registry',
    'comfylab.engine.security',
    'comfylab.blocks.base',
    'comfylab.blocks.base_script',
    'comfylab.blocks.loader',
    'comfylab.blocks.cluster'
]

# Ensure all submodules for key data science/hardware packages are collected
for pkg in ['scipy', 'pandas', 'pyvisa_py', 'usb', 'serial', 'gpib_ctypes', 'zeroconf', 'psutil', 'uvicorn', 'PIL', 'pyarrow', 'fastparquet', 'cv2']:
    try:
        hidden_imports += collect_submodules(pkg)
    except Exception:
        pass

a = Analysis(
    ['pyinstaller_entry.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=list(set(hidden_imports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Device driver and block modules are shipped as external source next to the binary
        # (copied by build_exe.py) so they remain extensible at runtime.
        'comfylab.devices',
        'comfylab.blocks.basic_math',
        'comfylab.blocks.cluster_boundary',
        'comfylab.blocks.constants',
        'comfylab.blocks.control_flow',
        'comfylab.blocks.dictionary',
        'comfylab.blocks.examples',
        'comfylab.blocks.external_library',
        'comfylab.blocks.io',
        'comfylab.blocks.lists',
        'comfylab.blocks.logic',
        'comfylab.blocks.math_fit',
        'comfylab.blocks.math_functions',
        'comfylab.blocks.ndarrays',
        'comfylab.blocks.outputs_basic',
        'comfylab.blocks.plots',
        'comfylab.blocks.publisher',
        'comfylab.blocks.script',
        'comfylab.blocks.script_external_python',
        'comfylab.blocks.script_js',
        'comfylab.blocks.script_julia',
        'comfylab.blocks.script_lua',
        'comfylab.blocks.script_octave',
        'comfylab.blocks.script_r',
        'comfylab.blocks.script_rust',
        'comfylab.blocks.script_wolfram',
        'comfylab.blocks.signal',
        'comfylab.blocks.strings',
        'comfylab.blocks.timing',
        'comfylab.blocks.utility',
        'comfylab.blocks.visa',
        'comfylab.blocks.devices',
        'tests',
        'frontend/node_modules',
        # Exclude unused GUI frameworks, deep learning, and optional heavy libraries
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'jax',
        'jaxlib',
        'cupy',
        'numba',
        'cython',
        'IPython',
        'ipykernel',
        'notebook',
        'jupyter',
        'matplotlib',
        'seaborn',
        'bokeh',
        'PyQt6',
        'PyQt5',
        'PySide6',
        'PySide2',
        'wx',
        'tkinter',
        'tcl',
        'curses',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ComfyLAB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
