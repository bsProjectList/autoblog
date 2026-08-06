import streamlit as st

from web.common import render_usage_sidebar

st.set_page_config(page_title="AutoBlog", page_icon=":material/newspaper:", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/viewer.py", title="생성된 글 보기", icon=":material/article:"),
        st.Page("app_pages/affiliate.py", title="제휴 글 생성", icon=":material/storefront:"),
        st.Page("app_pages/blog_writer.py", title="블로그 글 작성", icon=":material/edit_note:"),
        st.Page("app_pages/shorts.py", title="쇼츠 → 블로그", icon=":material/smart_display:"),
        st.Page("app_pages/goal.py", title="월 300만원", icon=":material/target:"),
        st.Page("app_pages/sns_promo.py", title="SNS 홍보", icon=":material/campaign:"),
        st.Page("app_pages/pipeline.py", title="파이프라인 실행", icon=":material/play_circle:"),
    ],
    position="top",
)

render_usage_sidebar()

page.run()
