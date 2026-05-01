"""
monitor.py — 의료 뉴스 키워드 모니터링 스크립트
================================================
기능:
  1. 2개 의료 뉴스 사이트 크롤링 (청년의사 · 의협신문, HTML 파싱)
  2. 제목에 키워드 포함 시 Gmail 이메일 알림 발송
  3. news_archive.csv에 결과 저장 (중복 URL 자동 제거)
  4. 사이트별 오류 발생 시 해당 사이트만 건너뜀

실행:
  python monitor.py
  python monitor.py --dry-run   # 이메일 미발송, 결과만 출력
"""

import argparse
import csv
import logging
import re
import smtplib
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import config

warnings.filterwarnings("ignore")  # SSL 경고 억제

# ── 로깅 설정 ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── 데이터 구조 ───────────────────────────────────────────
@dataclass
class Article:
    source:    str
    title:     str
    url:       str
    published: str
    found_at:  str = ""

    def __post_init__(self):
        if not self.found_at:
            self.found_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════
# 아카이브 (CSV)
# ══════════════════════════════════════════════════════════

CSV_COLUMNS = ["사이트명", "기사제목", "URL", "발견날짜"]


def load_archive(path: str) -> set[str]:
    """CSV에서 이미 저장된 URL 집합 로드"""
    seen: set[str] = set()
    p = Path(path)
    if not p.exists():
        return seen
    with open(p, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("URL"):
                seen.add(row["URL"].strip())
    log.info(f"아카이브 로드 완료: {len(seen)}개 기존 URL")
    return seen


def save_to_archive(articles: list[Article], path: str):
    """새 기사를 CSV에 추가 저장"""
    if not articles:
        return
    p = Path(path)
    write_header = not p.exists()
    with open(p, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for a in articles:
            writer.writerow({
                "사이트명": a.source,
                "기사제목": a.title,
                "URL":      a.url,
                "발견날짜": a.found_at,
            })
    log.info(f"CSV 저장 완료: {len(articles)}개 → {path}")


# ══════════════════════════════════════════════════════════
# HTTP 유틸
# ══════════════════════════════════════════════════════════

def http_get(url: str) -> requests.Response | None:
    try:
        resp = requests.get(
            url,
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log.warning(f"HTTP 요청 실패: {url} → {e}")
        return None


def to_absolute(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


def clean_url(url: str) -> str:
    """불필요한 트래킹 쿼리 파라미터 제거"""
    return re.sub(r"&sc_word[^&]*", "", url).rstrip("?&")


# ══════════════════════════════════════════════════════════
# 크롤러 — HTML 파싱 (requests + BeautifulSoup)
# ══════════════════════════════════════════════════════════

def crawl_html(site: dict) -> list[Article]:
    name      = site["name"]
    base      = site["base_url"]
    list_url  = site["list_url"]
    title_sel = site["title_selector"]
    link_kw   = site["link_filter"]
    pages     = site.get("pages", 3)

    log.info(f"[{name}] HTML 파싱 시작: {list_url} ({pages}페이지)")

    seen     : set[str]    = set()
    articles : list[Article] = []

    for page in range(1, pages + 1):
        url  = f"{list_url}?page={page}" if page > 1 else list_url
        resp = http_get(url)
        if not resp:
            log.warning(f"[{name}] 페이지 {page} 요청 실패 — 중단")
            break

        soup  = BeautifulSoup(resp.content, "html.parser")
        items = soup.select(title_sel)

        if not items:
            log.info(f"[{name}] 페이지 {page}: 기사 없음 — 종료")
            break

        for tag in items:
            title = tag.get_text(strip=True)
            href  = tag.get("href", "")
            if not href or link_kw not in href:
                continue
            full_url = clean_url(to_absolute(href, base))
            if full_url in seen:
                continue
            seen.add(full_url)
            articles.append(Article(source=name, title=title, url=full_url, published=""))

        log.info(f"[{name}] 페이지 {page}: {len(items)}개 항목 처리")
        time.sleep(config.REQUEST_DELAY)

    log.info(f"[{name}] 총 {len(articles)}개 고유 기사 수집 완료")
    return articles


# ══════════════════════════════════════════════════════════
# 키워드 감지
# ══════════════════════════════════════════════════════════

def is_keyword_match(title: str, keywords: list[str]) -> bool:
    return any(kw in title for kw in keywords)


def filter_by_keywords(articles: list[Article], keywords: list[str]) -> list[Article]:
    matched = [a for a in articles if is_keyword_match(a.title, keywords)]
    if matched:
        log.info(f"키워드 매칭 {len(matched)}건: {[a.title for a in matched]}")
    return matched


# ══════════════════════════════════════════════════════════
# 이메일 알림
# ══════════════════════════════════════════════════════════

def build_email_body(article: Article) -> str:
    return (
        f"사이트명  : {article.source}\n"
        f"기사 제목 : {article.title}\n"
        f"URL       : {article.url}\n"
        f"발견 시각 : {article.found_at}\n"
        f"\n──────────────────────────────\n"
        f"이 메일은 의사과학자 키워드 모니터링 시스템이 자동 발송했습니다.\n"
    )


def send_email(article: Article, dry_run: bool = False):
    subject = f"[의사과학자 알림] {article.title}"
    body    = build_email_body(article)

    if dry_run:
        log.info(f"[DRY-RUN] 이메일 미발송:\n  제목: {subject}")
        return

    msg = MIMEMultipart()
    msg["From"]    = config.EMAIL_SENDER
    msg["To"]      = config.EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)
        log.info(f"이메일 발송 완료: {subject}")
    except smtplib.SMTPException as e:
        log.error(f"이메일 발송 실패: {e}")


# ══════════════════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════════════════

def crawl_site(site: dict) -> list[Article]:
    """사이트 전략에 따라 크롤러 선택 실행"""
    strategy = site["strategy"]
    if strategy == "html":
        return crawl_html(site)
    else:
        log.error(f"알 수 없는 strategy: {strategy}")
        return []


def main(dry_run: bool = False):
    log.info("=" * 55)
    log.info("  의사과학자 키워드 모니터링 시작")
    log.info(f"  키워드: {config.KEYWORDS}")
    log.info(f"  모드: {'DRY-RUN (이메일 미발송)' if dry_run else '실제 실행'}")
    log.info("=" * 55)

    archive_urls = load_archive(config.ARCHIVE_PATH)
    new_articles : list[Article] = []
    total_crawled = 0

    for site in config.SITES:
        try:
            articles = crawl_site(site)
            total_crawled += len(articles)

            # 키워드 필터
            matched = filter_by_keywords(articles, config.KEYWORDS)

            # 중복 제거
            novel = [a for a in matched if a.url not in archive_urls]

            if not novel:
                log.info(f"[{site['name']}] 새 키워드 기사 없음")
                continue

            # 이메일 발송 + 아카이브 준비
            for article in novel:
                send_email(article, dry_run=dry_run)
                archive_urls.add(article.url)
                new_articles.append(article)

        except Exception as e:
            log.error(f"[{site['name']}] 예외 발생 — 건너뜀: {e}", exc_info=True)
            continue   # ← 다른 사이트는 계속 실행

    # CSV 저장
    if new_articles:
        save_to_archive(new_articles, config.ARCHIVE_PATH)

    # 최종 요약
    log.info("=" * 55)
    log.info(f"  크롤링 총계 : {total_crawled}개 기사")
    log.info(f"  키워드 신규 : {len(new_articles)}개 발견")
    if new_articles:
        for a in new_articles:
            log.info(f"    ✅ [{a.source}] {a.title}")
    log.info("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="의료 뉴스 키워드 모니터링")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="이메일 미발송, 결과만 출력 (테스트용)",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
