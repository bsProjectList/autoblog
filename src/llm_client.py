import os
from groq import Groq, RateLimitError as GroqRateLimitError
from src.usage_tracker import record_usage

try:
    from openai import OpenAI, RateLimitError as OpenAIRateLimitError
except ImportError:
    OpenAI = None
    OpenAIRateLimitError = None

GROQ_MODEL = "llama-3.3-70b-versatile"
OPENAI_MODEL = "gpt-4o-mini"

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


def chat_completion(messages, temperature=0.7, max_tokens=4000, response_format=None):
    kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if response_format:
        kwargs["response_format"] = response_format

    try:
        response = _groq_client.chat.completions.create(model=GROQ_MODEL, **kwargs)
        provider = "groq"
    except GroqRateLimitError as e:
        _fallback_to_openai(e)
        response = _openai_client.chat.completions.create(model=OPENAI_MODEL, **kwargs)
        provider = "openai"

    if getattr(response, "usage", None):
        record_usage(provider, response.usage.total_tokens)

    return response


def stream_completion(messages, temperature=0.7, max_tokens=8000):
    kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}

    try:
        stream = _groq_client.chat.completions.create(model=GROQ_MODEL, **kwargs)
        provider = "groq"
    except GroqRateLimitError as e:
        _fallback_to_openai(e)
        stream = _openai_client.chat.completions.create(model=OPENAI_MODEL, **kwargs)
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
