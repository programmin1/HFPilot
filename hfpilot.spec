# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

binaries = [
    ('C:/msys64/mingw64/lib/gio/modules/libgiognomeproxy.dll', 'lib/gio/modules'),
    ('C:/msys64/mingw64/lib/gio/modules/libgiolibproxy.dll', 'lib/gio/modules'),
    ('C:/msys64/mingw64/lib/gio/modules/libgiognutls.dll', 'lib/gio/modules'),
    ('C:/msys64/mingw64/lib/gio/modules/libgioopenssl.dll', 'lib/gio/modules'),
    # These should be picked up by dependency analysis of the above modules, but don't seem to be...
    ('C:/msys64/mingw64/bin/libgnutls-30.dll', '.'),
    ('C:/msys64/mingw64/bin/libintl-8.dll', '.'),
    ('C:/msys64/mingw64/bin/libproxy-1.dll', '.'),
    ('C:/msys64/mingw64/bin/libgio-2.0-0.dll', '.'),
    ('C:/msys64/mingw64/bin/libpython3.12.dll', '.'),
]
hiddenimports = []
datas = [
     ('C:/msys64/mingw64/lib/gio/modules/giomodule.cache', 'lib/gio/modules'),
    # Collect data (for when code is fixed not to assume current working directory)
    ('C:/msys64/mingw64/lib/girepository-1.0/Gio-2.0.typelib', 'lib/girepository-1.0'),
    ('C:/msys64/mingw64/lib/girepository-1.0/GLib-2.0.typelib', 'lib/girepository-1.0'),
    ('C:/msys64/mingw64/lib/girepository-1.0/GObject-2.0.typelib', 'lib/girepository-1.0'),
    ('src/HFLib', 'HFLib'),
    ('src/icon.svg', '.'),
    ('src/TX.svg', '.'),
    ('src/RX.svg', '.'),
    ('src/mapbox.svg', '.'),
    ('src/Main.glade', '.'),
    ('src/README-WINDOWS.TXT', '.'),
    ('src/ca-bundle.crt','.')
]
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',

]

a = Analysis(['src/HFPilot.py'],
             pathex=[],
             binaries=binaries,
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=['./extra-hooks/'],
             hooksconfig={},
             runtime_hooks=[],
             excludes=excludes,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, 
          [],
          exclude_binaries=True,
          binaries=binaries,
          contents_directory=".",
          name='hfpilot',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None , icon='resources/hfpilot.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas, 
               strip=False,
               upx=True,
               upx_exclude=[],
               contents_directory=".",
               name='hfpilot')
