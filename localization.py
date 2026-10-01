"""Application-owned text only. Website content and downloader logs stay original."""
import re

_language = "ko"


def set_language(language):
    global _language
    _language = language if language in ("ko", "en") else "ko"


def get_language():
    return _language


EN = {
    "사이트": "Site",
    "큐에 추가": "Add to queue", "클립보드 추가": "Paste URLs", "다운로드": "Download",
    "저장 폴더 열기": "Open folder", "최근 폴더 열기": "Recent folder",
    "선택 제거": "Remove selected", "큐 비우기": "Clear queue", "기록 지우기": "Clear history",
    "시간": "Time", "플랫폼": "Platform", "상태": "Status", "요약": "Summary",
    "저장 폴더": "Destination", "선택": "Browse", "계정 연결": "Accounts",
    " 연결": " Connect", " 계정 연결": " Account connection", "연결 해제": "Disconnect",
    " · 저장됨": " · Saved", "저장 항목": "Save", "영상 저장": "Videos",
    "이미지 저장 (Instagram · Behance)": "Images (Instagram · Behance)",
    "설명과 정보 JSON 저장": "Description and metadata JSON", "편의 기능": "Preferences",
    "클립보드 URL 자동 감지": "Detect clipboard URLs", "플랫폼/오늘 날짜 폴더로 저장": "Group by platform / date",
    "영상 품질": "Video quality", "최고 화질 - 영상+음성 자동 병합": "Best quality - merge video and audio",
    "호환 우선 - 없으면 자동 병합": "Compatible - merge if needed",
    "쿠키 파일 (선택 시 우선 적용)": "Cookie file (overrides saved accounts)",
    "업데이트 확인": "Check for updates", "진단 정보 복사": "Copy diagnostics",
    "URL 하나 또는 여러 개를 붙여넣으세요.": "Paste one or more media URLs.",
    "Instagram · Behance 계정 연결은 OUTPUT에서 관리합니다.": "",
    "다운로드 진행 상황과 오류가 여기에 표시됩니다.": "",
    "앱에 ffmpeg를 포함해 YouTube/Vimeo의 영상+음성 병합을 자동 처리합니다.": "",
    "저장 폴더 선택": "Choose destination", "cookies.txt 선택": "Choose cookies.txt",
    "저장 여부이며 로그인 유효성을 보장하지 않습니다. 만료되면 다시 연결하세요.": "Session saved; validity is not guaranteed. Reconnect if expired.",
    "계정 연결 창을 열 수 없습니다. 최신 설치 파일로 다시 설치해 주세요.": "Cannot open account connection. Reinstall the latest version.",
    "Fetch에 저장한 이 계정의 세션을 삭제할까요? 진행 중인 작업과 외부 브라우저의 로그인은 유지됩니다.": "Remove this saved session from Fetch? Active jobs and external browser sessions will not be affected.",
    "보안 저장소에 접근할 수 없어 연결을 해제하지 못했습니다.": "Cannot disconnect: secure storage is unavailable.",
    "업데이트 작업이 끝난 뒤 진단 정보를 열어 주세요.": "Wait for the update operation to finish before opening diagnostics.",
    "추가할 URL이 없습니다.": "No URLs to add.", "클립보드에서 URL을 찾지 못했습니다.": "No URLs found in the clipboard.",
    "작업 완료 후 닫아 주세요": "Wait for the current operation to finish",
    "다운로드할 URL을 큐에 추가하세요.": "Add a URL to the queue.", "다운로드할 항목을 체크하세요.": "Select items to download.",
    "저장할 항목을 하나 이상 선택하세요.": "Select at least one media type.", "쿠키 파일을 찾을 수 없습니다.": "Cookie file not found.",
    "다운로드 중...": "Downloading...", "최신 버전입니다.": "You are up to date.",
    "다운로드가 끝난 뒤 업데이트를 다시 확인해 주세요.": "Check for updates after downloads finish.",
    "업데이트 파일을 열었습니다. Fetch가 종료되면 새 Fetch를 응용 프로그램 폴더로 옮겨 기존 앱을 교체해 주세요.": "The update disk image is open. After Fetch closes, drag the new Fetch into Applications to replace the old app.",
    "다운로드된 파일이 없습니다.": "No files downloaded.", "완료": "Completed", "실패": "Failed",
    "다운로드된 파일이 없습니다. URL, 공개 여부, 쿠키 설정을 확인하세요.": "No files downloaded. Check the URL, access and cookie settings.",
    "저장된 계정 세션을 열 수 없거나 만료됐습니다. 계정을 다시 연결하거나 연결 해제 후 시도해 주세요.": "The saved session is unavailable or expired. Reconnect or disconnect the account and retry.",
    "썸네일을 찾지 못했습니다.": "No thumbnail found.",
    "HTTPS 인증서 검증에 실패했습니다. PC 시간과 네트워크 인증서를 확인해 주세요.": "HTTPS certificate verification failed. Check your clock and network certificates.",
    "선택한 쿠키가 만료됐거나 형식이 잘못됐습니다. 본인 브라우저에서 새 cookies.txt를 내보내 선택해 주세요.": "Cookies are expired or invalid. Export a fresh cookies.txt from your own browser.",
    "영상 정보를 찾지 못했습니다. 사진 게시물인지 또는 영상 접근이 제한됐는지 확인해 주세요.": "Video information is unavailable. Check whether this is an image post or a restricted video.",
    "Instagram에서 미디어 정보를 받지 못했습니다. 브라우저에서 게시물 접근 여부를 확인해 주세요. 로그인이 필요한 경우 cookies.txt를 선택하세요.": "Instagram returned no media information. Check access in your browser and connect your account if required.",
    "콘텐츠가 비공개이거나 삭제/차단된 상태일 수 있습니다.": "This content may be private, deleted or blocked.",
    "네트워크 연결 또는 방화벽/보안 프로그램이 다운로드를 막고 있을 수 있습니다.": "The network, firewall or security software may be blocking the download.",
    "영상과 음성 병합 단계에서 문제가 생겼습니다. 앱을 최신 버전으로 업데이트해 주세요.": "Video/audio merging failed. Update Fetch to the latest version.",
    "쿠키 가져오기": "Import cookies", "로그인 완료 · 연결 저장": "Save session", "취소": "Cancel",
    "로그인 확인": "Sign-in required", "Instagram 로그인을 먼저 완료해 주세요.": "Complete Instagram sign-in first.",
    "연결 저장 실패": "Session not saved", "가져오기 실패": "Import failed",
    "로그인 완료 여부와 보안 저장소 접근 권한을 확인해 주세요. 연결되지 않으면 본인 브라우저의 쿠키 파일을 가져올 수 있습니다.": "Check sign-in and secure storage access. If embedded sign-in is restricted, import cookies from your own browser.",
    "본인 계정 쿠키 가져오기": "Import your account cookies",
    "유효한 Netscape 쿠키 파일과 보안 저장소 접근 권한을 확인해 주세요.": "Check the Netscape cookie file and secure storage permissions.",
    "다음 실행부터 선택한 언어가 적용됩니다.": "The selected language will apply next time you open Fetch.",
    "언어 / Language": "Language / 언어", "한국어": "한국어",
    "Fetch 진단 정보": "Fetch diagnostics", "진단 중...": "Checking...", "닫기": "Close", "복사 완료": "Copied",
    "진단 생성에 실패했습니다. 개인정보 보호를 위해 오류 원문은 제외했습니다.": "Diagnostics failed. Raw error details were omitted for privacy.",
}

