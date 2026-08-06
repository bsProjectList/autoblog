import re
from datetime import datetime

import streamlit as st

from web.common import OUTPUT_DIR, render_copy_blocks, require_api_key

st.title("쇼츠 → 블로그")

st.session_state.setdefault("shorts_source", None)
st.session_state.setdefault("shorts_posts", None)
st.session_state.setdefault("shorts_product_row_count", 1)

with st.container(horizontal=True):
    st.text_input("YouTube Shorts URL", key="shorts_url", label_visibility="collapsed", placeholder="YouTube Shorts URL")
    extract_clicked = st.button("내용 추출", key="shorts_extract_btn", type="primary")

if extract_clicked:
    url = st.session_state["shorts_url"].strip()
    if not url:
        st.warning("YouTube Shorts URL을 입력하세요.")
    else:
        with st.spinner("쇼츠 내용 추출 중..."):
            try:
                from src.collector.youtube_shorts import extract_shorts

                st.session_state["shorts_source"] = extract_shorts(url)
                st.session_state["shorts_posts"] = None
            except Exception as e:
                st.error(f"쇼츠 추출 실패: {e}")
                st.session_state["shorts_source"] = None

source = st.session_state["shorts_source"]
if source is not None:
    st.caption(
        f"제목: {source.get('title', '')} | 채널: {source.get('channel', '')} | "
        f"내용 출처: {source.get('transcript_source', '없음')}"
    )
    transcript = source.get("transcript", "") or source.get("description", "")
    visual_text = source.get("visual_text", "")
    display_text = transcript
    if visual_text:
        display_text += f"\n\n[화면 분석 결과]\n{visual_text}"
    with st.expander("추출된 내용", expanded=True):
        st.text(display_text)

    with st.container(border=True):
        st.caption("쿠팡파트너스 상품 링크 (직접 입력)")
        for i in range(st.session_state["shorts_product_row_count"]):
            with st.container(horizontal=True):
                st.text_input(f"상품명 {i + 1}", key=f"shorts_product_name_{i}", label_visibility="collapsed", placeholder="상품명")
                st.text_input(f"쿠팡 링크 {i + 1}", key=f"shorts_product_url_{i}", label_visibility="collapsed", placeholder="쿠팡 링크")
        if st.button("상품 링크 추가", key="shorts_add_row_btn", icon=":material/add:"):
            st.session_state["shorts_product_row_count"] += 1
            st.rerun()

        st.session_state.setdefault("shorts_naver_checked", True)
        st.session_state.setdefault("shorts_google_checked", True)
        with st.container(horizontal=True):
            naver_checked = st.checkbox("네이버", key="shorts_naver_checked")
            google_checked = st.checkbox("구글", key="shorts_google_checked")
            generate_clicked = st.button("블로그 글 생성", key="shorts_generate_btn", type="primary", icon=":material/auto_awesome:")

    if generate_clicked:
        products = []
        for i in range(st.session_state["shorts_product_row_count"]):
            name = st.session_state.get(f"shorts_product_name_{i}", "").strip()
            url = st.session_state.get(f"shorts_product_url_{i}", "").strip()
            if url:
                products.append({"name": name, "url": url})

        generators = []
        if naver_checked:
            generators.append("naver")
        if google_checked:
            generators.append("google")

        if not products:
            st.warning("쿠팡 링크를 하나 이상 입력하세요.")
        elif not generators:
            st.warning("네이버 또는 구글을 선택하세요.")
        elif require_api_key("GROQ_API_KEY"):
            with st.spinner("블로그 글 생성 중..."):
                try:
                    from src.generator.shorts import generate_shorts_post

                    posts = [generate_shorts_post(source, products, seo_type) for seo_type in generators]
                except Exception as e:
                    st.error(f"쇼츠 글 생성 실패: {e}")
                else:
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    folder = OUTPUT_DIR / "shorts" / date_str
                    paths = []
                    for post in posts:
                        slug = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", post.title).strip("-")[:70] or "shorts"
                        path = folder / f"{slug}_{post.seo_type}.md"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(post.content, encoding="utf-8")
                        paths.append(path)
                    st.session_state["shorts_posts"] = posts
                    st.success(f"생성·저장 완료: {len(paths)}개")
                    st.rerun()

posts = st.session_state["shorts_posts"]
if posts:
    st.subheader("생성 결과")
    for post in posts:
        with st.expander(f"{post.seo_type.upper()} — {post.title}", expanded=True):
            render_copy_blocks(post.content, f"shorts_{post.seo_type}")
