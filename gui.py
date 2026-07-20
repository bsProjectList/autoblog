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

load_dotenv()

OUTPUT_DIR = Path("output")
AFFILIATE_DIR = OUTPUT_DIR / "affiliate"


class AutoBlogGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoBlog")
        self.geometry("1000x720")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.viewer_tab = ttk.Frame(notebook)
        self.affiliate_tab = ttk.Frame(notebook)
        self.pipeline_tab = ttk.Frame(notebook)
        notebook.add(self.viewer_tab, text="생성된 글 보기")
        notebook.add(self.affiliate_tab, text="제휴 글 생성")
        notebook.add(self.pipeline_tab, text="파이프라인 실행")

        self._current_folder = None
        self._current_post = None
        self._product_images = []
        self._product_photos = []

        self._build_viewer_tab()
        self._build_affiliate_tab()
        self._build_pipeline_tab()

    # ---------------- 생성된 글 보기 ----------------
    def _build_viewer_tab(self):
        left = ttk.Frame(self.viewer_tab, width=280)
        left.pack(side="left", fill="y", padx=8, pady=8)
        left.pack_propagate(False)

        ttk.Label(left, text="날짜").pack(anchor="w")
        self.date_list = tk.Listbox(left, height=12)
        self.date_list.pack(fill="x")
        self.date_list.bind("<<ListboxSelect>>", self._on_date_select)

        ttk.Label(left, text="파일").pack(anchor="w", pady=(10, 0))
        self.file_list = tk.Listbox(left)
        self.file_list.pack(fill="both", expand=True)
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)

        ttk.Button(left, text="새로고침", command=self._refresh_dates).pack(fill="x", pady=5)

        right = ttk.Frame(self.viewer_tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.content_text = scrolledtext.ScrolledText(right, wrap="word")
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
            (d.name for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name != "affiliate"),
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
        self._render_markdown(path.read_text(encoding="utf-8"))

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
        ttk.Button(search_row, text="검색", command=self._search_coupang).pack(side="left")

        self.coupang_result_list = tk.Listbox(coupang_box, height=5)
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
        ttk.Button(url_row, text="정보 가져오기", command=self._fetch_product).pack(side="left", padx=5)
        ttk.Button(url_row, text="클립보드에서 붙여넣기", command=self._paste_from_clipboard).pack(side="left", padx=5)

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
        self.desc_text = tk.Text(info, height=3)
        self.desc_text.grid(row=3, column=1, sticky="ew", padx=5, pady=3)

        image_box = ttk.LabelFrame(self.affiliate_tab, text="상품 이미지")
        image_box.pack(fill="x", padx=10, pady=(0, 5))
        self.image_canvas = tk.Canvas(image_box, height=140, highlightthickness=0)
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
        self.generate_btn = ttk.Button(btn_frame, text="글 생성", command=self._generate_post)
        self.generate_btn.pack(side="left")
        self.save_btn = ttk.Button(btn_frame, text="저장", command=self._save_post, state="disabled")
        self.save_btn.pack(side="left", padx=5)

        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(self.affiliate_tab, textvariable=self.status_var).pack(anchor="w", padx=10)
        self.progress = ttk.Progressbar(self.affiliate_tab, mode="indeterminate")
        self.progress.pack(fill="x", padx=10, pady=(0, 5))

        self.result_text = scrolledtext.ScrolledText(self.affiliate_tab, wrap="word", height=18)
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
            raw = self.clipboard_get()
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
                if 1 <= idx <= len(image_filenames):
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

        self.run_pipeline_btn = ttk.Button(top, text="파이프라인 실행", command=self._run_pipeline)
        self.run_pipeline_btn.grid(row=0, column=4, sticky="w", padx=(20, 0))

        self.pipeline_status_var = tk.StringVar(value="대기 중")
        ttk.Label(self.pipeline_tab, textvariable=self.pipeline_status_var).pack(anchor="w", padx=10)
        self.pipeline_progress = ttk.Progressbar(self.pipeline_tab, mode="indeterminate")
        self.pipeline_progress.pack(fill="x", padx=10, pady=(0, 5))

        self.pipeline_log = scrolledtext.ScrolledText(self.pipeline_tab, wrap="word")
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


if __name__ == "__main__":
    app = AutoBlogGUI()
    app.mainloop()