TEMPLATES = {
    "저장 위치: {0}": "Destination: {0}", "완료: {0}": "Completed: {0}", "오류: {0}": "Error: {0}",
    "{0}/{1}개 다운로드 완료, {2}개 실패\n\n": "{0}/{1} downloads completed, {2} failed\n\n",
    "{0}개 다운로드가 완료됐습니다.": "{0} downloads completed.",
    "영상 다운로드 중: {0}": "Downloading video: {0}", "영상 저장됨: {0}": "Video saved: {0}",
    "큐에 {0}개 URL을 추가했습니다.": "Added {0} URLs to the queue.",
    "클립보드에서 {0}개 URL을 추가했습니다.": "Added {0} URLs from the clipboard.",
    "클립보드 URL 자동 추가: {0}개": "Clipboard URLs added: {0}",
    "{0}\n미리보기 불러오는 중...": "{0}\nLoading preview...",
    "{0}\n미리보기 없음 - {1}": "{0}\nNo preview - {1}", "미리보기 실패: {0}": "Preview failed: {0}",
    "다운로드를 시작합니다. 큐: {0}개": "Starting downloads. Queue: {0}", "저장 폴더: {0}": "Destination: {0}",
    "업데이트 확인 중... 현재 버전 {0}": "Checking for updates... Current version {0}",
    "업데이트 확인에 실패했습니다.\n\n{0}": "Update check failed.\n\n{0}", "업데이트 확인 실패: {0}": "Update check failed: {0}",
    "최신 버전입니다. ({0})": "You are up to date. ({0})", "새 버전 발견: {0}": "New version: {0}",
    "새 버전 {0}이 있습니다.\n\n설치 파일을 내려받고 업데이트할까요?": "Version {0} is available.\n\nDownload and install the update?",
    "업데이트 다운로드 중: {0}": "Downloading update: {0}", "업데이트 다운로드 실패: {0}": "Update download failed: {0}",
    "업데이트 다운로드에 실패했습니다.\n\n{0}": "Update download failed.\n\n{0}",
    "업데이트 파일을 열 수 없습니다.\n{0}": "Cannot open the update file.\n{0}",
    "업데이트 설치를 시작할 수 없습니다.\n{0}": "Cannot start the update installer.\n{0}",
    "{0}\n\n저장 폴더를 열까요?": "{0}\n\nOpen the destination folder?",
    "{0}에서 미디어 정보를 확인하지 못했습니다. 로그인 필요, 요청 제한, 게시물 접근 제한 중 어느 원인인지는 이 응답만으로 확정할 수 없습니다. 브라우저에서 원본 접근을 확인해 주세요.": "{0} returned no usable media information. This response does not distinguish sign-in requirements, rate limits or access restrictions. Check the original page in your browser.",
    "{0} 요청 제한에 걸렸습니다. 반복 시도를 멈추고 잠시 후 다시 시도해 주세요.": "{0} rate limit reached. Stop repeated attempts and try again later.",
    "{0}가 접근을 거부했습니다(403). 브라우저에서 원본 접근을 확인해 주세요. 로그인 문제인지 자동 요청 차단인지는 이 응답만으로 구분할 수 없습니다.": "{0} denied access (403). Check the original page in your browser. This response does not identify whether sign-in or automated-request blocking caused it.",
    "{0}가 선택한 로그인 세션으로 접근을 허용하지 않았습니다. 브라우저에서 게시물 접근과 세션 만료 여부를 확인해 주세요.": "{0} rejected the selected session. Check access and session expiry in your browser.",
    "{0}가 로그인을 요구했습니다. 본인 계정으로 브라우저에서 접근 가능한 콘텐츠라면 cookies.txt를 선택해 주세요.": "{0} requires sign-in. Connect your own account or import cookies for content you can access.",
}
_patterns = [(re.compile('^' + re.sub(r'\\\{\d+\\\}', '(.*?)', re.escape(source)) + '$', re.S), target)
             for source, target in TEMPLATES.items()]

