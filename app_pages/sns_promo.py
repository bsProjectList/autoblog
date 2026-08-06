import streamlit as st

from web.common import require_api_key

st.title("SNS 홍보")

st.session_state.setdefault("sns_title", "")
st.session_state.setdefault("sns_url", "")
st.session_state.setdefault("sns_summary", "")
st.session_state.setdefault("sns_captions", None)

with st.container(border=True):
    st.text_input("글 제목", key="sns_title", persist_state="session")
    st.text_input("게시된 글 URL", key="sns_url", persist_state="session")
    st.text_area("핵심 내용 요약 (선택)", key="sns_summary", height=100, persist_state="session")

    if st.button("홍보 문구 생성", type="primary", icon=":material/auto_awesome:"):
        title = st.session_state["sns_title"].strip()
        url = st.session_state["sns_url"].strip()
        summary = st.session_state["sns_summary"].strip()

        if not title or not url:
            st.warning("글 제목과 URL을 입력하세요.")
        elif require_api_key("GROQ_API_KEY"):
            with st.spinner("홍보 문구 생성 중... (AI 호출)"):
                try:
                    from src.generator.sns_promo import generate_sns_captions, save_captions

                    captions = generate_sns_captions(title, url, summary)
                    saved_path = save_captions(captions, title, url)
                except Exception as e:
                    st.error(f"생성 실패: {e}")
                else:
                    st.session_state["sns_captions"] = captions
                    st.success(f"생성 완료 및 저장됨: {saved_path}")
                    st.rerun()

captions = st.session_state["sns_captions"]
if captions:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("쓰레드(Threads)용")
            st.code(captions.get("threads", ""), language=None, wrap_lines=True, height=200)
        with col2:
            st.subheader("인스타그램용")
            st.code(captions.get("instagram", ""), language=None, wrap_lines=True, height=200)
