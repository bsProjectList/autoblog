chrome.action.onClicked.addListener((tab) => {
  if (!tab.id) return;
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractAndCopy,
  });
});

async function extractAndCopy() {
  const SKIP_IMAGE_PATTERNS = ["icon", "logo", "sprite", "blank.gif", "pixel", "spinner", ".svg"];
  const MIN_IMAGE_SIZE = 200;
  const MAX_IMAGES = 40;

  function meta(prop) {
    const el = document.querySelector(`meta[property="${prop}"]`) || document.querySelector(`meta[name="${prop}"]`);
    return el ? (el.getAttribute("content") || "").trim() : "";
  }

  function showToast(message) {
    let toast = document.getElementById("__autoblog_toast__");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "__autoblog_toast__";
      toast.style.cssText =
        "position:fixed;top:20px;right:20px;z-index:2147483647;background:#222;color:#fff;" +
        "padding:12px 20px;border-radius:8px;font-size:14px;box-shadow:0 2px 10px rgba(0,0,0,.35);" +
        "font-family:-apple-system,'Segoe UI',sans-serif;";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => toast.remove(), 2500);
  }

  async function autoScrollToLoadImages() {
    const step = Math.max(window.innerHeight, 600);
    let lastHeight = 0;
    let y = 0;
    for (let i = 0; i < 40; i++) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 200));
      const h = document.body.scrollHeight;
      if (y >= h - window.innerHeight) {
        if (h === lastHeight) break;
        lastHeight = h;
      }
      y += step;
    }
    window.scrollTo(0, 0);
    await new Promise((r) => setTimeout(r, 200));
  }

  showToast("⏳ 상세 이미지 로딩을 위해 페이지를 스크롤하는 중...");
  await autoScrollToLoadImages();

  const title = meta("og:title") || document.title.trim();
  const description = meta("og:description") || "";
  const ogImage = meta("og:image") || "";

  const images = [];
  if (ogImage) images.push(ogImage);
  Array.from(document.querySelectorAll("img"))
    .filter((img) => img.naturalWidth >= MIN_IMAGE_SIZE && img.naturalHeight >= MIN_IMAGE_SIZE)
    .forEach((img) => {
      if (images.length >= MAX_IMAGES) return;
      const src = img.currentSrc || img.src;
      if (!src) return;
      const lowered = src.toLowerCase();
      if (SKIP_IMAGE_PATTERNS.some((p) => lowered.includes(p))) return;
      if (!images.includes(src)) images.push(src);
    });

  const bodyText = document.body.innerText.slice(0, 5000);
  const priceMatch = bodyText.match(/([\d,]{3,})\s*원/);
  const price = priceMatch ? priceMatch[1] + "원" : "";

  const data = {
    url: location.href,
    hostname: location.hostname,
    title,
    price,
    description,
    image_urls: images,
  };

  navigator.clipboard
    .writeText(JSON.stringify(data))
    .then(() => showToast(`✅ 상품 정보 + 이미지 ${images.length}개가 클립보드에 복사되었습니다.`))
    .catch((err) => showToast("❌ 클립보드 복사 실패: " + err));
}
