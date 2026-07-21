import json
from pathlib import Path
from typing import Dict

STATUS_FILE = Path("output") / ".publish_status.json"


def _load() -> Dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: Dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_status(path: str) -> Dict:
    return _load().get(str(path), {"status": "draft", "url": ""})


def set_published(path: str, url: str) -> None:
    data = _load()
    data[str(path)] = {"status": "published", "url": url}
    _save(data)


def set_draft(path: str) -> None:
    data = _load()
    data[str(path)] = {"status": "draft", "url": ""}
    _save(data)
