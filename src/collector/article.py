"""뉴스 링크에서 본문 텍스트를 보강 수집하는 경량 추출기."""

from html.parser import HTMLParser
from urllib.request import Request, urlopen


class _ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self._in_paragraph = False
        self._buffer = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self._skip += 1
        elif tag in {"p", "article"} and not self._skip:
            self._in_paragraph = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self._skip = max(0, self._skip - 1)
        elif tag in {"p", "article"} and self._in_paragraph:
            text = " ".join("".join(self._buffer).split())
            if len(text) >= 30:
                self.paragraphs.append(text)
            self._buffer = []
            self._in_paragraph = False

    def handle_data(self, data):
        if self._in_paragraph and not self._skip:
            self._buffer.append(data)


def fetch_article_text(url: str, max_chars: int = 6000) -> str:
    """원문 본문을 추출한다. 실패하면 빈 문자열을 반환해 RSS 요약을 사용하게 한다."""
    if not url:
        return ""
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 AutoBlog/1.0",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )
        with urlopen(request, timeout=15) as response:
            raw = response.read(2_000_000)
        parser = _ArticleParser()
        parser.feed(raw.decode("utf-8", errors="ignore"))
        return "\n\n".join(parser.paragraphs)[:max_chars]
    except Exception as exc:
        print(f"[Article] 원문 보강 실패: {exc}")
        return ""
