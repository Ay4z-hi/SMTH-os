# PyInstaller configuration for the SMTH Windows launcher.
# The OFL fonts are loaded at runtime with AddFontResourceExW (process-local),
# so they must travel with the executable.
a = Analysis(
    ['smth_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SMTH-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='assets/smth-black.ico',
)
