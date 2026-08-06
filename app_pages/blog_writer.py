import io
import re
from datetime import datetime

import streamlit as st

from web.common import OUTPUT_DIR, next_post_folder, render_copy_blocks, render_publish_status, require_api_key

st.title("블로그 글 작성")


def _seo_block(content: str, key: str) -> None:
    if st.button("SEO 진단", key=f"{key}_seo_btn"):
        st.session_state[f"{key}_seo_open"] = True
    if st.session_state.get(f"{key}_seo_open"):
        from src.seo_check import run_seo_check

        icons = {"pass": ":material/check_circle:", "warn": ":material/warning:", "fail": ":material/error:", "info": ":material/info:"}
        colors = {"pass": "green", "warn": "orange", "fail": "red", "info": "gray"}
        with st.expander("SEO 진단 결과", expanded=True):
            for item in run_seo_check(content):
                st.badge(item["label"], icon=icons.get(item["status"], ":material/circle:"), color=colors.get(item["status"], "gray"))
                st.caption(item["detail"])


def render_naver_writer() -> None:
    st.session_state.setdefault("naver_post", None)
    st.session_state.setdefault("naver_thumbnail", None)
    st.session_state.setdefault("naver_last_path", None)

    st.text_area("뉴스 원문 붙여넣기", key="naver_news_text", height=200, persist_state="session")

    if st.button("글 생성", key="naver_generate_btn", type="primary"):
        news_text = st.session_state["naver_news_text"].strip()
        if not news_text:
            st.warning("뉴스 원문을 붙여넣으세요.")
        elif not require_api_key("GROQ_API_KEY"):
            pass
        else:
            with st.spinner("블로그 글 생성 중... (AI 호출)"):
                try:
                    from src.generator.custom_naver import generate_naver_post_from_text

                    post = generate_naver_post_from_text(news_text)
                except Exception as e:
                    st.error(f"생성 실패: {e}")
                else:
                    st.session_state["naver_post"] = post
                    st.session_state["naver_result_text"] = post.content
                    st.session_state["naver_thumbnail"] = None
                    st.session_state["naver_last_path"] = None
                    st.rerun()

    post = st.session_state["naver_post"]
    if post is None:
        return

    with st.container(border=True):
        st.subheader("생성 결과 (저장 전 수정 가능)")
        st.text_area(
            "생성 결과", key="naver_result_text", height=320, label_visibility="collapsed", persist_state="session"
        )
        content = st.session_state["naver_result_text"]

        if st.session_state["naver_thumbnail"]:
            st.image(io.BytesIO(st.session_state["naver_thumbnail"]), width=200, caption="썸네일 미리보기")

        with st.container(horizontal=True):
            save_clicked = st.button("저장", key="naver_save_btn", type="primary", icon=":material/save:")
            if st.button("썸네일 이미지 생성 (유료 API)", key="naver_thumbnail_btn", icon=":material/image:"):
                if not require_api_key("OPENAI_API_KEY"):
                    pass
                else:
                    from src.generator.custom_naver import extract_thumbnail_prompt

                    prompt = extract_thumbnail_prompt(content)
                    if not prompt:
                        st.warning("본문에서 썸네일 프롬프트를 찾을 수 없습니다.")
                    else:
                        with st.spinner("썸네일 이미지 생성 중... (이미지 생성 API 호출)"):
                            try:
                                from src.generator.image_gen import generate_image

                                st.session_state["naver_thumbnail"] = generate_image(prompt, size="1024x1024")
                            except Exception as e:
                                st.error(f"이미지 생성 실패: {e}")
                                st.session_state["naver_thumbnail"] = None
                            else:
                                st.rerun()
            if st.button("SNS 홍보 문구 만들기", key="naver_sns_btn", icon=":material/campaign:"):
                from web.common import send_to_sns_tab

                send_to_sns_tab(post.title, content, st.session_state.get("naver_writer_url", ""))
            _seo_block(content, "naver")

        if save_clicked:
            date_str = datetime.now().strftime("%Y-%m-%d")
            date_folder = OUTPUT_DIR / "blog_writer" / "naver" / date_str
            slug = post.news_item.slug or "post"
            post_folder = next_post_folder(date_folder, slug)

            save_content = content.strip() + "\n"
            thumbnail = st.session_state["naver_thumbnail"]
            if thumbnail:
                image_filename = "thumbnail.png"
                (post_folder / image_filename).write_bytes(thumbnail)

                save_content = re.sub(
                    r"(^#{1,6}\s*.*썸네일.*\n+)?^3D digital thumbnail.+\n?",
                    "",
                    save_content,
                    count=1,
                    flags=re.MULTILINE,
                )
                save_content = save_content.rstrip() + "\n"
                lines = save_content.split("\n", 1)
                if lines[0].startswith("#"):
                    rest = lines[1].lstrip("\n") if len(lines) > 1 else ""
                    save_content = lines[0] + "\n\n" + f"![썸네일]({image_filename})" + "\n\n" + rest
                else:
                    save_content = f"![썸네일]({image_filename})" + "\n\n" + save_content

            path = post_folder / "post.md"
            path.write_text(save_content, encoding="utf-8")
            st.session_state["naver_last_path"] = path
            st.success(f"저장됨: {path}")

        render_copy_blocks(content, "naver_writer")
        render_publish_status("naver_writer", st.session_state["naver_last_path"])


