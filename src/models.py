from dataclasses import dataclass, field
from typing import List


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    summary: str
    content: str = ""  # 원문 보강 수집 결과
    published_at: str = ""
    importance_score: float = 0.0
    rank: int = 0
    keywords: List[str] = field(default_factory=list)
    slug: str = ""
    collection_method: str = ""  # "rss", "playwright"


@dataclass
class ImagePrompt:
    description: str
    purpose: str  # "thumbnail", "body_1", "body_2", "body_3"


@dataclass
class BlogPost:
    news_item: NewsItem
    title: str
    content: str
    seo_type: str  # "naver" or "google"
    image_prompts: List[ImagePrompt] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    meta_description: str = ""
    json_ld: str = ""
    filename: str = ""
