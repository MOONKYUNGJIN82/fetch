"""Bounded, isolated browser rendering for public Behance project pages."""
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse


_lock = threading.Lock()
_cache = {}


def valid_project(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.hostname in ('behance.net', 'www.behance.net')
            and parsed.path.startswith('/gallery/') and not parsed.username and not parsed.password)


def cookie_records(cookies):
    if cookies is None:
        return []
    if not isinstance(cookies, http.cookiejar.CookieJar):
        jar = http.cookiejar.MozillaCookieJar(str(cookies))
        jar.load(ignore_discard=True, ignore_expires=False)
        cookies = jar
    return [dict(name=c.name, value=c.value, domain=c.domain, path=c.path,
                 secure=c.secure, expires=c.expires, http_only=c.has_nonstandard_attr('HttpOnly'))
            for c in cookies if not c.is_expired() and
            (c.domain.lstrip('.') == 'behance.net' or c.domain.endswith('.behance.net'))]


def render_project(url, cookies=None):
    if not valid_project(url):
        raise ValueError('Browser rendering requires an HTTPS Behance project URL.')
    records = cookie_records(cookies)
    # Private pages are never cached; no sessions or HTML are written to disk.
    with _lock:
        cached = _cache.get(url) if not records else None
        if cached and time.monotonic() - cached[0] < 90:
            return cached[1]
        if getattr(sys, 'frozen', False):
            command = [sys.executable, '--behance-browser']
        else:
            executable = Path(sys.executable)
            if executable.name.lower() == 'pythonw.exe':
                executable = executable.with_name('python.exe')
            command = [str(executable), str(Path(__file__).with_name('instagram_downloader_ui.py')),
                       '--behance-browser']
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(command, input=json.dumps({'url': url, 'cookies': records}),
                                capture_output=True, encoding='utf-8', timeout=55, env=env,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('Behance browser could not load the project. Open the original page to check access.')
        try:
            page = json.loads(result.stdout)['html']
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError('Behance browser returned no project content.') from exc
        if not records:
            if len(_cache) >= 8:
                _cache.clear()
            _cache[url] = (time.monotonic(), page)
        return page


def browser_main():
    from PySide6.QtCore import QDateTime, QTimer, QUrl
    from PySide6.QtNetwork import QNetworkCookie
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

    input_stream = sys.stdin or os.fdopen(0, 'r', encoding='utf-8', closefd=False)
    output_stream = sys.stdout or os.fdopen(1, 'w', encoding='utf-8', closefd=False)
    request = json.load(input_stream)
    if not valid_project(request.get('url', '')):
        return 2
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    profile = QWebEngineProfile()
    profile.downloadRequested.connect(lambda item: item.cancel())
    page = QWebEnginePage(profile)
    page.setAudioMuted(True)
    done = False
    loaded = False

    def load_finished(ok):
        nonlocal loaded
        loaded = ok

    page.loadFinished.connect(load_finished)

    def finish(content=None):
        nonlocal done
        if done:
            return
        done = True
        page.triggerAction(QWebEnginePage.Stop)
        if content:
            print(json.dumps({'html': content}, ensure_ascii=True), file=output_stream, flush=True)
        app.exit(0 if content else 3)

    def inspect(content):
        if done:
            return
        if loaded and valid_project(page.url().toString()) and 'project-modules' in content:
            finish(content)

    timer = QTimer()
    timer.timeout.connect(lambda: page.toHtml(inspect))
    timer.start(750)
    QTimer.singleShot(45000, finish)
    store = profile.cookieStore()
    pending = set()

    def start():
        if not pending:
            page.load(QUrl(request['url']))

    def added(cookie):
        pending.discard((bytes(cookie.name()), cookie.domain(), cookie.path()))
        if not pending:
            store.cookieAdded.disconnect(added)
            start()

    for entry in request.get('cookies', []):
        domain = entry['domain']
        if domain.lstrip('.') != 'behance.net' and not domain.endswith('.behance.net'):
            continue
        cookie = QNetworkCookie(entry['name'].encode(), entry['value'].encode())
        cookie.setDomain(domain)
        cookie.setPath(entry['path'] or '/')
        cookie.setSecure(entry['secure'])
        cookie.setHttpOnly(entry.get('http_only', False))
        if entry['expires']:
            cookie.setExpirationDate(QDateTime.fromSecsSinceEpoch(entry['expires']))
        pending.add((bytes(cookie.name()), cookie.domain(), cookie.path()))
        store.setCookie(cookie)
    if pending:
        store.cookieAdded.connect(added)
    else:
        start()
    code = app.exec()
    timer.stop()
    # Qt requires page destruction before profile destruction.
    import shiboken6
    shiboken6.delete(page)
    shiboken6.delete(profile)
    return code
