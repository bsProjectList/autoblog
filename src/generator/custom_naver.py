import re
from src.llm_client import stream_completion
from src.models import BlogPost, NewsItem

SYSTEM_PROMPT = (
    "당신은 네이버 블로그 전문 작가입니다.\n"
    "뉴스나 이슈 원문을 바탕으로, 사용자가 지정한 고정 표준 포맷을 그대로 따라 블로그 포스트를 작성합니다.\n"
    "사실 기반으로 객관적이고 담백하게 작성하며, 과장된 표현이나 근거 없는 추측을 넣지 마세요."
)


def _prompt(news_text: str) -> str:
    return f"""다음 뉴스/이슈 원문을 바탕으로 네이버 블로그 포스트를 작성하세요.

[원문]
{news_text}

[작성 조건]
- 사실 기반, 객관적 서술. 과장된 표현 지양
- 자연스러운 한국어, 사람이 직접 쓴 느낌 (AI 티 제거)
- 각 섹션을 충분히 깊이 있게 서술
- [중요] 아래 구조를 절대 중간에 끝내지 말고, 태그와 썸네일 프롬프트까지 전부 작성해야 응답이 완료된 것입니다.

[포스트 구조 — 이 순서대로, 반드시 전부 작성]

# (제목 — 키워드 중심, 뉴스/이슈에 맞춰 SEO 최적화)

## 목차
1. 핵심 요약
2. 배경 및 이슈 설명
3. 주요 내용 분석
4. 전문가·기관 발표 내용
5. 영향 및 시사점
6. 향후 전망
7. 결론 정리

## 1. 핵심 요약
- 사건·뉴스·이슈의 주요 포인트 3~5가지 요약
- 독자가 가장 먼저 알아야 할 핵심 정보 정리

## 2. 배경 및 이슈 설명
- 뉴스 발생 배경 또는 이슈의 흐름 설명
- 관련 기관·인물·기업 등 기본 정보 정리

## 3. 주요 내용 분석
- 사실 기반 검증
- 데이터나 통계가 있을 경우 해석 포함
- 이슈의 의미, 영향, 문제점, 특징 등 분석

## 4. 공식 발표·전문가 의견 정리
- 정부·기관·기업 발표 내용
- 인터뷰·전문가 발언 요약
- 원문 기반으로 검증된 내용만 작성

## 5. 한국 사회·경제·정책적 영향
- 국민·소비자·시장·산업에 미칠 영향
- 장단점, 리스크, 전망 등

## 6. 향후 전망
- 다음 절차
- 정부 또는 기업이 취할 후속 조치
- 예상되는 사회적 반응

## 7. 결론 정리
- 요약 + 독자에게 전달할 핵심 메시지
- 지나친 과장 없는 객관적 마무리

## 태그
(#태그 20개, 한글 중심 + SEO 최적화)

[썸네일 프롬프트 — 영어로 작성. (주제 키워드) 자리에 이 글의 핵심 주제를 영어로 채워넣을 것]
3D digital thumbnail, bold Korean headline space at top, minimalistic composition, soft light, ultra-high quality, news infographic style, (주제 키워드), 4K style"""


def extract_thumbnail_prompt(content: str) -> str:
    match = re.search(r"^(3D digital thumbnail.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_post(news_text: str, content: str) -> BlogPost:
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "네이버 블로그 포스트"

    tags = re.findall(r"#([^\s#\n,]+)", content)[:20]

    slug = re.sub(r"[^\w가-힣\-]", "", title.replace(" ", "-"))[:30] or "post"

    news_stub = NewsItem(
        title=title,
        url="",
        source="수동 입력",
        summary=news_text[:200],
        slug=slug,
        collection_method="manual",
    )

    return BlogPost(
        news_item=news_stub,
        title=title,
        content=content,
        seo_type="naver_custom",
        tags=tags,
    )


def generate_naver_post_from_text(news_text: str) -> BlogPost:
    full_content = ""
    stream = stream_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(news_text)},
        ],
        temperature=0.8,
        # Groq on-demand TPM limit is 12,000; keep request headroom for the prompt.
        max_tokens=8500,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_content += delta

    return _parse_post(news_text, full_content)
