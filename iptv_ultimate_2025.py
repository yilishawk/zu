# iptv_ultimate.py
# 2025 年最新版：完美绕过 iptv-search.com 的 Cloudflare 反爬
# 保留你原始逻辑：卫视5页，其他2页，48小时清理死链

import cloudscraper
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
import base64
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ==================== 配置 ====================
KEY = base64.b64decode("S7q/H5ycQPnNl0UXkDw69Fx6zN/kn+1ZgWbLumBFzB8=")
IV  = base64.b64decode("fSb6cs5m9MZO2r/C/8Mdeg==")

SEARCH_GROUPS = {
    "cctv": "央视",
    "卫视": "卫视",
    "陕西": "陕西",
    "西安": "西安",
    "香港": "香港",
    "台湾": "台湾",
    "凤凰": "香港",
}

LIVE_FILE = "iptv_live.txt"
HISTORY_FILE = "iptv_history.json"

# ==================== 核心函数 ====================
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def decrypt_aes(enc):
    try:
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        decrypted = cipher.decrypt(base64.b64decode(enc))
        pad = decrypted[-1]
        if not (1 <= pad <= 16): pad = 0
        return decrypted[:-pad].decode("utf-8", errors="ignore").strip()
    except:
        return ""

def is_alive(url):
    try:
        r = scraper.head(url, timeout=10, allow_redirects=True)
        return r.status_code in (200, 206)
    except:
        return False

# ==================== 主程序 ====================
print("开始抓取 IPTV（使用 cloudscraper 绕过 Cloudflare）")

history = {}
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

now = int(time.time())
cutoff = now - 48 * 3600
new_sources = {}

for keyword, group in SEARCH_GROUPS.items():
    pages = 5 if keyword == "卫视" else 2
    print(f"抓取 {keyword} → {group}（{pages}页）")
    
    for page in range(1, pages + 1):
        url = f"https://iptv-search.com/zh-hans/search/?q={keyword}"
        if page > 1: url += f"&page={page}"
        
        for _ in range(3):
            html = scraper.get(url, timeout=20).text
            if "channel card" in html:
                break
            time.sleep(3)
        else:
            continue

        soup = BeautifulSoup(html, 'lxml')
        cards = soup.select(".channel.card")
        
        for card in cards:
            name_tag = card.select_one(".channel-name")
            enc_tag = card.select_one(".link-text[data-encrypted]")
            if not name_tag or not enc_tag: continue
            name = name_tag.get_text(strip=True)
            link = decrypt_aes(enc_tag["data-encrypted"])
            if link.startswith("http"):
                new_sources.setdefault(group, set()).add((name, link))
                history[link] = {"name": name, "group": group, "last_alive": now}
        
        time.sleep(2)

# 检测存活
candidates = [(n, u, g) for u, info in history.items() 
              if info["last_alive"] >= cutoff 
              for n, g in [(info["name"], info["group"])]]

live = {}
print(f"开始检测 {len(candidates)} 条链接存活...")

with ThreadPoolExecutor(max_workers=20) as pool:
    results = pool.map(lambda x: (x[0], x[1], x[2], is_alive(x[1])), candidates)
    for name, url, group, alive in results:
        if alive:
            live.setdefault(group, []).append((name, url))
            history[url]["last_alive"] = now

# 保存
with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(history, f, ensure_ascii=False, indent=2)

with open(LIVE_FILE, "w", encoding="utf-8") as f:
    f.write(f"# IPTV 纯净源 - {datetime.now().strftime('%Y-%m-%d %H:%M')} 自动更新\n")
    f.write("# 仅保留48小时内确认能播的源，秒开不卡！\n\n")
    for group in sorted(live.keys()):
        items = sorted(live[group])
        f.write(f"{group},#genre#\n")
        for name, url in items:
            f.write(f"{name},{url}\n")
        f.write("\n")

print(f"完成！存活 {sum(len(v) for v in live.values())} 条，文件：{LIVE_FILE}")
