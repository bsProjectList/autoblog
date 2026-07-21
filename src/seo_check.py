import re
from typing import Dict, List


def run_seo_check(content: str) -> List[Dict]:
    results = []

    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""
    if not title:
        results.append({"label": "제목", "status": "fail", "detail": "제목(# )을 찾을 수 없습니다."})
    else:
        title_len = len(title)
        if title_len < 15:
            results.append({"label": "제목 길이", "status": "warn", "detail": f"{title_len}자 — 너무 짧습니다 (권장 15~60자)."})
        elif title_len > 60:
            results.append({"label": "제목 길이", "status": "warn", "detail": f"{title_len}자 — 검색결과에서 잘릴 수 있습니다 (권장 15~60자)."})
        else:
            results.append({"label": "제목 길이", "status": "pass", "detail": f"{title_len}자 — 적절합니다."})

    meta_match = re.search(r"\*\*Meta Description\*\*:\s*(.+?)(?=\n)", content)
    if meta_match:
        meta_len = len(meta_match.group(1).strip())
        if 100 <= meta_len <= 160:
            results.append({"label": "메타 디스크립션", "status": "pass", "detail": f"{meta_len}자 — 적절합니다."})
        else:
            results.append({"label": "메타 디스크립션", "status": "warn", "detail": f"{meta_len}자 — 권장 100~160자."})
    else:
        results.append({"label": "메타 디스크립션", "status": "info", "detail": "없음 (이 글 형식엔 필수 아님)."})

    h2_count = len(re.findall(r"^##\s+", content, re.MULTILINE))
    if h2_count >= 3:
        results.append({"label": "소제목(H2) 구조", "status": "pass", "detail": f"{h2_count}개."})
    elif h2_count >= 1:
        results.append({"label": "소제목(H2) 구조", "status": "warn", "detail": f"{h2_count}개 — 3개 이상 권장."})
    else:
        results.append({"label": "소제목(H2) 구조", "status": "fail", "detail": "소제목이 없습니다."})

    tags = re.findall(r"#([^\s#\n,]+)", content)
    tag_count = len(tags)
    if tag_count >= 10:
        results.append({"label": "태그 개수", "status": "pass", "detail": f"{tag_count}개."})
    elif tag_count >= 3:
        results.append({"label": "태그 개수", "status": "warn", "detail": f"{tag_count}개 — 10개 이상 권장."})
    else:
        results.append({"label": "태그 개수", "status": "fail", "detail": f"{tag_count}개 — 태그가 거의 없습니다."})

    images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)
    if not images:
        results.append({"label": "이미지", "status": "warn", "detail": "본문에 이미지가 없습니다."})
    else:
        empty_alt = sum(1 for alt, _ in images if not alt.strip())
        if empty_alt:
            results.append({
                "label": "이미지 ALT 텍스트",
                "status": "warn",
                "detail": f"{len(images)}개 중 {empty_alt}개는 ALT 텍스트가 비어 있습니다.",
            })
        else:
            results.append({
                "label": "이미지 ALT 텍스트",
                "status": "pass",
                "detail": f"이미지 {len(images)}개 모두 ALT 텍스트 있음.",
            })

    body = re.sub(r"^#.*$", "", content, flags=re.MULTILINE)
    body = re.sub(r"[#*>\-\[\]()!]", "", body)
    char_count = len(body.strip())
    if char_count >= 3000:
        results.append({"label": "본문 분량", "status": "pass", "detail": f"약 {char_count}자."})
    elif char_count >= 1500:
        results.append({"label": "본문 분량", "status": "warn", "detail": f"약 {char_count}자 — 조금 더 늘리는 걸 권장."})
    else:
        results.append({"label": "본문 분량", "status": "fail", "detail": f"약 {char_count}자 — 너무 짧습니다."})

    paragraphs = [p for p in re.split(r"\n\s*\n", content) if p.strip() and not p.strip().startswith("#")]
    long_paragraphs = [p for p in paragraphs if len(p) > 500]
    if long_paragraphs:
        results.append({
            "label": "가독성(문단 길이)",
            "status": "warn",
            "detail": f"500자 넘는 긴 문단 {len(long_paragraphs)}개 발견 — 문단을 더 짧게 나누는 걸 권장.",
        })
    else:
        results.append({"label": "가독성(문단 길이)", "status": "pass", "detail": "문단 길이 적절."})

    return results
