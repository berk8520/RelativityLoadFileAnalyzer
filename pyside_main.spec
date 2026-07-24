import os

system32 = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')
vc_dlls = []
vc_dlls_collect = []

# Collect standard Visual C++ Runtime DLLs
for dll in ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'concrt140.dll']:
    dll_path = os.path.join(system32, dll)
    if os.path.exists(dll_path):
        vc_dlls.append((dll_path, 'PySide6'))
        vc_dlls.append((dll_path, 'shiboken6'))
        vc_dlls_collect.append((dll, dll_path, 'BINARY'))

# Collect Universal C Runtime (UCRT) DLLs for Windows Server 2016 support
ucrt_dir = 'C:\\Program Files (x86)\\Windows Kits\\10\\Redist\\ucrt\\DLLs\\x64'
if os.path.exists(ucrt_dir):
    for f in os.listdir(ucrt_dir):
        if f.lower().endswith('.dll'):
            dll_path = os.path.join(ucrt_dir, f)
            vc_dlls.append((dll_path, '.'))
            vc_dlls.append((dll_path, 'PySide6'))
            vc_dlls.append((dll_path, 'shiboken6'))
            vc_dlls_collect.append((f, dll_path, 'BINARY'))

# Exclude large, unused PySide6 packages
unused_pyside_modules = [
    'PySide6.Qt3D', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DQuick', 'PySide6.Qt3DQuickAnimation',
    'PySide6.Qt3DQuickExtras', 'PySide6.Qt3DQuickInput', 'PySide6.Qt3DQuickLogic',
    'PySide6.Qt3DQuickRender', 'PySide6.Qt3DQuickScene2D', 'PySide6.Qt3DQuickScene3D',
    'PySide6.Qt3DRender', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtGraphs',
    'PySide6.QtLocation', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaQuick', 'PySide6.QtQuick3D',
    'PySide6.QtSensors', 'PySide6.QtVirtualKeyboard', 'PySide6.QtSpatialAudio',
    'PySide6.QtRemoteObjects', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtScxml'
]

a = Analysis(
    ['pyside_main.py'],
    pathex=[],
    binaries=vc_dlls,
    datas=[('assets', 'assets'), ('viewer.html', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=unused_pyside_modules,
    noarchive=False,
    optimize=0,
)

# Filter out large unused Qt6 libraries from the binaries list
filtered_binaries = []
exclude_prefixes = [
    'qt63d', 'qt6charts', 'qt6datavisualization', 'qt6graphs', 
    'qt6location', 'qt6multimedia', 'qt6quick3d', 'qt6sensors', 
    'qt6virtualkeyboard', 'qt6spatialaudio', 'qt6remoteobjects', 
    'qt6sql', 'qt6test', 'qt6scxml'
]
for name, path, type in a.binaries:
    filename = os.path.basename(path).lower()
    if any(filename.startswith(prefix) for prefix in exclude_prefixes):
        continue
    filtered_binaries.append((name, path, type))
a.binaries = filtered_binaries

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pyside_main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app_icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    vc_dlls_collect,  # Place VC++ Redistributable & UCRT DLLs in the root folder next to pyside_main.exe
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pyside_main',
)
