import sys
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

from src.collector.rss import collect_rss_news
from src.collector.playwright_crawler import crawl_naver_economy
from src.collector.article import fetch_article_text
from src.analyzer.importance import score_and_select_top10
from src.generator.blog import generate_naver_post, generate_google_post
from src.models import BlogPost, NewsItem
from src.seo_check import run_seo_check

OUTPUT_DIR = Path("output")
TOP_N = 6  # Groq 무료 티어 일일 토큰 한도(TPD 100K) 내에서 안전하게 처리 가능한 뉴스 개수

SEO_GENERATORS = [
    (generate_naver_post, "Naver SEO"),
    (generate_google_post, "Google SEO"),
]
KST = ZoneInfo("Asia/Seoul")


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


def enrich_with_source(items: list, on_log=print) -> None:
    for item in items:
        content = fetch_article_text(item.url)
        if content:
            item.content = content
            on_log(f"    원문 보강 완료: {item.title[:45]}")
        else:
            on_log(f"    원문 보강 실패 — RSS 요약 사용: {item.title[:45]}")


def save_quality_report(date_str: str, records: list) -> Path:
    path = OUTPUT_DIR / date_str / "_quality_report.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_pipeline(top_n: int = TOP_N, seo_generators=None, on_log=print) -> list:
    seo_generators = SEO_GENERATORS if seo_generators is None else seo_generators
    date_str = datetime.now(KST).strftime("%Y-%m-%d")
    divider = "=" * 60

    on_log(f"\n{divider}")
    on_log(f"  AutoBlog Pipeline — {date_str}")
    on_log(f"{divider}\n")

    # ── Step 1: Collect ──────────────────────────────────────────
    on_log("[1단계] RSS 피드에서 뉴스 수집 중...")
    rss_items = collect_rss_news()

    on_log("\n[1단계] 네이버 경제 뉴스 크롤링 중...")
    naver_items = crawl_naver_economy()

    all_items = deduplicate(rss_items + naver_items)
    on_log(f"\n[1단계] 중복 제거 후 총 {len(all_items)}건")

    if not all_items:
        on_log("[오류] 수집된 뉴스가 없습니다. 종료합니다.")
        return []

    # ── Step 2: Analyze ──────────────────────────────────────────
    on_log(f"\n[2단계] 중요도 분석 및 TOP {top_n} 선정 중...")
    top_items = score_and_select_top10(all_items, top_n=top_n)

    if not top_items:
        on_log(f"[오류] TOP {top_n} 선정 실패. 종료합니다.")
        return []

    on_log(f"\n  선정된 TOP {len(top_items)}:")
    for item in top_items:
        on_log(f"    {item.rank:2d}. [{item.importance_score:3.0f}점] {item.title[:55]}")

    on_log("\n  선정 뉴스 원문 보강 수집 중...")
    enrich_with_source(top_items, on_log=on_log)

    # ── Step 3: Generate ─────────────────────────────────────────
    on_log(f"\n[3단계] 블로그 포스트 생성 ({len(top_items) * len(seo_generators)}개 예정)...")

    saved: list = []
    errors: list = []
    quality_records: list = []

    for news in top_items:
        on_log(f"\n  [{news.rank:2d}/{len(top_items)}] {news.title[:50]}")

        for gen_fn, label in seo_generators:
            on_log(f"    → {label} 생성 중...")
            try:
                post = gen_fn(news)
                path = save_post(post, date_str)
                saved.append(path)
                checks = run_seo_check(post.content)
                failed = [check for check in checks if check["status"] == "fail"]
                quality_records.append({
                    "file": str(path),
                    "title": post.title,
                    "seo_type": post.seo_type,
                    "checks": checks,
                    "status": "fail" if failed else "pass",
                })
                if failed:
                    on_log(f"    ⚠ 품질 경고 {len(failed)}건: {path.name}")
                on_log(f"    → {label} 완료: {path}")
            except Exception as e:
                on_log(f"    → {label} 실패: {e}")
                errors.append((news.title, label, str(e)))

    # ── Summary ──────────────────────────────────────────────────
    on_log(f"\n{divider}")
    on_log(f"  파이프라인 완료")
    on_log(f"  날짜: {date_str}")
    on_log(f"  생성된 포스트: {len(saved)}개 / 목표 {len(top_items) * len(seo_generators)}개")
    report_path = save_quality_report(date_str, quality_records)
    on_log(f"  저장 위치: {OUTPUT_DIR / date_str}")
    on_log(f"  품질 리포트: {report_path}")
    if errors:
        on_log(f"  오류: {len(errors)}건")
        for title, label, err in errors:
            on_log(f"    - [{label}] {title[:40]}: {err[:60]}")
    on_log(f"{divider}\n")

    return saved


if __name__ == "__main__":
    if not run_pipeline():
        sys.exit(1)
