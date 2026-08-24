# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent.parent
block_cipher = None

a = Analysis(
    [str(PROJECT_ROOT / 'windows' / 'src' / 'app.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / 'packages'), 'packages'),
        (str(PROJECT_ROOT / 'lml-icon.ico'), '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'pyqtgraph',
        'requests',
        'sqlite3',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'sklearn', 'pandas', 'matplotlib', 'scipy', 'tensorflow',
        'torch', 'torchvision', 'keras', 'statsmodels', 'seaborn',
        'plotly', 'bokeh', 'dash', 'flask', 'django',
        'IPython', 'jupyter', 'notebook', 'sphinx', 'pytest',
        'setuptools', 'pip', 'pkg_resources',
        'PIL', 'pillow',
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
    name='LocalMarketLab',
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
    icon=str(PROJECT_ROOT / 'lml-icon.ico'),
)
