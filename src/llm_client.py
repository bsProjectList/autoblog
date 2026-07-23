import os
import time
from groq import Groq, RateLimitError as GroqRateLimitError
from src.usage_tracker import get_today_tokens, record_usage

try:
    from openai import OpenAI, RateLimitError as OpenAIRateLimitError
except ImportError:
    OpenAI = None
    OpenAIRateLimitError = None

GROQ_MODEL = "llama-3.3-70b-versatile"
OPENAI_MODEL = "gpt-4o-mini"
GROQ_DAILY_TOKEN_LIMIT = int(os.environ.get("GROQ_DAILY_TOKEN_LIMIT", "90000"))

_groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
_openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) if (OpenAI and os.environ.get("OPENAI_API_KEY")) else None


def get_openai_client():
    return _openai_client


def _fallback_to_openai(e: Exception):
    if not _openai_client:
        raise RuntimeError(
            f"Groq 무료 한도를 초과했고 OPENAI_API_KEY도 설정되어 있지 않아 대체할 수 없습니다: {e}"
        ) from e
    print(f"[LLM] Groq 한도 초과 → OpenAI({OPENAI_MODEL})로 자동 전환")


def _groq_budget_exceeded() -> bool:
    return get_today_tokens("groq") >= GROQ_DAILY_TOKEN_LIMIT


def _request_with_retry(client, **kwargs):
    last_error = None
    for attempt in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise last_error


def chat_completion(messages, temperature=0.7, max_tokens=4000, response_format=None):
    kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if response_format:
        kwargs["response_format"] = response_format

    try:
        if _groq_budget_exceeded():
            raise RuntimeError(f"Groq 일일 토큰 한도({GROQ_DAILY_TOKEN_LIMIT:,})에 도달했습니다.")
        response = _request_with_retry(_groq_client, model=GROQ_MODEL, **kwargs)
        provider = "groq"
    except Exception as e:
        _fallback_to_openai(e)
        response = _request_with_retry(_openai_client, model=OPENAI_MODEL, **kwargs)
        provider = "openai"

    if getattr(response, "usage", None):
        record_usage(provider, response.usage.total_tokens)

    return response


def stream_completion(messages, temperature=0.7, max_tokens=8000):
    kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}

    try:
        if _groq_budget_exceeded():
            raise RuntimeError(f"Groq 일일 토큰 한도({GROQ_DAILY_TOKEN_LIMIT:,})에 도달했습니다.")
        stream = _request_with_retry(_groq_client, model=GROQ_MODEL, **kwargs)
        provider = "groq"
    except Exception as e:
        _fallback_to_openai(e)
        stream = _request_with_retry(_openai_client, model=OPENAI_MODEL, **kwargs)
        provider = "openai"

    return _tracked_stream(stream, provider, messages)


def _tracked_stream(stream, provider, messages):
    accumulated_chars = 0
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            accumulated_chars += len(delta)
        yield chunk

    prompt_chars = sum(len(m.get("content", "")) for m in messages)
    estimated_tokens = (prompt_chars + accumulated_chars) // 2
    record_usage(provider, estimated_tokens, estimated=True)
