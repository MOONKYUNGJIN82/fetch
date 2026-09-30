from __future__ import annotations

import html
import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request
from network_support import tls_context
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL
from yt_dlp.extractor.instagram import InstagramIE
from yt_dlp.networking import Request
from yt_dlp.utils import DownloadError

try:
    import imageio_ffmpeg
except Exception:  # pragma: no cover - optional runtime helper
    imageio_ffmpeg = None


DEFAULT_TEMPLATE = "%(title|media)s_%(id)s.%(ext)s"
DEFAULT_VIDEO_FORMAT = "bv*+ba/b"
COMPAT_VIDEO_FORMAT = "best[ext=mp4]/best"
INSTAGRAM_VIDEO_FORMAT = "best/best[ext=mp4]/bv*+ba/b"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".webm")


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int], None]


@dataclass
class DownloadResult:
    videos: int = 0
    images: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.videos or self.images) and not self.errors

    def summary(self) -> str:
        parts = []
        if self.videos:
            parts.append(f"videos: {self.videos}")
        if self.images:
            parts.append(f"images: {self.images}")
        if self.skipped:
            parts.append(f"skipped: {self.skipped}")
        if self.errors:
            parts.append(f"errors: {len(self.errors)}")
        return ", ".join(parts) if parts else "nothing downloaded"


class CallbackLogger:
    def __init__(self, log: LogCallback | None = None) -> None:
        self.log = log or (lambda message: None)

    def debug(self, message: str) -> None:
        if not message.startswith("[debug]"):
            self.log(message)

    def warning(self, message: str) -> None:
        self.log(f"Warning: {message}")

    def error(self, message: str) -> None:
        self.log(f"Error: {message}")


def is_behance_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host == "behance.net" or host.endswith(".behance.net")


def sanitize_filename(value: str, fallback: str = "download") -> str:
    value = urllib.parse.unquote(value)
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return value[:120] or fallback


def open_media_url(request, timeout: int, cookies: Path | None = None):
    if cookies is None:
        return urllib.request.urlopen(request, timeout=timeout, context=tls_context())
    jar = http.cookiejar.MozillaCookieJar(str(cookies))
    try:
        jar.load(ignore_discard=True, ignore_expires=False)
    except (OSError, http.cookiejar.LoadError) as exc:
        raise ValueError("선택한 쿠키 파일을 읽을 수 없습니다. Netscape 형식의 cookies.txt를 선택해 주세요.") from exc
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=tls_context()),
        urllib.request.HTTPCookieProcessor(jar),
    )
    return opener.open(request, timeout=timeout)


