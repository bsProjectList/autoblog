import os
from groq import Groq, RateLimitError as GroqRateLimitError

try:
    from openai import OpenAI, RateLimitError as OpenAIRateLimitError
except ImportError:
    OpenAI = None
    OpenAIRateLimitError = None

GROQ_MODEL = "llama-3.3-70b-versatile"
OPENAI_MODEL = "gpt-4o-mini"

_groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
_openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) if (OpenAI and os.environ.get("OPENAI_API_KEY")) else None


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
        return _groq_client.chat.completions.create(model=GROQ_MODEL, **kwargs)
    except GroqRateLimitError as e:
        _fallback_to_openai(e)
        return _openai_client.chat.completions.create(model=OPENAI_MODEL, **kwargs)


def stream_completion(messages, temperature=0.7, max_tokens=8000):
    kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}

    try:
        return _groq_client.chat.completions.create(model=GROQ_MODEL, **kwargs)
    except GroqRateLimitError as e:
        _fallback_to_openai(e)
        return _openai_client.chat.completions.create(model=OPENAI_MODEL, **kwargs)
