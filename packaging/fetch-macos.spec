from pathlib import Path
import os
import platform
from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path(SPECPATH).parent
datas, binaries, hiddenimports = collect_all('yt_dlp')
hiddenimports += ['keyring.backends.macOS']
datas += collect_data_files('yt_dlp_ejs')
datas += [(str(root / 'assets'), 'assets')]
binaries += [(str(root / 'build/macos/deno'), 'runtime')]
a = Analysis([str(root / 'instagram_downloader_ui.py')], pathex=[str(root)],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    excludes=['tkinter'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Fetch',
    console=False, debug=False, strip=False, upx=False,
    target_arch=platform.machine(), codesign_identity=os.environ.get('MAC_SIGN_IDENTITY'),
    entitlements_file=str(root / 'packaging/macos-entitlements.plist'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Fetch')
app = BUNDLE(coll, name='Fetch.app', icon=str(root / 'build/macos/Fetch.icns'),
    bundle_identifier='com.kallos.fetch',
    info_plist={
        'CFBundleShortVersionString': os.environ['FETCH_VERSION'],
        'CFBundleVersion': os.environ['FETCH_VERSION'],
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'KALLOS',
        'NSDownloadsFolderUsageDescription': 'Fetch saves downloaded media to your selected download folder.',
        'LSApplicationCategoryType': 'public.app-category.utilities',
    })
