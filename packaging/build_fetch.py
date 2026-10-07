"""Build an embedded Windows x64 app and its Inno Setup installer."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_config import APP_VERSION
PAYLOAD = ROOT / "release/fetch-standalone"
RUNTIME = PAYLOAD / "runtime"
PYTHON_ZIP = ROOT / "build/python-3.12.10-embed-amd64.zip"
PYTHON_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"

def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)

def build():
    if not PYTHON_ZIP.exists():
        PYTHON_ZIP.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve("https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip", PYTHON_ZIP)
    if hashlib.sha256(PYTHON_ZIP.read_bytes()).hexdigest() != PYTHON_SHA256:
        raise RuntimeError("Embedded Python checksum mismatch")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PYTHON_ZIP) as archive:
        archive.extractall(RUNTIME)
    deno_zip = ROOT / "build/deno-v2.9.6.zip"
    if not deno_zip.exists():
        urllib.request.urlretrieve("https://github.com/denoland/deno/releases/download/v2.9.6/deno-x86_64-pc-windows-msvc.zip", deno_zip)
    if hashlib.sha256(deno_zip.read_bytes()).hexdigest() != "15e5300b0ba3c3695a7621d90160a746ec9e710228cee639afa9d580f6e3cd11":
        raise RuntimeError("Deno checksum mismatch")
    with zipfile.ZipFile(deno_zip) as archive:
        archive.extractall(RUNTIME)
    site = RUNTIME / "Lib/site-packages"
    marker = RUNTIME / "requirements.sha256"
    requirements_hash = hashlib.sha256((ROOT / "requirements-fetch.txt").read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text() != requirements_hash:
        if site.exists():
            resolved = site.resolve()
            if not resolved.is_relative_to(PAYLOAD.resolve()) or site.is_symlink():
                raise RuntimeError("Unsafe generated dependency path")
            shutil.rmtree(resolved)
        run(sys.executable, "-m", "pip", "install", "--only-binary=:all:", "--target", site,
            "-r", ROOT / "requirements-fetch.txt")
        marker.write_text(requirements_hash)
    (RUNTIME / "python312._pth").write_text("python312.zip\n.\nLib/site-packages\n../app\nimport site\n", encoding="ascii")
    if (RUNTIME / "pyvenv.cfg").exists():
        raise RuntimeError("A virtual environment is not a standalone runtime")
    app = PAYLOAD / "app"
    app.mkdir(exist_ok=True)
    for name in ("app_config.py", "instagram_downloader_ui.py", "media_downloader.py", "update_manager.py", "network_support.py", "account_sessions.py", "account_dialog.py", "fetch_diagnostics.py", "localization.py", "behance_browser.py"):
        shutil.copy2(ROOT / name, app / name)
    shutil.copytree(ROOT / "assets", app / "assets", dirs_exist_ok=True)
    shutil.copy2(ROOT / "assets/fetch.ico", PAYLOAD / "Fetch.ico")
    (PAYLOAD / "README.txt").write_text(
        f"Fetch {APP_VERSION}\nWindows 10/11 x64. No Python installation required.\n"
        "Install with Fetch.Setup.exe. Use the in-app update button for future releases.\n"
        "Updates preserve download folders and user settings.\n"
        "https://github.com/MOONKYUNGJIN82/fetch/releases/latest\n", encoding="utf-8")
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    run(compiler, "/nologo", "/target:winexe", "/reference:System.Windows.Forms.dll",
        f"/win32icon:{ROOT / 'assets/fetch.ico'}", f"/out:{PAYLOAD / 'Fetch.exe'}", ROOT / "packaging/FetchLauncher.cs")
    run(RUNTIME / "python.exe", "-I", app / "instagram_downloader_ui.py", "--self-test")
    run(sys.executable, ROOT / "packaging/make_installer_art.py")
    inno = os.environ.get("INNO_SETUP_COMPILER", "C:/Program Files (x86)/Inno Setup 6/ISCC.exe")
    run(inno, "/Qp", f"/DAppVersion={APP_VERSION}", ROOT / "packaging/fetch.iss")
    installer = ROOT / "release/standalone/Fetch.Setup.exe"
    checksum = hashlib.sha256(installer.read_bytes()).hexdigest()
    installer.with_suffix(".exe.sha256").write_text(f"{checksum}  Fetch.Setup.exe\n", encoding="ascii")
    print(f"Built {installer}\nSHA256: {checksum}")

if __name__ == "__main__":
    build()
