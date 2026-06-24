from typing import List
from src.models import NewsItem


NAVER_ECONOMY_URL = "https://news.naver.com/section/101"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def crawl_naver_economy() -> List[NewsItem]:
    items: List[NewsItem] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()

            page.goto(NAVER_ECONOMY_URL, timeout=30000)
            page.wait_for_selector(".sa_item_flex", timeout=10000)

            articles = page.query_selector_all(".sa_item_flex")
            for article in articles[:30]:
                try:
                    title_el = article.query_selector(".sa_text_title")
                    title = title_el.inner_text().strip() if title_el else ""

                    link_el = article.query_selector("a.sa_text_title")
                    if not link_el:
                        link_el = article.query_selector("a")
                    url = link_el.get_attribute("href") if link_el else ""

                    press_el = article.query_selector(".sa_text_press")
                    source = press_el.inner_text().strip() if press_el else "Naver"

                    summary_el = article.query_selector(".sa_text_lede")
                    summary = summary_el.inner_text().strip() if summary_el else ""

                    if title and url:
                        items.append(NewsItem(
                            title=title,
                            url=url,
                            source=source,
                            summary=summary,
                            collection_method="playwright",
                        ))
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        print(f"[Playwright] Naver Economy 크롤링 오류: {e}")

    print(f"[Playwright] Naver Economy: {len(items)}건 수집")
    return items
