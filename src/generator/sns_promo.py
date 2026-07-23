import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict
from src.llm_client import chat_completion

SYSTEM_PROMPT = (
    "당신은 SNS 마케팅 카피라이터입니다. 블로그 글을 홍보하는 짧고 클릭을 유도하는 문구를 씁니다.\n"
    "제공된 본문에 있는 사실만 사용하고, 본문에 없는 수치·전망·사실을 절대 만들지 마세요.\n"
    "과장 없이 자연스럽게, 호기심을 자극하는 톤으로 작성하세요."
)


def _prompt(title: str, url: str, summary: str) -> str:
    summary_block = f"\n[본문에서 추출한 핵심 내용]\n{summary}\n" if summary else ""
    return f"""다음 블로그 글을 홍보하는 SNS 문구를 작성하세요.

[글 제목]
{title}

[게시된 글 URL]
{url}
{summary_block}
[작성 조건]
- 쓰레드(Threads)용: 짧은 후킹 문장(1~2줄) + 궁금증을 유발하는 티저 + 관련 해시태그 3~5개, 그 다음 반드시 줄바꿈을 하고 마지막 줄에 URL만 단독으로 배치 (해시태그나 다른 텍스트와 절대 붙이지 말 것. 쓰레드는 캡션의 링크가 클릭 가능함)
- 인스타그램용: 짧은 후킹 문장(1~2줄) + 이모지 활용 + 관련 해시태그 5~8개 + "프로필 링크에서 전체 글 확인하세요" 같은 문구로 유도 (인스타그램 캡션은 링크가 클릭되지 않으므로 URL을 직접 넣지 말 것)
- 두 문구 모두 200자 이내로 간결하게 작성
- 과장광고 표현 금지, 자연스러운 호기심 유발
- 제목과 본문 내용이 직접 연결되도록 작성
- 막연한 표현만 반복하지 말고 핵심 사실을 한 가지 이상 포함

다음 JSON 형식으로만 응답하세요:
{{
  "threads": "...",
  "instagram": "..."
}}"""


def generate_sns_captions(title: str, url: str, summary: str = "") -> Dict[str, str]:
    response = chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(title, url, summary)},
        ],
        temperature=0.45,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content.strip())
    captions = {
        "threads": (data.get("threads") or "").strip(),
        "instagram": (data.get("instagram") or "").strip(),
    }
    return validate_captions(captions, url)


def validate_captions(captions: Dict[str, str], url: str = "") -> Dict[str, str]:
    """채널별 길이와 URL 규칙을 보정한다."""
    threads = captions.get("threads", "").strip()
    instagram = captions.get("instagram", "").strip()
    if url and url not in threads:
        threads = f"{threads.rstrip()}\n{url}"
    if len(threads) > 500:
        threads = threads[:497].rstrip() + "..."
    if len(instagram) > 500:
        instagram = instagram[:497].rstrip() + "..."
    return {"threads": threads, "instagram": instagram}


def save_captions(captions: Dict[str, str], title: str, url: str = "") -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", title).strip("-")[:80] or "post"
    folder = Path("output") / "sns_promo" / date_str
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{slug}.json"
    path.write_text(
        json.dumps({"title": title, "url": url, **captions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
