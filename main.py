import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.collector.rss import collect_rss_news
from src.collector.playwright_crawler import crawl_naver_economy
from src.analyzer.importance import score_and_select_top10
from src.generator.blog import generate_naver_post, generate_google_post
from src.models import BlogPost, NewsItem

OUTPUT_DIR = Path("output")


def deduplicate(items: list) -> list:
    seen: set = set()
    unique = []
    for item in items:
        key = item.title[:40].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def save_post(post: BlogPost, date_str: str) -> Path:
    slug = (post.news_item.slug or f"news-{post.news_item.rank:02d}")[:30]
    slug = slug.replace("/", "-").replace("\\", "-")
    filename = f"{post.news_item.rank:02d}_{slug}_{post.seo_type}.md"

    output_path = OUTPUT_DIR / date_str / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(post.content, encoding="utf-8")
    print(f"    [저장] {output_path}")
    return output_path


def run_pipeline():
    date_str = datetime.now().strftime("%Y-%m-%d")
    divider = "=" * 60

    print(f"\n{divider}")
    print(f"  AutoBlog Pipeline — {date_str}")
    print(f"{divider}\n")

    # ── Step 1: Collect ──────────────────────────────────────────
    print("[1단계] RSS 피드에서 뉴스 수집 중...")
    rss_items = collect_rss_news()

    print("\n[1단계] 네이버 경제 뉴스 크롤링 중...")
    naver_items = crawl_naver_economy()

    all_items = deduplicate(rss_items + naver_items)
    print(f"\n[1단계] 중복 제거 후 총 {len(all_items)}건")

    if not all_items:
        print("[오류] 수집된 뉴스가 없습니다. 종료합니다.")
        sys.exit(1)

    # ── Step 2: Analyze ──────────────────────────────────────────
    print("\n[2단계] 중요도 분석 및 TOP 10 선정 중...")
    top10 = score_and_select_top10(all_items)

    if not top10:
        print("[오류] TOP 10 선정 실패. 종료합니다.")
        sys.exit(1)

    print(f"\n  선정된 TOP {len(top10)}:")
    for item in top10:
        print(f"    {item.rank:2d}. [{item.importance_score:3.0f}점] {item.title[:55]}")

    # ── Step 3: Generate ─────────────────────────────────────────
    print(f"\n[3단계] 블로그 포스트 생성 ({len(top10) * 2}개 예정)...")

    saved: list = []
    errors: list = []

    for news in top10:
        print(f"\n  [{news.rank:2d}/{len(top10)}] {news.title[:50]}")

        for gen_fn, label in [(generate_naver_post, "Naver SEO"), (generate_google_post, "Google SEO")]:
            print(f"    → {label} 생성 중...", end=" ", flush=True)
            try:
                post = gen_fn(news)
                path = save_post(post, date_str)
                saved.append(path)
                print("완료")
            except Exception as e:
                print(f"실패\n    [오류] {label}: {e}")
                errors.append((news.title, label, str(e)))

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{divider}")
    print(f"  파이프라인 완료")
    print(f"  날짜: {date_str}")
    print(f"  생성된 포스트: {len(saved)}개 / 목표 {len(top10) * 2}개")
    print(f"  저장 위치: {OUTPUT_DIR / date_str}")
    if errors:
        print(f"  오류: {len(errors)}건")
        for title, label, err in errors:
            print(f"    - [{label}] {title[:40]}: {err[:60]}")
    print(f"{divider}\n")


if __name__ == "__main__":
    run_pipeline()
