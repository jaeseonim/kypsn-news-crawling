"""
의료 뉴스 3개 사이트 크롤링 전략 검증 스크립트
- RSS 피드 존재 여부 확인
- robots.txt 크롤링 허용 여부 확인
- HTML 기사 목록 CSS 선택자 검증
"""

import requests
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore")  # SSL 경고 억제

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SITES = {
    "메디게이트뉴스": {
        "base": "https://www.medigatenews.com",
        "rss_candidates": ["/rss", "/feed", "/rss.xml"],
        "list_url": "https://www.medigatenews.com/news/list/1",
        "title_selectors": ["h2.news_title a", ".article_box .title a", ".news_tit a", "h3 a"],
        "link_selectors": [".news_list li a", ".article_box a", "a[href*='/news/article']"],
    },
    "청년의사": {
        "base": "https://www.docdocdoc.co.kr",
        "rss_candidates": ["/rss", "/feed", "/bbs/rss.php?bo_table=news"],
        "list_url": "https://www.docdocdoc.co.kr/news/articleList.html",
        "title_selectors": ["#bo_list .list_num .title a", ".article-list .item-title a", "ul.type2 li a.title", ".titles a"],
        "link_selectors": ["a[href*='articleView']", "#bo_list a", ".list_item a"],
    },
    "의협신문": {
        "base": "https://www.doctorsnews.co.kr",
        "rss_candidates": ["/rss", "/rss/allArticle.rss", "/feed", "/rss.xml"],
        "list_url": "https://www.doctorsnews.co.kr/news/articleList.html",
        "title_selectors": [".article-list-title a", ".list-titles a", "h4.titles a", ".type2 .titles a"],
        "link_selectors": ["a[href*='articleView.html?idxno=']", ".type2 li a", ".list_item a"],
    },
}


def separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def check_robots(name: str, base_url: str):
    print(f"\n[robots.txt] {base_url}/robots.txt")
    try:
        r = requests.get(f"{base_url}/robots.txt", headers=HEADERS, timeout=8, verify=False)
        if r.status_code == 200:
            print(r.text[:600])
        else:
            print(f"  → HTTP {r.status_code} (robots.txt 없음)")
    except Exception as e:
        print(f"  → 요청 실패: {e}")


def check_rss(name: str, base_url: str, candidates: list) -> str | None:
    print(f"\n[RSS 피드 탐색]")
    found = None
    for path in candidates:
        url = base_url + path
        try:
            r = requests.get(url, headers=HEADERS, timeout=8, verify=False)
            ct = r.headers.get("Content-Type", "")
            is_rss = (
                r.status_code == 200
                and ("xml" in ct or "rss" in ct or r.text.strip().startswith("<rss") or "<channel>" in r.text[:500])
            )
            status = "✅ RSS 발견!" if is_rss else f"❌ HTTP {r.status_code}"
            print(f"  {url}  →  {status}")
            if is_rss and not found:
                found = url
        except Exception as e:
            print(f"  {url}  →  연결 오류: {e}")
    return found


def check_html_selectors(name: str, list_url: str, title_selectors: list, link_selectors: list):
    print(f"\n[HTML 파싱 검증] {list_url}")
    try:
        r = requests.get(list_url, headers=HEADERS, timeout=10, verify=False)
        print(f"  HTTP 상태: {r.status_code}  |  인코딩: {r.apparent_encoding}")
        soup = BeautifulSoup(r.content, "html.parser")

        # 제목 선택자 검증
        print("\n  [제목 CSS 선택자 테스트]")
        for sel in title_selectors:
            tags = soup.select(sel)
            result = f"✅ {len(tags)}개 발견" if tags else "❌ 0개"
            sample = f'  → 샘플: "{tags[0].get_text(strip=True)[:40]}"' if tags else ""
            print(f"    {sel:45s}  {result}{sample}")

        # 링크 선택자 검증
        print("\n  [링크 CSS 선택자 테스트]")
        for sel in link_selectors:
            tags = soup.select(sel)
            result = f"✅ {len(tags)}개 발견" if tags else "❌ 0개"
            sample = f'  → href: {tags[0].get("href","")[:60]}' if tags else ""
            print(f"    {sel:45s}  {result}{sample}")

        # 추가: <a> 태그 중 기사 URL 패턴 자동 감지
        print("\n  [기사 URL 패턴 자동 감지 (상위 5개)]")
        all_links = soup.select("a[href]")
        article_links = [
            a.get("href", "") for a in all_links
            if any(kw in a.get("href", "") for kw in ["article", "news", "idxno", "wr_id", "view"])
        ]
        for href in list(dict.fromkeys(article_links))[:5]:
            print(f"    {href}")

    except Exception as e:
        print(f"  → 요청 실패: {e}")


def main():
    print("=" * 60)
    print("  의료 뉴스 사이트 크롤링 전략 검증 도구")
    print("  대상: 메디게이트뉴스 / 청년의사 / 의협신문")
    print("=" * 60)

    for name, cfg in SITES.items():
        separator(name)
        check_robots(name, cfg["base"])
        rss_url = check_rss(name, cfg["base"], cfg["rss_candidates"])
        if rss_url:
            print(f"\n  ✅ 최종 권장 방식: RSS  →  {rss_url}")
        else:
            print(f"\n  ⚠️  RSS 없음 → HTML 파싱 전략으로 전환")
            check_html_selectors(
                name,
                cfg["list_url"],
                cfg["title_selectors"],
                cfg["link_selectors"],
            )

    separator()
    print("  검증 완료. 위 결과를 바탕으로 스크래퍼를 작성하세요.")
    separator()


if __name__ == "__main__":
    main()
