"""보안뉴스 카테고리별 일일 TOP 10 다이제스트."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import feedparser

from src.collector.rss import _strip_html
from src.models import NewsItem


BOAN_RSS_FEEDS = {
    "사건·사고": "https://www.boannews.com/rss/S1N2.xml",
    "공공·정책": "https://www.boannews.com/rss/S1N3.xml",
    "비즈니스": "https://www.boannews.com/rss/S1N4.xml",
    "IT·과학": "https://www.boannews.com/rss/S1N6.xml",
    "오피니언": "https://www.boannews.com/rss/S1N7.xml",
}


def _one_line(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", _strip_html(text or "")).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text or "RSS 요약 없음"


def _parse_category(category: str, url: str, limit: int = 10) -> list[NewsItem]:
    feed = feedparser.parse(url)
    items: list[NewsItem] = []
    seen: set[str] = set()
    for entry in feed.entries:
        title = _strip_html(entry.get("title", "")).strip()
        link = entry.get("link", "").strip()
        key = link or title.lower()
        if not title or not link or key in seen:
            continue
        seen.add(key)
        items.append(
            NewsItem(
                title=title,
                url=link,
                source=f"보안뉴스 {category}",
                summary=_one_line(entry.get("summary", "") or entry.get("description", "")),
                published_at=entry.get("published", "") or entry.get("updated", ""),
                collection_method="rss",
            )
        )
        if len(items) >= limit:
            break
    return items


def collect_boan_top10(limit: int = 10) -> dict[str, list[NewsItem]]:
    result: dict[str, list[NewsItem]] = {}
    for category, url in BOAN_RSS_FEEDS.items():
        try:
            result[category] = _parse_category(category, url, limit)
        except Exception as exc:
            print(f"[보안뉴스] {category} 수집 실패: {exc}")
            result[category] = []
    return result


def render_markdown(categories: dict[str, list[NewsItem]], date_str: str) -> str:
    lines = [f"# 보안뉴스 카테고리별 TOP 10 ({date_str})", "", "> 각 카테고리 RSS의 최신 기사 10건입니다.", ""]
    for category, items in categories.items():
        lines.extend([f"## {category}", ""])
        if not items:
            lines.extend(["수집된 기사가 없습니다.", ""])
            continue
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}. [{item.title}]({item.url})")
            lines.append(f"   - {item.summary}")
        lines.append("")
    return "\n".join(lines)


def _discord_chunks(categories: dict[str, list[NewsItem]], date_str: str, max_chars: int = 1900) -> list[str]:
    chunks: list[str] = []
    current = f"🛡️ 보안뉴스 카테고리별 TOP 10 ({date_str})\n"
    for category, items in categories.items():
        heading = f"\n**{category}**\n"
        if len(current) + len(heading) > max_chars:
            chunks.append(current.rstrip())
            current = f"🛡️ 보안뉴스 계속 ({date_str})\n"
        current += heading
        for index, item in enumerate(items, start=1):
            entry = f"{index}. {item.title}\n   {_one_line(item.summary, 130)}\n   {item.url}\n"
            if len(current) + len(entry) > max_chars:
                chunks.append(current.rstrip())
                current = f"🛡️ 보안뉴스 계속 ({date_str})\n{entry}"
            else:
                current += entry
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def send_to_discord(categories: dict[str, list[NewsItem]], date_str: str) -> int:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("[보안뉴스] DISCORD_WEBHOOK_URL이 없어 Discord 전송을 건너뜁니다.")
        return 0

    sent = 0
    for message in _discord_chunks(categories, date_str):
        payload = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
        request = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=20) as response:
                if 200 <= response.status < 300:
                    sent += 1
                else:
                    print(f"[보안뉴스] Discord 응답 오류: HTTP {response.status}")
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"[보안뉴스] Discord 전송 실패: {exc}")
            break
        time.sleep(1)
    print(f"[보안뉴스] Discord 전송 완료: {sent}개 메시지")
    return sent


def run_boan_digest(output_dir: Path, date_str: str | None = None) -> Path:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    categories = collect_boan_top10(limit=10)
    target_dir = output_dir / date_str
    target_dir.mkdir(parents=True, exist_ok=True)
    digest_path = target_dir / "boan_news_digest.md"
    digest_path.write_text(render_markdown(categories, date_str), encoding="utf-8")
    send_to_discord(categories, date_str)
    total = sum(len(items) for items in categories.values())
    print(f"[보안뉴스] 카테고리 {len(categories)}개, 기사 {total}개 저장: {digest_path}")
    return digest_path
