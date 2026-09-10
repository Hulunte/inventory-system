# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for inventory-system
#
# Build: pyinstaller build.spec

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

pyserial_hiddenimports = collect_submodules('serial')
pyserial_hiddenimports += collect_submodules('serial.tools')
pyserial_hiddenimports += collect_submodules('serial.tools.list_ports')

a = Analysis(
    ['production.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/templates', 'app/templates'),
        ('app/static', 'app/static'),
        ('migrations', 'migrations'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'psycopg',
        'psycopg.rows',
        'waitress',
        'openpyxl',
        'zoneinfo',
        'email.mime.text',
        'email.mime.multipart',
        'email.mime.base',
        'email.encoders',
        'email.utils',
        # migrations/env.py is loaded dynamically by Alembic, so PyInstaller
        # cannot discover this standard-library submodule automatically.
        'logging.config',
    ] + pyserial_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'distutils',
        'setuptools',
        'pip',
        'pkg_resources',
        'numpy',
        'pandas',
        'matplotlib',
        'scipy',
        'PIL',
        'cv2',
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
    name='inventory-system',
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
    version='version_info.txt',
)
