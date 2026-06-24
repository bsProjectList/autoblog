import re
import feedparser
from typing import List
from src.models import NewsItem


RSS_FEEDS = {
    # Korean economic news
    "연합뉴스": "https://www.yna.co.kr/rss/economy.xml",
    "매일경제": "https://rss.mk.co.kr/rss/40300001/",
    "한국경제": "https://rss.hankyung.com/economy.xml",
    "이데일리": "https://rss.edaily.co.kr/edaily_economy.xml",
    # International
    "Reuters": "https://feeds.reuters.com/reuters/businessNews",
    "CNBC": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_feed(source: str, url: str) -> List[NewsItem]:
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            raw_summary = entry.get("summary", "") or entry.get("description", "")
            summary = _strip_html(raw_summary)[:500]
            published = entry.get("published", "") or entry.get("updated", "")

            item = NewsItem(
                title=_strip_html(entry.get("title", "")).strip(),
                url=entry.get("link", ""),
                source=source,
                summary=summary,
                published_at=published,
                collection_method="rss",
            )
            if item.title and item.url:
                items.append(item)
    except Exception as e:
        print(f"[RSS] Error fetching {source}: {e}")
    return items


def collect_rss_news() -> List[NewsItem]:
    all_items: List[NewsItem] = []
    for source, url in RSS_FEEDS.items():
        items = parse_feed(source, url)
        all_items.extend(items)
        print(f"[RSS] {source}: {len(items)}건 수집")
    return all_items
