import mimetypes
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

SKIP_IMAGE_PATTERNS = ("icon", "logo", "sprite", "blank.gif", "pixel", "spinner", ".svg")
BLOCK_TITLE_PATTERNS = ("access denied", "just a moment", "406 not acceptable", "attention required")
MIN_IMAGE_SIZE = 200

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

PLATFORM_PATTERNS = [
    (r"coupang\.com|coupa\.ng", "쿠팡 파트너스"),
    (r"smartstore\.naver|naver\.me|shopping\.naver|connect\.naver", "네이버 커넥트"),
    (r"toss|tossshopping", "토스 쇼핑"),
]


def detect_platform(url: str) -> str:
    for pattern, name in PLATFORM_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return "기타 쇼핑몰"


def crawl_product_page(url: str, max_images: int = 5) -> Dict[str, str]:
    result = {
        "title": "",
        "price": "",
        "description": "",
        "image_url": "",
        "image_urls": [],
        "platform": detect_platform(url),
    }

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
            page = context.new_page()
            response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            if response is not None and response.status >= 400:
                result["error"] = f"사이트 접근이 차단되었거나 오류가 발생했습니다 (HTTP {response.status}). 봇 차단 가능성이 높습니다 — 직접 입력해주세요."
                browser.close()
                return result

            page_title = page.title().strip()
            if any(pattern in page_title.lower() for pattern in BLOCK_TITLE_PATTERNS):
                result["error"] = f"사이트에서 접근을 차단한 것으로 보입니다 ('{page_title}'). 직접 입력해주세요."
                browser.close()
                return result

            def meta(prop: str) -> str:
                el = page.query_selector(f'meta[property="{prop}"]') or page.query_selector(f'meta[name="{prop}"]')
                return el.get_attribute("content").strip() if el else ""

            result["title"] = meta("og:title") or page_title
            result["description"] = meta("og:description")

            image_urls: List[str] = []
            og_image = meta("og:image")
            if og_image:
                image_urls.append(urljoin(url, og_image))

            candidates = page.eval_on_selector_all(
                "img",
                "els => els.map(el => ({src: el.currentSrc || el.src, w: el.naturalWidth, h: el.naturalHeight}))",
            )
            for candidate in candidates:
                if len(image_urls) >= max_images:
                    break
                if candidate["w"] < MIN_IMAGE_SIZE or candidate["h"] < MIN_IMAGE_SIZE:
                    continue
                src = candidate.get("src")
                if not src:
                    continue
                src = urljoin(url, src)
                lowered = src.lower()
                if any(skip in lowered for skip in SKIP_IMAGE_PATTERNS):
                    continue
                if src not in image_urls:
                    image_urls.append(src)

            result["image_urls"] = image_urls[:max_images]
            result["image_url"] = image_urls[0] if image_urls else ""

            body_text = page.inner_text("body")[:5000]
            price_match = re.search(r"([\d,]{3,})\s*원", body_text)
            if price_match:
                result["price"] = price_match.group(1) + "원"

            browser.close()
    except Exception as e:
        result["error"] = str(e)

    return result


def download_image(image_url: str) -> Optional[Tuple[bytes, str]]:
    if not image_url:
        return None
    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            content_type = resp.headers.get_content_type()

        ext = mimetypes.guess_extension(content_type) or Path(image_url.split("?")[0]).suffix or ".jpg"
        if ext == ".jpe":
            ext = ".jpg"
        return data, ext
    except Exception:
        return None


def download_images(image_urls: List[str], min_count: int = 3) -> List[Tuple[bytes, str]]:
    images = []
    for image_url in image_urls:
        image = download_image(image_url)
        if image:
            images.append(image)
    if len(images) < min_count:
        print(f"[상품 크롤러] 이미지 {min_count}개 목표였으나 {len(images)}개만 확보됨 (사이트 제공 이미지 부족)")
    return images