EN.update({
    "작성 시각 (UTC)": "Generated (UTC)", "운영체제": "Operating system",
    "있음": "Available", "없음": "None", "미확인": "Not checked", "확인 실패": "Check failed",
    "확인 불가": "Unknown", "앱 포함": "Bundled", "시스템 경로에 있음": "On system PATH",
    "쓰기 성공 (검사용 파일 삭제)": "Write successful (test file removed)",
    "쓰기 권한 없음": "Write permission denied", "접근 또는 쓰기 실패": "Access or write failed",
    "폴더 없음 (생성 여부 미확인)": "Folder absent (creation not tested)", "남은 공간": "Free space",
    "Instagram 세션 파일": "Instagram session file", "Behance 세션 파일": "Behance session file",
    "수동 쿠키 선택": "Manual cookie selected", "예": "Yes", "아니오": "No",
    "세션 유효성/사이트 연결": "Session validity / site connection", "검사하지 않음": "Not tested",
    "최근 오류 분류 (오래된 순):": "Recent error categories (oldest first):",
    "기록된 오류 없음": "No recorded errors", "기타 오류 (원문 제외)": "Other error (raw message omitted)",
    "인증 필요": "Authentication required", "세션 확인 필요": "Check session", "요청 제한": "Rate limit",
    "접근 거부": "Access denied", "TLS 인증서": "TLS certificate", "연결 시간 초과": "Connection timeout",
    "네트워크 연결": "Network connection", "저장 권한": "Storage permission", "미디어 추출": "Media extraction",
    "URL, 경로, 계정명, 쿠키, 토큰, 오류 원문은 포함하지 않습니다.": "URLs, paths, account names, cookies, tokens and raw errors are excluded.",
    "오류 분류는 로그의 단서이며 확정 진단이 아닙니다. 자동 전송되지 않습니다.": "Categories are clues, not a definitive diagnosis. Nothing is uploaded automatically.",
})


def translate_report(report):
    if get_language() != "en":
        return report
    lines = []
    for line in report.splitlines():
        if line in EN:
            lines.append(tr(line))
        elif ": " in line:
            key, value = line.split(": ", 1)
            lines.append(tr(key) + ": " + tr(value))
        else:
            lines.append(", ".join(tr(part) for part in line.split(", ")))
    return "\n".join(lines)


def tr(text):
    if _language != "en" or not isinstance(text, str):
        return text
    if text in EN:
        return EN[text]
    for pattern, target in _patterns:
        match = pattern.fullmatch(text)
        if match:
            return target.format(*match.groups())
    return text
