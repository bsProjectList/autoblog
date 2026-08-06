import streamlit as st

from src.goal_tracker import calculate_summary, load_state, save_state

st.title("쿠팡파트너스 월 300만원 운영 대시보드")

if "goal_state" not in st.session_state:
    st.session_state["goal_state"] = load_state()
state = st.session_state["goal_state"]

summary = calculate_summary(state)
with st.container(border=True):
    with st.container(horizontal=True):
        st.metric("목표 수익", f"{summary['target']:,}원")
        st.metric("현재 수익", f"{summary['current']:,}원")
        st.metric("진행률", f"{summary['progress']:.1f}%")
        st.metric("남은 주문 필요 수", f"{summary['orders_needed']:,}건")
    st.progress(summary["progress"] / 100)

with st.form("goal_form"):
    tab_strategy, tab_daily, tab_benchmark, tab_metrics = st.tabs(
        ["타깃·채널 전략", "오늘 실행", "벤치마킹·대본", "채널 성과"]
    )

    with tab_strategy:
        target_revenue = st.number_input("월 목표 수익(원)", value=int(state["target_revenue"]), step=100_000)
        current_revenue = st.number_input("현재 수익(원)", value=int(state["current_revenue"]), step=10_000)
        category = st.text_input("카테고리", value=state["category"])
        persona = st.text_input("핵심 타깃", value=state["persona"])
        tone = st.text_input("페르소나 말투", value=state["tone"])
        keywords = st.text_input("핵심 키워드", value=state["keywords"])
        st.caption(
            "채널 운영 원칙 — Threads: 확산·댓글 소통 / Instagram: 릴스·신뢰 / Blog: 검색·전환  \n"
            "자동 댓글·자동 업로드 없이 수동 운영을 기록합니다."
        )

    with tab_daily:
        daily = state["daily"]
        col1, col2 = st.columns(2)
        with col1:
            analyzed_posts = st.number_input("분석한 떡상 게시글 수 (목표 50)", value=int(daily.get("analyzed_posts", 0)), min_value=0)
            scripts = st.number_input("준비한 대본 수 (목표 5)", value=int(daily.get("scripts", 0)), min_value=0)
            comments = st.number_input("자연스러운 댓글 소통 수", value=int(daily.get("comments", 0)), min_value=0)
            manual_uploads = st.number_input("수동 업로드 수", value=int(daily.get("manual_uploads", 0)), min_value=0)
            link_eligible_posts = st.number_input(
                "조회수 2,000 이상 링크 게시물 수", value=int(daily.get("link_eligible_posts", 0)), min_value=0
            )
        with col2:
            st.caption("오늘 체크리스트")
            checklist = daily.get("checklist", {})
            check_labels = ["추천탭 눈팅 완료", "관련 카테고리 검색 완료", "벤치마킹 계정 분석", "대본 5개 준비", "수동 업로드 기록", "수익·조회수 기록"]
            check_values = {label: st.checkbox(label, value=bool(checklist.get(label, False))) for label in check_labels}

    with tab_benchmark:
        st.caption("게시물 URL, 조회수, 후킹 문장, 구조, 댓글 반응을 기록하세요. 하루 50개 분석을 목표로 합니다.")
        benchmark_notes = st.text_area("벤치마킹 노트", value=daily.get("benchmark_notes", ""), height=150)
        st.caption("대본 형식: 1) 후킹 2) 문제 3) 해결·상품 4) CTA 5) 채널별 변환 메모")
        scripts_text = st.text_area("대본", value=daily.get("scripts_text", ""), height=200)

    with tab_metrics:
        channels = state["channels"]
        channel_values = {}
        for channel, label in [("threads", "Threads"), ("instagram", "Instagram"), ("blog", "Blog")]:
            st.caption(label)
            c1, c2, c3 = st.columns(3)
            for field in ("views", "clicks", "orders"):
                st.session_state.setdefault(f"goal_{channel}_{field}", int(channels[channel].get(field, 0)))
            channel_values[channel] = {
                "views": c1.number_input("조회수", min_value=0, key=f"goal_{channel}_views"),
                "clicks": c2.number_input("클릭", min_value=0, key=f"goal_{channel}_clicks"),
                "orders": c3.number_input("주문", min_value=0, key=f"goal_{channel}_orders"),
            }

    submitted = st.form_submit_button("저장·계산", type="primary")

