import re
from typing import Dict
from src.llm_client import stream_completion
from src.models import BlogPost, NewsItem

SYSTEM_PROMPT = (
    "당신은 제휴 마케팅 블로그 작가입니다. 상품 정보를 바탕으로 신뢰감 있는 리뷰·추천형 블로그 글을 씁니다.\n"
    "과장 광고 표현이나 근거 없는 최상급 표현을 피하고, 실사용 후기처럼 자연스러운 한국어 구어체로 작성하세요.\n"
    "글 마지막에는 반드시 '이 포스팅은 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다.' 문구를 포함하세요."
)


def _image_placement_instructions(image_count: int) -> str:
    if image_count <= 0:
        return ""
    return f"""

[이미지 배치 지시 — 반드시 준수]
현재 상품 이미지가 {image_count}장 준비되어 있습니다. 본문을 작성하면서 내용과 어울리는 위치에 아래 자리표시자를 삽입하세요.
- 형식: [IMAGE_1], [IMAGE_2] ... [IMAGE_{image_count}] (대괄호 포함, 정확히 이 형식, 번호는 1부터 {image_count}까지)
- {image_count}개를 전부, 한 곳에 몰아넣지 말고 '들어가며' 직후, '주요 특징'의 각 소제목 사이, '구매 정보' 근처 등에 고르게 분산해서 배치
- 자리표시자는 단독 줄에 배치하고 앞뒤로 빈 줄을 둘 것"""


def _prompt(product: Dict[str, str], url: str, image_count: int = 0) -> str:
    return f"""다음 상품 정보를 바탕으로 {product.get('platform', '')} 제휴 링크 홍보용 블로그 포스트를 작성하세요.

[상품 정보]
플랫폼: {product.get('platform', '')}
상품명: {product.get('title', '') or '정보 없음'}
가격: {product.get('price', '') or '정보 없음'}
설명: {product.get('description', '') or '정보 없음'}
구매 링크: {url}

[작성 조건]
- 분량: 2000자 이상
- 실제 사용 후기처럼 자연스러운 한국어 구어체, AI 티 제거
- 상품의 장점 3~4가지를 소제목으로 구분해 설명
- 본문 중간과 구매 정보 섹션에 구매 링크({url})를 자연스럽게 삽입
- 마지막에 파트너스 수수료 고지 문구 포함
{_image_placement_instructions(image_count)}

[포스트 구조 — 이 순서대로 작성]

# (SEO 최적화 제목)

## 들어가며
(2~3문장)

## 이런 분께 추천해요
- (불릿 3~4개)

## 주요 특징
(소제목 2~3개, 각 1~2문단)

## 구매 정보
[여기서 구매하기]({url})

## 마무리
(1문단 + 파트너스 수수료 고지 문구)

## 태그
(#태그 형식으로 10개)"""


def _parse_post(url: str, product: Dict[str, str], content: str) -> BlogPost:
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else (product.get("title") or "제휴 상품 리뷰")

    tags = re.findall(r"#([^\s#\n,]+)", content)[:10]

    slug_source = product.get("title") or title
    slug = re.sub(r"[^\w가-힣\-]", "", slug_source.replace(" ", "-"))[:30] or "affiliate"

    news_stub = NewsItem(
        title=title,
        url=url,
        source=product.get("platform", "제휴"),
        summary=product.get("description", ""),
        slug=slug,
        collection_method="affiliate",
    )

    return BlogPost(
        news_item=news_stub,
        title=title,
        content=content,
        seo_type="affiliate",
        tags=tags,
    )


def generate_affiliate_post(url: str, product: Dict[str, str], image_count: int = 0) -> BlogPost:
    full_content = ""
    stream = stream_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(product, url, image_count)},
        ],
        temperature=0.8,
        max_tokens=6000,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_content += delta

    return _parse_post(url, product, full_content)