def render_tistory_writer() -> None:
    st.session_state.setdefault("tistory_post", None)
    st.session_state.setdefault("tistory_images", [])
    st.session_state.setdefault("tistory_last_path", None)

    st.text_area("뉴스 원문 붙여넣기", key="tistory_news_text", height=200, persist_state="session")

    if st.button("글 생성", key="tistory_generate_btn", type="primary"):
        news_text = st.session_state["tistory_news_text"].strip()
        if not news_text:
            st.warning("뉴스 원문을 붙여넣으세요.")
        elif not require_api_key("GROQ_API_KEY"):
            pass
        else:
            with st.spinner("블로그 글 생성 중... (AI 호출, 분량이 길어 시간이 걸릴 수 있음)"):
                try:
                    from src.generator.custom_tistory import generate_tistory_post_from_text

                    post = generate_tistory_post_from_text(news_text)
                except Exception as e:
                    st.error(f"생성 실패: {e}")
                else:
                    st.session_state["tistory_post"] = post
                    st.session_state["tistory_result_text"] = post.content
                    st.session_state["tistory_images"] = []
                    st.session_state["tistory_last_path"] = None
                    st.rerun()

    post = st.session_state["tistory_post"]
    if post is None:
        return

    with st.container(border=True):
        st.subheader("생성 결과 (저장 전 수정 가능)")
        st.text_area(
            "생성 결과", key="tistory_result_text", height=320, label_visibility="collapsed", persist_state="session"
        )
        content = st.session_state["tistory_result_text"]

        images = st.session_state["tistory_images"]
        if images:
            st.image([io.BytesIO(item["data"]) for item in images], width=160, caption=[item["alt"] for item in images])

        with st.container(horizontal=True):
            save_clicked = st.button("저장", key="tistory_save_btn", type="primary", icon=":material/save:")
            if st.button("이미지 3장 생성 (유료 API)", key="tistory_image_btn", icon=":material/image:"):
                if not require_api_key("OPENAI_API_KEY"):
                    pass
                else:
                    from src.generator.custom_tistory import extract_image_prompts

                    prompts = extract_image_prompts(content)
                    if not prompts:
                        st.warning("본문에서 이미지 생성 프롬프트를 찾을 수 없습니다.")
                    else:
                        from src.generator.image_gen import generate_image

                        results = []
                        with st.spinner(f"이미지 {len(prompts)}장 생성 중... (이미지 생성 API 호출, 시간이 걸릴 수 있음)"):
                            for item in prompts:
                                try:
                                    data = generate_image(item["prompt"], size="1536x1024")
                                    results.append({"data": data, "alt": item["alt"], "error": None})
                                except Exception as e:
                                    results.append({"data": None, "alt": item["alt"], "error": str(e)})

                        st.session_state["tistory_images"] = [r for r in results if r["data"]]
                        failed = [r for r in results if r["error"]]
                        if failed:
                            st.warning(f"이미지 {len(st.session_state['tistory_images'])}장 생성 완료, {len(failed)}장 실패: {failed[0]['error']}")
                        else:
                            st.success(f"이미지 {len(st.session_state['tistory_images'])}장 생성 완료.")
                        st.rerun()
            if st.button("SNS 홍보 문구 만들기", key="tistory_sns_btn", icon=":material/campaign:"):
                from web.common import send_to_sns_tab

                send_to_sns_tab(post.title, content, st.session_state.get("tistory_writer_url", ""))
            _seo_block(content, "tistory")

        if save_clicked:
            date_str = datetime.now().strftime("%Y-%m-%d")
            date_folder = OUTPUT_DIR / "blog_writer" / "tistory" / date_str
            slug = post.news_item.slug or "post"
            post_folder = next_post_folder(date_folder, slug)

            save_content = content.strip() + "\n"
            if images:
                save_content = re.sub(r"\n##\s*이미지 생성 프롬프트.*\Z", "\n", save_content, flags=re.DOTALL)

                image_lines = []
                for idx, item in enumerate(images, start=1):
                    image_filename = f"image_{idx:02d}.png"
                    (post_folder / image_filename).write_bytes(item["data"])
                    image_lines.append((item["alt"], image_filename))

                heading_positions = [m.start() for m in re.finditer(r"^##\s+(?!✍️).+$", save_content, re.MULTILINE)]
                for idx, (alt, image_filename) in enumerate(image_lines):
                    if idx >= len(heading_positions):
                        break
                    pos = heading_positions[idx]
                    line_end = save_content.index("\n", pos) + 1
                    image_md = f"\n![{alt}]({image_filename})\n\n"
                    save_content = save_content[:line_end] + image_md + save_content[line_end:]
                    heading_positions = [p + len(image_md) if p > pos else p for p in heading_positions]

            path = post_folder / "post.md"
            path.write_text(save_content, encoding="utf-8")
            st.session_state["tistory_last_path"] = path
            st.success(f"저장됨: {path}")

        render_copy_blocks(content, "tistory_writer")
        render_publish_status("tistory_writer", st.session_state["tistory_last_path"])


tab_naver, tab_tistory = st.tabs(["네이버 블로그", "티스토리 블로그"])
with tab_naver:
    render_naver_writer()
with tab_tistory:
    render_tistory_writer()
