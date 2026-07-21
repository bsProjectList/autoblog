import json
from datetime import datetime
from pathlib import Path
from typing import Dict

USAGE_FILE = Path("output") / ".usage_stats.json"


def _load() -> Dict:
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: Dict) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_usage(provider: str, tokens: int, estimated: bool = False) -> None:
    if tokens <= 0:
        return
    date_str = datetime.now().strftime("%Y-%m-%d")
    data = _load()
    day = data.setdefault(date_str, {})
    entry = day.setdefault(provider, {"tokens": 0, "has_estimate": False})
    entry["tokens"] += tokens
    entry["has_estimate"] = entry["has_estimate"] or estimated
    _save(data)


def get_today_usage() -> Dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    return _load().get(date_str, {})


def record_image_cost(usd: float) -> None:
    date_str = datetime.now().strftime("%Y-%m-%d")
    data = _load()
    day = data.setdefault(date_str, {})
    day["image_cost_usd"] = round(day.get("image_cost_usd", 0.0) + usd, 4)
    _save(data)
