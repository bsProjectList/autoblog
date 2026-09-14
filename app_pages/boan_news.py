from datetime import datetime
import re
from zoneinfo import ZoneInfo

import streamlit as st

from src.boan_digest import collect_boan_top10
from src.collector.article import fetch_article_text


KST = ZoneInfo("Asia/Seoul")


@st.cache_data(ttl=900, show_spinner=False)
def load_today_news():
    return collect_boan_top10(limit=10)


@st.cache_data(ttl=86400, show_spinner=False)
def load_article(url: str) -> str:
    return fetch_article_text(url, max_chars=20000)


def render_article_body(content: str) -> None:
    """문단과 원문 줄바꿈을 Streamlit 블록으로 분리해 가독성을 유지한다."""
    blocks = [re.sub(r"[ \t]+", " ", block).strip() for block in re.split(r"\n{2,}", content)]
    for block in blocks:
        if block:
            st.markdown(block.replace("\n", "  \n"))


st.title("보안뉴스")
st.caption(f"보안뉴스 RSS 기준 · {datetime.now(KST):%Y-%m-%d %H:%M} KST · 카테고리별 최신 TOP 10")

if st.button("뉴스 새로고침", icon=":material/refresh:"):
    load_today_news.clear()
    load_article.clear()
    st.rerun()

categories = load_today_news()
category_tabs = st.tabs(list(categories))

for tab, (category, items) in zip(category_tabs, categories.items()):
    with tab:
        if not items:
            st.warning("현재 기사를 가져오지 못했습니다. 잠시 후 새로고침해 주세요.")
            continue

        options = [f"{index}. {item.title}" for index, item in enumerate(items, start=1)]
        selected_index = st.selectbox(
            "기사 선택",
            range(len(items)),
            format_func=lambda index: options[index],
            key=f"boan_news_{category}",
        )
        item = items[selected_index]

        st.subheader(item.title)
        st.caption(f"출처: {item.source} · {item.published_at or '게시일 정보 없음'}")
        st.markdown(f"[보안뉴스 원문 열기]({item.url})")

        with st.container(border=True):
            st.markdown("**RSS 요약**")
            st.write(item.summary)

        with st.spinner("기사 본문을 불러오는 중..."):
            article_text = load_article(item.url)
        if article_text:
            st.divider()
            st.markdown("### 기사 본문")
            with st.container(border=True):
                render_article_body(article_text)
        else:
            st.info("본문을 가져오지 못했습니다. 원문 링크에서 확인해 주세요.")
