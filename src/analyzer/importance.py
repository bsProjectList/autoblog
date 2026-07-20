import json
import re
from typing import List
from src.llm_client import chat_completion
from src.models import NewsItem

SYSTEM_PROMPT = (
    "당신은 경제 뉴스 에디터입니다. 블로그 트래픽 극대화를 위해 뉴스를 평가하고 TOP 10을 선정합니다.\n\n"
    "평가 기준 (각 25점, 합계 100점):\n"
    "1. 검색량 예상 — 관련 키워드의 예상 검색량\n"
    "2. 투자 관심도 — 주식·부동산·금융 투자자들의 관심도\n"
    "3. 대중 관심도 — 일반 대중의 관심도\n"
    "4. 지속성 — 1~3일 이상 화제가 될 가능성\n\n"
    "반드시 유효한 JSON만 반환하세요. 다른 텍스트는 포함하지 마세요."
)


def _build_news_list_text(news_items: List[NewsItem]) -> str:
    lines = []
    for i, item in enumerate(news_items):
        summary_short = item.summary[:200] if item.summary else "요약 없음"
        lines.append(f"{i + 1}. [{item.source}] {item.title}\n   요약: {summary_short}")
    return "\n\n".join(lines)


def score_and_select_top10(news_items: List[NewsItem], top_n: int = 10) -> List[NewsItem]:
    if not news_items:
        return []

    news_text = _build_news_list_text(news_items)

    prompt = f"""오늘 수집된 경제 뉴스 {len(news_items)}개입니다.

{news_text}

위 뉴스 중 블로그 트래픽 관점에서 최고의 TOP {top_n}을 선정하세요.
다음 JSON 형식으로만 응답하세요:

{{
  "top10": [
    {{
      "index": 1,
      "score": 85,
      "keywords": ["키워드1", "키워드2", "키워드3"],
      "slug": "url-slug-korean",
      "reason": "선정 이유 한 줄"
    }}
  ]
}}

index는 위 뉴스 목록의 번호입니다. score는 100점 만점입니다."""

    response = chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content.strip()

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"[Analyzer] JSON 디코딩 오류: {e}")
        return news_items[:top_n]

    top10_data = result.get("top10", [])
    selected: List[NewsItem] = []

    for rank, item_data in enumerate(top10_data, start=1):
        idx = item_data.get("index", 0) - 1
        if 0 <= idx < len(news_items):
            news = news_items[idx]
            news.importance_score = float(item_data.get("score", 0))
            news.keywords = item_data.get("keywords", [])
            news.slug = item_data.get("slug", f"news-{rank:02d}").replace(" ", "-")
            news.rank = rank
            selected.append(news)

    print(f"[Analyzer] TOP {len(selected)}개 선정 완료")
    return selected
