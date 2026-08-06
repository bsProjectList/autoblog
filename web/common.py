import os
import re
from pathlib import Path

import streamlit as st

OUTPUT_DIR = Path("output")


def strip_markdown_to_plain(content: str) -> str:
    text = content
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_usage_sidebar() -> None:
    from src.usage_tracker import OPENAI_COST_PER_MILLION_TOKENS, get_cumulative_cost_usd, get_today_usage

    with st.sidebar:
        if st.button("사용량 새로고침", icon=":material/refresh:", width="stretch"):
            st.rerun()

        usage = get_today_usage()
        groq = usage.get("groq", {})
        openai_u = usage.get("openai", {})
        image_cost = usage.get("image_cost_usd", 0.0)

        groq_tokens = groq.get("tokens", 0)
        openai_tokens = openai_u.get("tokens", 0)
        openai_cost = openai_tokens / 1_000_000 * OPENAI_COST_PER_MILLION_TOKENS
        today_cost = openai_cost + image_cost
        cumulative_cost = get_cumulative_cost_usd()

        st.caption("오늘 사용량")
        st.progress(min(groq_tokens / 100_000, 1.0), text=f"Groq {groq_tokens:,}/100,000 토큰")
        st.caption(
            f"OpenAI {openai_tokens:,} 토큰 (약 ${openai_cost:.3f})  \n"
            f"이미지 ${image_cost:.2f}  \n"
            f"오늘 예상 비용 약 ${today_cost:.3f}  \n"
            f"누적 총 예상 비용 약 ${cumulative_cost:.3f}"
        )


def require_api_key(var_name: str) -> bool:
    if not os.environ.get(var_name):
        st.error(f"{var_name}가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
        return False
    return True


def render_copy_blocks(content: str, key_prefix: str) -> None:
    st.caption("마크다운 원문 (코드 블록 우측 상단 아이콘으로 복사)")
    st.code(content, language="markdown", wrap_lines=True, height=200)
    st.caption("일반 텍스트")
    st.code(strip_markdown_to_plain(content), language=None, wrap_lines=True, height=200)


def next_post_folder(date_folder: Path, slug: str) -> Path:
    date_folder.mkdir(parents=True, exist_ok=True)
    existing = [d for d in date_folder.glob(f"{slug}_*") if d.is_dir()]
    suffix = f"{len(existing) + 1:02d}"
    post_folder = date_folder / f"{slug}_{suffix}"
    post_folder.mkdir(parents=True, exist_ok=True)
    return post_folder


def render_publish_status(path_key: str, file_path) -> None:
    """file_path may be None if nothing has been saved yet."""
    from src.publish_status import get_status, set_draft, set_published

    if file_path is None:
        st.caption("상태: 아직 저장되지 않음")
        return

    status = get_status(str(file_path))
    with st.container(horizontal=True, vertical_alignment="center"):
        if status["status"] == "published":
            st.badge("게시됨", icon=":material/check_circle:", color="green")
            st.caption(status["url"])
        else:
            st.badge("초안", icon=":material/edit:", color="gray")

    with st.container(horizontal=True):
        url = st.text_input("게시 URL", value=status.get("url", ""), key=f"{path_key}_url")
        if st.button("게시완료로 표시", icon=":material/check:", key=f"{path_key}_publish_btn"):
            if url.strip():
                set_published(str(file_path), url.strip())
                st.rerun()
            else:
                st.warning("게시 URL을 입력하세요.")
        if st.button("초안으로 되돌리기", icon=":material/undo:", key=f"{path_key}_draft_btn"):
            set_draft(str(file_path))
            st.rerun()


def send_to_sns_tab(title: str, content: str, url: str = "") -> None:
    st.session_state["sns_title"] = title
    st.session_state["sns_summary"] = extract_summary_from_content(content)
    st.session_state["sns_url"] = url
    st.switch_page("app_pages/sns_promo.py")


def extract_summary_from_content(content: str, max_chars: int = 1200) -> str:
    body = re.split(
        r"\n(?:\*\*THUMBNAIL\*\*|##\s*(?:태그|관련 태그|JSON-LD)|```)",
        content,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    paragraphs = []
    for block in re.split(r"\n\s*\n", body):
        lines = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", ">", "![")):
                continue
            if re.match(r"^\d+[.)]\s", line) or line.startswith(("-", "*")):
                continue
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
            lines.append(line)
        paragraph = " ".join(lines).strip()
        if len(paragraph) >= 40:
            paragraphs.append(paragraph)

    return "\n\n".join(paragraphs[:4])[:max_chars]
