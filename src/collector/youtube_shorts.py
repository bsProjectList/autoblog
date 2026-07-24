"""YouTube Shorts metadata and transcript extraction."""

import html
import base64
import os
import re
import subprocess
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


def _analyze_video_frames(info: dict) -> str:
    """대표 프레임의 상품명·가격·화면 문구를 비전 모델로 추출한다."""
    if not os.environ.get("OPENAI_API_KEY"):
        return ""
    try:
        import imageio_ffmpeg
        import yt_dlp
        from openai import OpenAI

        with tempfile.TemporaryDirectory(prefix="autoblog-shorts-video-") as temp_dir:
            video_template = str(Path(temp_dir) / "video.%(ext)s")
            options = {
                "format": "worst[ext=mp4]/worst",
                "outtmpl": video_template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([info["webpage_url"]])
            videos = list(Path(temp_dir).glob("video.*"))
            if not videos:
                return ""
            frame_pattern = str(Path(temp_dir) / "frame-%02d.jpg")
            subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(videos[0]), "-vf", "fps=1/5,scale=720:-1", "-frames:v", "3", frame_pattern],
                check=True,
                capture_output=True,
            )
            frames = sorted(Path(temp_dir).glob("frame-*.jpg"))
            if not frames:
                return ""
            content = [{"type": "text", "text": "이 쇼츠 화면에서 읽을 수 있는 상품명, 가격, 브랜드명, 핵심 문구만 한국어로 추출하세요. 보이지 않는 내용은 추측하지 말고 '확인 불가'라고 하세요."}]
            for frame in frames:
                encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"}})
            response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                temperature=0.1,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[Shorts] 화면 분석 실패: {exc}")
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
    visual_text = _analyze_video_frames({**info, "webpage_url": url})

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
        "visual_text": visual_text,
    }
