from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QSize, QSettings, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_config import APP_NAME, APP_VERSION
from media_downloader import (
    COMPAT_VIDEO_FORMAT,
    bundled_js_runtimes,
    DEFAULT_VIDEO_FORMAT,
    USER_AGENT,
    download_urls,
    extract_behance_media,
    is_behance_url,
    is_instagram_url,
    extract_instagram_info,
)
from update_manager import UpdateInfo, check_for_update, download_installer
from yt_dlp import YoutubeDL
from network_support import tls_context


BEST_VIDEO_FORMAT = "bv*+ba/b"
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
HISTORY_LIMIT = 80


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base_path / relative_path


def load_pretendard(app: QApplication) -> str:
    font_path = resource_path("assets/fonts/PretendardVariable.ttf")
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
                app.setFont(QFont(family, 10))
                return family
    family = "Pretendard"
    app.setFont(QFont(family, 10))
    return family


def app_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / "AppData" / "Local" if sys.platform.startswith("win") else Path.home() / ".local" / "share"
    folder = base / APP_NAME
    try:
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    except PermissionError:
        fallback = Path.cwd() / "downloads" / ".fetch_data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def default_download_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Downloads" / APP_NAME
    return Path("downloads").resolve()


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_PATTERN.findall(text):
        url = match.rstrip(".,);]\n\r\t")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def platform_name(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "instagram.com" in host:
        return "Instagram"
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube"
    if "behance.net" in host:
        return "Behance"
    if "vimeo.com" in host:
        return "Vimeo"
    return "Media"


def dated_output_dir(base_dir: Path, platform: str, use_platform_folder: bool) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    if use_platform_folder:
        return base_dir / platform.lower() / today
    return base_dir / today


def write_source_url(target_dir: Path, url: str) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    source_file = target_dir / "source_urls.txt"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with source_file.open("a", encoding="utf-8") as file:
        file.write(f"[{stamp}] {url}\n")


def friendly_error(message: str, platform: str = "", has_cookies: bool = False) -> str:
    lowered = message.lower()
    service = platform or ("Instagram" if "instagram" in lowered else "사이트")
    if "login" in lowered and " or " in lowered and any(term in lowered for term in ("rate-limit", "rate limit", "not available", "unavailable")):
        return f"{service}에서 미디어 정보를 확인하지 못했습니다. 로그인 필요, 요청 제한, 게시물 접근 제한 중 어느 원인인지는 이 응답만으로 확정할 수 없습니다. 브라우저에서 원본 접근을 확인해 주세요."
    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return f"{service} 요청 제한에 걸렸습니다. 반복 시도를 멈추고 잠시 후 다시 시도해 주세요."
    if "403" in lowered or "forbidden" in lowered:
        return f"{service}가 접근을 거부했습니다(403). 브라우저에서 원본 접근을 확인해 주세요. 로그인 문제인지 자동 요청 차단인지는 이 응답만으로 구분할 수 없습니다."
    if "certificate_verify_failed" in lowered:
        return "HTTPS 인증서 검증에 실패했습니다. PC 시간과 네트워크 인증서를 확인해 주세요."
    if "cookie" in lowered and any(term in lowered for term in ("expired", "invalid", "failed to load", "does not look like")):
        return "선택한 쿠키가 만료됐거나 형식이 잘못됐습니다. 본인 브라우저에서 새 cookies.txt를 내보내 선택해 주세요."
    if any(term in lowered for term in ("login required", "log in", "login_required", "not authorized", "login is required", "login-required")):
        if has_cookies:
            return f"{service}가 선택한 로그인 세션으로 접근을 허용하지 않았습니다. 브라우저에서 게시물 접근과 세션 만료 여부를 확인해 주세요."
        return f"{service}가 로그인을 요구했습니다. 본인 계정으로 브라우저에서 접근 가능한 콘텐츠라면 cookies.txt를 선택해 주세요."
    if "no video formats found" in lowered or "video formats are missing" in lowered:
        return "영상 정보를 찾지 못했습니다. 사진 게시물인지 또는 영상 접근이 제한됐는지 확인해 주세요."
    if "empty media response" in lowered:
        return "Instagram에서 미디어 정보를 받지 못했습니다. 브라우저에서 게시물 접근 여부를 확인해 주세요. 로그인이 필요한 경우 cookies.txt를 선택하세요."
    if "private" in lowered or "unavailable" in lowered or "not found" in lowered:
        return "콘텐츠가 비공개이거나 삭제/차단된 상태일 수 있습니다."
    if "network" in lowered or "timed out" in lowered or "10013" in lowered or "connection" in lowered:
        return "네트워크 연결 또는 방화벽/보안 프로그램이 다운로드를 막고 있을 수 있습니다."
    if "ffmpeg" in lowered:
        return "영상과 음성 병합 단계에서 문제가 생겼습니다. 앱을 최신 버전으로 업데이트해 주세요."
    return message


class DownloadWorker(QObject):
    log = Signal(str)
    progress = Signal(int)
    finished = Signal(bool, str, object)

    def __init__(
        self,
        urls: list[str],
        output_dir: Path,
        cookies: Path | None,
        write_metadata: bool,
        include_videos: bool,
        include_images: bool,
        format_selector: str,
        platform_subfolders: bool,
    ) -> None:
        super().__init__()
        self.urls = urls
        self.output_dir = output_dir
        self.cookies = cookies
        self.write_metadata = write_metadata
        self.include_videos = include_videos
        self.include_images = include_images
        self.format_selector = format_selector
        self.platform_subfolders = platform_subfolders
        self.saved_files: list[str] = []

    def run(self) -> None:
        records: list[dict[str, str]] = []
        errors: list[str] = []
        total = len(self.urls)
        completed = 0

        try:
            for index, url in enumerate(self.urls, start=1):
                platform = platform_name(url)
                target_dir = dated_output_dir(self.output_dir, platform, self.platform_subfolders)
                write_source_url(target_dir, url)
                self.log.emit(f"[{index}/{total}] {platform}: {url}")
                self.log.emit(f"저장 위치: {target_dir}")
                result = download_urls(
                    [url],
                    target_dir,
                    format_selector=self.format_selector,
                    cookies=self.cookies,
                    write_metadata=self.write_metadata,
                    allow_multiple=False,
                    include_videos=self.include_videos,
                    include_images=self.include_images,
                    log=self.log.emit,
                    progress=None,
                    progress_hook=self.on_video_progress,
                )
                ok = bool(result.videos or result.images) and not result.errors
                if ok:
                    completed += 1
                    records.append(
                        {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "platform": platform,
                            "url": url,
                            "folder": str(target_dir),
                            "summary": result.summary(),
                            "status": "완료",
                        }
                    )
                    self.log.emit(f"완료: {result.summary()}")
                else:
                    error_text = "\n".join(friendly_error(error, platform, bool(self.cookies)) for error in result.errors) if result.errors else "다운로드된 파일이 없습니다."
                    errors.append(f"{platform}: {error_text}")
                    records.append(
                        {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "platform": platform,
                            "url": url,
                            "folder": str(target_dir),
                            "summary": error_text,
                            "status": "실패",
                        }
                    )
                self.progress.emit(int(index * 100 / max(total, 1)))
        except Exception as exc:
            self.finished.emit(False, f"오류: {friendly_error(str(exc))}", records)
            return

        if errors:
            message = f"{completed}/{total}개 다운로드 완료, {len(errors)}개 실패\n\n" + "\n".join(errors)
            self.finished.emit(False, message, records)
            return

        if completed:
            self.progress.emit(100)
            self.finished.emit(True, f"{completed}개 다운로드가 완료됐습니다.", records)
        else:
            self.finished.emit(False, "다운로드된 파일이 없습니다. URL, 공개 여부, 쿠키 설정을 확인하세요.", records)

    def on_video_progress(self, data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes")
            if total and downloaded:
                self.progress.emit(max(0, min(99, int(downloaded * 100 / total))))
            speed = data.get("speed")
            speed_text = f" · {speed / 1024 / 1024:.1f} MB/s" if speed else ""
            filename = data.get("filename")
            if filename:
                self.log.emit(f"영상 다운로드 중: {Path(filename).name}{speed_text}")
        elif status == "finished":
            filename = data.get("filename")
            if filename:
                self.saved_files.append(str(filename))
                self.log.emit(f"영상 저장됨: {Path(filename).name}")


class ThumbnailWorker(QObject):
    finished = Signal(str, bool, object, str, str)

    def __init__(self, url: str, cookies: Path | None) -> None:
        super().__init__()
        self.url = url
        self.cookies = cookies

    @Slot()
    def run(self) -> None:
        try:
            title = platform_name(self.url)
            thumbnail_url = ""
            parsed = urllib.parse.urlparse(self.url)
            video_id = ""
            if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
                video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
                if not video_id and parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
                    video_id = parsed.path.split("/")[2]
            elif parsed.hostname in ("youtu.be", "www.youtu.be"):
                video_id = parsed.path.strip("/").split("/")[0]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                # Preview does not need format extraction, Deno or playlist expansion.
                canonical = "https://www.youtube.com/watch?v=" + video_id
                thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                try:
                    endpoint = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": canonical, "format": "json"})
                    with urllib.request.urlopen(endpoint, timeout=10, context=tls_context()) as response:
                        title = str(json.load(response).get("title") or title)
                except Exception:
                    pass
            elif is_behance_url(self.url):
                images, videos = extract_behance_media(self.url, cookies=self.cookies)
                thumbnail_url = images[0] if images else ""
                title = "Behance"
            else:
                options: dict[str, Any] = {
                    "quiet": True,
                    "js_runtimes": bundled_js_runtimes(),
                    "no_warnings": True,
                    "skip_download": True,
                    "noplaylist": True,
                    "socket_timeout": 15,
                    "retries": 1,
                    "ignore_no_formats_error": True,
                    "http_headers": {"User-Agent": USER_AGENT},
                }
                if self.cookies:
                    options["cookiefile"] = str(self.cookies)
                with YoutubeDL(options) as ydl:
                    info = extract_instagram_info(ydl, self.url) if is_instagram_url(self.url) else ydl.extract_info(self.url, download=False)
                    if isinstance(info, dict) and info.get("_type") == "playlist":
                        info = next((entry for entry in info.get("entries", []) if entry), info)
                if isinstance(info, dict):
                    title = str(info.get("title") or platform_name(self.url))
                    thumbnail_url = str(info.get("thumbnail") or "")
                    thumbnails = info.get("thumbnails")
                    if not thumbnail_url and isinstance(thumbnails, list) and thumbnails:
                        thumbnail_url = str(thumbnails[-1].get("url") or "")
            if not thumbnail_url:
                self.finished.emit(self.url, False, None, title, "썸네일을 찾지 못했습니다.")
                return
            request = urllib.request.Request(thumbnail_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20, context=tls_context()) as response:
                data = response.read(4 * 1024 * 1024)
            self.finished.emit(self.url, True, data, title, "")
        except Exception as exc:
            self.finished.emit(self.url, False, None, platform_name(self.url), friendly_error(str(exc), platform_name(self.url), bool(self.cookies)))


class UpdateCheckWorker(QObject):
    finished = Signal(bool, object, str)

    def run(self) -> None:
        try:
            update = check_for_update()
        except Exception as exc:
            self.finished.emit(False, None, str(exc))
            return
        self.finished.emit(True, update, "")


class UpdateDownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(bool, object, str)

    def __init__(self, update: UpdateInfo) -> None:
        super().__init__()
        self.update = update

    def run(self) -> None:
        try:
            installer = download_installer(self.update, self.progress.emit)
        except Exception as exc:
            self.finished.emit(False, None, str(exc))
            return
        self.finished.emit(True, installer, "")


class MainWindow(QMainWindow):
    def __init__(self, font_family: str) -> None:
        super().__init__()
        self.font_family = font_family
        self.download_thread: QThread | None = None
        self.worker: DownloadWorker | None = None
        self.update_thread: QThread | None = None
        self.update_worker: QObject | None = None
        self.thumbnail_thread: QThread | None = None
        self.thumbnail_worker: QObject | None = None
        self.thumbnail_pending: list[str] = []
        self.pending_update: UpdateInfo | None = None
        self.pending_installer: Path | None = None
        self.silent_update_check = False
        self.settings = QSettings("KALLOS", APP_NAME)
        self.history_path = app_data_dir() / "history.json"
        self.history: list[dict[str, str]] = self.load_history()
        self.last_clipboard_text = ""
        self.last_output_dir: Path | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource_path("assets/fetch.ico"))))
        self.setMinimumSize(1180, 720)

        root = QWidget()
        root.setObjectName("AppRoot")
        page = QVBoxLayout(root)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        page.addWidget(self.top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        workspace = self.workspace()
        if sys.platform == "darwin":
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(workspace)
            body.addWidget(scroll, 1)
        else:
            body.addWidget(workspace, 1)
        body.addWidget(self.side_panel())
        page.addLayout(body, 1)

        self.setCentralWidget(root)
        self.apply_styles()
        self.load_settings()
        self.refresh_history()
        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.timeout.connect(self.scan_clipboard)
        self.clipboard_timer.start(1500)
        if "--interaction-test" not in sys.argv and "--smoke-test" not in sys.argv:
            QTimer.singleShot(5000, lambda: self.check_updates(silent=True))

    def top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 9, 18, 9)
        layout.setSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("TopTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        center = QLabel("Instagram  ·  YouTube  ·  Behance  ·  Vimeo")
        center.setObjectName("TopMeta")
        center.setAlignment(Qt.AlignCenter)

        brand = QLabel()
        brand.setObjectName("TopBrandLogo")
        brand.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        brand_pixmap = QPixmap(str(resource_path("assets/KALLOS_LOGO.png")))
        if not brand_pixmap.isNull():
            brand.setPixmap(brand_pixmap.scaledToHeight(22, Qt.SmoothTransformation))
        else:
            brand.setText("KALLOS")

        layout.addWidget(title, 0)
        layout.addWidget(center, 1)
        layout.addWidget(brand, 0)
        return bar

    def workspace(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Workspace")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        stage = QFrame()
        stage.setObjectName("Stage")
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(22, 20, 22, 18)
        stage_layout.setSpacing(10)
        if sys.platform == "darwin":
            stage_layout.setSizeConstraint(QLayout.SetMinimumSize)
            layout.setSizeConstraint(QLayout.SetMinimumSize)

        eyebrow = QLabel("DOWNLOAD QUEUE")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Media URLs")
        title.setObjectName("StageTitle")
        hint = QLabel("공개 콘텐츠는 바로 저장하고, 로그인 필요한 콘텐츠는 cookies.txt를 선택하세요.")
        hint.setObjectName("StageHint")

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("URL 하나 또는 여러 개를 붙여넣으세요.")
        self.url_input.returnPressed.connect(self.add_urls_from_input)

        action_row = QHBoxLayout()
        self.add_queue_button = QPushButton("큐에 추가")
        self.add_queue_button.clicked.connect(self.add_urls_from_input)
        self.clipboard_button = QPushButton("클립보드 추가")
        self.clipboard_button.clicked.connect(self.add_urls_from_clipboard)
        self.download_button = QPushButton("다운로드")
        self.download_button.setObjectName("PrimaryButton")
        self.download_button.clicked.connect(self.start_download)
        self.open_folder_button = QPushButton("저장 폴더 열기")
        self.open_folder_button.clicked.connect(self.open_output)
        self.open_last_button = QPushButton("최근 폴더 열기")
        self.open_last_button.clicked.connect(self.open_last_output)
        action_row.setSpacing(8)
        action_row.addWidget(self.add_queue_button)
        action_row.addWidget(self.clipboard_button)
        action_row.addWidget(self.download_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addWidget(self.open_last_button)
        action_row.addStretch(1)

        self.queue_list = QListWidget()
        self.queue_list.setObjectName("QueueList")
        self.queue_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.queue_list.setIconSize(QSize(128, 72))
        self.queue_list.setSpacing(6)
        self.queue_list.setAlternatingRowColors(False)
        self.queue_list.setWordWrap(True)

        queue_actions = QHBoxLayout()
        queue_actions.setSpacing(8)
        self.remove_queue_button = QPushButton("선택 제거")
        self.remove_queue_button.clicked.connect(self.remove_selected_queue_items)
        self.clear_queue_button = QPushButton("큐 비우기")
        self.clear_queue_button.clicked.connect(self.clear_queue)
        queue_actions.addWidget(self.remove_queue_button)
        queue_actions.addWidget(self.clear_queue_button)
        queue_actions.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)

        stage_layout.addWidget(eyebrow)
        stage_layout.addWidget(title)
        stage_layout.addWidget(hint)
        stage_layout.addWidget(self.url_input)
        stage_layout.addLayout(action_row)
        stage_layout.addWidget(self.queue_list)
        stage_layout.addLayout(queue_actions)
        stage_layout.addWidget(self.progress)
        stage_layout.addStretch(1)

        log_header = QHBoxLayout()
        log_label = QLabel("ACTIVITY")
        log_label.setObjectName("Eyebrow")
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusLabel")
        log_header.addWidget(log_label)
        log_header.addStretch(1)
        log_header.addWidget(self.status_label)

        self.log_output = QPlainTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("다운로드 진행 상황과 오류가 여기에 표시됩니다.")

        history_header = QHBoxLayout()
        history_label = QLabel("HISTORY")
        history_label.setObjectName("Eyebrow")
        self.clear_history_button = QPushButton("기록 지우기")
        self.clear_history_button.clicked.connect(self.clear_history)
        history_header.addWidget(history_label)
        history_header.addStretch(1)
        history_header.addWidget(self.clear_history_button)

        self.history_table = QTableWidget(0, 5)
        self.history_table.setObjectName("HistoryTable")
        self.history_table.setHorizontalHeaderLabels(["시간", "플랫폼", "상태", "요약", "URL"])
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.cellDoubleClicked.connect(self.open_history_folder)

        layout.addWidget(stage, 2)
        layout.addLayout(log_header)
        layout.addWidget(self.log_output, 1)
        layout.addLayout(history_header)
        layout.addWidget(self.history_table, 1)
        return frame

    def side_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("SidePanel")
        panel.setFixedWidth(318)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        heading = QLabel("OUTPUT")
        heading.setObjectName("Eyebrow")
        layout.addWidget(heading)

        layout.addWidget(self.field_label("저장 폴더"))
        output_row = QHBoxLayout()
        self.output_input = QLineEdit(str(default_download_dir()))
        browse_output = QPushButton("선택")
        browse_output.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(browse_output)
        layout.addLayout(output_row)

        layout.addWidget(self.field_label("로그인 쿠키"))
        cookie_row = QHBoxLayout()
        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("cookies.txt")
        browse_cookies = QPushButton("선택")
        browse_cookies.clicked.connect(self.choose_cookies)
        cookie_row.addWidget(self.cookies_input, 1)
        cookie_row.addWidget(browse_cookies)
        layout.addLayout(cookie_row)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        layout.addWidget(self.field_label("저장 항목"))
        self.video_check = QCheckBox("영상 저장")
        self.video_check.setChecked(True)
        self.image_check = QCheckBox("이미지 저장 (Instagram · Behance)")
        self.image_check.setChecked(True)
        self.metadata_check = QCheckBox("설명과 정보 JSON 저장")
        layout.addWidget(self.video_check)
        layout.addWidget(self.image_check)
        layout.addWidget(self.metadata_check)

        layout.addWidget(self.field_label("편의 기능"))
        self.clipboard_check = QCheckBox("클립보드 URL 자동 감지")
        self.clipboard_check.setChecked(True)
        self.platform_folder_check = QCheckBox("플랫폼/오늘 날짜 폴더로 저장")
        self.platform_folder_check.setChecked(True)
        layout.addWidget(self.clipboard_check)
        layout.addWidget(self.platform_folder_check)

        layout.addWidget(self.field_label("영상 품질"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("최고 화질 - 영상+음성 자동 병합", DEFAULT_VIDEO_FORMAT)
        self.quality_combo.addItem("호환 우선 - MP4 단일 파일", COMPAT_VIDEO_FORMAT)
        layout.addWidget(self.quality_combo)

        info = QLabel("앱에 ffmpeg를 포함해 YouTube/Vimeo의 영상+음성 병합을 자동 처리합니다.")
        info.setObjectName("FinePrint")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.update_button = QPushButton("업데이트 확인")
        self.update_button.clicked.connect(self.check_updates)
        layout.addWidget(self.update_button)
        layout.addStretch(1)

        return panel

    def field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", self.output_input.text())
        if folder:
            self.output_input.setText(folder)
            self.save_settings()

    def choose_cookies(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "cookies.txt 선택", "", "Text files (*.txt);;All files (*)")
        if file_name:
            self.cookies_input.setText(file_name)
            self.save_settings()

    def open_output(self) -> None:
        output_dir = Path(self.output_input.text()).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir)))

    def open_last_output(self) -> None:
        target = self.last_output_dir or Path(self.output_input.text()).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def add_urls_from_input(self) -> None:
        urls = extract_urls(self.url_input.text())
        if not urls:
            QMessageBox.warning(self, APP_NAME, "추가할 URL이 없습니다.")
            return
        added = self.add_urls_to_queue(urls)
        self.url_input.clear()
        self.append_log(f"큐에 {added}개 URL을 추가했습니다.")

    def add_urls_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        urls = extract_urls(text)
        if not urls:
            QMessageBox.information(self, APP_NAME, "클립보드에서 URL을 찾지 못했습니다.")
            return
        added = self.add_urls_to_queue(urls)
        self.append_log(f"클립보드에서 {added}개 URL을 추가했습니다.")

    def add_urls_to_queue(self, urls: list[str]) -> int:
        existing = set(self.all_queue_urls())
        added = 0
        for url in urls:
            if url in existing:
                continue
            item = QListWidgetItem(url)
            item.setData(Qt.UserRole, url)
            item.setCheckState(Qt.Checked)
            item.setToolTip(url)
            item.setSizeHint(QSize(0, 92))
            self.queue_list.addItem(item)
            existing.add(url)
            self.enqueue_thumbnail(url)
            added += 1
        return added

    def remove_selected_queue_items(self) -> None:
        for item in self.queue_list.selectedItems():
            self.queue_list.takeItem(self.queue_list.row(item))

    def clear_queue(self) -> None:
        self.thumbnail_pending.clear()
        self.queue_list.clear()

    def all_queue_urls(self) -> list[str]:
        urls: list[str] = []
        for index in range(self.queue_list.count()):
            item = self.queue_list.item(index)
            urls.append(str(item.data(Qt.UserRole) or item.text()))
        return urls

    def queued_urls(self) -> list[str]:
        urls: list[str] = []
        for index in range(self.queue_list.count()):
            item = self.queue_list.item(index)
            if item.checkState() == Qt.Checked:
                urls.append(str(item.data(Qt.UserRole) or item.text()))
        return urls

    def remove_checked_queue_items(self) -> None:
        for index in range(self.queue_list.count() - 1, -1, -1):
            item = self.queue_list.item(index)
            if item.checkState() == Qt.Checked:
                self.queue_list.takeItem(index)

    def scan_clipboard(self) -> None:
        if not hasattr(self, "clipboard_check") or not self.clipboard_check.isChecked():
            return
        text = QApplication.clipboard().text().strip()
        if not text or text == self.last_clipboard_text:
            return
        self.last_clipboard_text = text
        urls = extract_urls(text)
        if not urls:
            return
        added = self.add_urls_to_queue(urls)
        if added:
            self.append_log(f"클립보드 URL 자동 추가: {added}개")

    def load_settings(self) -> None:
        self.output_input.setText(self.settings.value("output_dir", str(default_download_dir())))
        self.cookies_input.setText(self.settings.value("cookies", ""))
        self.video_check.setChecked(self.settings.value("include_videos", True, type=bool))
        self.image_check.setChecked(self.settings.value("include_images", True, type=bool))
        self.metadata_check.setChecked(self.settings.value("write_metadata", False, type=bool))
        self.clipboard_check.setChecked(self.settings.value("clipboard_watch", True, type=bool))
        self.platform_folder_check.setChecked(self.settings.value("platform_folders", True, type=bool))
        quality_index = self.settings.value("quality_index", 0, type=int)
        if 0 <= quality_index < self.quality_combo.count():
            self.quality_combo.setCurrentIndex(quality_index)

    def save_settings(self) -> None:
        self.settings.setValue("output_dir", self.output_input.text())
        self.settings.setValue("cookies", self.cookies_input.text())
        self.settings.setValue("include_videos", self.video_check.isChecked())
        self.settings.setValue("include_images", self.image_check.isChecked())
        self.settings.setValue("write_metadata", self.metadata_check.isChecked())
        self.settings.setValue("clipboard_watch", self.clipboard_check.isChecked())
        self.settings.setValue("platform_folders", self.platform_folder_check.isChecked())
        self.settings.setValue("quality_index", self.quality_combo.currentIndex())

    def load_history(self) -> list[dict[str, str]]:
        try:
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save_history(self) -> None:
        self.history_path.write_text(
            json.dumps(self.history[:HISTORY_LIMIT], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_history_records(self, records: list[dict[str, str]]) -> None:
        if not records:
            return
        self.history = records + self.history
        self.history = self.history[:HISTORY_LIMIT]
        self.save_history()
        self.refresh_history()

    def refresh_history(self) -> None:
        if not hasattr(self, "history_table"):
            return
        self.history_table.setRowCount(0)
        for record in self.history[:HISTORY_LIMIT]:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            values = [
                record.get("time", ""),
                record.get("platform", ""),
                record.get("status", ""),
                record.get("summary", ""),
                record.get("url", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.history_table.setItem(row, column, item)
            self.history_table.item(row, 0).setData(Qt.UserRole, record.get("folder", ""))
        self.history_table.resizeColumnsToContents()
        self.history_table.setColumnWidth(3, 240)
        self.history_table.setColumnWidth(4, 320)

    def open_history_folder(self, row: int, _column: int) -> None:
        item = self.history_table.item(row, 0)
        if item is None:
            return
        folder = item.data(Qt.UserRole)
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def clear_history(self) -> None:
        self.history = []
        self.save_history()
        self.refresh_history()

    def enqueue_thumbnail(self, url: str) -> None:
        if url not in self.thumbnail_pending:
            self.thumbnail_pending.append(url)
        if self.thumbnail_thread is None:
            self.start_next_thumbnail()

    def start_next_thumbnail(self) -> None:
        if self.thumbnail_thread is not None:
            return
        while self.thumbnail_pending:
            url = self.thumbnail_pending.pop(0)
            item = self.find_queue_item(url)
            if item is None:
                continue
            item.setText(f"{platform_name(url)}\n미리보기 불러오는 중...")
            item.setToolTip(url)
            self.fetch_thumbnail(url)
            return

    def find_queue_item(self, url: str) -> QListWidgetItem | None:
        for index in range(self.queue_list.count()):
            item = self.queue_list.item(index)
            if str(item.data(Qt.UserRole) or item.text()) == url:
                return item
        return None

    def fetch_thumbnail(self, url: str) -> None:
        if self.thumbnail_thread is not None:
            return
        cookies = Path(self.cookies_input.text()).expanduser().resolve() if self.cookies_input.text().strip() else None
        if cookies and not cookies.exists():
            cookies = None

        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailWorker(url, cookies)
        self.thumbnail_worker.moveToThread(self.thumbnail_thread)
        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_worker.finished.connect(self.thumbnail_finished, Qt.QueuedConnection)
        self.thumbnail_worker.finished.connect(self.thumbnail_thread.quit)
        self.thumbnail_worker.finished.connect(self.thumbnail_worker.deleteLater)
        self.thumbnail_thread.finished.connect(self.thumbnail_thread.deleteLater)
        self.thumbnail_thread.finished.connect(self.clear_thumbnail_worker)
        self.thumbnail_thread.start()

    @Slot(str, bool, object, str, str)
    def thumbnail_finished(self, url: str, ok: bool, data: object, title: str, error: str) -> None:
        item = self.find_queue_item(url)
        if item is None:
            return
        display_title = title.strip() if title.strip() else platform_name(url)
        item.setText(f"{display_title}\n{url}")
        item.setToolTip(error if error else url)
        if ok and isinstance(data, (bytes, bytearray)):
            image = QImage.fromData(bytes(data))
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                item.setIcon(QIcon(pixmap.scaled(QSize(128, 72), Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                return
        item.setText(f"{display_title}\n미리보기 없음 - {url}")
        if error:
            self.append_log(f"미리보기 실패: {error}")

    @Slot()
    def clear_thumbnail_worker(self) -> None:
        self.thumbnail_thread = None
        self.thumbnail_worker = None
        self.start_next_thumbnail()

    def closeEvent(self, event: object) -> None:
        if any(thread is not None for thread in (self.download_thread, self.thumbnail_thread, self.update_thread)):
            event.ignore()
            self.status_label.setText("작업 완료 후 닫아 주세요")
            return
        self.save_settings()
        super().closeEvent(event)

    def start_download(self) -> None:
        if self.url_input.text().strip():
            self.add_urls_to_queue(extract_urls(self.url_input.text()))
            self.url_input.clear()

        urls = self.queued_urls()
        if not urls:
            message = "다운로드할 URL을 큐에 추가하세요."
            if self.queue_list.count():
                message = "다운로드할 항목을 체크하세요."
            QMessageBox.warning(self, APP_NAME, message)
            return

        if not self.video_check.isChecked() and not self.image_check.isChecked():
            QMessageBox.warning(self, APP_NAME, "저장할 항목을 하나 이상 선택하세요.")
            return

        self.save_settings()
        output_dir = Path(self.output_input.text()).expanduser().resolve()
        cookies = Path(self.cookies_input.text()).expanduser().resolve() if self.cookies_input.text().strip() else None
        if cookies and not cookies.exists():
            QMessageBox.warning(self, APP_NAME, "쿠키 파일을 찾을 수 없습니다.")
            return

        self.log_output.clear()
        self.progress.setValue(0)
        self.status_label.setText("Running")
        self.set_busy(True)
        self.append_log(f"다운로드를 시작합니다. 큐: {len(urls)}개")
        self.append_log(f"저장 폴더: {output_dir}")
        self.last_output_dir = output_dir

        self.download_thread = QThread()
        self.worker = DownloadWorker(
            urls,
            output_dir,
            cookies,
            self.metadata_check.isChecked(),
            self.video_check.isChecked(),
            self.image_check.isChecked(),
            self.quality_combo.currentData(),
            self.platform_folder_check.isChecked(),
        )
        self.worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.download_finished, Qt.QueuedConnection)
        self.worker.finished.connect(self.download_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.finished.connect(self.clear_download_worker)
        self.download_thread.start()

    @Slot()
    def clear_download_worker(self) -> None:
        self.download_thread = None
        self.worker = None

    def check_updates(self, silent: bool = False) -> None:
        if self.update_thread is not None or self.download_thread is not None:
            return
        self.silent_update_check = silent
        self.status_label.setText("Checking")
        self.update_button.setEnabled(False)
        self.append_log(f"업데이트 확인 중... 현재 버전 {APP_VERSION}")

        self.update_thread = QThread()
        self.update_worker = UpdateCheckWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.finished.connect(self.update_check_finished, Qt.QueuedConnection)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self.clear_update_worker)
        self.update_thread.start()

    @Slot(bool, object, str)
    def update_check_finished(self, ok: bool, update: object, error: str) -> None:
        self.status_label.setText("Ready")
        self.update_button.setEnabled(True)
        if not ok:
            if not self.silent_update_check:
                QMessageBox.warning(self, APP_NAME, f"업데이트 확인에 실패했습니다.\n\n{error}")
            self.append_log(f"업데이트 확인 실패: {error}")
            return
        if update is None:
            if not self.silent_update_check:
                QMessageBox.information(self, APP_NAME, f"최신 버전입니다. ({APP_VERSION})")
            self.append_log("최신 버전입니다.")
            return

        if self.download_thread is not None:
            self.append_log("다운로드가 끝난 뒤 업데이트를 다시 확인해 주세요.")
            return
        assert isinstance(update, UpdateInfo)
        self.append_log(f"새 버전 발견: {update.version}")
        answer = QMessageBox.question(
            self,
            APP_NAME,
            f"새 버전 {update.version}이 있습니다.\n\n설치 파일을 내려받고 업데이트할까요?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            if self.update_thread is None:
                self.download_update(update)
            else:
                self.pending_update = update

    def download_update(self, update: UpdateInfo) -> None:
        if self.update_thread is not None:
            return
        self.status_label.setText("Updating")
        self.progress.setValue(0)
        self.set_busy(True)
        self.append_log(f"업데이트 다운로드 중: {update.asset_name}")

        self.update_thread = QThread()
        self.update_worker = UpdateDownloadWorker(update)
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.progress.connect(self.progress.setValue)
        self.update_worker.finished.connect(self.update_download_finished, Qt.QueuedConnection)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self.clear_update_worker)
        self.update_thread.start()

    @Slot(bool, object, str)
    def update_download_finished(self, ok: bool, installer: object, error: str) -> None:
        self.set_busy(False)
        if not ok:
            self.status_label.setText("Error")
            QMessageBox.critical(self, APP_NAME, f"업데이트 다운로드에 실패했습니다.\n\n{error}")
            self.append_log(f"업데이트 다운로드 실패: {error}")
            return

        self.pending_installer = Path(installer)

    def install_pending_update(self) -> None:
        self.clipboard_timer.stop()
        self.thumbnail_pending.clear()
        if self.thumbnail_thread is not None:
            QTimer.singleShot(250, self.install_pending_update)
            return
        installer_path = self.pending_installer
        self.pending_installer = None
        if installer_path is None:
            return
        self.save_settings()
        if sys.platform == "darwin":
            try:
                subprocess.run(["/usr/bin/open", str(installer_path)], check=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                self.clipboard_timer.start(1500)
                QMessageBox.critical(self, APP_NAME, f"업데이트 파일을 열 수 없습니다.\n{exc}")
                return
            QMessageBox.information(self, APP_NAME,
                "업데이트 파일을 열었습니다. Fetch가 종료되면 새 Fetch를 응용 프로그램 폴더로 옮겨 기존 앱을 교체해 주세요.")
            QApplication.quit()
            return
        install_dir = Path(__file__).resolve().parent.parent
        if not (install_dir / "Fetch.exe").exists():
            install_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP_NAME
        try:
            subprocess.Popen(
                [str(installer_path), "/SILENT", "/NORESTART", f"/DIR={install_dir}", "/RESTARTFETCH=1"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            self.clipboard_timer.start(1500)
            QMessageBox.critical(self, APP_NAME, f"업데이트 설치를 시작할 수 없습니다.\n{exc}")
            return
        QApplication.quit()

    @Slot()
    def clear_update_worker(self) -> None:
        self.update_thread = None
        self.update_worker = None
        if self.pending_installer is not None:
            self.install_pending_update()
            return
        if self.pending_update is not None:
            update = self.pending_update
            self.pending_update = None
            self.download_update(update)

    @Slot(str)
    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    @Slot(bool, str, object)
    def download_finished(self, ok: bool, message: str, records: object) -> None:
        self.append_log(message)
        if isinstance(records, list):
            self.add_history_records(records)
        if ok:
            self.remove_checked_queue_items()
        self.set_busy(False)
        self.status_label.setText("Complete" if ok else "Error")
        if ok:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                f"{message}\n\n저장 폴더를 열까요?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.open_last_output()
        else:
            QMessageBox.critical(self, APP_NAME, message)

    def set_busy(self, busy: bool) -> None:
        controls = [
            self.add_queue_button,
            self.clipboard_button,
            self.remove_queue_button,
            self.clear_queue_button,
            self.download_button,
            self.open_folder_button,
            self.open_last_button,
            self.update_button,
            self.url_input,
            self.queue_list,
            self.output_input,
            self.cookies_input,
            self.video_check,
            self.image_check,
            self.metadata_check,
            self.clipboard_check,
            self.platform_folder_check,
            self.quality_combo,
        ]
        for control in controls:
            control.setEnabled(not busy)
        self.download_button.setText("다운로드 중..." if busy else "다운로드")

    def apply_styles(self) -> None:
        font_stack = f'"{self.font_family}", "Pretendard", "Segoe UI", "Malgun Gothic", sans-serif'
        self.setStyleSheet(
            f"""
            QWidget {{
                background: #0e1116;
                color: #d9dde5;
                font-family: {font_stack};
                font-size: 12px;
            }}
            #TopBar {{
                background: #12151a;
                border-bottom: 1px solid #222730;
            }}
            #TopMeta {{
                color: #7f8794;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0px;
            }}
            #TopTitle {{
                color: #f1f3f6;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 0px;
            }}
            #TopBrandLogo {{
                min-width: 104px;
            }}
            #Workspace {{
                background: #0d1015;
                border-right: 1px solid #222730;
            }}
            #Stage {{
                background: #11151b;
                border: 1px solid #28303a;
                border-radius: 6px;
            }}
            #StageTitle {{
                color: #f0f2f6;
                font-size: 21px;
                font-weight: 800;
            }}
            #StageHint, #FinePrint {{
                color: #8b94a3;
                font-size: 11px;
            }}
            #SidePanel {{
                background: #13161c;
                border-left: 1px solid #242a33;
            }}
            #Eyebrow {{
                color: #858e9d;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0px;
            }}
            #FieldLabel {{
                color: #9ca5b4;
                font-size: 11px;
                font-weight: 700;
            }}
            #StatusLabel {{
                color: #d8bd65;
                font-size: 11px;
                font-weight: 800;
            }}
            #Divider {{
                background: #2a2f3a;
            }}
            QLabel {{
                background: transparent;
            }}
            QLineEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {{
                background: #191d24;
                border: 1px solid #2c333e;
                border-radius: 5px;
                color: #e8ebf1;
                padding: 8px 10px;
                selection-background-color: #d8bd65;
                selection-color: #101216;
                font-family: {font_stack};
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
                border-color: #d8bd65;
            }}
            QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{
                color: #69717d;
                background: #151922;
            }}
            #LogOutput {{
                min-height: 132px;
            }}
            #QueueList {{
                min-height: 164px;
                padding: 6px;
            }}
            #HistoryTable {{
                min-height: 104px;
                gridline-color: #2b313c;
                padding: 0;
            }}
            QHeaderView::section {{
                background: #151922;
                color: #8e97a6;
                border: 0;
                border-bottom: 1px solid #2c333e;
                padding: 5px;
                font-weight: 700;
            }}
            QListWidget::item, QTableWidget::item {{
                padding: 5px;
            }}
            QListWidget::item {{
                border: 1px solid transparent;
                border-radius: 5px;
                margin: 2px;
            }}
            QListWidget::item:hover {{
                background: #202630;
                border-color: #333b47;
            }}
            QListWidget::indicator {{
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1px solid #596371;
                background: #11151b;
            }}
            QListWidget::indicator:checked {{
                background: #d8bd65;
                border-color: #d8bd65;
            }}
            QListWidget::item:selected, QTableWidget::item:selected {{
                background: #d8bd65;
                color: #111317;
            }}
            QPushButton {{
                background: #1c2129;
                border: 1px solid #303743;
                border-radius: 5px;
                color: #e6e9ef;
                padding: 8px 12px;
                min-width: 82px;
                font-weight: 700;
                font-family: {font_stack};
            }}
            QPushButton:hover {{
                background: #252b34;
                border-color: #414957;
            }}
            QPushButton:disabled {{
                color: #68707c;
                background: #171b22;
                border-color: #252a33;
            }}
            #PrimaryButton {{
                background: #d8bd65;
                border-color: #d8bd65;
                color: #111317;
                min-width: 118px;
            }}
            #PrimaryButton:hover {{
                background: #e2ca7a;
            }}
            QProgressBar {{
                border: 1px solid #2b323d;
                border-radius: 3px;
                height: 6px;
                background: #080a0e;
                font-family: {font_stack};
            }}
            QProgressBar::chunk {{
                background: #d8bd65;
                border-radius: 3px;
            }}
            QCheckBox {{
                background: transparent;
                color: #d6dae2;
                spacing: 8px;
                font-family: {font_stack};
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #46505e;
                background: #191d25;
            }}
            QCheckBox::indicator:checked {{
                background: #d8bd65;
                border-color: #d8bd65;
            }}
            QComboBox::drop-down {{
                border: 0;
                width: 28px;
            }}
            QMessageBox QLabel, QMessageBox QPushButton {{
                font-family: {font_stack};
            }}
            """
        )


def main() -> int:
    if "--self-test" in sys.argv:
        required_assets = [
            resource_path("assets/fetch.ico"),
            resource_path("assets/fonts/PretendardVariable.ttf"),
        ]
        missing = [str(path) for path in required_assets if not path.exists()]
        if missing:
            print("Missing required assets: " + ", ".join(missing), file=sys.stderr)
            return 1
        app = QApplication.instance() or QApplication([sys.argv[0], "-platform", "offscreen"])
        font_family = load_pretendard(app)
        probe = QWidget()
        probe.resize(320, 160)
        probe.show()
        app.processEvents()
        if probe.grab().isNull() or not font_family:
            return 2
        import ssl
        import imageio_ffmpeg
        if not tls_context().get_ca_certs():
            return 3
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-version"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deno = bundled_js_runtimes()["deno"].get("path")
        if deno:
            subprocess.run([deno, "--version"], check=True, stdout=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print(f"Fetch {APP_VERSION}: Qt, fonts, SSL, downloader and ffmpeg OK")
        return 0

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(resource_path("assets/fetch.ico"))))
    font_family = load_pretendard(app)
    window = MainWindow(font_family)
    window.show()
    if "--interaction-test" in sys.argv:
        import time
        index = sys.argv.index("--interaction-test")
        url, destination = sys.argv[index + 1:index + 3]
        window.clipboard_timer.stop()
        window.clipboard_check.setChecked(True)
        QApplication.clipboard().setText(url)
        window.scan_clipboard()
        deadline = time.monotonic() + 60
        def check_preview() -> None:
            if window.thumbnail_thread is not None and time.monotonic() < deadline:
                QTimer.singleShot(100, check_preview)
                return
            item = window.queue_list.item(0)
            ok = window.thumbnail_thread is None and item is not None and not item.icon().isNull()
            if not ok:
                print(window.log_output.toPlainText(), file=sys.stderr)
            captured = window.grab().save(destination)
            app.exit(0 if ok and captured else 1)
        QTimer.singleShot(100, check_preview)
    if "--smoke-test" in sys.argv:
        window.clipboard_timer.stop()
        output = Path(sys.argv[sys.argv.index("--smoke-test") + 1])
        def capture_smoke_test() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            screenshot = window.grab()
            app.exit(0 if not screenshot.isNull() and screenshot.save(str(output)) else 1)
        QTimer.singleShot(500, capture_smoke_test)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())



