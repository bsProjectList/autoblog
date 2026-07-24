"""YouTube Shorts metadata and transcript extraction."""

import html
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


def extract_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.netloc.lower() not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        raise ValueError("유튜브 쇼츠 URL을 입력하세요.")
    if parsed.netloc.lower() == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.path.startswith("/shorts/"):
        video_id = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
    else:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id or ""):
        raise ValueError("유효한 YouTube 영상 ID를 찾을 수 없습니다.")
    return video_id


def _clean_transcript(raw: str) -> str:
    lines = []
    seen = set()
    for line in raw.replace("\r", "").split("\n"):
        line = re.sub(r"<[^>]+>", "", html.unescape(line)).strip()
        if not line or "-->" in line or line.isdigit() or line.upper() == "WEBVTT":
            continue
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return " ".join(lines)


def _fetch_caption(caption_url: str) -> str:
    request = Request(caption_url, headers={"User-Agent": "Mozilla/5.0 AutoBlog/1.0"})
    with urlopen(request, timeout=20) as response:
        return _clean_transcript(response.read().decode("utf-8", errors="ignore"))


def _extract_caption(info: dict) -> str:
    caption_sets = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    for captions in caption_sets:
        for language in ("ko", "ko-KR", "en", "en-US"):
            formats = captions.get(language) or []
            for item in reversed(formats):
                if item.get("url"):
                    try:
                        text = _fetch_caption(item["url"])
                        if text:
                            return text
                    except Exception:
                        continue
    return ""


def _transcribe_audio(info: dict) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        return ""
    from openai import OpenAI

    with tempfile.TemporaryDirectory(prefix="autoblog-shorts-") as temp_dir:
        output_template = str(Path(temp_dir) / "audio.%(ext)s")
        try:
            import yt_dlp

            options = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([info["webpage_url"]])
            files = list(Path(temp_dir).glob("audio.*"))
            if not files:
                return ""
            with files[0].open("rb") as audio_file:
                result = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text",
                )
            return str(result).strip()
        except Exception as exc:
            print(f"[Shorts] 음성 인식 실패: {exc}")
            return ""


def extract_shorts(url: str) -> dict:
    """공개 쇼츠의 정보와 자막을 반환한다. 자막이 없으면 음성 인식을 시도한다."""
    video_id = extract_video_id(url)
    try:
        import yt_dlp

        options = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except ImportError as exc:
        raise RuntimeError("yt-dlp가 설치되어 있지 않습니다. requirements.txt를 설치하세요.") from exc
    except Exception as exc:
        raise RuntimeError(f"쇼츠 정보를 가져오지 못했습니다: {exc}") from exc

    transcript = _extract_caption(info)
    transcript_source = "자막"
    if not transcript:
        transcript = _transcribe_audio({**info, "webpage_url": url})
        transcript_source = "음성 인식" if transcript else "없음"

    return {
        "video_id": video_id,
        "url": url,
        "title": (info.get("title") or "").strip(),
        "description": (info.get("description") or "").strip(),
        "channel": (info.get("channel") or info.get("uploader") or "").strip(),
        "thumbnail": info.get("thumbnail") or "",
        "duration": info.get("duration") or 0,
        "transcript": transcript,
        "transcript_source": transcript_source,
    }
