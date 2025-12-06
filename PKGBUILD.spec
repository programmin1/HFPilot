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
]

a = Analysis(['PKGBUILD'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, 
          binaries=binaries
          [],
          exclude_binaries=True,
          name='PKGBUILD',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas, 
               strip=False,
               upx=True,
               upx_exclude=[],
               name='PKGBUILD')
