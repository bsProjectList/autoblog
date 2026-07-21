import io
import json
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageTk
import pyperclip
import ttkbootstrap as tb

load_dotenv()

OUTPUT_DIR = Path("output")
AFFILIATE_DIR = OUTPUT_DIR / "affiliate"


class AutoBlogGUI(tb.Window):
    def __init__(self):
        super().__init__(title="AutoBlog", themename="flatly")
        self.geometry("1080x760")
        self.colors = self.style.colors

        self.usage_bar = ttk.Frame(self)
        self.usage_bar.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.usage_label_var = tk.StringVar(value="사용량 불러오는 중...")
        ttk.Label(self.usage_bar, textvariable=self.usage_label_var).pack(side="left")
        self.groq_usage_progress = ttk.Progressbar(self.usage_bar, mode="determinate", maximum=100000, length=180)
        self.groq_usage_progress.pack(side="left", padx=10)
        tb.Button(self.usage_bar, text="새로고침", command=self._refresh_usage_bar, bootstyle="secondary").pack(
            side="right"
        )

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.notebook = notebook

        self.viewer_tab = ttk.Frame(notebook)
        self.affiliate_tab = ttk.Frame(notebook)
        self.blog_writer_tab = ttk.Frame(notebook)
        self.sns_promo_tab = ttk.Frame(notebook)
        self.pipeline_tab = ttk.Frame(notebook)
        notebook.add(self.viewer_tab, text="생성된 글 보기")
        notebook.add(self.affiliate_tab, text="제휴 글 생성")
        notebook.add(self.blog_writer_tab, text="블로그 글 작성")
        notebook.add(self.sns_promo_tab, text="SNS 홍보")
        notebook.add(self.pipeline_tab, text="파이프라인 실행")

        self._current_folder = None
        self._current_post = None
        self._current_raw_content = None
        self._current_file_path = None
        self._product_images = []
        self._product_photos = []
        self._product_reviews = []
        self._naver_writer_post = None
        self._tistory_writer_post = None
        self._naver_writer_last_path = None
        self._tistory_writer_last_path = None
        self._naver_thumbnail_image = None
        self._naver_thumbnail_photo = None
        self._tistory_images = []
        self._tistory_photos = []

        self._build_viewer_tab()
        self._build_affiliate_tab()
        self._build_blog_writer_tab()
        self._build_sns_promo_tab()
        self._build_pipeline_tab()
        self._refresh_usage_bar()

    def _refresh_usage_bar(self):
        from src.usage_tracker import get_today_usage
        usage = get_today_usage()
        groq = usage.get("groq", {})
        openai_u = usage.get("openai", {})
        image_cost = usage.get("image_cost_usd", 0.0)

        groq_tokens = groq.get("tokens", 0)
        groq_est = "(일부 추정)" if groq.get("has_estimate") else ""
        openai_tokens = openai_u.get("tokens", 0)
        openai_est = "(일부 추정)" if openai_u.get("has_estimate") else ""
        openai_cost = openai_tokens / 1_000_000 * 0.375
        total_cost = openai_cost + image_cost

        self.groq_usage_progress["value"] = min(groq_tokens, 100000)
        self.usage_label_var.set(
            f"오늘 사용량 — Groq {groq_tokens:,}/100,000 토큰{groq_est}  |  "
            f"OpenAI {openai_tokens:,} 토큰{openai_est} (약 ${openai_cost:.3f})  |  "
            f"이미지 ${image_cost:.2f}  |  총 예상 비용 약 ${total_cost:.3f}"
        )

    # ---------------- 테마 헬퍼 ----------------
    def _style_text_widget(self, widget):
        widget.configure(
            bg=self.colors.inputbg,
            fg=self.colors.inputfg,
            insertbackground=self.colors.inputfg,
            selectbackground=self.colors.selectbg,
            selectforeground=self.colors.selectfg,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors.border,
            highlightcolor=self.colors.primary,
            padx=6,
            pady=6,
        )
        return widget

    def _style_listbox(self, widget):
        widget.configure(
            bg=self.colors.inputbg,
            fg=self.colors.inputfg,
            selectbackground=self.colors.primary,
            selectforeground=self.colors.selectfg,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors.border,
            highlightcolor=self.colors.primary,
            borderwidth=0,
        )
        return widget

    # ---------------- 생성된 글 보기 ----------------
    def _build_viewer_tab(self):
        left = ttk.Frame(self.viewer_tab, width=280)
        left.pack(side="left", fill="y", padx=8, pady=8)
        left.pack_propagate(False)

        ttk.Label(left, text="날짜").pack(anchor="w")
        self.date_list = self._style_listbox(tk.Listbox(left, height=12))
        self.date_list.pack(fill="x")
        self.date_list.bind("<<ListboxSelect>>", self._on_date_select)

        ttk.Label(left, text="파일").pack(anchor="w", pady=(10, 0))
        self.file_list = self._style_listbox(tk.Listbox(left))
        self.file_list.pack(fill="both", expand=True)
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)

        tb.Button(left, text="새로고침", command=self._refresh_dates, bootstyle="secondary").pack(fill="x", pady=5)

        right = ttk.Frame(self.viewer_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        right_toolbar = ttk.Frame(right)
        right_toolbar.pack(fill="x", pady=(0, 5))
        tb.Button(right_toolbar, text="마크다운으로 복사", command=self._copy_markdown, bootstyle="secondary").pack(side="left")
        tb.Button(right_toolbar, text="일반 글로 복사", command=self._copy_plain_text, bootstyle="secondary").pack(
            side="left", padx=5
        )
        tb.Button(
            right_toolbar, text="SNS 홍보 문구 만들기", command=self._send_viewer_post_to_sns, bootstyle="info"
        ).pack(side="left", padx=5)
        tb.Button(right_toolbar, text="SEO 진단", command=self._run_viewer_seo_check, bootstyle="warning").pack(side="left")

        publish_row = ttk.Frame(right)
        publish_row.pack(fill="x", pady=(0, 5))
        self.viewer_publish_status_var = tk.StringVar(value="상태: -")
        ttk.Label(publish_row, textvariable=self.viewer_publish_status_var).pack(side="left")
        ttk.Label(publish_row, text="게시 URL:").pack(side="left", padx=(15, 3))
        self.viewer_publish_url_var = tk.StringVar()
        ttk.Entry(publish_row, textvariable=self.viewer_publish_url_var, width=40).pack(
            side="left", fill="x", expand=True, padx=3
        )
        tb.Button(
            publish_row, text="게시완료로 표시", command=self._mark_viewer_post_published, bootstyle="success"
        ).pack(side="left")

        self.content_text = self._style_text_widget(scrolledtext.ScrolledText(right, wrap="word"))
        self.content_text.pack(fill="both", expand=True)
        self.content_text.tag_configure("h1", font=("Segoe UI", 18, "bold"), spacing3=6)
        self.content_text.tag_configure("h2", font=("Segoe UI", 14, "bold"), spacing3=4)
        self.content_text.tag_configure("h3", font=("Segoe UI", 12, "bold"), spacing3=3)
        self.content_text.tag_configure("bold", font=("Segoe UI", 10, "bold"))

        self._refresh_dates()

    def _refresh_dates(self):
        self.date_list.delete(0, tk.END)
        if not OUTPUT_DIR.exists():
            return
        dates = sorted(
            (d.name for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name not in ("affiliate", "blog_writer")),
            reverse=True,
        )
        for d in dates:
            self.date_list.insert(tk.END, d)

    def _on_date_select(self, _event):
        sel = self.date_list.curselection()
        if not sel:
            return
        date_str = self.date_list.get(sel[0])
        self._current_folder = OUTPUT_DIR / date_str
        self.file_list.delete(0, tk.END)
        for f in sorted(self._current_folder.glob("*.md")):
            self.file_list.insert(tk.END, f.name)

    def _on_file_select(self, _event):
        sel = self.file_list.curselection()
        if not sel or not self._current_folder:
            return
        filename = self.file_list.get(sel[0])
        path = self._current_folder / filename
        self._current_file_path = path
        self._current_raw_content = path.read_text(encoding="utf-8")
        self._render_markdown(self._current_raw_content)

        from src.publish_status import get_status
        status = get_status(str(path))
        if status["status"] == "published":
            self.viewer_publish_status_var.set("상태: 게시됨")
            self.viewer_publish_url_var.set(status["url"])
        else:
            self.viewer_publish_status_var.set("상태: 초안")
            self.viewer_publish_url_var.set("")

    def _mark_viewer_post_published(self):
        path = getattr(self, "_current_file_path", None)
        if not path:
            messagebox.showwarning("알림", "먼저 왼쪽에서 파일을 선택하세요.")
            return
        url = self.viewer_publish_url_var.get().strip()
        if not url:
            messagebox.showwarning("알림", "게시된 글의 URL을 입력하세요.")
            return
        from src.publish_status import set_published
        set_published(str(path), url)
        self.viewer_publish_status_var.set("상태: 게시됨")
        messagebox.showinfo("완료", "게시 상태로 표시했습니다.")

    def _run_viewer_seo_check(self):
        raw = getattr(self, "_current_raw_content", None)
        if not raw:
            messagebox.showwarning("알림", "먼저 왼쪽에서 파일을 선택하세요.")
            return
        self._show_seo_check_dialog(raw)

    def _show_seo_check_dialog(self, content):
        from src.seo_check import run_seo_check
        results = run_seo_check(content)

        dialog = tk.Toplevel(self)
        dialog.title("SEO 진단 결과")
        dialog.geometry("520x420")
        dialog.configure(bg=self.colors.bg)

        icons = {"pass": "✅", "warn": "⚠️", "fail": "❌", "info": "ℹ️"}
        text = self._style_text_widget(scrolledtext.ScrolledText(dialog, wrap="word"))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        for item in results:
            icon = icons.get(item["status"], "•")
            text.insert(tk.END, f"{icon} {item['label']}\n    {item['detail']}\n\n")
        text.config(state="disabled")

    def _strip_markdown_to_plain(self, content: str) -> str:
        text = content
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
        text = re.sub(r"```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _copy_markdown(self):
        raw = getattr(self, "_current_raw_content", None)
        if not raw:
            messagebox.showwarning("알림", "먼저 왼쪽에서 파일을 선택하세요.")
            return
        pyperclip.copy(raw)
        messagebox.showinfo("복사 완료", "마크다운 원문이 클립보드에 복사되었습니다.")

    def _copy_plain_text(self):
        raw = getattr(self, "_current_raw_content", None)
        if not raw:
            messagebox.showwarning("알림", "먼저 왼쪽에서 파일을 선택하세요.")
            return
        pyperclip.copy(self._strip_markdown_to_plain(raw))
        messagebox.showinfo("복사 완료", "일반 텍스트로 클립보드에 복사되었습니다.")

    def _send_viewer_post_to_sns(self):
        raw = getattr(self, "_current_raw_content", None)
        if not raw:
            messagebox.showwarning("알림", "먼저 왼쪽에서 파일을 선택하세요.")
            return
        title_match = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ""

        from src.publish_status import get_status
        path = getattr(self, "_current_file_path", None)
        url = get_status(str(path))["url"] if path else ""

        self._send_to_sns_tab(title, raw, url)

    def _render_markdown(self, text):
        self.content_text.delete("1.0", tk.END)
        for line in text.split("\n"):
            if line.startswith("### "):
                self.content_text.insert(tk.END, line[4:] + "\n", "h3")
            elif line.startswith("## "):
                self.content_text.insert(tk.END, line[3:] + "\n", "h2")
            elif line.startswith("# "):
                self.content_text.insert(tk.END, line[2:] + "\n", "h1")
            else:
                pos = 0
                for match in re.finditer(r"\*\*(.+?)\*\*", line):
                    self.content_text.insert(tk.END, line[pos:match.start()])
                    self.content_text.insert(tk.END, match.group(1), "bold")
                    pos = match.end()
                self.content_text.insert(tk.END, line[pos:] + "\n")

    # ---------------- 제휴 글 생성 ----------------
    def _build_affiliate_tab(self):
        coupang_box = ttk.LabelFrame(self.affiliate_tab, text="쿠팡 상품 검색 (Open API — 크롤링 차단 없음)")
        coupang_box.pack(fill="x", padx=10, pady=(10, 0))

        search_row = ttk.Frame(coupang_box)
        search_row.pack(fill="x", padx=5, pady=5)
        ttk.Label(search_row, text="키워드:").pack(side="left")
        self.coupang_keyword_entry = ttk.Entry(search_row)
        self.coupang_keyword_entry.pack(side="left", fill="x", expand=True, padx=5)
        tb.Button(search_row, text="검색", command=self._search_coupang, bootstyle="primary").pack(side="left")

        self.coupang_result_list = self._style_listbox(tk.Listbox(coupang_box, height=5))
        self.coupang_result_list.pack(fill="x", padx=5, pady=(0, 5))
        self.coupang_result_list.bind("<<ListboxSelect>>", self._on_coupang_result_select)
        self._coupang_results = []

        top = ttk.Frame(self.affiliate_tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="상품 URL (네이버 커넥트 / 쿠팡 파트너스 / 토스 쇼핑):").pack(anchor="w")
        url_row = ttk.Frame(top)
        url_row.pack(fill="x", pady=5)
        self.url_entry = ttk.Entry(url_row)
        self.url_entry.pack(side="left", fill="x", expand=True)
        tb.Button(url_row, text="정보 가져오기", command=self._fetch_product, bootstyle="primary").pack(side="left", padx=5)
        tb.Button(url_row, text="클립보드에서 붙여넣기", command=self._paste_from_clipboard, bootstyle="secondary").pack(
            side="left", padx=5
        )

        info = ttk.LabelFrame(self.affiliate_tab, text="상품 정보 (자동 수집 실패 시 직접 입력)")
        info.pack(fill="x", padx=10, pady=5)
        info.columnconfigure(1, weight=1)

        ttk.Label(info, text="플랫폼:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.platform_var = tk.StringVar()
        ttk.Entry(info, textvariable=self.platform_var).grid(row=0, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(info, text="상품명:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.name_var = tk.StringVar()
        ttk.Entry(info, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(info, text="가격:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.price_var = tk.StringVar()
        ttk.Entry(info, textvariable=self.price_var).grid(row=2, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(info, text="설명:").grid(row=3, column=0, sticky="nw", padx=5, pady=3)
        self.desc_text = self._style_text_widget(tk.Text(info, height=3))
        self.desc_text.grid(row=3, column=1, sticky="ew", padx=5, pady=3)

        image_box = ttk.LabelFrame(self.affiliate_tab, text="상품 이미지")
        image_box.pack(fill="x", padx=10, pady=(0, 5))
        self.image_canvas = tk.Canvas(image_box, height=140, highlightthickness=0, bg=self.colors.bg)
        image_scrollbar = ttk.Scrollbar(image_box, orient="horizontal", command=self.image_canvas.xview)
        self.image_canvas.configure(xscrollcommand=image_scrollbar.set)
        self.image_canvas.pack(fill="x", padx=5, pady=(5, 0))
        image_scrollbar.pack(fill="x", padx=5, pady=(0, 5))

        self.image_preview_frame = ttk.Frame(self.image_canvas)
        self.image_canvas.create_window((0, 0), window=self.image_preview_frame, anchor="nw")
        self.image_preview_frame.bind(
            "<Configure>",
            lambda _e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")),
        )

        self.image_placeholder_label = ttk.Label(self.image_preview_frame, text="(이미지 없음)")
        self.image_placeholder_label.pack(side="left")

        btn_frame = ttk.Frame(self.affiliate_tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        self.generate_btn = tb.Button(btn_frame, text="글 생성", command=self._generate_post, bootstyle="primary")
        self.generate_btn.pack(side="left")
        self.save_btn = tb.Button(btn_frame, text="저장", command=self._save_post, state="disabled", bootstyle="success")
        self.save_btn.pack(side="left", padx=5)

        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(self.affiliate_tab, textvariable=self.status_var).pack(anchor="w", padx=10)
        self.progress = ttk.Progressbar(self.affiliate_tab, mode="indeterminate")
        self.progress.pack(fill="x", padx=10, pady=(0, 5))

        self.result_text = self._style_text_widget(scrolledtext.ScrolledText(self.affiliate_tab, wrap="word", height=18))
        self.result_text.pack(fill="both", expand=True, padx=10, pady=5)

    def _search_coupang(self):
        keyword = self.coupang_keyword_entry.get().strip()
        if not keyword:
            messagebox.showwarning("알림", "검색어를 입력하세요.")
            return

        self.status_var.set("쿠팡 상품 검색 중...")
        self.progress.start(10)

        def task():
            try:
                from src.collector.coupang_api import search_products
                products = search_products(keyword, limit=5)
                self.after(0, lambda: self._on_coupang_search_done(products, None))
            except Exception as e:
                self.after(0, lambda: self._on_coupang_search_done(None, e))

        threading.Thread(target=task, daemon=True).start()

    def _on_coupang_search_done(self, products, error):
        self.progress.stop()
        if error:
            self.status_var.set(f"쿠팡 검색 실패: {error}")
            messagebox.showerror("오류", str(error))
            return

        self._coupang_results = products or []
        self.coupang_result_list.delete(0, tk.END)
        for p in self._coupang_results:
            self.coupang_result_list.insert(tk.END, f"{p['title'][:45]} - {p['price']}")

        if not self._coupang_results:
            self.status_var.set("검색 결과가 없습니다.")
        else:
            self.status_var.set(f"{len(self._coupang_results)}개 검색됨. 목록에서 선택하세요.")

    def _on_coupang_result_select(self, _event):
        sel = self.coupang_result_list.curselection()
        if not sel:
            return
        product = self._coupang_results[sel[0]]

        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, product["product_url"])
        self.platform_var.set("쿠팡 파트너스")
        self.name_var.set(product["title"])
        self.price_var.set(product["price"])
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", product["description"])
        self._product_reviews = []

        self.status_var.set("상품 이미지 다운로드 중...")
        self.progress.start(10)

        def task():
            from src.collector.product_crawler import download_images
            images = download_images([product["image_url"]], min_count=1)
            self.after(0, lambda: self._on_coupang_image_done(images))

        threading.Thread(target=task, daemon=True).start()

    def _on_coupang_image_done(self, images):
        self.progress.stop()
        self._show_product_images(images)
        self.status_var.set("쿠팡 상품 정보를 가져왔습니다. 필요시 수정 후 '글 생성'을 누르세요.")

    def _paste_from_clipboard(self):
        try:
            raw = pyperclip.paste()
            data = json.loads(raw)
        except Exception as e:
            messagebox.showerror(
                "오류",
                f"클립보드 내용을 상품 정보로 읽을 수 없습니다.\n"
                f"크롬 확장 프로그램으로 먼저 상품 페이지에서 정보를 복사해주세요.\n({e})",
            )
            return

        from src.collector.product_crawler import detect_platform

        url = data.get("url", "")
        platform = detect_platform(url) if url else data.get("hostname", "")

        result = {
            "platform": platform,
            "title": data.get("title", ""),
            "price": data.get("price", ""),
            "description": data.get("description", ""),
        }
        self._product_reviews = data.get("reviews", [])

        self.status_var.set("클립보드에서 정보를 가져왔습니다. 처리 중...")
        self.progress.start(10)

        def task():
            final_url = url
            if platform == "쿠팡 파트너스" and url:
                try:
                    from src.collector.coupang_api import create_deeplink
                    final_url = create_deeplink(url)
                except Exception as e:
                    print(f"[쿠팡] 딥링크(제휴 링크) 변환 실패, 원본 URL 사용: {e}")

            from src.collector.product_crawler import download_images
            images = download_images(data.get("image_urls", []), min_count=3)
            self.after(0, lambda: self._on_paste_done(result, images, final_url, final_url != url))

        threading.Thread(target=task, daemon=True).start()

    def _on_paste_done(self, result, images, final_url, was_converted):
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, final_url)
        self._on_fetch_done(result, images)
        if result["platform"] == "쿠팡 파트너스":
            if was_converted:
                self.status_var.set("쿠팡 URL을 파트너스 제휴 링크로 자동 변환했습니다. " + self.status_var.get())
            else:
                self.status_var.set("⚠ 제휴 링크 변환 실패 — 원본 URL이 남아있어 수수료가 안 붙을 수 있습니다.")

    def _fetch_product(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("알림", "URL을 입력하세요.")
            return

        from src.collector.product_crawler import detect_platform
        if detect_platform(url) == "쿠팡 파트너스":
            messagebox.showwarning(
                "쿠팡은 검색으로",
                "쿠팡은 URL 크롤링이 차단되어 있어 여기로는 정보를 못 가져옵니다.\n"
                "위쪽 '쿠팡 상품 검색' 박스에 키워드를 입력해서 검색해주세요.",
            )
            return

        self.status_var.set("상품 정보 가져오는 중...")
        self.progress.start(10)
        self._product_images = []
        self._product_reviews = []
        self._clear_image_preview()

        def task():
            from src.collector.product_crawler import crawl_product_page, download_images
            result = crawl_product_page(url)
            images = download_images(result.get("image_urls", []), min_count=3)
            self.after(0, lambda: self._on_fetch_done(result, images))

        threading.Thread(target=task, daemon=True).start()

    def _clear_image_preview(self):
        for widget in self.image_preview_frame.winfo_children():
            widget.destroy()
        self._product_photos = []
        self.image_placeholder_label = ttk.Label(self.image_preview_frame, text="(이미지 없음)")
        self.image_placeholder_label.pack(side="left")

    def _show_product_images(self, images):
        self._product_images = images
        self._clear_image_preview()
        if images:
            self.image_placeholder_label.pack_forget()
            for data, _ext in images:
                try:
                    pil_image = Image.open(io.BytesIO(data))
                    pil_image.thumbnail((120, 120))
                    photo = ImageTk.PhotoImage(pil_image)
                    self._product_photos.append(photo)
                    ttk.Label(self.image_preview_frame, image=photo).pack(side="left", padx=3)
                except Exception:
                    continue

    def _on_fetch_done(self, result, images):
        self.progress.stop()
        self.platform_var.set(result.get("platform", ""))
        self.name_var.set(result.get("title", ""))
        self.price_var.set(result.get("price", ""))
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", result.get("description", ""))

        self._show_product_images(images)

        if result.get("error"):
            self.status_var.set(f"일부 정보를 가져오지 못했습니다 ({result['error'][:60]}). 직접 입력 후 진행하세요.")
        elif len(images) < 3:
            self.status_var.set(f"이미지 {len(images)}개만 확보됨(목표 3개+). 필요시 수정 후 '글 생성'을 누르세요.")
        else:
            self.status_var.set(f"정보와 이미지 {len(images)}개를 가져왔습니다. 필요시 수정 후 '글 생성'을 누르세요.")

    def _generate_post(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("알림", "URL을 입력하세요.")
            return
        if not os.environ.get("GROQ_API_KEY"):
            messagebox.showerror("오류", "GROQ_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return

        product = {
            "platform": self.platform_var.get().strip(),
            "title": self.name_var.get().strip(),
            "price": self.price_var.get().strip(),
            "description": self.desc_text.get("1.0", tk.END).strip(),
            "reviews": self._product_reviews,
        }

        image_count = len(self._product_images)

        self.status_var.set("블로그 글 생성 중... (AI 호출)")
        self.progress.start(10)
        self.generate_btn.config(state="disabled")

        def task():
            try:
                from src.generator.affiliate import generate_affiliate_post
                post = generate_affiliate_post(url, product, image_count=image_count)
                self.after(0, lambda: self._on_generate_done(post, None))
            except Exception as e:
                self.after(0, lambda: self._on_generate_done(None, e))

        threading.Thread(target=task, daemon=True).start()

    def _on_generate_done(self, post, error):
        self.progress.stop()
        self.generate_btn.config(state="normal")
        if error:
            self.status_var.set(f"생성 실패: {error}")
            messagebox.showerror("오류", str(error))
            return
        self._current_post = post
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", post.content)
        self.status_var.set("생성 완료. '저장'을 눌러 파일로 저장하세요.")
        self.save_btn.config(state="normal")
        self._refresh_usage_bar()

    def _save_post(self):
        if not self._current_post:
            return
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_folder = AFFILIATE_DIR / date_str
        date_folder.mkdir(parents=True, exist_ok=True)

        slug = self._current_post.news_item.slug or "affiliate"
        existing = [d for d in date_folder.glob(f"{slug}_*") if d.is_dir()]
        suffix = f"{len(existing) + 1:02d}"
        post_folder = date_folder / f"{slug}_{suffix}"
        post_folder.mkdir(parents=True, exist_ok=True)

        content = self.result_text.get("1.0", tk.END).strip() + "\n"

        if self._product_images:
            product_name = self.name_var.get().strip() or "상품 이미지"
            image_filenames = []
            for idx, (data, ext) in enumerate(self._product_images, start=1):
                image_filename = f"image_{idx:02d}{ext}"
                (post_folder / image_filename).write_bytes(data)
                image_filenames.append(image_filename)

            used_indices = set()

            def replace_placeholder(match):
                idx = int(match.group(1))
                if 1 <= idx <= len(image_filenames) and idx not in used_indices:
                    used_indices.add(idx)
                    return f"![{product_name} {idx}]({image_filenames[idx - 1]})"
                return ""

            content = re.sub(r"\[IMAGE_(\d+)\]", replace_placeholder, content)

            leftover = [f for i, f in enumerate(image_filenames, start=1) if i not in used_indices]
            if leftover:
                leftover_md = "\n\n".join(f"![{product_name}]({f})" for f in leftover)
                tag_match = re.search(r"\n##\s*태그", content)
                if tag_match:
                    pos = tag_match.start()
                    content = content[:pos] + "\n" + leftover_md + "\n" + content[pos:]
                else:
                    content = content.rstrip() + "\n\n" + leftover_md + "\n"

        path = post_folder / "post.md"
        path.write_text(content, encoding="utf-8")

        self.status_var.set(f"저장됨: {path}")
        messagebox.showinfo("저장 완료", str(path))
        self._refresh_dates()

    # ---------------- 블로그 글 작성 ----------------
    def _build_blog_writer_tab(self):
        inner = ttk.Notebook(self.blog_writer_tab)
        inner.pack(fill="both", expand=True)

        self.naver_writer_tab = ttk.Frame(inner)
        self.tistory_writer_tab = ttk.Frame(inner)
        inner.add(self.naver_writer_tab, text="네이버 블로그")
        inner.add(self.tistory_writer_tab, text="티스토리 블로그")

        self._build_naver_writer_tab()
        self._build_tistory_writer_tab()

    def _build_naver_writer_tab(self):
        tab = self.naver_writer_tab

        ttk.Label(tab, text="뉴스 원문 붙여넣기:").pack(anchor="w", padx=10, pady=(10, 0))
        self.naver_input_text = self._style_text_widget(scrolledtext.ScrolledText(tab, wrap="word", height=10))
        self.naver_input_text.pack(fill="both", expand=False, padx=10, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        self.naver_generate_btn = tb.Button(
            btn_frame, text="글 생성", command=self._generate_naver_writer_post, bootstyle="primary"
        )
        self.naver_generate_btn.pack(side="left")
        self.naver_copy_btn = tb.Button(
            btn_frame, text="마크다운으로 복사", command=self._copy_naver_writer_markdown, state="disabled", bootstyle="secondary"
        )
        self.naver_copy_btn.pack(side="left", padx=5)
        self.naver_copy_plain_btn = tb.Button(
            btn_frame, text="일반 글로 복사", command=self._copy_naver_writer_plain, state="disabled", bootstyle="secondary"
        )
        self.naver_copy_plain_btn.pack(side="left", padx=5)
        self.naver_save_btn = tb.Button(
            btn_frame, text="저장", command=self._save_naver_writer_post, state="disabled", bootstyle="success"
        )
        self.naver_save_btn.pack(side="left")
        self.naver_sns_btn = tb.Button(
            btn_frame, text="SNS 홍보 문구 만들기", command=self._send_naver_writer_post_to_sns, state="disabled", bootstyle="info"
        )
        self.naver_sns_btn.pack(side="left", padx=5)
        tb.Button(btn_frame, text="SEO 진단", command=self._run_naver_writer_seo_check, bootstyle="warning").pack(side="left")
        self.naver_image_btn = tb.Button(
            btn_frame, text="썸네일 이미지 생성 (유료 API)", command=self._generate_naver_thumbnail,
            state="disabled", bootstyle="info-outline",
        )
        self.naver_image_btn.pack(side="left", padx=5)

        self.naver_thumbnail_preview = ttk.Label(tab, text="")
        self.naver_thumbnail_preview.pack(anchor="w", padx=10, pady=(0, 5))

        publish_row = ttk.Frame(tab)
        publish_row.pack(fill="x", padx=10, pady=(0, 5))
        self.naver_publish_status_var = tk.StringVar(value="상태: 초안")
        ttk.Label(publish_row, textvariable=self.naver_publish_status_var).pack(side="left")
        ttk.Label(publish_row, text="게시 URL:").pack(side="left", padx=(15, 3))
        self.naver_publish_url_var = tk.StringVar()
        ttk.Entry(publish_row, textvariable=self.naver_publish_url_var, width=40).pack(
            side="left", fill="x", expand=True, padx=3
        )
        tb.Button(
            publish_row, text="게시완료로 표시", command=self._mark_naver_writer_published, bootstyle="success"
        ).pack(side="left")

        self.naver_writer_status_var = tk.StringVar(value="대기 중")
        ttk.Label(tab, textvariable=self.naver_writer_status_var).pack(anchor="w", padx=10)
        self.naver_writer_progress = ttk.Progressbar(tab, mode="indeterminate")
        self.naver_writer_progress.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Label(tab, text="생성 결과:").pack(anchor="w", padx=10)
        self.naver_result_text = self._style_text_widget(scrolledtext.ScrolledText(tab, wrap="word"))
        self.naver_result_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _generate_naver_writer_post(self):
        news_text = self.naver_input_text.get("1.0", tk.END).strip()
        if not news_text:
            messagebox.showwarning("알림", "뉴스 원문을 붙여넣으세요.")
            return
        if not os.environ.get("GROQ_API_KEY"):
            messagebox.showerror("오류", "GROQ_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return

        self.naver_writer_status_var.set("블로그 글 생성 중... (AI 호출)")
        self.naver_writer_progress.start(10)
        self.naver_generate_btn.config(state="disabled")
        self.naver_copy_btn.config(state="disabled")
        self.naver_copy_plain_btn.config(state="disabled")
        self.naver_save_btn.config(state="disabled")
        self.naver_sns_btn.config(state="disabled")
        self.naver_image_btn.config(state="disabled")
        self._naver_thumbnail_image = None
        self.naver_thumbnail_preview.config(image="", text="")

        def task():
            try:
                from src.generator.custom_naver import generate_naver_post_from_text
                post = generate_naver_post_from_text(news_text)
                self.after(0, lambda: self._on_naver_writer_done(post, None))
            except Exception as e:
                self.after(0, lambda: self._on_naver_writer_done(None, e))

        threading.Thread(target=task, daemon=True).start()

    def _on_naver_writer_done(self, post, error):
        self.naver_writer_progress.stop()
        self.naver_generate_btn.config(state="normal")
        if error:
            self.naver_writer_status_var.set(f"생성 실패: {error}")
            messagebox.showerror("오류", str(error))
            return
        self._naver_writer_post = post
        self.naver_result_text.delete("1.0", tk.END)
        self.naver_result_text.insert("1.0", post.content)
        self.naver_writer_status_var.set("생성 완료. 복사하거나 저장하세요.")
        self.naver_copy_btn.config(state="normal")
        self.naver_copy_plain_btn.config(state="normal")
        self.naver_save_btn.config(state="normal")
        self.naver_sns_btn.config(state="normal")
        self.naver_image_btn.config(state="normal")
        self._refresh_usage_bar()

    def _generate_naver_thumbnail(self):
        if not self._naver_writer_post:
            return
        if not os.environ.get("OPENAI_API_KEY"):
            messagebox.showerror("오류", "OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return

        from src.generator.custom_naver import extract_thumbnail_prompt
        content = self.naver_result_text.get("1.0", tk.END).strip()
        prompt = extract_thumbnail_prompt(content)
        if not prompt:
            messagebox.showwarning("알림", "본문에서 썸네일 프롬프트를 찾을 수 없습니다.")
            return

        self.naver_writer_status_var.set("썸네일 이미지 생성 중... (이미지 생성 API 호출)")
        self.naver_writer_progress.start(10)
        self.naver_image_btn.config(state="disabled")

        def task():
            try:
                from src.generator.image_gen import generate_image
                data = generate_image(prompt, size="1024x1024")
                self.after(0, lambda: self._on_naver_thumbnail_done(data, None))
            except Exception as e:
                self.after(0, lambda: self._on_naver_thumbnail_done(None, e))

        threading.Thread(target=task, daemon=True).start()

    def _on_naver_thumbnail_done(self, data, error):
        self.naver_writer_progress.stop()
        self.naver_image_btn.config(state="normal")
        if error:
            self.naver_writer_status_var.set(f"이미지 생성 실패: {error}")
            messagebox.showerror("오류", str(error))
            return

        self._naver_thumbnail_image = (data, ".png")
        try:
            pil_image = Image.open(io.BytesIO(data))
            pil_image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(pil_image)
            self._naver_thumbnail_photo = photo
            self.naver_thumbnail_preview.config(image=photo, text="")
        except Exception:
            pass

        self.naver_writer_status_var.set("썸네일 생성 완료. '저장'을 누르면 글에 포함됩니다.")
        self._refresh_usage_bar()

    def _send_naver_writer_post_to_sns(self):
        if not self._naver_writer_post:
            return
        content = self.naver_result_text.get("1.0", tk.END).strip()
        self._send_to_sns_tab(self._naver_writer_post.title, content, self.naver_publish_url_var.get().strip())

    def _run_naver_writer_seo_check(self):
        content = self.naver_result_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("알림", "먼저 글을 생성하세요.")
            return
        self._show_seo_check_dialog(content)

    def _mark_naver_writer_published(self):
        path = getattr(self, "_naver_writer_last_path", None)
        if not path:
            messagebox.showwarning("알림", "먼저 글을 저장하세요.")
            return
        url = self.naver_publish_url_var.get().strip()
        if not url:
            messagebox.showwarning("알림", "게시된 글의 URL을 입력하세요.")
            return
        from src.publish_status import set_published
        set_published(str(path), url)
        self.naver_publish_status_var.set("상태: 게시됨")
        messagebox.showinfo("완료", "게시 상태로 표시했습니다.")

    def _copy_naver_writer_markdown(self):
        content = self.naver_result_text.get("1.0", tk.END).strip()
        if not content:
            return
        pyperclip.copy(content)
        messagebox.showinfo("복사 완료", "마크다운 원문이 클립보드에 복사되었습니다.")

    def _copy_naver_writer_plain(self):
        content = self.naver_result_text.get("1.0", tk.END).strip()
        if not content:
            return
        pyperclip.copy(self._strip_markdown_to_plain(content))
        messagebox.showinfo("복사 완료", "일반 텍스트로 클립보드에 복사되었습니다.")

    def _save_naver_writer_post(self):
        if not self._naver_writer_post:
            return
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_folder = OUTPUT_DIR / "blog_writer" / "naver" / date_str
        date_folder.mkdir(parents=True, exist_ok=True)

        slug = self._naver_writer_post.news_item.slug or "post"
        existing = [d for d in date_folder.glob(f"{slug}_*") if d.is_dir()]
        suffix = f"{len(existing) + 1:02d}"
        post_folder = date_folder / f"{slug}_{suffix}"
        post_folder.mkdir(parents=True, exist_ok=True)

        content = self.naver_result_text.get("1.0", tk.END).strip() + "\n"

        if self._naver_thumbnail_image:
            data, ext = self._naver_thumbnail_image
            image_filename = f"thumbnail{ext}"
            (post_folder / image_filename).write_bytes(data)

            content = re.sub(
                r"(^#{1,6}\s*.*썸네일.*\n+)?^3D digital thumbnail.+\n?",
                "",
                content,
                count=1,
                flags=re.MULTILINE,
            )
            content = content.rstrip() + "\n"
            lines = content.split("\n", 1)
            if lines[0].startswith("#"):
                rest = lines[1].lstrip("\n") if len(lines) > 1 else ""
                content = lines[0] + "\n\n" + f"![썸네일]({image_filename})" + "\n\n" + rest
            else:
                content = f"![썸네일]({image_filename})" + "\n\n" + content

        path = post_folder / "post.md"
        path.write_text(content, encoding="utf-8")
        self._naver_writer_last_path = path
        self.naver_publish_status_var.set("상태: 초안")
        self.naver_publish_url_var.set("")

        self.naver_writer_status_var.set(f"저장됨: {path}")
        messagebox.showinfo("저장 완료", str(path))

    def _build_tistory_writer_tab(self):
        tab = self.tistory_writer_tab

        ttk.Label(tab, text="뉴스 원문 붙여넣기:").pack(anchor="w", padx=10, pady=(10, 0))
        self.tistory_input_text = self._style_text_widget(scrolledtext.ScrolledText(tab, wrap="word", height=10))
        self.tistory_input_text.pack(fill="both", expand=False, padx=10, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        self.tistory_generate_btn = tb.Button(
            btn_frame, text="글 생성", command=self._generate_tistory_writer_post, bootstyle="primary"
        )
        self.tistory_generate_btn.pack(side="left")
        self.tistory_copy_btn = tb.Button(
            btn_frame, text="마크다운으로 복사", command=self._copy_tistory_writer_markdown, state="disabled", bootstyle="secondary"
        )
        self.tistory_copy_btn.pack(side="left", padx=5)
        self.tistory_copy_plain_btn = tb.Button(
            btn_frame, text="일반 글로 복사", command=self._copy_tistory_writer_plain, state="disabled", bootstyle="secondary"
        )
        self.tistory_copy_plain_btn.pack(side="left", padx=5)
        self.tistory_save_btn = tb.Button(
            btn_frame, text="저장", command=self._save_tistory_writer_post, state="disabled", bootstyle="success"
        )
        self.tistory_save_btn.pack(side="left")
        self.tistory_sns_btn = tb.Button(
            btn_frame, text="SNS 홍보 문구 만들기", command=self._send_tistory_writer_post_to_sns, state="disabled", bootstyle="info"
        )
        self.tistory_sns_btn.pack(side="left", padx=5)
        tb.Button(btn_frame, text="SEO 진단", command=self._run_tistory_writer_seo_check, bootstyle="warning").pack(side="left")
        self.tistory_image_btn = tb.Button(
            btn_frame, text="이미지 3장 생성 (유료 API)", command=self._generate_tistory_images,
            state="disabled", bootstyle="info-outline",
        )
        self.tistory_image_btn.pack(side="left", padx=5)

        self.tistory_image_preview_frame = ttk.Frame(tab)
        self.tistory_image_preview_frame.pack(fill="x", padx=10, pady=(0, 5))

        publish_row = ttk.Frame(tab)
        publish_row.pack(fill="x", padx=10, pady=(0, 5))
        self.tistory_publish_status_var = tk.StringVar(value="상태: 초안")
        ttk.Label(publish_row, textvariable=self.tistory_publish_status_var).pack(side="left")
        ttk.Label(publish_row, text="게시 URL:").pack(side="left", padx=(15, 3))
        self.tistory_publish_url_var = tk.StringVar()
        ttk.Entry(publish_row, textvariable=self.tistory_publish_url_var, width=40).pack(
            side="left", fill="x", expand=True, padx=3
        )
        tb.Button(
            publish_row, text="게시완료로 표시", command=self._mark_tistory_writer_published, bootstyle="success"
        ).pack(side="left")

        self.tistory_writer_status_var = tk.StringVar(value="대기 중")
        ttk.Label(tab, textvariable=self.tistory_writer_status_var).pack(anchor="w", padx=10)
        self.tistory_writer_progress = ttk.Progressbar(tab, mode="indeterminate")
        self.tistory_writer_progress.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Label(tab, text="생성 결과:").pack(anchor="w", padx=10)
        self.tistory_result_text = self._style_text_widget(scrolledtext.ScrolledText(tab, wrap="word"))
        self.tistory_result_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _generate_tistory_writer_post(self):
        news_text = self.tistory_input_text.get("1.0", tk.END).strip()
        if not news_text:
            messagebox.showwarning("알림", "뉴스 원문을 붙여넣으세요.")
            return
        if not os.environ.get("GROQ_API_KEY"):
            messagebox.showerror("오류", "GROQ_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return

        self.tistory_writer_status_var.set("블로그 글 생성 중... (AI 호출, 분량이 길어 시간이 걸릴 수 있음)")
        self.tistory_writer_progress.start(10)
        self.tistory_generate_btn.config(state="disabled")
        self.tistory_copy_btn.config(state="disabled")
        self.tistory_copy_plain_btn.config(state="disabled")
        self.tistory_save_btn.config(state="disabled")
        self.tistory_sns_btn.config(state="disabled")
        self.tistory_image_btn.config(state="disabled")
        self._tistory_images = []
        for widget in self.tistory_image_preview_frame.winfo_children():
            widget.destroy()

        def task():
            try:
                from src.generator.custom_tistory import generate_tistory_post_from_text
                post = generate_tistory_post_from_text(news_text)
                self.after(0, lambda: self._on_tistory_writer_done(post, None))
            except Exception as e:
                self.after(0, lambda: self._on_tistory_writer_done(None, e))

        threading.Thread(target=task, daemon=True).start()

    def _on_tistory_writer_done(self, post, error):
        self.tistory_writer_progress.stop()
        self.tistory_generate_btn.config(state="normal")
        if error:
            self.tistory_writer_status_var.set(f"생성 실패: {error}")
            messagebox.showerror("오류", str(error))
            return
        self._tistory_writer_post = post
        self.tistory_result_text.delete("1.0", tk.END)
        self.tistory_result_text.insert("1.0", post.content)
        self.tistory_writer_status_var.set("생성 완료. 복사하거나 저장하세요.")
        self.tistory_copy_btn.config(state="normal")
        self.tistory_copy_plain_btn.config(state="normal")
        self.tistory_save_btn.config(state="normal")
        self.tistory_sns_btn.config(state="normal")
        self.tistory_image_btn.config(state="normal")
        self._refresh_usage_bar()

    def _generate_tistory_images(self):
        if not self._tistory_writer_post:
            return
        if not os.environ.get("OPENAI_API_KEY"):
            messagebox.showerror("오류", "OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return

        from src.generator.custom_tistory import extract_image_prompts
        content = self.tistory_result_text.get("1.0", tk.END).strip()
        prompts = extract_image_prompts(content)
        if not prompts:
            messagebox.showwarning("알림", "본문에서 이미지 생성 프롬프트를 찾을 수 없습니다.")
            return

        self.tistory_writer_status_var.set(f"이미지 {len(prompts)}장 생성 중... (이미지 생성 API 호출, 시간이 걸릴 수 있음)")
        self.tistory_writer_progress.start(10)
        self.tistory_image_btn.config(state="disabled")

        def task():
            from src.generator.image_gen import generate_image
            results = []
            for item in prompts:
                try:
                    data = generate_image(item["prompt"], size="1536x1024")
                    results.append({"data": data, "alt": item["alt"], "error": None})
                except Exception as e:
                    results.append({"data": None, "alt": item["alt"], "error": str(e)})
            self.after(0, lambda: self._on_tistory_images_done(results))

        threading.Thread(target=task, daemon=True).start()

    def _on_tistory_images_done(self, results):
        self.tistory_writer_progress.stop()
        self.tistory_image_btn.config(state="normal")

        self._tistory_images = [r for r in results if r["data"]]
        failed = [r for r in results if r["error"]]

        for widget in self.tistory_image_preview_frame.winfo_children():
            widget.destroy()
        self._tistory_photos = []
        for item in self._tistory_images:
            try:
                pil_image = Image.open(io.BytesIO(item["data"]))
                pil_image.thumbnail((160, 160))
                photo = ImageTk.PhotoImage(pil_image)
                self._tistory_photos.append(photo)
                ttk.Label(self.tistory_image_preview_frame, image=photo).pack(side="left", padx=3)
            except Exception:
                continue

        if failed:
            self.tistory_writer_status_var.set(
                f"이미지 {len(self._tistory_images)}장 생성 완료, {len(failed)}장 실패: {failed[0]['error']}"
            )
        else:
            self.tistory_writer_status_var.set(f"이미지 {len(self._tistory_images)}장 생성 완료. '저장'을 누르면 글에 포함됩니다.")
        self._refresh_usage_bar()

    def _send_tistory_writer_post_to_sns(self):
        if not self._tistory_writer_post:
            return
        content = self.tistory_result_text.get("1.0", tk.END).strip()
        self._send_to_sns_tab(self._tistory_writer_post.title, content, self.tistory_publish_url_var.get().strip())

    def _run_tistory_writer_seo_check(self):
        content = self.tistory_result_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("알림", "먼저 글을 생성하세요.")
            return
        self._show_seo_check_dialog(content)

    def _mark_tistory_writer_published(self):
        path = getattr(self, "_tistory_writer_last_path", None)
        if not path:
            messagebox.showwarning("알림", "먼저 글을 저장하세요.")
            return
        url = self.tistory_publish_url_var.get().strip()
        if not url:
            messagebox.showwarning("알림", "게시된 글의 URL을 입력하세요.")
            return
        from src.publish_status import set_published
        set_published(str(path), url)
        self.tistory_publish_status_var.set("상태: 게시됨")
        messagebox.showinfo("완료", "게시 상태로 표시했습니다.")

    def _copy_tistory_writer_markdown(self):
        content = self.tistory_result_text.get("1.0", tk.END).strip()
        if not content:
            return
        pyperclip.copy(content)
        messagebox.showinfo("복사 완료", "원문이 클립보드에 복사되었습니다.")

    def _copy_tistory_writer_plain(self):
        content = self.tistory_result_text.get("1.0", tk.END).strip()
        if not content:
            return
        pyperclip.copy(self._strip_markdown_to_plain(content))
        messagebox.showinfo("복사 완료", "일반 텍스트로 클립보드에 복사되었습니다.")

    def _save_tistory_writer_post(self):
        if not self._tistory_writer_post:
            return
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_folder = OUTPUT_DIR / "blog_writer" / "tistory" / date_str
        date_folder.mkdir(parents=True, exist_ok=True)

        slug = self._tistory_writer_post.news_item.slug or "post"
        existing = [d for d in date_folder.glob(f"{slug}_*") if d.is_dir()]
        suffix = f"{len(existing) + 1:02d}"
        post_folder = date_folder / f"{slug}_{suffix}"
        post_folder.mkdir(parents=True, exist_ok=True)

        content = self.tistory_result_text.get("1.0", tk.END).strip() + "\n"

        if self._tistory_images:
            content = re.sub(r"\n##\s*이미지 생성 프롬프트.*\Z", "\n", content, flags=re.DOTALL)

            image_lines = []
            for idx, item in enumerate(self._tistory_images, start=1):
                image_filename = f"image_{idx:02d}.png"
                (post_folder / image_filename).write_bytes(item["data"])
                image_lines.append((item["alt"], image_filename))

            heading_positions = [
                m.start() for m in re.finditer(r"^##\s+(?!✍️).+$", content, re.MULTILINE)
            ]
            for idx, (alt, image_filename) in enumerate(image_lines):
                if idx >= len(heading_positions):
                    break
                pos = heading_positions[idx]
                line_end = content.index("\n", pos) + 1
                image_md = f"\n![{alt}]({image_filename})\n\n"
                content = content[:line_end] + image_md + content[line_end:]
                heading_positions = [p + len(image_md) if p > pos else p for p in heading_positions]

        path = post_folder / "post.md"
        path.write_text(content, encoding="utf-8")
        self._tistory_writer_last_path = path
        self.tistory_publish_status_var.set("상태: 초안")
        self.tistory_publish_url_var.set("")

        self.tistory_writer_status_var.set(f"저장됨: {path}")
        messagebox.showinfo("저장 완료", str(path))

    # ---------------- SNS 홍보 연동 helper ----------------
    def _extract_summary_from_content(self, content: str, max_chars: int = 200) -> str:
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(">") or line.startswith("!["):
                continue
            if re.match(r"^\d+[.)]\s", line) or line.startswith("-") or line.startswith("*"):
                continue
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            if len(line) < 40:
                continue
            return line[:max_chars]
        return ""

    def _send_to_sns_tab(self, title: str, content: str, url: str = ""):
        self.sns_title_var.set(title)
        self.sns_summary_text.delete("1.0", tk.END)
        self.sns_summary_text.insert("1.0", self._extract_summary_from_content(content))
        self.sns_url_var.set(url)
        self.notebook.select(self.sns_promo_tab)
        if url:
            self.sns_status_var.set("제목·요약·URL이 자동으로 채워졌습니다. '홍보 문구 생성'을 누르세요.")
        else:
            self.sns_status_var.set("제목·요약이 자동으로 채워졌습니다. 게시 후 URL을 입력하고 '홍보 문구 생성'을 누르세요.")

    # ---------------- SNS 홍보 ----------------
    def _build_sns_promo_tab(self):
        tab = self.sns_promo_tab

        form = ttk.Frame(tab)
        form.pack(fill="x", padx=10, pady=10)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="글 제목:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.sns_title_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.sns_title_var).grid(row=0, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(form, text="게시된 글 URL:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.sns_url_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.sns_url_var).grid(row=1, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(form, text="핵심 내용 요약 (선택):").grid(row=2, column=0, sticky="nw", padx=5, pady=3)
        self.sns_summary_text = self._style_text_widget(tk.Text(form, height=3))
        self.sns_summary_text.grid(row=2, column=1, sticky="ew", padx=5, pady=3)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        self.sns_generate_btn = tb.Button(
            btn_frame, text="홍보 문구 생성", command=self._generate_sns_captions, bootstyle="primary"
        )
        self.sns_generate_btn.pack(side="left")

        self.sns_status_var = tk.StringVar(value="대기 중")
        ttk.Label(tab, textvariable=self.sns_status_var).pack(anchor="w", padx=10)
        self.sns_progress = ttk.Progressbar(tab, mode="indeterminate")
        self.sns_progress.pack(fill="x", padx=10, pady=(0, 5))

        threads_box = ttk.LabelFrame(tab, text="쓰레드(Threads)용")
        threads_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.sns_threads_text = self._style_text_widget(tk.Text(threads_box, wrap="word", height=6))
        self.sns_threads_text.pack(fill="both", expand=True, side="left", padx=5, pady=5)
        tb.Button(threads_box, text="복사", command=lambda: self._copy_sns_text(self.sns_threads_text)).pack(
            side="right", padx=5, pady=5, anchor="n"
        )

        instagram_box = ttk.LabelFrame(tab, text="인스타그램용")
        instagram_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.sns_instagram_text = self._style_text_widget(tk.Text(instagram_box, wrap="word", height=6))
        self.sns_instagram_text.pack(fill="both", expand=True, side="left", padx=5, pady=5)
        tb.Button(instagram_box, text="복사", command=lambda: self._copy_sns_text(self.sns_instagram_text)).pack(
            side="right", padx=5, pady=5, anchor="n"
        )

    def _generate_sns_captions(self):
        title = self.sns_title_var.get().strip()
        url = self.sns_url_var.get().strip()
        summary = self.sns_summary_text.get("1.0", tk.END).strip()

        if not title or not url:
            messagebox.showwarning("알림", "글 제목과 URL을 입력하세요.")
            return
        if not os.environ.get("GROQ_API_KEY"):
            messagebox.showerror("오류", "GROQ_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return

        self.sns_status_var.set("홍보 문구 생성 중... (AI 호출)")
        self.sns_progress.start(10)
        self.sns_generate_btn.config(state="disabled")

        def task():
            try:
                from src.generator.sns_promo import generate_sns_captions
                captions = generate_sns_captions(title, url, summary)
                self.after(0, lambda: self._on_sns_captions_done(captions, None))
            except Exception as e:
                self.after(0, lambda: self._on_sns_captions_done(None, e))

        threading.Thread(target=task, daemon=True).start()

    def _on_sns_captions_done(self, captions, error):
        self.sns_progress.stop()
        self.sns_generate_btn.config(state="normal")
        if error:
            self.sns_status_var.set(f"생성 실패: {error}")
            messagebox.showerror("오류", str(error))
            return

        self.sns_threads_text.delete("1.0", tk.END)
        self.sns_threads_text.insert("1.0", captions.get("threads", ""))
        self.sns_instagram_text.delete("1.0", tk.END)
        self.sns_instagram_text.insert("1.0", captions.get("instagram", ""))
        self.sns_status_var.set("생성 완료. 각 박스의 '복사' 버튼으로 복사하세요.")
        self._refresh_usage_bar()

    def _copy_sns_text(self, text_widget):
        content = text_widget.get("1.0", tk.END).strip()
        if not content:
            return
        pyperclip.copy(content)
        messagebox.showinfo("복사 완료", "클립보드에 복사되었습니다.")

    # ---------------- 파이프라인 실행 ----------------
    def _build_pipeline_tab(self):
        from main import TOP_N as DEFAULT_TOP_N

        top = ttk.Frame(self.pipeline_tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="뉴스 개수(TOP_N):").grid(row=0, column=0, sticky="w")
        self.topn_var = tk.IntVar(value=DEFAULT_TOP_N)
        ttk.Spinbox(top, from_=1, to=15, width=5, textvariable=self.topn_var).grid(row=0, column=1, sticky="w", padx=5)

        self.naver_seo_var = tk.BooleanVar(value=True)
        self.google_seo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="네이버 SEO", variable=self.naver_seo_var).grid(row=0, column=2, sticky="w", padx=(20, 5))
        ttk.Checkbutton(top, text="구글 SEO", variable=self.google_seo_var).grid(row=0, column=3, sticky="w")

        self.run_pipeline_btn = tb.Button(top, text="파이프라인 실행", command=self._run_pipeline, bootstyle="primary")
        self.run_pipeline_btn.grid(row=0, column=4, sticky="w", padx=(20, 0))

        self.pipeline_status_var = tk.StringVar(value="대기 중")
        ttk.Label(self.pipeline_tab, textvariable=self.pipeline_status_var).pack(anchor="w", padx=10)
        self.pipeline_progress = ttk.Progressbar(self.pipeline_tab, mode="indeterminate")
        self.pipeline_progress.pack(fill="x", padx=10, pady=(0, 5))

        self.pipeline_log = self._style_text_widget(scrolledtext.ScrolledText(self.pipeline_tab, wrap="word"))
        self.pipeline_log.pack(fill="both", expand=True, padx=10, pady=5)

    def _pipeline_log_line(self, message):
        self.pipeline_log.insert(tk.END, str(message) + "\n")
        self.pipeline_log.see(tk.END)

    def _run_pipeline(self):
        if not os.environ.get("GROQ_API_KEY"):
            messagebox.showerror("오류", "GROQ_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
            return
        if not self.naver_seo_var.get() and not self.google_seo_var.get():
            messagebox.showwarning("알림", "네이버 SEO, 구글 SEO 중 최소 하나는 선택하세요.")
            return

        top_n = self.topn_var.get()
        from src.generator.blog import generate_naver_post, generate_google_post

        seo_generators = []
        if self.naver_seo_var.get():
            seo_generators.append((generate_naver_post, "Naver SEO"))
        if self.google_seo_var.get():
            seo_generators.append((generate_google_post, "Google SEO"))

        self.pipeline_log.delete("1.0", tk.END)
        self.run_pipeline_btn.config(state="disabled")
        self.pipeline_status_var.set("파이프라인 실행 중...")
        self.pipeline_progress.start(10)

        def on_log(message):
            self.after(0, lambda: self._pipeline_log_line(message))

        def task():
            try:
                from main import run_pipeline
                run_pipeline(top_n=top_n, seo_generators=seo_generators, on_log=on_log)
            except Exception as e:
                on_log(f"[치명적 오류] {e}")
            finally:
                self.after(0, self._on_pipeline_done)

        threading.Thread(target=task, daemon=True).start()

    def _on_pipeline_done(self):
        self.pipeline_progress.stop()
        self.run_pipeline_btn.config(state="normal")
        self.pipeline_status_var.set("완료")
        self._refresh_dates()
        self._refresh_usage_bar()


if __name__ == "__main__":
    app = AutoBlogGUI()
    app.mainloop()
