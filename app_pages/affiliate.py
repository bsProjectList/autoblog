import io
import json
import re
from datetime import datetime

import streamlit as st

from web.common import OUTPUT_DIR, next_post_folder, render_copy_blocks, render_publish_status, require_api_key

st.title("제휴 글 생성")

PLATFORMS = [
    ("naver", "네이버 커넥트", False),
    ("coupang", "쿠팡 파트너스", True),
    ("toss", "토스 쇼핑", False),
]


def _state(kind: str, field: str, default=None):
    key = f"aff_{kind}_{field}"
    if key not in st.session_state:
        st.session_state[key] = default
    return key


def render_platform(kind: str, label: str, show_coupang_search: bool) -> None:
    url_key = _state(kind, "url", "")
    platform_key = _state(kind, "platform", label)
    name_key = _state(kind, "name", "")
    price_key = _state(kind, "price", "")
    desc_key = _state(kind, "desc", "")
    images_key = _state(kind, "images", [])
    reviews_key = _state(kind, "reviews", [])
    coupang_results_key = _state(kind, "coupang_results", [])
    post_key = _state(kind, "post", None)
    result_text_key = _state(kind, "result_text", "")
    last_path_key = _state(kind, "last_path", None)

    with st.container(border=True):
        if show_coupang_search:
            with st.expander("쿠팡 상품 검색 (Open API — 크롤링 차단 없음)", icon=":material/search:"):
                with st.container(horizontal=True):
                    keyword = st.text_input("검색어", key=f"aff_{kind}_keyword", label_visibility="collapsed", placeholder="검색어")
                    search_clicked = st.button("검색", key=f"aff_{kind}_search_btn")
                if search_clicked:
                    if not keyword.strip():
                        st.warning("검색어를 입력하세요.")
                    else:
                        from src.collector.coupang_api import search_products

                        with st.spinner("쿠팡 상품 검색 중..."):
                            try:
                                st.session_state[coupang_results_key] = search_products(keyword.strip(), limit=5)
                            except Exception as e:
                                st.error(f"쿠팡 검색 실패: {e}")

                results = st.session_state[coupang_results_key]
                if results:
                    labels = [f"{p['title'][:45]} - {p['price']}" for p in results]
                    choice = st.radio("검색 결과", labels, key=f"aff_{kind}_coupang_choice", label_visibility="collapsed")
                    if st.button("이 상품 불러오기", key=f"aff_{kind}_use_result_btn"):
                        product = results[labels.index(choice)]
                        st.session_state[url_key] = product["product_url"]
                        st.session_state[platform_key] = "쿠팡 파트너스"
                        st.session_state[name_key] = product["title"]
                        st.session_state[price_key] = product["price"]
                        st.session_state[desc_key] = product["description"]
                        st.session_state[reviews_key] = []

                        from src.collector.product_crawler import download_images

                        with st.spinner("상품 이미지 다운로드 중..."):
                            st.session_state[images_key] = download_images([product["image_url"]], min_count=1)
                        st.rerun()

        with st.expander("크롬 확장 프로그램으로 복사한 상품 정보 붙여넣기", icon=":material/content_paste:"):
            st.caption(
                "크롬 확장 프로그램으로 상품 페이지에서 정보를 복사한 뒤, 아래에 Ctrl+V로 붙여넣고 버튼을 누르세요."
            )
            pasted = st.text_area("붙여넣기", key=f"aff_{kind}_paste_area", label_visibility="collapsed", height=100)
            if st.button("붙여넣은 내용 처리", key=f"aff_{kind}_paste_btn"):
                try:
                    data = json.loads(pasted)
                except Exception as e:
                    st.error(f"붙여넣은 내용을 상품 정보로 읽을 수 없습니다: {e}")
                else:
                    from src.collector.product_crawler import detect_platform, download_images

                    url = data.get("url", "")
                    platform = detect_platform(url) if url else data.get("hostname", "")
                    final_url = url
                    was_converted = False
                    if platform == "쿠팡 파트너스" and url:
                        from src.collector.coupang_api import create_deeplink

                        try:
                            final_url = create_deeplink(url)
                            was_converted = final_url != url
                        except Exception as e:
                            st.warning(f"쿠팡 딥링크(제휴 링크) 변환 실패, 원본 URL 사용: {e}")

                    with st.spinner("이미지 다운로드 중..."):
                        images = download_images(data.get("image_urls", []), min_count=3)

                    st.session_state[url_key] = final_url
                    st.session_state[platform_key] = platform
                    st.session_state[name_key] = data.get("title", "")
                    st.session_state[price_key] = data.get("price", "")
                    st.session_state[desc_key] = data.get("description", "")
                    st.session_state[reviews_key] = data.get("reviews", [])
                    st.session_state[images_key] = images

                    if platform == "쿠팡 파트너스":
                        if was_converted:
                            st.success("쿠팡 URL을 파트너스 제휴 링크로 자동 변환했습니다.")
                        else:
                            st.warning("제휴 링크 변환 실패 — 원본 URL이 남아있어 수수료가 안 붙을 수 있습니다.")
                    st.rerun()

        st.caption(f"상품 URL ({label})")
        with st.container(horizontal=True):
            st.text_input(
                "상품 URL", key=url_key, label_visibility="collapsed", placeholder=f"{label} 상품 URL", persist_state="session"
            )
            fetch_clicked = st.button("정보 가져오기", key=f"aff_{kind}_fetch_btn")

        if fetch_clicked:
            url = st.session_state[url_key].strip()
            if not url:
                st.warning("URL을 입력하세요.")
            else:
                from src.collector.product_crawler import detect_platform

                if detect_platform(url) == "쿠팡 파트너스":
                    st.warning(
                        "쿠팡은 URL 크롤링이 차단되어 있어 여기로는 정보를 못 가져옵니다. "
                        "위쪽 '쿠팡 상품 검색' 박스에 키워드를 입력해서 검색해주세요."
                    )
                else:
                    from src.collector.product_crawler import crawl_product_page, download_images

                    with st.spinner("상품 정보 가져오는 중..."):
                        result = crawl_product_page(url)
                        images = download_images(result.get("image_urls", []), min_count=3)

                    st.session_state[platform_key] = result.get("platform", "")
                    st.session_state[name_key] = result.get("title", "")
                    st.session_state[price_key] = result.get("price", "")
                    st.session_state[desc_key] = result.get("description", "")
                    st.session_state[images_key] = images
                    st.session_state[reviews_key] = []

                    if result.get("error"):
                        st.warning(f"일부 정보를 가져오지 못했습니다 ({result['error'][:80]}). 직접 입력 후 진행하세요.")
                    elif len(images) < 3:
                        st.info(f"이미지 {len(images)}개만 확보됨(목표 3개+). 필요시 수정 후 '글 생성'을 누르세요.")
                    else:
                        st.success(f"정보와 이미지 {len(images)}개를 가져왔습니다.")
                    st.rerun()

        with st.expander("상품 정보 (자동 수집 실패 시 직접 입력)", icon=":material/edit:", expanded=True):
            st.text_input("플랫폼", key=platform_key, persist_state="session")
            st.text_input("상품명", key=name_key, persist_state="session")
            st.text_input("가격", key=price_key, persist_state="session")
            st.text_area("설명", key=desc_key, height=80, persist_state="session")

            images = st.session_state[images_key]
            st.caption(f"상품 이미지 ({len(images)}개)")
            if images:
                st.image([io.BytesIO(data) for data, _ext in images], width=140)
            else:
                st.caption("(이미지 없음)")

        if st.button("글 생성", key=f"aff_{kind}_generate_btn", type="primary", icon=":material/auto_awesome:"):
            url = st.session_state[url_key].strip()
            if not url:
                st.warning("URL을 입력하세요.")
            elif not require_api_key("GROQ_API_KEY"):
                pass
            else:
                images = st.session_state[images_key]
                product = {
                    "platform": st.session_state[platform_key].strip(),
                    "title": st.session_state[name_key].strip(),
                    "price": st.session_state[price_key].strip(),
                    "description": st.session_state[desc_key].strip(),
                    "reviews": st.session_state[reviews_key],
                }
                with st.spinner("블로그 글 생성 중... (AI 호출)"):
                    try:
                        from src.generator.affiliate import generate_affiliate_post

                        post = generate_affiliate_post(url, product, image_count=len(images))
                    except Exception as e:
                        st.error(f"생성 실패: {e}")
                    else:
                        st.session_state[post_key] = post
                        st.session_state[result_text_key] = post.content
                        st.success("생성 완료. 필요하면 아래에서 수정한 뒤 저장하세요.")
                        st.rerun()

    post = st.session_state[post_key]
    if post is not None:
        images = st.session_state[images_key]
        with st.container(border=True):
            st.subheader("생성 결과 (저장 전 수정 가능)")
            st.text_area("생성 결과", key=result_text_key, height=320, label_visibility="collapsed", persist_state="session")

            with st.container(horizontal=True):
                save_clicked = st.button("저장", key=f"aff_{kind}_save_btn", type="primary", icon=":material/save:")
                if st.button("SNS 홍보 문구 만들기", key=f"aff_{kind}_sns_btn", icon=":material/campaign:"):
                    from web.common import send_to_sns_tab

                    send_to_sns_tab(post.title, st.session_state[result_text_key], "")
                if st.button("SEO 진단", key=f"aff_{kind}_seo_btn", icon=":material/fact_check:"):
                    st.session_state[f"aff_{kind}_seo_open"] = True

            if save_clicked:
                date_str = datetime.now().strftime("%Y-%m-%d")
                date_folder = OUTPUT_DIR / "affiliate" / date_str
                slug = post.news_item.slug or "affiliate"
                post_folder = next_post_folder(date_folder, slug)

                content = st.session_state[result_text_key].strip() + "\n"

                if images:
                    product_name = st.session_state[name_key].strip() or "상품 이미지"
                    image_filenames = []
                    for idx, (data, ext) in enumerate(images, start=1):
                        image_filename = f"image_{idx:02d}{ext}"
                        (post_folder / image_filename).write_bytes(data)
                        image_filenames.append(image_filename)

                    used_indices = set()

                    def replace_placeholder(match):
                        idx = int(match.group(1))
                        if 1 <= idx <= len(image_filenames) and idx not in used_indices:
                            used_indices.add(idx)
                            return f"![{product_name} {idx}]({image_filenames[idx - 1]})"
                        return ""

                    content = re.sub(r"\[IMAGE_(\d+)\]", replace_placeholder, content)

                    leftover = [f for i, f in enumerate(image_filenames, start=1) if i not in used_indices]
                    if leftover:
                        leftover_md = "\n\n".join(f"![{product_name}]({f})" for f in leftover)
                        tag_match = re.search(r"\n##\s*태그", content)
                        if tag_match:
                            pos = tag_match.start()
                            content = content[:pos] + "\n" + leftover_md + "\n" + content[pos:]
                        else:
                            content = content.rstrip() + "\n\n" + leftover_md + "\n"

                path = post_folder / "post.md"
                path.write_text(content, encoding="utf-8")
                st.session_state[last_path_key] = path
                st.success(f"저장됨: {path}")

            if st.session_state.get(f"aff_{kind}_seo_open"):
                from src.seo_check import run_seo_check

                icons = {"pass": ":material/check_circle:", "warn": ":material/warning:", "fail": ":material/error:", "info": ":material/info:"}
                colors = {"pass": "green", "warn": "orange", "fail": "red", "info": "gray"}
                with st.expander("SEO 진단 결과", expanded=True):
                    for item in run_seo_check(st.session_state[result_text_key]):
                        st.badge(item["label"], icon=icons.get(item["status"], ":material/circle:"), color=colors.get(item["status"], "gray"))
                        st.caption(item["detail"])

            render_copy_blocks(st.session_state[result_text_key], f"aff_{kind}")
            render_publish_status(f"aff_{kind}", st.session_state[last_path_key])


tabs = st.tabs([label for _kind, label, _show in PLATFORMS])
for tab, (kind, label, show_coupang_search) in zip(tabs, PLATFORMS):
    with tab:
        render_platform(kind, label, show_coupang_search)
