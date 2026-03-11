"""
Sitemap Crawler MVP
爬取目標網站，解析 sitemap.xml，遍歷所有頁面，
並偵測是否被 interstitial page（如 DevTunnels 確認頁）阻擋。
"""

import requests
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# === 設定 ===
_raw = sys.argv[1] if len(sys.argv) > 1 else "https://lawrence565.github.io/test_toolbox"
# 若使用者帶入完整的 index.html 路徑，自動截斷到目錄層
if _raw.endswith("/index.html"):
    _raw = _raw[: -len("/index.html")]
BASE_URL = _raw.rstrip("/")
TIMEOUT = 15
HEADERS = {
    "User-Agent": "SitemapCrawler/1.0 (MVP Test Bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# DevTunnels interstitial 特徵
INTERSTITIAL_SIGNATURES = [
    "devtunnels",
    "interstitial",
    "tunnel-warning",
    "continue to site",
    "confirm access",
    "dev tunnel",
    "port forwarding",
    "Microsoft Dev Tunnels",
]


class LinkExtractor(HTMLParser):
    """從 HTML 中提取所有 <a href> 連結"""
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def detect_interstitial(text, url):
    """偵測回應內容是否為 interstitial page"""
    lower = text.lower()
    hits = [sig for sig in INTERSTITIAL_SIGNATURES if sig.lower() in lower]
    if hits:
        return True, hits
    # 額外檢查：頁面太短且不含預期內容
    if len(text.strip()) < 200 and "claude" not in lower:
        return True, ["suspicious: very short page without expected content"]
    return False, []


def fetch(url, session):
    """發送 GET 請求並回傳 (response, error_msg)"""
    try:
        resp = session.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return resp, None
    except requests.exceptions.SSLError as e:
        return None, f"SSL Error: {e}"
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection Error: {e}"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.RequestException as e:
        return None, f"Request Error: {e}"


def parse_sitemap(xml_text, base_url):
    """解析 sitemap.xml，回傳 URL 清單"""
    urls = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_elem in root.findall(".//sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            priority = url_elem.find("sm:priority", ns)
            if loc is not None and loc.text:
                urls.append({
                    "loc": loc.text.strip(),
                    "priority": priority.text.strip() if priority is not None else "—",
                })
    except ET.ParseError as e:
        print(f"  ⚠ Sitemap XML 解析失敗: {e}")
    return urls


def extract_links(html_text, page_url):
    """從 HTML 提取同站內部連結"""
    parser = LinkExtractor()
    parser.feed(html_text)
    base_domain = urlparse(page_url).netloc
    internal = set()
    for href in parser.links:
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        full = urljoin(page_url, href)
        if urlparse(full).netloc == base_domain and full.endswith((".html", "/")):
            internal.add(full.split("#")[0])  # 去除 anchor
    return internal


def main():
    print("=" * 60)
    print(f"🕷  Sitemap Crawler MVP")
    print(f"   目標: {BASE_URL}")
    print("=" * 60)

    session = requests.Session()
    results = []

    # --- Step 1: 取得首頁 ---
    print(f"\n[1/4] 取得首頁 {BASE_URL}/")
    resp, err = fetch(f"{BASE_URL}/", session)
    if err:
        print(f"  ❌ {err}")
        print("\n結論: 無法連線到目標網站")
        return
    print(f"  HTTP {resp.status_code} | Content-Length: {len(resp.text)} bytes")
    if resp.history:
        print(f"  重導向鏈: {' → '.join(r.url for r in resp.history)} → {resp.url}")

    if resp.status_code >= 400:
        print(f"  ❌ 首頁回傳 {resp.status_code}，請確認 BASE_URL 是否正確")
        print(f"     實際請求 URL: {resp.url}")
        return

    is_blocked, sigs = detect_interstitial(resp.text, resp.url)
    if is_blocked:
        print(f"  🚧 偵測到 Interstitial Page!")
        print(f"     匹配特徵: {', '.join(sigs)}")
        print(f"     頁面前 500 字元:")
        print(f"     {resp.text[:500]}")
    else:
        print(f"  ✅ 首頁正常載入（含 'claude' 相關內容）")

    results.append({
        "url": f"{BASE_URL}/",
        "status": resp.status_code,
        "size": len(resp.text),
        "interstitial": is_blocked,
    })

    # --- Step 2: robots.txt ---
    print(f"\n[2/4] 取得 robots.txt")
    resp_robots, err = fetch(f"{BASE_URL}/robots.txt", session)
    if err:
        print(f"  ⚠ {err}")
    elif resp_robots.status_code == 200:
        print(f"  HTTP {resp_robots.status_code}")
        print(f"  內容:\n  {resp_robots.text.strip().replace(chr(10), chr(10) + '  ')}")
    else:
        print(f"  HTTP {resp_robots.status_code} (未找到)")

    # --- Step 3: sitemap.xml ---
    print(f"\n[3/4] 取得並解析 sitemap.xml")
    resp_sitemap, err = fetch(f"{BASE_URL}/sitemap.xml", session)
    sitemap_urls = []
    if err:
        print(f"  ⚠ {err}")
    elif resp_sitemap.status_code == 200:
        is_blocked_sm, sigs_sm = detect_interstitial(resp_sitemap.text, resp_sitemap.url)
        if is_blocked_sm:
            print(f"  🚧 sitemap.xml 也被 Interstitial 阻擋!")
            print(f"     匹配特徵: {', '.join(sigs_sm)}")
        else:
            sitemap_urls = parse_sitemap(resp_sitemap.text, BASE_URL)
            print(f"  ✅ 解析成功，共 {len(sitemap_urls)} 個 URL")
            for u in sitemap_urls:
                print(f"     [{u['priority']}] {u['loc']}")
    else:
        print(f"  HTTP {resp_sitemap.status_code} (未找到)")

    # --- Step 4: 逐頁爬取 ---
    # 收集所有要爬的 URL（sitemap + 首頁發現的連結）
    all_urls = set()
    if sitemap_urls:
        for u in sitemap_urls:
            # 把 sitemap 中的 example.com 替換為實際 base URL
            real_url = u["loc"].replace("https://example.com", BASE_URL)
            all_urls.add(real_url)
    # 從首頁 HTML 提取連結
    if not is_blocked:
        discovered = extract_links(resp.text, f"{BASE_URL}/")
        all_urls.update(discovered)

    # 去掉已爬過的首頁
    all_urls.discard(f"{BASE_URL}/")
    all_urls.discard(f"{BASE_URL}/index.html")

    print(f"\n[4/4] 逐頁爬取（共 {len(all_urls)} 個頁面）")
    blocked_count = 0
    ok_count = 0

    for url in sorted(all_urls):
        resp_page, err = fetch(url, session)
        if err:
            print(f"  ❌ {url}\n     {err}")
            results.append({"url": url, "status": 0, "size": 0, "interstitial": False, "error": err})
            continue

        is_pg_blocked, pg_sigs = detect_interstitial(resp_page.text, url)
        status_icon = "🚧" if is_pg_blocked else "✅"
        print(f"  {status_icon} [{resp_page.status_code}] {url} ({len(resp_page.text)} bytes)")

        if is_pg_blocked:
            blocked_count += 1
            print(f"     Interstitial 特徵: {', '.join(pg_sigs)}")
        else:
            ok_count += 1
            # 顯示頁面 title
            title_start = resp_page.text.find("<title>")
            title_end = resp_page.text.find("</title>")
            if title_start != -1 and title_end != -1:
                title = resp_page.text[title_start + 7:title_end].strip()
                print(f"     Title: {title}")

        results.append({
            "url": url,
            "status": resp_page.status_code,
            "size": len(resp_page.text),
            "interstitial": is_pg_blocked,
        })

    # --- 總結 ---
    print("\n" + "=" * 60)
    print("📊 爬取結果總結")
    print("=" * 60)
    total = len(results)
    total_blocked = sum(1 for r in results if r.get("interstitial"))
    total_ok = sum(1 for r in results if not r.get("interstitial") and r.get("status", 0) == 200)
    total_err = sum(1 for r in results if r.get("error"))

    print(f"  總頁面數:    {total}")
    print(f"  成功載入:    {total_ok}")
    print(f"  被阻擋:      {total_blocked}")
    print(f"  連線失敗:    {total_err}")
    print()

    if total_blocked > 0:
        print("  🚧 結論: 爬蟲被 Interstitial Page 阻擋！")
        print("     DevTunnels 的 interstitial page 會在瀏覽器外的請求中出現，")
        print("     因為它需要使用者在瀏覽器中手動確認存取。")
        print("     建議: 使用 --host 0.0.0.0 搭配 ngrok，或部署到靜態主機。")
    elif total_ok == total:
        print("  ✅ 結論: 所有頁面皆正常載入，未被 interstitial 阻擋！")
    else:
        print("  ⚠ 結論: 部分頁面有錯誤，請檢查上方詳細記錄。")


if __name__ == "__main__":
    main()
