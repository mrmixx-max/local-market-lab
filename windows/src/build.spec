# -*- mode: python ; coding: utf-8 -*-
"""
Local Market Lab — PyInstaller Build Spec (Optimized for <30MB EXE)

Strategy:
  1. Exclude all unused Qt6 DLLs (Quick, QML, Multimedia, Pdf, etc.)
  2. Exclude opengl32sw.dll (20MB software renderer)
  3. Exclude ffmpeg DLLs (avcodec, avformat, avutil = 37MB)
  4. Exclude numpy distutils, tests, doc, f2py (not needed at runtime)
  5. Exclude all unused Python packages (web frameworks, imaging, etc.)
  6. Enable UPX compression when available
  7. Bundle certifi CA certificates properly
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent.parent
block_cipher = None

# -------------------------------------------------------------------
# Qt6 DLLs to EXCLUDE — only keep Core, Gui, Widgets
# -------------------------------------------------------------------
QT6_EXCLUDE_DLLS = [
    # Quick / QML (not used — we use QtWidgets only)
    'Qt6Quick.dll', 'Qt6Qml.dll', 'Qt6QmlModels.dll', 'Qt6QmlMeta.dll',
    'Qt6QmlWorkerScript.dll', 'Qt6Quick3D.dll', 'Qt6Quick3DAssetImport.dll',
    'Qt6Quick3DAssetUtils.dll', 'Qt6Quick3DEffects.dll', 'Qt6Quick3DGlslParser.dll',
    'Qt6Quick3DHelpers.dll', 'Qt6Quick3DHelpersImpl.dll', 'Qt6Quick3DIblBaker.dll',
    'Qt6Quick3DParticles.dll', 'Qt6Quick3DPhysics.dll', 'Qt6Quick3DPhysicsHelpers.dll',
    'Qt6Quick3DRuntimeRender.dll', 'Qt6Quick3DSpatialAudio.dll', 'Qt6Quick3DUtils.dll',
    'Qt6Quick3DXr.dll', 'Qt6QuickControls2.dll', 'Qt6QuickControls2Basic.dll',
    'Qt6QuickControls2BasicStyleImpl.dll', 'Qt6QuickControls2Fusion.dll',
    'Qt6QuickControls2FusionStyleImpl.dll', 'Qt6QuickControls2Imagine.dll',
    'Qt6QuickControls2ImagineStyleImpl.dll', 'Qt6QuickControls2Impl.dll',
    'Qt6QuickControls2Material.dll', 'Qt6QuickControls2MaterialStyleImpl.dll',
    'Qt6QuickControls2Universal.dll', 'Qt6QuickControls2UniversalStyleImpl.dll',
    'Qt6QuickDialogs2.dll', 'Qt6QuickDialogs2QuickImpl.dll', 'Qt6QuickDialogs2Utils.dll',
    'Qt6QuickEffects.dll', 'Qt6QuickLayouts.dll', 'Qt6QuickParticles.dll',
    'Qt6QuickShapes.dll', 'Qt6QuickTemplates2.dll', 'Qt6QuickTest.dll',
    'Qt6QuickTimeline.dll', 'Qt6QuickTimelineBlendTrees.dll', 'Qt6QuickVectorImage.dll',
    'Qt6QuickVectorImageGenerator.dll', 'Qt6QuickWidgets.dll',
    # Multimedia (not used)
    'Qt6Multimedia.dll', 'Qt6MultimediaQuick.dll', 'Qt6MultimediaWidgets.dll',
    # PDF (not used)
    'Qt6Pdf.dll', 'Qt6PdfQuick.dll', 'Qt6PdfWidgets.dll',
    # Bluetooth, NFC, Sensors, etc. (not used)
    'Qt6Bluetooth.dll', 'Qt6Nfc.dll', 'Qt6Sensors.dll', 'Qt6SensorsQuick.dll',
    'Qt6Positioning.dll', 'Qt6PositioningQuick.dll',
    # Other unused Qt modules
    'Qt6Designer.dll', 'Qt6Help.dll', 'Qt6DBus.dll',
    'Qt6LabsAnimation.dll', 'Qt6LabsFolderListModel.dll', 'Qt6LabsPlatform.dll',
    'Qt6LabsQmlModels.dll', 'Qt6LabsSettings.dll', 'Qt6LabsSharedImage.dll',
    'Qt6LabsWavefrontMesh.dll',
    'Qt6Network.dll', 'Qt6OpenGL.dll', 'Qt6OpenGLWidgets.dll',
    'Qt6PrintSupport.dll', 'Qt6RemoteObjects.dll', 'Qt6RemoteObjectsQml.dll',
    'Qt6SerialPort.dll', 'Qt6ShaderTools.dll', 'Qt6SpatialAudio.dll',
    'Qt6Sql.dll', 'Qt6StateMachine.dll', 'Qt6StateMachineQml.dll',
    'Qt6Svg.dll', 'Qt6SvgWidgets.dll', 'Qt6Test.dll',
    'Qt6TextToSpeech.dll', 'Qt6WebChannel.dll', 'Qt6WebChannelQuick.dll',
    'Qt6WebSockets.dll', 'Qt6Concurrent.dll', 'Qt6Xml.dll',
    # OpenGL software renderer (20MB — not needed, GPU handles this)
    'opengl32sw.dll',
    # FFmpeg codecs (37MB — not needed for a non-media app)
    'avcodec-61.dll', 'avformat-61.dll', 'avutil-59.dll',
    'avcodec-60.dll', 'avformat-60.dll', 'avutil-58.dll',
    'avcodec-62.dll', 'avformat-62.dll', 'avutil-60.dll',
    'swresample-5.dll', 'swresample-4.dll', 'swresample-6.dll',
    'swscale-8.dll', 'swscale-7.dll', 'swscale-9.dll',
    'swscale-6.dll', 'swscale-5.dll',
]

# -------------------------------------------------------------------
# Qt6 plugins to EXCLUDE
# -------------------------------------------------------------------
QT6_EXCLUDE_PLUGINS = [
    # Image formats we don't need
    'imageformats/qgif.dll', 'imageformats/qicns.dll', 'imageformats/qjp2.dll',
    'imageformats/qmng.dll', 'imageformats/qtga.dll', 'imageformats/qtiff.dll',
    'imageformats/qwbmp.dll', 'imageformats/qwebp.dll',
    # Styles we don't need
    'styles/qmodernstyle.dll',
    # Platforms we don't need
    'platforms/qminimal.dll', 'platforms/qoffscreen.dll',
]

# -------------------------------------------------------------------
# Python modules to EXCLUDE — comprehensive list for minimal EXE
# -------------------------------------------------------------------
EXCLUDE_MODULES = [
    # Heavy scientific (not used)
    'sklearn', 'pandas', 'matplotlib', 'scipy', 'tensorflow',
    'torch', 'torchvision', 'keras', 'statsmodels', 'seaborn',
    'plotly', 'bokeh', 'dash',
    # Numpy submodules not needed at runtime
    'numpy.distutils', 'numpy.distutils.cpuinfo', 'numpy.distutils.misc_util',
    'numpy.distutils.system_info', 'numpy.distutils.log',
    'numpy.tests', 'numpy.testing', 'numpy.doc',
    'numpy.f2py', 'numpy.py', 'numpy.version',
    'numpy.core.tests', 'numpy.core._dotblas',
    'numpy.lib.tests', 'numpy.linalg.tests',
    'numpy.fft.tests', 'numpy.random.tests',
    'numpy.ma.tests', 'numpy.matrixlib.tests',
    'numpy.compat', 'numpy.core.include', 'numpy.core.lib',
    # Web frameworks (not used in GUI)
    'flask', 'django', 'aiohttp', 'tornado',
    'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous', 'click',
    # API server (not bundled in GUI EXE)
    'fastapi', 'uvicorn', 'pydantic', 'starlette', 'anyio',
    'httptools', 'uvloop', 'yaml', 'yfinance',
    'h11', 'httptools', 'watchfiles', 'python_multipart',
    # Dev tools
    'IPython', 'jupyter', 'notebook', 'sphinx', 'pytest',
    'setuptools', 'pip', 'pkg_resources', 'pip._internal',
    'pyflakes', 'pycodestyle', 'mccabe', 'rope',
    # Imaging (not used)
    'PIL', 'pillow', 'PIL._imaging',
    # Crypto (not used)
    'cryptography', 'Crypto', 'Cryptodome',
    # Other unused stdlib
    'tkinter', 'turtle', 'idlelib', 'ensurepip',
    '_pydecimal', 'pydoc', 'doctest', 'unittest',
    'lib2to3', 'test', 'tests',
    'xmlrpc', 'mailbox', 'mhlib', 'mimetools', 'MimeWriter',
    'mimify', 'multifile', 'netrc', 'nturl2path',
    'plistlib', 'pstats', 'pty', 'sched', 'smtpd',
    'smtplib', 'sndhdr', 'sunau', 'sunaudiodev',
    'telnetlib', 'this', 'timeit', 'toai',
    'trace', 'traceback', 'tty', 'urllib.robotparser',
    'wave', 'webbrowser', 'xdrlib', 'zipfile',  # zipfile is stdlib but often not needed
    # Qt modules we don't use
    'PyQt6.QtBluetooth', 'PyQt6.QtDesigner', 'PyQt6.QtHelp',
    'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtNetwork',
    'PyQt6.QtNfc', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtPdf', 'PyQt6.QtPdfQuick', 'PyQt6.QtPdfWidgets',
    'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport', 'PyQt6.QtQml',
    'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickControls2',
    'PyQt6.QtQuickDialogs2', 'PyQt6.QtQuickDialogs2Utils',
    'PyQt6.QtQuickLayouts', 'PyQt6.QtQuickParticles',
    'PyQt6.QtQuickShapes', 'PyQt6.QtQuickTemplates2',
    'PyQt6.QtQuickTest', 'PyQt6.QtQuickTimeline',
    'PyQt6.QtQuickWidgets', 'PyQt6.QtRemoteObjects',
    'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtSpatialAudio',
    'PyQt6.QtSql', 'PyQt6.QtStateMachine', 'PyQt6.QtSvg',
    'PyQt6.QtSvgWidgets', 'PyQt6.QtTest', 'PyQt6.QtTextToSpeech',
    'PyQt6.QtWebChannel', 'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebSockets', 'PyQt6.QtXml',
    'PyQt6.Qt3DAnimation', 'PyQt6.Qt3DCore', 'PyQt6.Qt3DExtras',
    'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic', 'PyQt6.Qt3DQuick',
    'PyQt6.Qt3DQuickAnimation', 'PyQt6.Qt3DQuickExtras',
    'PyQt6.Qt3DQuickInput', 'PyQt6.Qt3DQuickRender',
    'PyQt6.Qt3DQuickScene2D', 'PyQt6.Qt3DRender',
    'PyQt6.QtCharts', 'PyQt6.QtDataVisualization',
    'PyQt6.QtHttpServer', 'PyQt6.QtLabsAnimation',
    'PyQt6.QtLabsFolderListModel', 'PyQt6.QtLabsPlatform',
    'PyQt6.QtLabsQmlModels', 'PyQt6.QtLabsSettings',
    'PyQt6.QtLabsSharedImage', 'PyQt6.QtLabsWavefrontMesh',
    'PyQt6.QtMultimediaQuick', 'PyQt6.QtShaderTools',
    'PyQt6.sip',  # sip module — not needed when using compiled PyQt6
]

# -------------------------------------------------------------------
# Binary filter: exclude specific DLLs
# -------------------------------------------------------------------
def filter_binaries(binaries):
    """Remove unwanted Qt6 DLLs from the binary list."""
    filtered = []
    for dest, src, typecode in binaries:
        basename = os.path.basename(dest)
        if basename in QT6_EXCLUDE_DLLS:
            continue
        # Check plugin excludes
        skip = False
        dest_normalized = dest.replace('\\', '/')
        for plugin in QT6_EXCLUDE_PLUGINS:
            if plugin in dest_normalized:
                skip = True
                break
        if not skip:
            filtered.append((dest, src, typecode))
    return filtered

# -------------------------------------------------------------------
# Collect certifi CA bundle
# -------------------------------------------------------------------
def collect_certifi():
    """Collect certifi CA bundle as data files."""
    try:
        import certifi
        cert_path = certifi.where()
        if os.path.exists(cert_path):
            return [(cert_path, 'certifi')]
    except ImportError:
        pass
    return []

# -------------------------------------------------------------------
# Analysis
# -------------------------------------------------------------------
a = Analysis(
    [str(PROJECT_ROOT / 'windows' / 'src' / 'app.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / 'packages'), 'packages'),
    ] + collect_certifi(),
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.graphicsItems.PlotItem',
        'pyqtgraph.graphicsItems.ViewBox',
        'pyqtgraph.graphicsItems.PlotCurveItem',
        'pyqtgraph.graphicsItems.ScatterPlotItem',
        'pyqtgraph.graphicsItems.BarGraphItem',
        'pyqtgraph.graphicsItems.LegendItem',
        'pyqtgraph.graphicsItems.AxisItem',
        'pyqtgraph.graphicsItems.GridItem',
        'pyqtgraph.graphicsItems.InfiniteLine',
        'pyqtgraph.graphicsItems.LinearRegionItem',
        'pyqtgraph.exporters',
        'pyqtgraph.exporters.ImageExporter',
        'pyqtgraph.exporters.SVGExporter',
        'pyqtgraph.Qt',
        'pyqtgraph.Qt.QtWidgets',
        'pyqtgraph.Qt.QtCore',
        'pyqtgraph.Qt.QtGui',
        'pyqtgraph.functions',
        'pyqtgraph.widgets',
        'requests',
        'certifi',
        'sqlite3',
        'numpy',
        'numpy.core',
        'numpy.core._methods',
        'numpy.lib.format',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDE_MODULES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out unwanted binaries
a.binaries = filter_binaries(a.binaries)

# Remove duplicate datas
seen_datas = set()
unique_datas = []
for item in a.datas:
    src = item[0]
    if src not in seen_datas:
        seen_datas.add(src)
        unique_datas.append(item)
a.datas = unique_datas

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# -------------------------------------------------------------------
# One-file EXE (optimized)
# -------------------------------------------------------------------
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
    strip=True,
    upx=True,
    upx_exclude=[
        # MSVC runtime DLLs — UPX breaks these
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'msvcp140_1.dll',
        'msvcp140_2.dll',
        'msvcp140_atomic_wait.dll',
        'msvcp140_codecvt_ids.dll',
        'concrt140.dll',
        'vccorlib140.dll',
        # Python DLLs
        'python3.dll',
        'python311.dll',
        # Qt6 DLLs that may have issues with UPX
        'Qt6Core.dll',
        'Qt6Gui.dll',
        'Qt6Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'lml-icon.ico'),
    manifest=str(PROJECT_ROOT / 'windows' / 'src' / 'app.manifest'),
    version=str(PROJECT_ROOT / 'windows' / 'src' / 'version_info.txt'),
)
