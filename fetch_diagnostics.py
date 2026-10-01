"""Local-only diagnostics with allowlisted output, never raw logs or credentials."""
import importlib.metadata
import platform
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app_config import APP_VERSION
from localization import tr, translate_report


def error_categories(log):
    rules = [
        ("인증 필요", r"login required|log in|login_required|로그인.*(?:요구|필요)"),
        ("세션 확인 필요", r"cookie|쿠키|세션.*(?:만료|실패)"),
        ("요청 제한", r"too many requests|rate.limit|429"),
        ("접근 거부", r"forbidden|접근 거부|403"),
        ("TLS 인증서", r"certificate_verify_failed|certificate verify|인증서"),
        ("연결 시간 초과", r"timed out|timeout|시간 초과"),
        ("네트워크 연결", r"connection refused|connection reset|name resolution|urlopen error"),
        ("저장 권한", r"permission denied|access.denied|winerror 5|액세스.*거부"),
        ("미디어 추출", r"no video formats|no formats|requested format is not available|미디어.*못|썸네일.*못"),
    ]
    results = []
    for line in log.splitlines()[-300:]:
        labels = [name for name, pattern in rules if re.search(pattern, line, re.I)]
        codes = re.findall(r"(?:HTTP(?: Error)?[ :]+|status(?: code)?[ :=]+)([45]\d{2})\b", line, re.I)
        labels += ["HTTP " + code for code in codes]
        if not labels and re.search(r"error|failed|오류|실패", line, re.I):
            labels = ["기타 오류 (원문 제외)"]
        if labels:
            results.append(", ".join(dict.fromkeys(labels)))
    return results[-15:]


def folder_check(folder):
    try:
        if not folder.is_dir():
            return "폴더 없음 (생성 여부 미확인)", "미확인"
        free = f"{shutil.disk_usage(folder).free // (1024 ** 3)} GiB"
        with tempfile.TemporaryFile(prefix=".fetch-diagnostic-", dir=folder) as file:
            file.write(b"Fetch diagnostic\n")
            file.flush()
        return "쓰기 성공 (검사용 파일 삭제)", free
    except PermissionError:
        return "쓰기 권한 없음", "미확인"
    except OSError:
        return "접근 또는 쓰기 실패", "미확인"


def build_report(folder, log, saved_services=(), manual_cookie=False):
    from media_downloader import bundled_js_runtimes
    versions = []
    for package in ("yt-dlp", "PySide6-Essentials", "PySide6-Addons", "certifi", "imageio-ffmpeg"):
        try:
            version = importlib.metadata.version(package)
            version = version if re.fullmatch(r"[0-9A-Za-z.+_-]{1,60}", version) else "확인 불가"
        except importlib.metadata.PackageNotFoundError:
            version = "없음"
        versions.append(f"{package}: {version}")
    write, free = folder_check(Path(folder))
    try:
        import imageio_ffmpeg
        ffmpeg = "있음" if Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file() else "없음"
    except Exception:
        ffmpeg = "확인 실패"
    try:
        deno_path = bundled_js_runtimes().get("deno", {}).get("path")
        deno = "앱 포함" if deno_path and Path(deno_path).is_file() else ("시스템 경로에 있음" if shutil.which("deno") else "없음")
    except Exception:
        deno = "확인 실패"
    system = "Windows" if sys.platform == "win32" else "macOS" if sys.platform == "darwin" else "기타"
    release = platform.mac_ver()[0] if sys.platform == "darwin" else platform.release()
    release = release if re.fullmatch(r"[0-9A-Za-z._-]{1,40}", release) else "미확인"
    arch = platform.machine()
    arch = arch if arch in ("AMD64", "x86_64", "arm64", "aarch64", "x86", "i386") else "기타"
    lines = ["Fetch 진단 정보", "작성 시각 (UTC): " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
             f"Fetch: {APP_VERSION}", f"운영체제: {system} {release} / {arch}",
             f"Python runtime: {platform.python_version()}", *versions,
             f"FFmpeg: {ffmpeg}", f"Deno: {deno}", f"저장 폴더: {write}", f"남은 공간: {free}",
             "Instagram 세션 파일: " + ("있음" if "instagram" in saved_services else "없음"),
             "Behance 세션 파일: " + ("있음" if "behance" in saved_services else "없음"),
             "수동 쿠키 선택: " + ("예" if manual_cookie else "아니오"),
             "세션 유효성/사이트 연결: 검사하지 않음", "", "최근 오류 분류 (오래된 순):"]
    lines += error_categories(log) or ["기록된 오류 없음"]
    lines += ["", "URL, 경로, 계정명, 쿠키, 토큰, 오류 원문은 포함하지 않습니다.",
              "오류 분류는 로그의 단서이며 확정 진단이 아닙니다. 자동 전송되지 않습니다."]
    return translate_report("\n".join(lines))


def show_diagnostics(parent, folder, log, saved_services, manual_cookie):
    from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QApplication

    class Worker(QObject):
        ready = Signal(str)

        @Slot()
        def run(self):
            try:
                report = build_report(folder, log, saved_services, manual_cookie)
            except Exception:
                report = tr("진단 생성에 실패했습니다. 개인정보 보호를 위해 오류 원문은 제외했습니다.")
            self.ready.emit(report)

    class Dialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle(tr("Fetch 진단 정보"))
            self.resize(660, 600)
            layout = QVBoxLayout(self)
            self.text = QPlainTextEdit(tr("진단 중..."))
            self.text.setReadOnly(True)
            layout.addWidget(self.text)
            row = QHBoxLayout()
            self.copy = QPushButton(tr("진단 정보 복사"))
            self.copy.setEnabled(False)
            self.copy.clicked.connect(self.copy_report)
            close = QPushButton(tr("닫기"))
            close.clicked.connect(self.reject)
            row.addWidget(self.copy)
            row.addWidget(close)
            layout.addLayout(row)
            self.running = True
            self.thread = QThread(self)
            self.worker = Worker()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.ready.connect(self.received, Qt.QueuedConnection)
            self.worker.ready.connect(self.thread.quit)
            self.worker.ready.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.stopped)
            self.thread.start()

        @Slot(str)
        def received(self, report):
            self.text.setPlainText(report)
            self.copy.setEnabled(True)

        @Slot()
        def stopped(self):
            self.running = False

        def copy_report(self):
            QApplication.clipboard().setText(self.text.toPlainText())
            self.copy.setText(tr("복사 완료"))

        def reject(self):
            if not self.running:
                super().reject()

        def closeEvent(self, event):
            if self.running:
                event.ignore()
            else:
                super().closeEvent(event)

    dialog = Dialog()
    dialog.exec()
    dialog.deleteLater()
