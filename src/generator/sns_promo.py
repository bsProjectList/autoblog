import json
from typing import Dict
from src.llm_client import chat_completion

SYSTEM_PROMPT = (
    "당신은 SNS 마케팅 카피라이터입니다. 블로그 글을 홍보하는 짧고 클릭을 유도하는 문구를 씁니다.\n"
    "과장 없이 자연스럽게, 호기심을 자극하는 톤으로 작성하세요."
)


def _prompt(title: str, url: str, summary: str) -> str:
    summary_block = f"\n[핵심 내용 요약]\n{summary}\n" if summary else ""
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
        temperature=0.9,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content.strip())
    return {
        "threads": (data.get("threads") or "").strip(),
        "instagram": (data.get("instagram") or "").strip(),
    }
