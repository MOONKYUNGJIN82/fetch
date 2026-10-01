"""Explicit, user-controlled service login in an ephemeral browser profile."""
import http.cookiejar
from localization import tr

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QFileDialog

from account_sessions import SERVICES, SessionStore


class AccountDialog(QDialog):
    def __init__(self, service, parent=None, test_mode=False):
        super().__init__(parent)
        self.service = service
        self.store = SessionStore()
        self.setWindowTitle(SERVICES[service][0] + tr(" 계정 연결"))
        self.resize(920, 720)
        self.setMinimumSize(560, 480)
        layout = QVBoxLayout(self)
        self.address = QLabel()
        self.address.setWordWrap(True)
        layout.addWidget(self.address)
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView
        self.profile = QWebEngineProfile(self)
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self.view)
        self.view.setPage(self.page)
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        self.cookies = {}
        self.profile.cookieStore().cookieAdded.connect(self.cookie_added)
        self.profile.cookieStore().cookieRemoved.connect(self.cookie_removed)
        self.view.urlChanged.connect(self.show_address)
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        import_button = QPushButton(tr("쿠키 가져오기"))
        import_button.clicked.connect(self.import_cookies)
        save = QPushButton(tr("로그인 완료 · 연결 저장"))
        save.clicked.connect(self.save_session)
        cancel = QPushButton(tr("취소"))
        cancel.clicked.connect(self.reject)
        row.addWidget(import_button)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(save)
        layout.addLayout(row)
        if test_mode:
            self.view.setHtml('<html><head><title>Fetch browser test</title></head><body><h1>Fetch account browser</h1></body></html>')
        else:
            self.view.load(QUrl(SERVICES[service][2]))

    def show_address(self, url):
        display = QUrl(url)
        display.setQuery("")
        display.setFragment("")
        display.setUserInfo("")
        self.address.setText(display.toDisplayString())

    def cookie_added(self, cookie):
        self.cookies[(cookie.domain(), cookie.path(), bytes(cookie.name()))] = cookie

    def cookie_removed(self, cookie):
        self.cookies.pop((cookie.domain(), cookie.path(), bytes(cookie.name())), None)

    def save_session(self):
        if self.service == "instagram" and not any(
                bytes(c.name()) == b"sessionid" and
                c.domain().lstrip(".") in ("instagram.com", "www.instagram.com")
                for c in self.cookies.values()):
            QMessageBox.warning(self, tr("로그인 확인"), tr("Instagram 로그인을 먼저 완료해 주세요."))
            return
        jar = http.cookiejar.CookieJar()
        for cookie in self.cookies.values():
            domain = cookie.domain()
            jar.set_cookie(http.cookiejar.Cookie(
                0, bytes(cookie.name()).decode("utf-8"), bytes(cookie.value()).decode("utf-8"),
                None, False, domain, domain.startswith("."), domain.startswith("."),
                cookie.path() or "/", True, cookie.isSecure(),
                None if cookie.isSessionCookie() else cookie.expirationDate().toSecsSinceEpoch(),
                cookie.isSessionCookie(), None, None, {"HttpOnly": None} if cookie.isHttpOnly() else {}))
        try:
            self.store.save(self.service, jar)
        except Exception:
            QMessageBox.warning(self, tr("연결 저장 실패"), tr("로그인 완료 여부와 보안 저장소 접근 권한을 확인해 주세요. 연결되지 않으면 본인 브라우저의 쿠키 파일을 가져올 수 있습니다."))
            return
        self.accept()

    def import_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("본인 계정 쿠키 가져오기"), "", "Cookies (*.txt)")
        if not path:
            return
        try:
            self.store.import_file(self.service, path)
        except Exception:
            QMessageBox.warning(self, tr("가져오기 실패"), tr("유효한 Netscape 쿠키 파일과 보안 저장소 접근 권한을 확인해 주세요."))
            return
        self.accept()

    def done(self, result):
        self.view.stop()
        self.cookies.clear()
        # Delete the page before its profile, as required by Qt WebEngine.
        self.page.deleteLater()
        self.page.destroyed.connect(self.profile.deleteLater)
        super().done(result)


def browser_self_test(app, destination):
    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QNetworkCookie
    dialog = AccountDialog('instagram', test_mode=True)
    app.setQuitOnLastWindowClosed(False)
    done = False

    def finish(ok):
        nonlocal done
        if done:
            return
        done = True
        if ok:
            cookie = QNetworkCookie(b'fetch_test', b'synthetic')
            cookie.setDomain('.instagram.com')
            cookie.setPath('/')
            dialog.cookie_added(cookie)
            ok = bool(dialog.cookies) and dialog.profile.isOffTheRecord() and dialog.grab().save(str(destination))
        dialog.reject()
        QTimer.singleShot(500, lambda: app.exit(0 if ok else 1))

    def loaded(ok):
        if not ok:
            finish(False)
            return
        dialog.page.runJavaScript('document.title', lambda title: finish(title == 'Fetch browser test'))

    dialog.view.loadFinished.connect(loaded)
    QTimer.singleShot(30000, lambda: finish(False))
    dialog.show()
    return app.exec()
