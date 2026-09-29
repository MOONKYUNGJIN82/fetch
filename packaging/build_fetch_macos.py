"""Build and exercise a native Mac app. Run on matching-architecture macOS only."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_config import APP_VERSION

def run(*args, **kwargs):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True, **kwargs)

def build():
    if sys.platform != 'darwin':
        raise SystemExit('Mac packages must be built and tested on macOS.')
    arch = platform.machine()
    if arch not in ('arm64', 'x86_64'):
        raise SystemExit(f'Unsupported architecture: {arch}')
    os.environ['FETCH_VERSION'] = APP_VERSION
    work = ROOT / 'build/macos'
    work.mkdir(parents=True, exist_ok=True)
    asset_name = f'deno-{"aarch64" if arch == "arm64" else "x86_64"}-apple-darwin.zip'
    request = urllib.request.Request('https://api.github.com/repos/denoland/deno/releases/tags/v2.9.6',
        headers={'User-Agent': 'Fetch-Build'})
    with urllib.request.urlopen(request, timeout=60) as response:
        release = json.load(response)
    asset = next(a for a in release['assets'] if a['name'] == asset_name)
    digest = asset.get('digest', '')
    if not digest.startswith('sha256:'):
        raise RuntimeError('Deno release checksum unavailable')
    archive_path = work / asset_name
    urllib.request.urlretrieve(asset['browser_download_url'], archive_path)
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != digest[7:]:
        raise RuntimeError('Deno checksum mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        (work / 'deno').write_bytes(archive.read('deno'))
    (work / 'deno').chmod(0o755)

    iconset = work / 'Fetch.iconset'
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            filename = f'icon_{size}x{size}{"@2x" if scale == 2 else ""}.png'
            run('sips', '-z', size * scale, size * scale, ROOT / 'assets/fetch_icon_clean.png',
                '--out', iconset / filename, stdout=subprocess.DEVNULL)
    run('iconutil', '-c', 'icns', iconset, '-o', work / 'Fetch.icns')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', ROOT / 'packaging/fetch-macos.spec')
    app = ROOT / 'dist/Fetch.app'
    executable = app / 'Contents/MacOS/Fetch'
    run(executable, '--self-test')
    run(executable, '--smoke-test', work / 'Fetch-ui.png')
    run('codesign', '--verify', '--deep', '--strict', app)

    # A copied app runs without the build interpreter on PATH, matching drag-to-install.
    installed = work / 'Applications test' / 'Fetch.app'
    if installed.exists():
        if not installed.resolve().is_relative_to(work.resolve()):
            raise RuntimeError('Unsafe test app location')
        shutil.rmtree(installed)
    installed.parent.mkdir(exist_ok=True)
    run('ditto', app, installed)
    env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
           'PYTHONHOME': '/nonexistent-fetch-python', 'PYTHONPATH': '/nonexistent-fetch-python'}
    run(installed / 'Contents/MacOS/Fetch', '--self-test', env=env)

    staging = work / 'dmg-content'
    staging.mkdir(exist_ok=True)
    if (staging / 'Fetch.app').exists():
        shutil.rmtree(staging / 'Fetch.app')
    run('ditto', app, staging / 'Fetch.app')
    if not (staging / 'Applications').exists():
        (staging / 'Applications').symlink_to('/Applications')
    if not os.environ.get('MAC_SIGN_IDENTITY'):
        (staging / 'PREVIEW.txt').write_text(
            'Developer preview. Apple Developer ID signing and notarization are pending.\n'
            'This is not an App Store release or a Gatekeeper-approved public distribution.\n')
    output = ROOT / 'release/macos'
    output.mkdir(parents=True, exist_ok=True)
    dmg = output / f'Fetch-macOS-{arch}.dmg'
    run('hdiutil', 'create', '-volname', 'Fetch', '-srcfolder', staging,
        '-ov', '-format', 'UDZO', dmg)
    checksum = hashlib.sha256(dmg.read_bytes()).hexdigest()
    dmg.with_suffix('.dmg.sha256').write_text(f'{checksum}  {dmg.name}\n')
    report = {'version': APP_VERSION, 'arch': arch, 'os': platform.mac_ver()[0],
              'self_test': True, 'relocated_self_test': True, 'ui_render': True,
              'developer_id_signed': bool(os.environ.get('MAC_SIGN_IDENTITY')),
              'notarized': False, 'sha256': checksum}
    (output / f'verification-{arch}.json').write_text(json.dumps(report, indent=2))

if __name__ == '__main__':
    build()
