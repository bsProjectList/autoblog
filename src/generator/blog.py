import os
import re
from typing import List
from groq import Groq
from src.models import NewsItem, BlogPost, ImagePrompt

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

NAVER_SYSTEM = (
    "당신은 네이버 블로그 SEO 전문가입니다.\n"
    "경제 뉴스를 바탕으로 사람이 직접 쓴 것 같은 자연스러운 한국어 블로그 포스트를 작성합니다.\n"
    "AI가 쓴 티가 나지 않게, 전문적이면서도 읽기 쉬운 구어체 문체로 작성하세요.\n"
    "딱딱한 나열식 문장, 반복적인 접속사, 과도한 존댓말 사용을 피하세요."
)

GOOGLE_SYSTEM = (
    "당신은 구글 SEO 전문가입니다.\n"
    "E-E-A-T(경험·전문성·권위·신뢰) 원칙을 준수하며 검색 최적화된 경제 블로그 포스트를 작성합니다.\n"
    "Featured Snippet 최적화를 위해 첫 단락에 핵심 답변을 반드시 포함하세요."
)


def _naver_prompt(news: NewsItem) -> str:
    kw = ", ".join(news.keywords) if news.keywords else news.title
    return f"""다음 경제 뉴스를 바탕으로 네이버 블로그 SEO 최적화 포스트를 작성하세요.

[뉴스 정보]
제목: {news.title}
출처: {news.source}
요약: {news.summary}
핵심 키워드: {kw}

[작성 조건]
- 분량: 최소 5000자 이상 (공백 포함), 7000자까지 허용
- 자연스러운 한국어, 사람이 직접 쓴 느낌
- AI 티 완전 제거
- 핵심 키워드를 제목과 본문에 자연스럽게 삽입
- 각 섹션을 충분히 깊이 있게 서술. 내용이 부족하면 관련 배경지식·사례·통계를 추가

[가독성 규칙 — 반드시 준수]
- 한 문단은 3~4문장으로 제한. 절대 긴 문단 금지
- 문단과 문단 사이 반드시 빈 줄 삽입
- 각 소제목(##) 아래 첫 줄은 핵심 내용 한 문장으로 시작
- 중요한 수치·용어는 **굵게** 표시
- 긴 내용은 번호 목록이나 불릿(-)으로 분리
- 독자가 스크롤하면서 쉽게 읽을 수 있는 구조

[포스트 구조 — 이 순서대로 작성]

# (SEO 최적화 제목)

## 목차
1. ...
(5~7개 항목)

## 들어가며

(첫 번째 문단: 독자의 관심을 끄는 도입, 3~4문장)

(두 번째 문단: 이 글에서 다룰 내용 예고, 2~3문장)

## 핵심 내용 요약

(핵심 포인트 3~4개를 불릿으로 정리 후, 1~2문단 설명)

## 발생 배경

(2~3문단, 각 문단 사이 빈 줄)

## 시장·경제 영향

(2~3문단 또는 번호 목록으로 영향 항목 나열)

## 개인 투자자 관점

(실천 가능한 조언을 불릿 또는 번호 목록으로 정리)

## 향후 전망

(2~3문단, 낙관/비관 시나리오 구분해서 서술)

## 마무리

(핵심 정리 1문단 + 독자에게 메시지 1문단)

## 태그
(#태그 형식으로 20개)

[이미지 프롬프트 — 영어로 작성]
**THUMBNAIL**: realistic, professional news article style, 16:9, 4K, (썸네일 묘사)
**BODY_1**: realistic, 16:9, 4K, (뉴스 핵심 내용 시각화)
**BODY_2**: realistic, financial chart or market scene, 16:9, 4K, (시장 영향 시각화)
**BODY_3**: cinematic, forward-looking, 16:9, 4K, (향후 전망 시각화)"""


