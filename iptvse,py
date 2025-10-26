# iptv_scraper.py
import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
import base64
import time
import random
import os
from concurrent.futures import ThreadPoolExecutor

# ====================== AES 密钥 ======================
KEY = base64.b64decode("S7q/H5ycQPnNl0UXkDw69Fx6zN/kn+1ZgWbLumBFzB8=")
IV = base64.b64decode("fSb6cs5m9MZO2r/C/8Mdeg==")

# ====================== 搜索分组 ======================
SEARCH_GROUPS = {
    "cctv": "央视",
    "卫视": "卫视",
    "陕西": "陕西",
    "西安": "西安",
    "香港": "香港",
    "台湾": "台湾",
    "凤凰": "香港",
}

# ====================== 文件路径 ======================
LIVE_FILE = "iptv_live.txt"        # 最终播放文件（只保留能播）
HISTORY_FILE = "iptv_history.txt"  # 所有抓到过的源（永不丢失）
BACKUP_FILE = "iptv_backup.txt"    # 自动备份

# ====================== 请求头 ======================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# ====================== 全局结果（本次抓取）======================
grouped_results = {}

# ====================== AES 解密 ======================
def decrypt_aes_base64(encrypted_b64: str) -> str:
    try:
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        decrypted = cipher.decrypt(base64.b64decode(encrypted_b64))
        pad_len = decrypted[-1]
        return decrypted[:-pad_len].decode("utf-8", errors="ignore").strip()
    except:
        return ""

# ====================== 检测链接是否能播放 ======================
def is_link_alive(link: str) -> bool:
    try:
        r = requests.head(link, timeout=6, allow_redirects=True, headers=HEADERS)
        if r.status_code in (200, 206):
            return True
        if r.status_code in (403, 405):
            r = requests.get(link, timeout=6, stream=True, headers=HEADERS)
            if r.status_code == 200:
                next(r.raw.read(1024), None)
                return True
        return False
    except:
        return False

# ====================== 并发过滤存活链接 ======================
def filter_live_links(links):
    live = set()
    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {pool.submit(is_link_alive, link): (name, link) for name, link in links}
        for f in futures:
            name, link = futures[f]
            if f.result():
                live.add((name, link))
            else:
                print(f"    失效 → {name}")
    return live

# ====================== 加载历史数据 ======================
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    history = {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        group = None
        for line in f:
            line = line.strip()
            if not line: continue
            if line.endswith(",#genre#"):
                group = line[:-8]
                history[group] = set()
            elif group and "," in line:
                name, link = line.split(",", 1)
                history[group].add((name.strip(), link.strip()))
    return history

# ====================== 保存合并 + 过滤 ======================
def save_and_filter():
    print(f"\n开始合并与过滤...")
    history = load_history()
    total_hist = sum(len(v) for v in history.values())
    print(f"历史库：{total_hist} 条")

    merged = {}
    for g in set(history.keys()) | set(grouped_results.keys()):
        merged[g] = history.get(g, set()) | grouped_results.get(g, set())
    total_merged = sum(len(v) for v in merged.values())
    print(f"合并后：{total_merged} 条（+{total_merged - total_hist}）")

    print(f"检测链接存活（并发15线程）...")
    live_data = {}
    for group, items in merged.items():
        if not items: continue
        print(f"  检测 {group} ({len(items)} 条)")
        live_data[group] = filter_live_links(items)
    
    live_count = sum(len(v) for v in live_data.values())
    print(f"存活：{live_count} 条")

    # 备份旧文件
    for f in [LIVE_FILE, HISTORY_FILE]:
        if os.path.exists(f):
            os.replace(f, BACKUP_FILE)

    # 保存历史（所有）
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for g in sorted(merged.keys()):
            items = sorted(merged[g])
            if not items: continue
            f.write(f"{g},#genre#\n")
            for n, l in items: f.write(f"{n},{l}\n")
            f.write("\n")

    # 保存存活（推荐播放）
    with open(LIVE_FILE, "w", encoding="utf-8") as f:
        for g in sorted(live_data.keys()):
            items = sorted(live_data[g])
            if not items: continue
            f.write(f"{g},#genre#\n")
            for n, l in items: f.write(f"{n},{l}\n")
            f.write("\n")

    print(f"\n保存完成！")
    print(f"   所有历史 → {HISTORY_FILE}")
    print(f"   仅存活 → {LIVE_FILE}（推荐播放）")

# ====================== 抓取关键词（卫视5页，其他1页，无数据重试）======================
def scrape_keyword(keyword: str, group: str):
    print(f"\n抓取关键词: {keyword} → {group}")
    max_pages = 5 if keyword == "卫视" else 1
    success_pages = 0

    for page in range(1, max_pages + 1):
        url = f"https://iptv-search.com/zh-hans/search/?q={keyword}"
        if page > 1:
            url += f"&page={page}"
        print(f"  页码 {page}: {url}", end="")

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select(".channel.card")
                
                if not cards:
                    print(" [无数据]", end="")
                    if attempt < 2:
                        delay = random.uniform(3, 5)
                        print(f" 延迟 {delay:.1f}s 后重试...", end="")
                        time.sleep(delay)
                        continue
                    break

                added = 0
                for c in cards:
                    name_tag = c.select_one(".channel-name")
                    span = c.select_one(".link-text")
                    if not name_tag or not span: continue
                    name = name_tag.text.strip()
                    enc = span.get("data-encrypted", "").strip()
                    if not enc: continue
                    link = decrypt_aes_base64(enc)
                    if not link.startswith("http"): continue
                    grouped_results.setdefault(group, set()).add((name, link))
                    added += 1
                print(f" [成功 +{added}]", end="")
                success_pages += 1
                break

            except requests.Timeout:
                print(f" [超时{attempt+1}]", end="")
                if attempt < 2:
                    time.sleep(random.uniform(3, 5))
            except Exception as e:
                print(f" [错误{attempt+1}]", end="")
                if attempt < 2:
                    time.sleep(2)
        else:
            print(" [彻底失败]", end="")
        
        time.sleep(random.uniform(1.5, 3))
    
    print(f"  → 成功 {success_pages}/{max_pages} 页")

# ====================== 主程序 ======================
if __name__ == "__main__":
    print("IPTV 终极抓取启动：增量 + 过滤 + 永不丢失\n")
    start = time.time()

    for kw, group in SEARCH_GROUPS.items():
        scrape_keyword(kw, group)

    save_and_filter()

    print(f"\n总耗时: {time.time() - start:.1f} 秒")
    print("抓取 + 过滤完成！数据已安全保存！")
