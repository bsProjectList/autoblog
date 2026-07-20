import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List

DOMAIN = "https://api-gateway.coupang.com"
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"
DEEPLINK_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"


def _sign(method: str, path: str, query: str = "") -> str:
    access_key = os.environ.get("COUPANG_ACCESS_KEY", "")
    secret_key = os.environ.get("COUPANG_SECRET_KEY", "")

    signed_date = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    message = signed_date + method + path + query
    signature = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={signed_date}, signature={signature}"


def search_products(keyword: str, limit: int = 5) -> List[Dict]:
    if not os.environ.get("COUPANG_ACCESS_KEY") or not os.environ.get("COUPANG_SECRET_KEY"):
        raise RuntimeError("COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY가 설정되어 있지 않습니다.")

    query = f"keyword={urllib.parse.quote(keyword)}&limit={limit}"
    authorization = _sign("GET", SEARCH_PATH, query)

    url = f"{DOMAIN}{SEARCH_PATH}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": authorization, "Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    if body.get("rCode") not in ("0", 0):
        raise RuntimeError(f"쿠팡 API 오류: {body.get('rMessage')}")

    products = []
    for item in body.get("data", {}).get("productData", []):
        products.append({
            "product_id": item.get("productId"),
            "title": item.get("productName", ""),
            "price": f"{item.get('productPrice', 0):,}원",
            "description": f"카테고리: {item.get('categoryName', '')}",
            "image_url": item.get("productImage", ""),
            "product_url": item.get("productUrl", ""),
            "is_rocket": item.get("isRocket", False),
            "is_free_shipping": item.get("isFreeShipping", False),
        })
    return products


def create_deeplink(coupang_url: str) -> str:
    if not os.environ.get("COUPANG_ACCESS_KEY") or not os.environ.get("COUPANG_SECRET_KEY"):
        raise RuntimeError("COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY가 설정되어 있지 않습니다.")

    body = json.dumps({"coupangUrls": [coupang_url]})
    authorization = _sign("POST", DEEPLINK_PATH)

    req = urllib.request.Request(
        f"{DOMAIN}{DEEPLINK_PATH}",
        data=body.encode("utf-8"),
        headers={"Authorization": authorization, "Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        response_body = json.loads(resp.read().decode("utf-8"))

    if response_body.get("rCode") not in ("0", 0):
        raise RuntimeError(f"쿠팡 딥링크 변환 오류: {response_body.get('rMessage')}")

    data = response_body.get("data", [])
    if not data:
        raise RuntimeError("쿠팡 딥링크 변환 결과가 비어 있습니다.")

    return data[0].get("shortenUrl") or data[0].get("landingUrl") or coupang_url