def _google_prompt(news: NewsItem) -> str:
    kw = ", ".join(news.keywords) if news.keywords else news.title
    return f"""다음 경제 뉴스를 바탕으로 구글 SEO 최적화 포스트를 작성하세요.

[뉴스 정보]
제목: {news.title}
출처: {news.source}
요약: {news.summary}
핵심 키워드: {kw}

[작성 조건]
- 분량: 최소 5000자 이상 (공백 포함), 8000자까지 허용
- E-E-A-T 원칙 준수
- 첫 단락에 핵심 답변 포함 (Featured Snippet 최적화)
- FAQ 섹션 필수 (5개 Q&A)
- JSON-LD Article Schema 필수

[가독성 규칙 — 반드시 준수]
- 한 문단은 3~4문장으로 제한. 절대 긴 문단 금지
- 문단과 문단 사이 반드시 빈 줄 삽입
- 각 소제목(##) 아래 첫 줄은 핵심 내용 한 문장으로 시작
- 중요한 수치·용어는 **굵게** 표시
- 긴 내용은 번호 목록이나 불릿(-)으로 분리
- 독자가 스크롤하면서 쉽게 읽을 수 있는 구조

[포스트 구조]

# (H1 제목 — 검색 키워드 포함)

**Meta Description**: (150~160자, 핵심 키워드 포함)

## 목차
(FAQ 포함 7~9개 항목)

## 핵심 요약

(2~3문장 핵심 답변 — Featured Snippet 대응)

## 발생 배경 및 원인 분석

(2~3문단, 각 문단 사이 빈 줄. 원인을 번호 목록으로 정리 후 설명)

## 시장 영향 및 경제적 파급효과

(영향 항목을 불릿으로 나열 후 각 항목 1~2문장 설명)

## 전문가 분석 및 투자자 시사점

(2~3문단. 투자자 체크리스트를 불릿으로 포함)

## 향후 전망 및 시나리오

(낙관 시나리오 / 비관 시나리오로 나눠서 각 2~3문장)

## 자주 묻는 질문 (FAQ)
**Q1**: ...

**A1**: (2~3문장 답변)

(총 5개, Q와 A 사이 빈 줄)

## 결론

(핵심 정리 1문단 + 독자 행동 촉구 1문단)

## 관련 태그
(#태그 20개)

[이미지 프롬프트 — 영어]
**THUMBNAIL**: realistic, professional, 16:9, 4K, (썸네일 묘사)
**BODY_1**: realistic, news style, 16:9, 4K, (핵심 장면)
**BODY_2**: realistic, financial/market, 16:9, 4K, (시장 영향)
**BODY_3**: cinematic, future-oriented, 16:9, 4K, (전망)

[JSON-LD Schema]
```json
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{news.title}",
  "description": "meta description here",
  "keywords": "{kw}",
  "articleSection": "Economy",
  "inLanguage": "ko-KR",
  "author": {{
    "@type": "Organization",
    "name": "AutoBlog"
  }}
}}
```"""


def _extract_image_prompts(content: str) -> List[ImagePrompt]:
    prompts = []
    for key, purpose in [
        ("THUMBNAIL", "thumbnail"),
        ("BODY_1", "body_1"),
        ("BODY_2", "body_2"),
        ("BODY_3", "body_3"),
    ]:
        pattern = rf"\*\*{key}\*\*:\s*(.+?)(?=\n\*\*(?:THUMBNAIL|BODY_[123])\*\*|\Z)"
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            prompts.append(ImagePrompt(
                description=match.group(1).strip(),
                purpose=purpose,
            ))
    return prompts


def _parse_post(news: NewsItem, content: str, seo_type: str) -> BlogPost:
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else news.title

    tags = re.findall(r"#([^\s#\n,]+)", content)[:20]

    meta_description = ""
    meta_match = re.search(r"\*\*Meta Description\*\*:\s*(.+?)(?=\n)", content)
    if meta_match:
        meta_description = meta_match.group(1).strip()

    json_ld = ""
    jsonld_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
    if jsonld_match:
        json_ld = jsonld_match.group(1).strip()

    image_prompts = _extract_image_prompts(content)

    return BlogPost(
        news_item=news,
        title=title,
        content=content,
        seo_type=seo_type,
        image_prompts=image_prompts,
        tags=tags,
        meta_description=meta_description,
        json_ld=json_ld,
    )


def generate_naver_post(news: NewsItem) -> BlogPost:
    full_content = ""
    with client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": NAVER_SYSTEM},
            {"role": "user", "content": _naver_prompt(news)},
        ],
        temperature=0.9,
        max_tokens=10000,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_content += delta
    return _parse_post(news, full_content, "naver")


def generate_google_post(news: NewsItem) -> BlogPost:
    full_content = ""
    with client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": GOOGLE_SYSTEM},
            {"role": "user", "content": _google_prompt(news)},
        ],
        temperature=0.7,
        max_tokens=12000,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_content += delta
    return _parse_post(news, full_content, "google")
