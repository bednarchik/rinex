To build this python program we use PyInstaller

rinex_verification.spec has already been created.
this file is at the root of Rinex_verification folder

1. open a cmd (containing the python path)

2. switch to the virtualenv for this program
c:\virtenv\rinexx\Scripts\activate

3. cd to root of project
(rinexx) cd c:\virtenv\rinexx\Scripts>cd C:\Users\acochnav\Documents\GitHub\Rinex_verification\

4. run pyinstaller on the spec file.
(rinexx) C:\Users\acochnav\Documents\GitHub\Rinex_verification>pyinstaller rinex_verification.spec

5. a "dist" folder is created with the .exe, this is the binary to distribute.

---------------------rinex_verification.spec--------------------------------------------

# -*- mode: python ; coding: utf-8 -*-

import distutils
if distutils.distutils_path.endswith('__init__.py'):
    distutils.distutils_path = os.path.dirname(distutils.distutils_path)

block_cipher = None


a = Analysis(['source\\rinex_verification.py'],
             pathex=['.'],

             binaries=[],
             datas=[('./source/help.pdf', '.'), ('./source/logo.png', '.')],
             hiddenimports=[],
             hookspath=[],
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
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='rinex_verification',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False )
          
          
-----------------------------------------------------------------