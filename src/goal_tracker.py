"""Persistence and calculations for the Coupang Partners monthly goal dashboard."""

import json
from datetime import datetime
from pathlib import Path

STATE_PATH = Path("output") / "monthly_goal" / "goal_state.json"

DEFAULT_STATE = {
    "target_revenue": 3_000_000,
    "current_revenue": 0,
    "category": "생활용품·살림템",
    "persona": "25~44세 직장인 여성, 1~4인 가구",
    "tone": "실용적이고 솔직한 문제 해결형",
    "keywords": "정리, 수납, 청소, 주방, 가성비, 살림 꿀팁",
    "channels": {
        "threads": {"role": "확산·댓글 소통", "views": 0, "clicks": 0, "orders": 0},
        "instagram": {"role": "릴스·브랜드 신뢰", "views": 0, "clicks": 0, "orders": 0},
        "blog": {"role": "검색 유입·전환", "views": 0, "clicks": 0, "orders": 0},
    },
    "daily": {
        "date": "",
        "analyzed_posts": 0,
        "scripts": 0,
        "comments": 0,
        "manual_uploads": 0,
        "link_eligible_posts": 0,
        "checklist": {},
        "benchmark_notes": "",
        "scripts_text": "",
    },
}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return json.loads(json.dumps(DEFAULT_STATE, ensure_ascii=False))
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    merged = json.loads(json.dumps(DEFAULT_STATE, ensure_ascii=False))
    _deep_merge(merged, state)
    return merged


def _deep_merge(target: dict, source: dict) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def save_state(state: dict) -> Path:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return STATE_PATH


def calculate_summary(state: dict) -> dict:
    target = max(0, int(state.get("target_revenue", 0)))
    current = max(0, int(state.get("current_revenue", 0)))
    daily = state.get("daily", {})
    return {
        "target": target,
        "current": current,
        "remaining": max(0, target - current),
        "progress": min(100.0, (current / target * 100) if target else 0),
        "analyzed_posts": int(daily.get("analyzed_posts", 0)),
        "scripts": int(daily.get("scripts", 0)),
        "link_eligible_posts": int(daily.get("link_eligible_posts", 0)),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
