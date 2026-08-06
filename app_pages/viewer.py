import re

import streamlit as st

from web.common import OUTPUT_DIR, render_copy_blocks, render_publish_status

EXCLUDED_FOLDERS = {"affiliate", "blog_writer", "shorts", "monthly_goal"}

st.title("생성된 글 보기")


def list_dates() -> list[str]:
    if not OUTPUT_DIR.exists():
        return []
    return sorted(
        (d.name for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name not in EXCLUDED_FOLDERS),
        reverse=True,
    )


with st.sidebar:
    with st.container(horizontal=True):
        if st.button("새로고침", icon=":material/refresh:"):
            st.rerun()
        if st.button("GitHub에서 pull", icon=":material/cloud_download:"):
            with st.spinner("GitHub pull 중..."):
                import subprocess

                result = subprocess.run(
                    ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                )
            output = (result.stdout + "\n" + result.stderr).strip()
            if result.returncode:
                st.error(output[-1200:] or "pull 실패")
            else:
                st.success(output[-1000:] or "변경 사항이 없습니다.")
                st.rerun()

    dates = list_dates()
    if not dates:
        st.info("output 폴더에 날짜별 글이 없습니다.")
        st.stop()

    selected_date = st.selectbox("날짜", dates)

    folder = OUTPUT_DIR / selected_date
    files = sorted(f.name for f in folder.glob("*.md"))

    query = st.text_input("파일 검색", placeholder="파일명으로 검색")
    if query:
        files = [f for f in files if query.lower() in f.lower()]

    if not files:
        st.info("조건에 맞는 파일이 없습니다.")
        st.stop()

    selected_file = st.radio("파일", files, label_visibility="collapsed")

file_path = folder / selected_file
raw_content = file_path.read_text(encoding="utf-8")

title_match = re.search(r"^#\s+(.+)$", raw_content, re.MULTILINE)
st.subheader(title_match.group(1).strip() if title_match else selected_file)

with st.container(border=True):
    render_publish_status(f"viewer_{file_path}", file_path)
    with st.container(horizontal=True):
        if st.button("SNS 홍보 문구 만들기", icon=":material/campaign:"):
            from src.publish_status import get_status
            from web.common import send_to_sns_tab

            url = get_status(str(file_path)).get("url", "")
            send_to_sns_tab(title_match.group(1).strip() if title_match else selected_file, raw_content, url)

        if st.button("SEO 진단", icon=":material/fact_check:"):
            st.session_state[f"viewer_seo_open_{file_path}"] = True

if st.session_state.get(f"viewer_seo_open_{file_path}"):
    from src.seo_check import run_seo_check

    icons = {"pass": ":material/check_circle:", "warn": ":material/warning:", "fail": ":material/error:", "info": ":material/info:"}
    colors = {"pass": "green", "warn": "orange", "fail": "red", "info": "gray"}
    with st.expander("SEO 진단 결과", expanded=True):
        for item in run_seo_check(raw_content):
            st.badge(item["label"], icon=icons.get(item["status"], ":material/circle:"), color=colors.get(item["status"], "gray"))
            st.caption(item["detail"])

tab_preview, tab_copy = st.tabs(["미리보기", "복사"])
with tab_preview:
    st.markdown(raw_content)
with tab_copy:
    render_copy_blocks(raw_content, f"viewer_{file_path}")
