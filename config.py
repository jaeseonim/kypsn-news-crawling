# config.py — 설정값 전용 파일
# ⚠️  Gmail 주소/비밀번호는 반드시 환경변수(GitHub Secrets)로 관리하세요.
#     로컬 테스트 시에는 .env 파일 또는 직접 값을 입력하세요.

import os

# ── 키워드 ────────────────────────────────────────────────
KEYWORDS = ["의사과학자"]          # 모니터링할 키워드 목록 (추가 가능)

# ── 이메일 설정 ───────────────────────────────────────────
EMAIL_SENDER   = os.environ.get("GMAIL_ADDRESS", "your_gmail@gmail.com")
EMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "your_app_password_here")
EMAIL_RECEIVER = os.environ.get("NOTIFY_EMAIL", "receiver@example.com")

# ── 아카이브 파일 ──────────────────────────────────────────
ARCHIVE_PATH = "news_archive.csv"

# ── 사이트 설정 ───────────────────────────────────────────
# strategy: "rss" | "html"
SITES = [
    {
        "name":           "청년의사",
        "strategy":       "html",
        "base_url":       "https://www.docdocdoc.co.kr",
        "list_url":       "https://www.docdocdoc.co.kr/news/articleList.html",
        "title_selector": ".titles a",
        "link_filter":    "articleView",   # href에 이 문자열이 포함된 링크만 수집
        "pages":          3,
    },
    {
        "name":           "의협신문",
        "strategy":       "html",
        "base_url":       "https://www.doctorsnews.co.kr",
        "list_url":       "https://www.doctorsnews.co.kr/news/articleList.html",
        "title_selector": ".list-titles a",
        "link_filter":    "idxno=",
        "pages":          3,
    },
]

# ── HTTP 설정 ─────────────────────────────────────────────
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 10   # 초
REQUEST_DELAY   = 1.0  # 요청 간격 (초)
