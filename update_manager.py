from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import tempfile
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from network_support import tls_context

from app_config import APP_VERSION, GITHUB_INSTALLER_ASSET, GITHUB_OWNER, GITHUB_RELEASE_API, GITHUB_REPO


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    notes: str
    asset_name: str
    download_url: str
    sha256: str | None = None


def latest_release_api_url() -> str:
    if GITHUB_RELEASE_API:
        return GITHUB_RELEASE_API
    if not GITHUB_OWNER or not GITHUB_REPO:
        raise RuntimeError("GitHub 저장소 정보가 설정되지 않았습니다. app_config.py의 GITHUB_OWNER/GITHUB_REPO를 입력하세요.")
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def version_key(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts[:4]) or (0,)


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    latest_key = version_key(latest)
    current_key = version_key(current)
    length = max(len(latest_key), len(current_key))
    return latest_key + (0,) * (length - len(latest_key)) > current_key + (0,) * (length - len(current_key))


def _request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Fetch-Updater",
        },
    )
    with urllib.request.urlopen(request, timeout=20, context=tls_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def installer_asset_name(system: str | None = None, machine: str | None = None) -> str:
    system = system or sys.platform
    machine = (machine or platform.machine()).lower()
    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "Fetch-macOS-arm64.dmg"
        if machine in ("x86_64", "amd64"):
            return "Fetch-macOS-x86_64.dmg"
        raise RuntimeError("지원하지 않는 Mac CPU입니다.")
    if system == "win32":
        return GITHUB_INSTALLER_ASSET
    raise RuntimeError("이 운영체제의 설치 파일은 아직 제공되지 않습니다.")


def check_for_update(current_version: str = APP_VERSION) -> UpdateInfo | None:
    if sys.platform == "darwin":
        releases = _request_json(f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases?per_page=100")
        if isinstance(releases, dict):
            releases = [releases]
        candidates = []
        for release in releases:
            tag = str(release.get("tag_name") or "")
            if release.get("draft"):
                continue
            if release.get("prerelease") and not re.fullmatch(r"v?\d+\.\d+\.\d+-macos-preview\.\d+", tag):
                continue
            if any(a.get("name") == installer_asset_name() for a in release.get("assets", [])):
                candidates.append(release)
        if not candidates:
            return None
        data = max(candidates, key=lambda r: version_key(r["tag_name"].split("-")[0]))
    else:
        data = _request_json(latest_release_api_url())
    latest_version = str(data.get("tag_name") or data.get("name") or "").lstrip("vV")
    if sys.platform == "darwin":
        latest_version = latest_version.split("-")[0]
    if data.get("draft") or (data.get("prerelease") and sys.platform != "darwin"):
        return None
    if not latest_version or not is_newer_version(latest_version, current_version):
        return None

    assets = data.get("assets") or []
    expected_asset = installer_asset_name()
    selected = None
    for asset in assets:
        if asset.get("name") == expected_asset:
            selected = asset
            break
    if selected is None and sys.platform == "win32":
        for asset in assets:
            name = str(asset.get("name") or "")
            if name.lower().endswith(".exe") and "setup" in name.lower():
                selected = asset
                break
    if selected is None:
        raise RuntimeError(f"최신 릴리스에서 이 컴퓨터용 설치 파일({expected_asset})을 찾을 수 없습니다.")

    notes = str(data.get("body") or "").strip()
    asset_digest = str(selected.get("digest") or "")
    sha256 = asset_digest[7:].lower() if re.fullmatch(r"sha256:[a-fA-F0-9]{64}", asset_digest) else None
    for line in notes.splitlines():
        if not sha256 and "sha256" in line.lower() and (
            selected["name"] in line or (sys.platform == "win32" and len(assets) <= 2)
        ):
            match = re.search(r"\b[a-fA-F0-9]{64}\b", line)
            if match:
                sha256 = match.group(0).lower()
                break

    if not sha256:
        raise RuntimeError("릴리스에 설치 파일의 SHA256 검증 정보가 없습니다.")
    return UpdateInfo(
        version=latest_version,
        notes=notes,
        asset_name=str(selected.get("name") or GITHUB_INSTALLER_ASSET),
        download_url=str(selected["browser_download_url"]),
        sha256=sha256,
    )


def download_installer(update: UpdateInfo, progress: Callable[[int], None] | None = None) -> Path:
    if not update.sha256 or not re.fullmatch(r"[a-fA-F0-9]{64}", update.sha256):
        raise RuntimeError("업데이트 검증 정보가 없습니다.")
    url = urllib.parse.urlparse(update.download_url)
    expected_path = f"/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/"
    if url.scheme != "https" or url.hostname != "github.com" or not url.path.startswith(expected_path):
        raise RuntimeError("올바른 Fetch GitHub 다운로드 주소가 아닙니다.")
    if Path(update.asset_name).name != update.asset_name or "/" in update.asset_name or "\\" in update.asset_name:
        raise RuntimeError("올바르지 않은 업데이트 파일명입니다.")
    target_dir = Path(tempfile.mkdtemp(prefix="FetchUpdate-"))
    target = target_dir / update.asset_name
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(update.download_url, headers={"User-Agent": "Fetch-Updater"})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=60, context=tls_context()) as response, partial.open("wb") as file:
            total = int(response.headers.get("Content-Length") or "0")
            received = 0
            while chunk := response.read(1024 * 512):
                file.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress and total:
                    progress(min(99, int(received * 100 / total)))
        if not received or (total and received != total):
            raise RuntimeError("업데이트 파일 다운로드가 완료되지 않았습니다.")
        if digest.hexdigest().lower() != update.sha256.lower():
            raise RuntimeError("업데이트 파일 검증에 실패했습니다. SHA256 값이 일치하지 않습니다.")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    if progress:
        progress(100)
    return target
