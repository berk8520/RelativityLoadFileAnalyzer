import os

system32 = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')
vc_dlls = []
for dll in ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'concrt140.dll']:
    dll_path = os.path.join(system32, dll)
    if os.path.exists(dll_path):
        vc_dlls.append((dll_path, '.'))
        vc_dlls.append((dll_path, 'PySide6'))
        vc_dlls.append((dll_path, 'shiboken6'))

a = Analysis(
    ['pyside_main.py'],
    pathex=[],
    binaries=vc_dlls,
    datas=[('assets', 'assets'), ('viewer.html', '.')],
    hiddenimports=[],
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
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pyside_main',
)
