"""Exercise the real modal worker, clipboard and close lifecycle."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QPlainTextEdit
from fetch_diagnostics import show_diagnostics
from instagram_downloader_ui import load_pretendard

app = QApplication([])
load_pretendard(app)
failed = []
errors = []
def unhandled(kind, value, traceback):
    errors.append(kind.__name__)
    sys.__excepthook__(kind, value, traceback)
sys.excepthook = unhandled

def check():
    dialog = app.activeModalWidget()
    if dialog is None:
        return
    buttons = dialog.findChildren(QPushButton)
    copy = next(b for b in buttons if b.text() == '진단 정보 복사')
    if not copy.isEnabled() or dialog.running:
        return
    timer.stop()
    try:
        report = dialog.findChild(QPlainTextEdit).toPlainText()
        assert 'HTTP 403' in report
        assert 'SECRET' not in report
        copy.click()
        assert app.clipboard().text() == report
        screenshot = Path('build/Fetch-diagnostics-dialog.png').resolve()
        dialog.grab().save(str(screenshot))
    except Exception as exc:
        failed.append(type(exc).__name__)
    dialog.reject()

timer = QTimer()
timer.timeout.connect(check)
timer.start(50)
QTimer.singleShot(15000, lambda: os._exit(2))
with tempfile.TemporaryDirectory() as folder:
    show_diagnostics(None, folder, 'HTTP Error 403 https://private.example/?token=SECRET', [], False)
assert not failed and not errors, (failed, errors)
print('PASS: modal worker, sanitized report, clipboard, close lifecycle')
