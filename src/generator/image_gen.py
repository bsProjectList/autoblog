import base64
from src.llm_client import get_openai_client
from src.usage_tracker import record_image_cost

IMAGE_MODEL = "gpt-image-1"

# gpt-image-1은 토큰 단위 과금. 정확한 gpt-image-1 output 단가가 공개되지 않아
# 같은 계열 gpt-image-1.5의 확인된 단가를 근사치로 사용 (실제 비용과 다소 오차 가능).
INPUT_TOKEN_PRICE = 5.00 / 1_000_000
OUTPUT_TOKEN_PRICE = 32.00 / 1_000_000


def generate_image(prompt: str, size: str = "1024x1024") -> bytes:
    client = get_openai_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않아 이미지를 생성할 수 없습니다.")

    response = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size=size,
    )
    data = base64.b64decode(response.data[0].b64_json)

    usage = getattr(response, "usage", None)
    if usage:
        cost = usage.input_tokens * INPUT_TOKEN_PRICE + usage.output_tokens * OUTPUT_TOKEN_PRICE
        record_image_cost(cost)

    return data
