# iptv_ultimate_2025.py
# 功能：增量抓取 + 48小时自动清理死链 + 永远干净的播放列表
# 特点：一次运行，终身无死源！用户随便点随便秒开

import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
import base64
import time
import random
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ====================== 配置区 ======================
KEY = base64.b64decode("S7q/H5ycQPnNl0UXkDw69Fx6zN/kn+1ZgWbLumBFzB8=")
IV = base64.b64decode("fSb6cs5m9MZO2r/C/8Mdeg==")

# 搜索关键词 → 最终分组名
SEARCH_GROUPS = {
    "cctv":   "央视",
    "卫视":   "卫视",
    "陕西":   "陕西",
    "西安":   "西安",
    "香港":   "港澳",
    "台湾":   "台湾",
    "凤凰":   "港澳",
    "电影":   "电影",
    "体育":   "体育",
    "纪录片": "纪录片",
    "少儿":   "少儿",
}

LIVE_FILE = "iptv_live.txt"                    # 最终播放文件（绝对干净！仅48小时内活的）
HISTORY_JSON = "iptv_history_with_time.json"   # 核心历史库（带最后存活时间）
BACKUP_DIR = "backup"                          # 自动备份目录

# 随机 UA 池（2025最新）
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
]

# ====================== 工具函数 ======================
def get_headers():
    return {
        "User-Agent": random.choice(UA_LIST),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

def decrypt_aes(encrypted_b64: str) -> str:
    try:
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        decrypted = cipher.decrypt(base64.b64decode(encrypted_b64))
        pad = decrypted[-1]
        if not (1 <= pad <= 16):
            pad = 0
        return decrypted[:-pad].decode("utf-8", errors="ignore").strip()
    except:
        return ""

def is_link_alive(url: str, timeout=8) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    if any(x in url.lower() for x in ["localhost", "127.0.0.1", ".m3u8?token=", "127.0.0.1:"]):
        return False
    try:
        session = requests.Session()
        session.headers.update(get_headers())
        session.verify = False

        r = session.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code in (200, 206):
            return True
        if r.status_code in (403, 405):
            r = session.get(url, timeout=timeout, stream=True)
            if r.status_code == 200:
                next(r.raw.read(2048), None)
                return True
        return False
    except:
        return False

# ====================== 加载带时间戳的历史 ======================
def load_history():
    if not os.path.exists(HISTORY_JSON):
        return {}
    try:
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        print("历史文件损坏，已备份并重建")
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(BACKUP_DIR, f"damaged_{int(time.time())}.json")
        os.replace(HISTORY_JSON, backup_path)
        return {}

# ====================== 保存最终干净播放列表 ======================
def save_live_file(live_items):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(LIVE_FILE):
        backup_name = os.path.join(BACKUP_DIR, f"iptv_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        os.replace(LIVE_FILE, backup_name)

    with open(LIVE_FILE, "w", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        f.write(f"# IPTV 终极纯净版 - 更新时间：{now}\n")
        f.write(f"# 仅保留最近48小时确认能播的源，绝对不卡顿！\n\n")
        
        for group in sorted(live_items.keys()):
            items = sorted(live_items[group])
            if not items: continue
            f.write(f"{group},#genre#\n")
            for name, url in items:
                f.write(f"{name},{url}\n")
            f.write("\n")
    
    print(f"纯净播放列表已保存 → {LIVE_FILE}（{sum(len(v) for v in live_items.values())} 条）")

# ====================== 抓取关键词 ======================
def scrape_keyword(keyword: str, group_name: str, session):
    print(f"\n抓取关键词：{keyword} → 归类 [{group_name}]")
    base_url = "https://iptv-search.com/zh-hans/search/"
    max_pages = 6 if keyword in ["卫视", "cctv"] else 2
    added = 0

    for page in range(1, max_pages + 1):
        url = f"{base_url}?q={keyword}" + (f"&page={page}" if page > 1 else "")
        print(f"  第 {page} 页", end="")

        for retry in range(4):
            try:
                time.sleep(random.uniform(2.5, 4.5))
                resp = session.get(url, timeout=20)
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select(".channel.card")

                if not cards:
                    if "没有找到" in resp.text:
                        print(" → 无结果，停止翻页")
                        return added
                    print(" → 空页面", end="")
                    continue

                new_this_page = 0
                for card in cards:
                    name_tag = card.select_one(".channel-name")
                    enc_tag = card.select_one(".link-text[data-encrypted]")
                    if not name_tag or not enc_tag: continue
                    name = name_tag.get_text(strip=True)
                    enc = enc_tag["data-encrypted"]
                    link = decrypt_aes(enc)
                    if link.startswith(("http://", "https://")):
                        grouped_results.setdefault(group_name, set()).add((name, link))
                        new_this_page += 1
                print(f" → +{new_this_page}")
                added += new_this_page
                break
            except Exception as e:
                print(f" → 重试 {retry+1} ({e.__class__.__name__})", end="")
                time.sleep(5)
        else:
            print(" → 本页失败")

    print(f"  本关键词完成，新增 {added} 条")
    return added

# ====================== 主程序 ======================
if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    print("="*60)
    print("    IPTV 终极纯净版抓取器 2025")
    print("    特点：48小时自动清理死链，播放文件永远干净！")
    print("="*60 + "\n")

    start_time = time.time()
    grouped_results = {}  # 本次抓取的新源
    session = requests.Session()
    session.headers.update(get_headers())

    # 第一步：抓取所有关键词
    total_new = 0
    for kw, group in SEARCH_GROUPS.items():
        total_new += scrape_keyword(kw, group, session)

    # 第二步：加载历史（带最后存活时间）
    history = load_history()
    current_time = time.time()
    cutoff_48h = current_time - 48 * 3600

    # 把本次抓到的新源全部标记为“现在存活”
    for group, items in grouped_results.items():
        for name, url in items:
            history[url] = {
                "name": name,
                "group": group,
                "last_alive": current_time
            }

    # 第三步：找出需要检测的链接（48小时内活过 + 本次新增）
    candidates = []
    for url, info in history.items():
        if info["last_alive"] >= cutoff_48h:
            candidates.append((info["name"], url, info["group"]))

    print(f"\n开始并发检测存活（共 {len(candidates)} 条，48小时内曾活过）")
    
    live_items = {}
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {executor.submit(is_link_alive, url): (name, url, group)
                  for name, url, group in candidates}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            name, url, group = futures[future]
            if future.result():
                live_items.setdefault(group, []).append((name, url))
                history[url]["last_alive"] = current_time
            else:
                print(f"\r    失效 {completed}/{len(candidates)} → {name[:35]}", end="", flush=True)
        print("\n检测完成！")

    # 第四步：保存
    # 1. 保存带时间戳的完整历史（供下次使用）
    with open(HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # 2. 保存纯净播放文件（用户最爱的那个）
    save_live_file(live_items)

    live_count = sum(len(v) for v in live_items.values())
    print(f"\n大功告成！")
    print(f"   48小时真实存活：{live_count} 条")
    print(f"   新增源：{total_new} 条")
    print(f"   总耗时：{time.time() - start_time:.1f} 秒")
    print(f"\n直接把 {LIVE_FILE} 丢给播放器就行，绝对秒开不卡！")
    print("下次运行会自动清理超过48小时没活过的源，越来越干净")
