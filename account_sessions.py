"""Service-scoped sessions. Persistent cookies are encrypted; downloads use memory only."""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

SERVICES = {
    "instagram": ("Instagram", "instagram.com", "https://www.instagram.com/accounts/login/"),
    "behance": ("Behance", "behance.net", "https://www.behance.net/"),
}


def service_for_url(url):
    host = (urlparse(url).hostname or "").lower()
    return next((key for key, (_, domain, _) in SERVICES.items()
                 if host == domain or host.endswith("." + domain)), None)


def allowed_cookie(service, cookie):
    domain = cookie.domain.lstrip(".").lower()
    root = SERVICES[service][1]
    return (domain == root or domain.endswith("." + root)) and not cookie.is_expired()


def native_keyring():
    # Never silently fall back to an unencrypted third-party keyring backend.
    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()
    if sys.platform == "darwin":
        from keyring.backends.macOS import Keyring
        return Keyring()
    raise RuntimeError("계정 보관은 Windows와 macOS에서 지원합니다.")


class SessionStore:
    def __init__(self, folder=None, backend=None):
        base = (Path.home() / "Library/Application Support" if sys.platform == "darwin"
                else Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")))
        self.folder = Path(folder) if folder else base / "Fetch" / "accounts"
        self.backend = backend

    def path(self, service):
        if service not in SERVICES:
            raise ValueError("Unknown service")
        return self.folder / (service + ".session")

    def cipher(self, service, create=False):
        from cryptography.fernet import Fernet
        backend = self.backend or native_keyring()
        key = backend.get_password("Fetch.AccountSessions", service)
        if not key and create:
            key = Fernet.generate_key().decode("ascii")
            backend.set_password("Fetch.AccountSessions", service, key)
        if not key:
            raise RuntimeError("저장된 로그인 정보를 열 수 없습니다. 계정을 다시 연결해 주세요.")
        return Fernet(key.encode("ascii"))

    def save(self, service, cookies):
        records = [dict(domain=c.domain, path=c.path, secure=c.secure, expires=c.expires,
                        name=c.name, value=c.value, rest=c._rest)
                   for c in cookies if allowed_cookie(service, c)]
        if not records:
            raise ValueError("이 서비스의 유효한 쿠키가 없습니다. 로그인을 완료한 뒤 다시 시도해 주세요.")
        payload = json.dumps({"saved_at": int(time.time()), "cookies": records}).encode()
        encrypted = self.cipher(service, create=True).encrypt(payload)
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.path(service)
        temporary = target.with_suffix(".tmp")
        try:
            temporary.write_bytes(encrypted)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, service):
        from yt_dlp.cookies import YoutubeDLCookieJar
        jar = YoutubeDLCookieJar()
        target = self.path(service)
        if not target.exists():
            return jar
        data = json.loads(self.cipher(service).decrypt(target.read_bytes()))
        for record in data["cookies"]:
            cookie = http.cookiejar.Cookie(
                0, record["name"], record["value"], None, False, record["domain"],
                record["domain"].startswith("."), record["domain"].startswith("."),
                record["path"], True, record["secure"], record["expires"],
                record["expires"] is None, None, None, record.get("rest", {}))
            if allowed_cookie(service, cookie):
                jar.set_cookie(cookie)
        return jar

    def remove(self, service):
        target = self.path(service)
        backend = self.backend or native_keyring()
        if backend.get_password("Fetch.AccountSessions", service):
            backend.delete_password("Fetch.AccountSessions", service)
        target.unlink(missing_ok=True)

    def import_file(self, service, path):
        jar = http.cookiejar.MozillaCookieJar(str(path))
        jar.load(ignore_discard=True, ignore_expires=False)
        self.save(service, jar)


def cookies_for_url(url, explicit=None):
    if explicit is not None:
        return explicit
    service = service_for_url(url)
    if service is None:
        return None
    store = SessionStore()
    if not store.path(service).exists():
        return None
    jar = store.load(service)
    if not len(jar):
        raise RuntimeError("저장된 로그인 세션이 만료됐습니다. 계정을 다시 연결해 주세요.")
    return jar


def apply_session(ydl, cookies):
    if isinstance(cookies, http.cookiejar.CookieJar):
        ydl.cookiejar = cookies
