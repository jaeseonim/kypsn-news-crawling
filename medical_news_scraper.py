"""
의료 뉴스 스크래퍼 - 검증된 전략 기반 최종 버전
=================================================
사이트별 전략 (2026-05-01 검증):
  - 메디게이트뉴스 : RSS  → https://www.medigatenews.com/rss.xml
  - 청년의사       : HTML → .titles a  /  a[href*='articleView']
  - 의협신문       : HTML → .list-titles a  /  a[href*='articleView.html?idxno=']

출력 형식: JSON (articles_YYYYMMDD_HHMMSS.json)
"""

import json
import re
import time
import warnings
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")  # SSL 경고 억제

# ── 공통 설정 ──────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
REQUEST_DELAY = 1.0   # 요청 간격 (초) — 서버 부하 방지
OUTPUT_DIR    = Path(__file__).parent  # 스크립트와 같은 폴더에 저장


# ── 데이터 구조 ───────────────────────────────────────────
@dataclass
class Article:
    source: str        # 사이트명
    title: str         # 기사 제목
    url: str           # 기사 URL (절대경로)
    published: str     # 발행일 (있을 경우)
    summary: str       # 요약/리드문 (있을 경우)


# ── 공통 유틸 ─────────────────────────────────────────────
def get(url: str, timeout: int = 10) -> requests.Response | None:
    """GET 요청 — 실패 시 None 반환"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"  [오류] {url}\n         {e}")
        return None


def absolute_url(href: str, base: str) -> str:
    """상대경로를 절대 URL로 변환"""
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


# ══════════════════════════════════════════════════════════
# 1. 메디게이트뉴스 — RSS 파싱
# ══════════════════════════════════════════════════════════
def scrape_medigatenews(limit: int = 20) -> list[Article]:
    """
    전략: RSS (https://www.medigatenews.com/rss.xml)
    robots.txt: 없음(404) → 제한 없음
    """
    SOURCE  = "메디게이트뉴스"
    RSS_URL = "https://www.medigatenews.com/rss.xml"
    BASE    = "https://www.medigatenews.com"

    print(f"\n[{SOURCE}] RSS 수집 중... ({RSS_URL})")
    resp = get(RSS_URL)
    if not resp:
        return []

    articles = []
    try:
        root = ET.fromstring(resp.content)
        ns   = {"media": "http://search.yahoo.com/mrss/"}
        channel = root.find("channel")
        items   = channel.findall("item") if channel else root.findall(".//item")

        for item in items[:limit]:
            title     = (item.findtext("title") or "").strip()
            link      = (item.findtext("link")  or "").strip()
            pub_date  = (item.findtext("pubDate") or "").strip()
            desc_raw  = item.findtext("description") or ""
            # description 내 HTML 태그 제거
            summary   = BeautifulSoup(desc_raw, "html.parser").get_text(strip=True)[:200]

            if title and link:
                articles.append(Article(
                    source    = SOURCE,
                    title     = title,
                    url       = absolute_url(link, BASE),
                    published = pub_date,
                    summary   = summary,
                ))
    except ET.ParseError as e:
        print(f"  [XML 파싱 오류] {e}")

    print(f"  → {len(articles)}개 기사 수집 완료")
    return articles


# ══════════════════════════════════════════════════════════
# 2. 청년의사 — HTML 파싱
# ══════════════════════════════════════════════════════════
def scrape_docdocdoc(pages: int = 3) -> list[Article]:
    """
    전략: HTML 파싱
    기사 목록: /news/articleList.html?page=N
    제목: .titles a  (검증: 21개/페이지)
    링크: a[href*='articleView']  (검증: 44개/페이지)
    robots.txt: Disallow /admin/ 만 제한 → 크롤링 허용
    """
    SOURCE   = "청년의사"
    BASE     = "https://www.docdocdoc.co.kr"
    LIST_URL = f"{BASE}/news/articleList.html"

    print(f"\n[{SOURCE}] HTML 파싱 중... ({pages}페이지)")

    seen     = set()
    articles = []

    for page in range(1, pages + 1):
        url  = f"{LIST_URL}?page={page}"
        resp = get(url)
        if not resp:
            break

        soup  = BeautifulSoup(resp.content, "html.parser")
        items = soup.select(".titles a")

        if not items:
            print(f"  [페이지 {page}] 기사 없음 — 종료")
            break

        for tag in items:
            title = tag.get_text(strip=True)
            href  = tag.get("href", "")
            if not href or "articleView" not in href:
                continue
            full_url = absolute_url(href, BASE)
            if full_url in seen:
                continue
            seen.add(full_url)

            # idxno 추출
            m = re.search(r"idxno=(\d+)", href)
            article_id = m.group(1) if m else ""

            articles.append(Article(
                source    = SOURCE,
                title     = title,
                url       = full_url,
                published = "",      # 목록에서는 발행일 미노출 → 상세 페이지 필요
                summary   = "",
            ))

        print(f"  페이지 {page}: {len(items)}개 항목 처리")
        time.sleep(REQUEST_DELAY)

    print(f"  → 총 {len(articles)}개 고유 기사 수집 완료")
    return articles


# ══════════════════════════════════════════════════════════
# 3. 의협신문 — HTML 파싱
# ══════════════════════════════════════════════════════════
def scrape_doctorsnews(pages: int = 3) -> list[Article]:
    """
    전략: HTML 파싱
    기사 목록: /news/articleList.html?page=N
    제목: .list-titles a  (검증: 20개/페이지)
    링크: a[href*='articleView.html?idxno=']  (검증: 39개/페이지)
    robots.txt: Allow: / | Disallow: /admin/, /bbs/ → 크롤링 허용
    """
    SOURCE   = "의협신문"
    BASE     = "https://www.doctorsnews.co.kr"
    LIST_URL = f"{BASE}/news/articleList.html"

    print(f"\n[{SOURCE}] HTML 파싱 중... ({pages}페이지)")

    seen     = set()
    articles = []

    for page in range(1, pages + 1):
        url  = f"{LIST_URL}?page={page}"
        resp = get(url)
        if not resp:
            break

        soup  = BeautifulSoup(resp.content, "html.parser")
        items = soup.select(".list-titles a")

        if not items:
            print(f"  [페이지 {page}] 기사 없음 — 종료")
            break

        for tag in items:
            title = tag.get_text(strip=True)
            href  = tag.get("href", "")
            if not href or "idxno=" not in href:
                continue
            # 불필요한 쿼리 파라미터 제거 (sc_word 등)
            clean_href = re.sub(r"&sc_word[^&]*", "", href)
            full_url   = absolute_url(clean_href, BASE)
            if full_url in seen:
                continue
            seen.add(full_url)

            articles.append(Article(
                source    = SOURCE,
                title     = title,
                url       = full_url,
                published = "",
                summary   = "",
            ))

        print(f"  페이지 {page}: {len(items)}개 항목 처리")
        time.sleep(REQUEST_DELAY)

    print(f"  → 총 {len(articles)}개 고유 기사 수집 완료")
    return articles


# ══════════════════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  의료 뉴스 스크래퍼 시작")
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_articles: list[Article] = []

    all_articles += scrape_medigatenews(limit=20)
    all_articles += scrape_docdocdoc(pages=3)
    all_articles += scrape_doctorsnews(pages=3)

    # ── 결과 저장 ───────────────────────────────────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"articles_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            [asdict(a) for a in all_articles],
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ── 최종 요약 ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  수집 완료 요약")
    print("=" * 60)

    from collections import Counter
    counts = Counter(a.source for a in all_articles)
    for source, cnt in counts.items():
        print(f"  {source:12s}: {cnt:3d}개")
    print(f"  {'합계':12s}: {len(all_articles):3d}개")
    print(f"\n  저장 경로: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
