"""Generate affiliate blog posts from YouTube Shorts information."""

import re
from typing import Dict, List

from src.generator.blog import _parse_post
from src.llm_client import stream_completion
from src.models import BlogPost, NewsItem


DISCLOSURE = "이 글은 쿠팡파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다."


def _products_text(products: List[Dict[str, str]]) -> str:
    return "\n".join(
        f"- 상품명: {item.get('name', '').strip()}\n  쿠팡 링크: {item.get('url', '').strip()}"
        for item in products
        if item.get("url", "").strip()
    )


def generate_shorts_post(source: dict, products: List[Dict[str, str]], seo_type: str) -> BlogPost:
    product_text = _products_text(products)
    if not product_text:
        raise ValueError("쿠팡 링크를 하나 이상 입력하세요.")
    transcript = source.get("transcript", "") or "(자막·음성 내용을 추출하지 못했습니다.)"
    prompt = f"""다음 YouTube Shorts 내용을 바탕으로 쿠팡 상품 소개·구매 가이드형 블로그 글을 작성하세요.

[쇼츠 정보]
제목: {source.get('title', '')}
채널: {source.get('channel', '')}
원본 URL: {source.get('url', '')}
설명: {source.get('description', '')[:2500]}
추출된 음성/자막({source.get('transcript_source', '알 수 없음')}):
{transcript[:7000]}
화면에서 추출한 상품명·가격·문구:
{source.get('visual_text', '')[:3000] or '(화면 분석 결과 없음)'}

[사용자가 입력한 쿠팡 상품 링크]
{product_text}

[작성 규칙]
- 쇼츠의 내용과 상품 링크를 근거로 작성하고, 입력 정보에 없는 가격·성능·수치를 만들지 마세요.
- 쇼츠 내용을 그대로 베끼지 말고 핵심을 재구성한 독창적인 글로 작성하세요.
- 상품의 장점뿐 아니라 구매 전 확인할 점도 균형 있게 포함하세요.
- 쿠팡 링크는 관련 상품 설명 뒤에 마크다운 링크로 배치하세요.
- 글 마지막에 다음 고지 문구를 그대로 포함하세요: {DISCLOSURE}
- 제목은 검색 의도가 드러나는 자연스러운 한국어로 작성하세요.
- 분량은 3000~5000자입니다.

[출력 구조]
# 제목
## 쇼츠에서 소개한 내용
## 어떤 상품인지
## 주요 특징과 활용법
## 구매 전 확인할 점
## 이런 분께 추천합니다
## 결론
## 관련 태그

"""
    full_content = ""
    stream = stream_completion(
        messages=[
            {"role": "system", "content": "당신은 사실에 근거한 한국어 커머스 블로그 편집자입니다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.55 if seo_type == "naver" else 0.45,
        max_tokens=8000,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_content += delta
    if DISCLOSURE not in full_content:
        full_content = full_content.rstrip() + f"\n\n> {DISCLOSURE}\n"

    news = NewsItem(
        title=source.get("title", "YouTube Shorts 상품 소개"),
        url=source.get("url", ""),
        source=f"YouTube Shorts · {source.get('channel', '')}".strip(" ·"),
        summary=transcript[:500],
        content=transcript,
        slug=re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", source.get("title", "shorts"))[:60].strip("-") or "shorts",
    )
    return _parse_post(news, full_content, seo_type)
