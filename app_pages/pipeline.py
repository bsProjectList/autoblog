import streamlit as st

from main import TOP_N as DEFAULT_TOP_N
from web.common import require_api_key

st.title("파이프라인 실행")

with st.container(border=True):
    with st.container(horizontal=True):
        top_n = st.number_input("뉴스 개수(TOP_N)", min_value=1, max_value=15, value=DEFAULT_TOP_N)
        naver_seo = st.checkbox("네이버 SEO", value=True)
        google_seo = st.checkbox("구글 SEO", value=True)
        run_clicked = st.button("파이프라인 실행", type="primary", icon=":material/play_arrow:")

if run_clicked:
    if not require_api_key("GROQ_API_KEY"):
        pass
    elif not naver_seo and not google_seo:
        st.warning("네이버 SEO, 구글 SEO 중 최소 하나는 선택하세요.")
    else:
        from src.generator.blog import generate_google_post, generate_naver_post

        seo_generators = []
        if naver_seo:
            seo_generators.append((generate_naver_post, "Naver SEO"))
        if google_seo:
            seo_generators.append((generate_google_post, "Google SEO"))

        lines: list[str] = []
        log_slot = st.empty()

        def on_log(message: str) -> None:
            lines.append(str(message))
            log_slot.code("\n".join(lines), language=None, height=400)

        with st.status("파이프라인 실행 중...", expanded=True) as status:
            try:
                from main import run_pipeline

                run_pipeline(top_n=int(top_n), seo_generators=seo_generators, on_log=on_log)
            except Exception as e:
                on_log(f"[치명적 오류] {e}")
                status.update(label="파이프라인 실패", state="error")
            else:
                status.update(label="파이프라인 완료", state="complete")
