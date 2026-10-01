"""Run separately from offscreen unit tests to exercise the native browser process."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWebEngineWidgets import QWebEngineView
from account_dialog import AccountDialog
from account_sessions import SessionStore


class Backend:
    def __init__(self):
        self.data = {}

    def get_password(self, service, name):
        return self.data.get((service, name))

    def set_password(self, service, name, value):
        self.data[service, name] = value


QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
temp = tempfile.TemporaryDirectory()
backend = Backend()
store = SessionStore(temp.name, backend)
errors = []
def unhandled(kind, value, traceback):
    errors.append(kind.__name__)
    sys.__excepthook__(kind, value, traceback)
sys.excepthook = unhandled
with patch('account_dialog.SessionStore', return_value=store), patch.object(QWebEngineView, 'load'):
    dialog = AccountDialog('instagram')
dialog.show()
dialog.view.setHtml('<html><body style="background:#111;color:white"><h1>Fetch account browser test</h1></body></html>', QUrl('https://www.instagram.com/'))


def check():
    try:
        assert dialog.profile.isOffTheRecord()
        cookie = QNetworkCookie(b'sessionid', b'fake-browser-session')
        cookie.setDomain('.instagram.com')
        cookie.setPath('/')
        cookie.setSecure(True)
        dialog.cookie_added(cookie)
        dialog.save_session()
        restored = SessionStore(temp.name, backend).load('instagram')
        assert next(iter(restored)).value == 'fake-browser-session'
        assert b'fake-browser-session' not in store.path('instagram').read_bytes()
        print('PASS: browser renders; ephemeral profile; encrypted session restored by new store', flush=True)
    except Exception as exc:
        errors.append(type(exc).__name__)
        dialog.reject()
    QTimer.singleShot(500, app.quit)


QTimer.singleShot(2500, check)
app.exec()
temp.cleanup()
sys.exit(1 if errors else 0)