if submitted:
    state["target_revenue"] = int(target_revenue)
    state["current_revenue"] = int(current_revenue)
    state["category"] = category.strip()
    state["persona"] = persona.strip()
    state["tone"] = tone.strip()
    state["keywords"] = keywords.strip()
    state["daily"]["analyzed_posts"] = int(analyzed_posts)
    state["daily"]["scripts"] = int(scripts)
    state["daily"]["comments"] = int(comments)
    state["daily"]["manual_uploads"] = int(manual_uploads)
    state["daily"]["link_eligible_posts"] = int(link_eligible_posts)
    state["daily"]["checklist"] = check_values
    state["daily"]["benchmark_notes"] = benchmark_notes.strip()
    state["daily"]["scripts_text"] = scripts_text.strip()
    for channel, values in channel_values.items():
        state["channels"][channel].update(values)
    path = save_state(state)
    st.success(f"저장됨: {path}")
    st.rerun()

st.subheader("게시물·링크 게이트")
with st.container(border=True):
    st.session_state.setdefault("goal_avg_commission", int(state.get("average_commission", 5000)))
    avg_commission = st.number_input("평균 주문 수수료(원)", min_value=1, step=500, key="goal_avg_commission")
    if avg_commission != state.get("average_commission"):
        state["average_commission"] = int(avg_commission)
        save_state(state)

    with st.form("goal_post_form", clear_on_submit=True):
        st.caption("게시물 성과 기록")
        c1, c2 = st.columns(2)
        post_channel = c1.selectbox("채널", ["threads", "instagram", "blog"])
        post_title = c2.text_input("제목/메모")
        post_url = st.text_input("URL")
        c3, c4, c5, c6 = st.columns(4)
        post_views = c3.number_input("조회수", min_value=0, value=0)
        post_clicks = c4.number_input("클릭", min_value=0, value=0)
        post_orders = c5.number_input("주문", min_value=0, value=0)
        post_revenue = c6.number_input("수익", min_value=0, value=0)
        post_link_added = st.checkbox("쿠팡 링크 삽입")
        post_submitted = st.form_submit_button("게시물 저장", type="primary")

    if post_submitted:
        if post_link_added and post_views < 2000:
            st.warning("링크 삽입 보류 — 조회수 2,000회 이상인 게시물에만 쿠팡 링크를 삽입할 수 있습니다.")
        else:
            from datetime import datetime

            state.setdefault("posts", []).append(
                {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "channel": post_channel,
                    "title": post_title.strip() or "제목 없음",
                    "url": post_url.strip(),
                    "views": int(post_views),
                    "clicks": int(post_clicks),
                    "orders": int(post_orders),
                    "revenue": int(post_revenue),
                    "link_added": bool(post_link_added and post_views >= 2000),
                }
            )
            state["current_revenue"] = sum(int(p.get("revenue", 0)) for p in state["posts"])
            save_state(state)
            st.success("게시물이 저장되었습니다.")
            st.rerun()

    for item in reversed(state.get("posts", [])):
        gate = "링크 허용" if item.get("link_added") else "링크 대기"
        st.caption(
            f"[{item.get('channel', '')}] {item.get('title', '')[:35]} | 조회 {item.get('views', 0):,} | "
            f"클릭 {item.get('clicks', 0):,} | 주문 {item.get('orders', 0):,} | 수익 {item.get('revenue', 0):,}원 | {gate}"
        )