def fetch_text(url: str, cookies: Path | None = None) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with open_media_url(request, timeout=30, cookies=cookies) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize_page_text(page: str) -> str:
    text = html.unescape(page)
    replacements = {
        "\\/": "/",
        "\\u002F": "/",
        "\\u002f": "/",
        "\\u0026": "&",
        "\\u003D": "=",
        "\\u003d": "=",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def media_score(url: str) -> int:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    score = 0
    if "/source/" in path:
        score += 10000
    for match in re.finditer(r"(?:max_|disp_|fs_)?(\d{3,5})", path):
        score = max(score, int(match.group(1)))
    if ".mp4" in path or ".webm" in path:
        score += 5000
    return score


def extension_from_url(url: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS:
        return suffix
    return ".bin"


def extract_behance_media(url: str, log: LogCallback | None = None, cookies: Path | None = None) -> tuple[list[str], list[str]]:
    logger = log or (lambda message: None)
    logger("Fetching Behance page...")
    page = normalize_page_text(fetch_text(url, cookies=cookies) if cookies else fetch_text(url))

    candidates = re.findall(
        r"https?://[^\"'<>\s\\]+?\.(?:jpg|jpeg|png|webp|gif|mp4|mov|m4v|webm)(?:\?[^\"'<>\s\\]+)?",
        page,
        flags=re.IGNORECASE,
    )

    images: dict[str, str] = {}
    videos: dict[str, str] = {}
    for candidate in candidates:
        cleaned = candidate.rstrip(".,);]")
        parsed = urllib.parse.urlparse(cleaned)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()
        if not (host == "behance.net" or host.endswith(".behance.net")):
            continue
        if "/project_modules/" not in path:
            continue
        suffix = Path(path).suffix.lower()
        key = Path(path).name.lower()
        if suffix in IMAGE_EXTENSIONS:
            previous = images.get(key)
            if previous is None or media_score(cleaned) > media_score(previous):
                images[key] = cleaned
        elif suffix in VIDEO_EXTENSIONS:
            previous = videos.get(key)
            if previous is None or media_score(cleaned) > media_score(previous):
                videos[key] = cleaned

    return list(images.values()), list(videos.values())


def is_instagram_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host == "instagram.com" or host.endswith(".instagram.com")


class FetchInstagramIE(InstagramIE):
    @classmethod
    def ie_key(cls):
        return "Instagram"

    def _extract_product_media(self, product_media):
        info = super()._extract_product_media(product_media)
        # Preserve the actual media kind; a missing video URL alone is not proof of a photo.
        info["fetch_media_type"] = product_media.get("media_type")
        return info


def extract_instagram_info(ydl, url):
    ydl.add_info_extractor(FetchInstagramIE(ydl))
    ydl.params["ignore_no_formats_error"] = True
    return ydl.extract_info(url, download=False, process=False, ie_key="Instagram")


def download_instagram(ydl, url, output_dir, include_videos, include_images, logger):
    result = DownloadResult()
    info = extract_instagram_info(ydl, url)
    if not info:
        result.errors.append("Instagram returned no media information.")
        return result
    entries = info.get("entries") if info.get("_type") == "playlist" else [info]
    for index, entry in enumerate(entries or [], 1):
        try:
            if entry.get("fetch_media_type") == 1:
                if not include_images:
                    result.skipped += 1
                    continue
                images = [t for t in entry.get("thumbnails", []) if t.get("url")]
                if not images:
                    raise ValueError("Instagram photo URL is missing.")
                # yt-dlp orders Instagram candidates from smallest to largest when dimensions are absent.
                photo = max(enumerate(images), key=lambda pair: ((pair[1].get("width") or 0) * (pair[1].get("height") or 0), pair[0]))[1]
                suffix = extension_from_url(photo["url"])
                if suffix not in IMAGE_EXTENSIONS:
                    suffix = ".jpg"
                target = output_dir / (sanitize_filename(str(info.get("id") or "instagram")) +
                    "_" + str(index).zfill(2) + "_" + sanitize_filename(str(entry.get("id") or index)) + suffix)
                temporary = target.with_suffix(target.suffix + ".part")
                try:
                    with ydl.urlopen(Request(photo["url"], headers={"Referer": "https://www.instagram.com/"})) as response:
                        content_type = response.headers.get("Content-Type", "").lower()
                        if not content_type.startswith("image/"):
                            raise ValueError("Instagram did not return an image.")
                        with temporary.open("wb") as stream:
                            while chunk := response.read(128 * 1024):
                                stream.write(chunk)
                    if not temporary.stat().st_size:
                        raise ValueError("Instagram returned an empty image.")
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                result.images += 1
                logger(f"Image saved: {target.name}")
            elif include_videos:
                if not entry.get("formats") and not entry.get("url"):
                    raise ValueError("Instagram video formats are missing; media access could not be verified.")
                processed = ydl.process_ie_result(dict(entry), download=True)
                if not processed:
                    raise ValueError("Instagram video download did not complete.")
                result.videos += 1
            else:
                result.skipped += 1
        except Exception as exc:
            result.errors.append(f"Instagram item {index}: {exc}")
            logger(result.errors[-1])
    return result


def project_folder_from_url(output_dir: Path, url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if "gallery" in parts:
        index = parts.index("gallery")
        name_parts = parts[index + 1 :]
        name = "_".join(name_parts[:2]) if name_parts else "behance_project"
    else:
        name = parts[-1] if parts else parsed.netloc
    return output_dir / sanitize_filename(name, "behance_project")


def download_direct_files(
    urls: list[str],
    folder: Path,
    kind: str,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    cookies: Path | None = None,
    errors: list[str] | None = None,
) -> int:
    logger = log or (lambda message: None)
    folder.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    total = len(urls)

    for index, url in enumerate(urls, start=1):
        suffix = extension_from_url(url)
        source_name = sanitize_filename(Path(urllib.parse.urlparse(url).path).stem, f"{kind}_{index:03d}")
        target = folder / f"{index:03d}_{source_name}{suffix}"
        if target.exists() and target.stat().st_size > 0:
            downloaded += 1
            logger(f"Already exists: {target.name}")
            continue

        logger(f"Downloading {kind} {index}/{total}: {target.name}")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.behance.net/"})
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            with open_media_url(request, timeout=60, cookies=cookies) as response, temporary.open("wb") as file:
                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" in content_type or "application/json" in content_type:
                    raise ValueError("서버가 미디어 대신 오류 페이지를 반환했습니다.")
                expected = int(response.headers.get("Content-Length") or 0)
                received = 0
                while chunk := response.read(1024 * 128):
                    file.write(chunk)
                    received += len(chunk)
                if not received or (expected and expected != received):
                    raise ValueError("미디어 파일 다운로드가 중단되거나 비어 있습니다.")
            temporary.replace(target)
            downloaded += 1
        except Exception as exc:
            if errors is None:
                raise
            message = f"Behance {kind} {index}: {exc}"
            errors.append(message)
            logger(message)
        finally:
            temporary.unlink(missing_ok=True)
        if progress:
            progress(min(100, int(index * 100 / max(total, 1))))

    return downloaded


def bundled_js_runtimes() -> dict:
    name = "deno.exe" if sys.platform == "win32" else "deno"
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    executable = base / "runtime" / name
    return {"deno": {"path": str(executable)}} if executable.exists() else {"deno": {}}


def build_ydl_options(
    output_dir: Path,
    format_selector: str = DEFAULT_VIDEO_FORMAT,
    cookies: Path | None = None,
    write_metadata: bool = False,
    allow_multiple: bool = False,
    quiet: bool = False,
    log: LogCallback | None = None,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "format": format_selector,
        "js_runtimes": bundled_js_runtimes(),
        "outtmpl": str(output_dir / DEFAULT_TEMPLATE),
        "noplaylist": not allow_multiple,
        "quiet": quiet,
        "no_warnings": quiet,
        "merge_output_format": "mp4",
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "logger": CallbackLogger(log),
    }
    if imageio_ffmpeg is not None:
        try:
            options["ffmpeg_location"] = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    if progress_hook:
        options["progress_hooks"] = [progress_hook]
    if cookies:
        options["cookiefile"] = str(cookies)
    if write_metadata:
        options["writedescription"] = True
        options["writeinfojson"] = True
    return options


def download_urls(
    urls: list[str],
    output_dir: Path,
    format_selector: str = DEFAULT_VIDEO_FORMAT,
    cookies: Path | None = None,
    write_metadata: bool = False,
    allow_multiple: bool = False,
    include_videos: bool = True,
    include_images: bool = True,
    quiet: bool = False,
    continue_on_error: bool = False,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> DownloadResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = log or (lambda message: None)
    result = DownloadResult()

    for url in urls:
        logger(f"URL: {url}")
        url_result = DownloadResult()

        if is_instagram_url(url):
            options = build_ydl_options(
                output_dir, format_selector=format_selector, cookies=cookies,
                write_metadata=write_metadata, allow_multiple=True, quiet=quiet,
                log=logger, progress_hook=progress_hook,
            )
            try:
                with YoutubeDL(options) as ydl:
                    url_result = download_instagram(ydl, url, output_dir, include_videos, include_images, logger)
            except Exception as exc:
                url_result.errors.append(f"Instagram extraction failed: {exc}")
        elif is_behance_url(url):
            try:
                images, direct_videos = extract_behance_media(url, logger, cookies=cookies)
                if include_images:
                    url_result.images += download_direct_files(images, output_dir, "image", logger, progress, cookies, url_result.errors)
                if include_videos:
                    url_result.videos += download_direct_files(direct_videos, output_dir, "video", logger, progress, cookies, url_result.errors)
                    if not direct_videos:
                        # Let yt-dlp resolve embedded players only after page access succeeds.
                        options = build_ydl_options(output_dir, format_selector, cookies, write_metadata,
                                                    allow_multiple, quiet, logger, progress_hook)
                        try:
                            with YoutubeDL(options) as ydl:
                                info = ydl.extract_info(url, download=True)
                            if info:
                                url_result.videos += 1
                        except Exception as exc:
                            logger(f"Behance embedded video: {exc}")
                            if not url_result.images:
                                url_result.errors.append(f"Behance video: {exc}")
                if not url_result.images and not url_result.videos and not url_result.errors:
                    url_result.errors.append("Behance: 선택한 종류의 미디어를 찾지 못했습니다.")
            except Exception as exc:
                url_result.errors.append(f"Behance extraction failed: {exc}")
        elif include_videos:
            selector = INSTAGRAM_VIDEO_FORMAT if is_instagram_url(url) and format_selector == DEFAULT_VIDEO_FORMAT else format_selector
            options = build_ydl_options(
                output_dir,
                format_selector=selector,
                cookies=cookies,
                write_metadata=write_metadata,
                allow_multiple=allow_multiple,
                quiet=quiet,
                log=logger,
                progress_hook=progress_hook,
            )
            try:
                with YoutubeDL(options) as ydl:
                    ydl.download([url])
                url_result.videos += 1
            except DownloadError as exc:
                message = f"Video download failed: {exc}"
                if is_behance_url(url) and include_images:
                    logger(message)
                    logger("Continuing with Behance image extraction...")
                else:
                    url_result.errors.append(message)
            except Exception as exc:
                url_result.errors.append(f"Video download error: {exc}")

        result.videos += url_result.videos
        result.images += url_result.images
        result.skipped += url_result.skipped
        result.errors.extend(url_result.errors)

        if url_result.errors and not continue_on_error:
            break

    if progress:
        progress(100)
    return result




