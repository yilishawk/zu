import re
import requests
import concurrent.futures
import time
import os

# --- 配置区 ---
# 建议更换为一个更稳定的源，或者保留原链接
URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
CHECK_TIMEOUT = 3
MAX_WORKERS = 50
DEEP_SPEED_GROUPS = ["央视", "卫视", "香港"]
OUTPUT_FILE = "tv.m3u"

def get_speed_score(c_obj, group_name):
    """深度测速逻辑"""
    url = c_obj["url"]
    is_deep = group_name in DEEP_SPEED_GROUPS
    try:
        start_time = time.time()
        # 增加 verify=False 防止 SSL 证书错误导致测速失败
        with requests.get(url, timeout=CHECK_TIMEOUT, stream=True, headers=HEADERS, verify=False) as res:
            if res.status_code == 200:
                ttfb = time.time() - start_time
                if is_deep:
                    downloaded = 0
                    test_start = time.time()
                    for chunk in res.iter_content(chunk_size=1024 * 64):
                        downloaded += len(chunk)
                        if downloaded >= 1024 * 1024 or (time.time() - test_start) > 1.2:
                            break
                    duration = time.time() - test_start
                    speed = (downloaded / 1024 / 1024) / (duration + 0.001)
                    c_obj["speed"] = ttfb * 0.3 + (1 / (speed + 0.1)) * 0.7
                else:
                    c_obj["speed"] = ttfb
                return c_obj
    except:
        pass
    c_obj["speed"] = 99.0
    return c_obj

def is_pure_abc(name):
    """剔除纯英文/数字频道名"""
    clean = re.sub(r'[\s\d\-\_\.\(\)\[\]]', '', name)
    if clean.isalpha() and not re.search(r'[\u4e00-\u9fa5]', name):
        return True
    return False

def get_weight(name, group):
    n = name.upper()
    if group == "央视":
        match = re.search(r'CCTV(\d+)', n)
        return int(match.group(1)) if match else 99
    if group == "香港":
        if any(x in n for x in ["凤凰", "鳳凰"]): return 1
        return 10
    if group == "台灣":
        if any(x in n for x in ["新闻", "新聞"]): return 1
        if any(x in n for x in ["综合", "綜合"]): return 2
        if any(x in n for x in ["娱乐", "娛樂", "综艺"]): return 3
        return 10
    return 100

def main():
    print(f"开始获取源数据: {URL}")
    raw = ""
    for i in range(3):  # 增加 3 次重试机制
        try:
            r = requests.get(URL, headers=HEADERS, timeout=30, verify=False)
            if r.status_code == 200:
                raw = r.text
                break
        except Exception as e:
            print(f"第 {i+1} 次尝试失败: {e}")
            time.sleep(5)

    if not raw or ("#EXTM3U" not in raw and "http" not in raw):
        print("❌ 错误: 未能获取到有效的源数据内容！")
        return # 这里返回会导致后续不生成文件，触发 Workflow 报错是正确的

    lines = raw.splitlines()
    channels = []
    print(f"解析中... 共 {len(lines)} 行数据")

    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # 兼容性解析：提取名称和台标
            logo = re.search(r'tvg-logo="([^"]*)"', line).group(1) if 'tvg-logo="' in line else ""
            name = line.split(",", 1)[-1].strip()
            
            # 清洗名称
            name = re.sub(r'^\s*\[[^\]]*\]\s*', '', name)
            name = re.sub(r'\s*\([^)]*\)|\s*(ipv6|backup|备用|备|4m|8m|1080|高清|HD).*', '', name, flags=re.I).strip()
            
            # 统一 CCTV 命名
            cctv_m = re.search(r'cctv[ -]?(\d+)', name, re.I)
            if cctv_m: name = f"CCTV{cctv_m.group(1)}"

            # 寻找下一行的 URL
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if next_line.startswith("http"):
                    channels.append({"name": name, "url": next_line, "logo": logo, "speed": 99.0})
                    break

    if not channels:
        print("❌ 解析失败: 未发现任何频道链接！")
        return

    # 分组过滤
    order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","其他省份"]
    groups = {g: [] for g in order}

    def get_group_name(n):
        n_l = n.lower()
        if "cctv" in n_l: return "央视"
        if "卫视" in n_l: return "卫视"
        if any(x in n_l for x in ["凤凰", "翡翠", "tvb", "hks", "凤凰"]): return "香港"
        if any(x in n_l for x in ["台湾", "台灣", "中视", "华视", "民视"]): return "台灣"
        for p in ["北京", "上海", "广东", "浙江", "江苏", "湖南"]:
            if p in n_l: return p
        return "其他省份"

    filtered = [c for c in channels if not (get_group_name(c["name"]) in ["香港", "台灣"] and is_pure_abc(c["name"]))]
    
    print(f"🚀 开始并发测速，有效频道数: {len(filtered)}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(get_speed_score, c, get_group_name(c["name"])) for c in filtered]
        tested = [f.result() for f in concurrent.futures.as_completed(futures)]

    for c in tested:
        groups[get_group_name(c["name"])].append(c)

    # 生成文件
    result = ["#EXTM3U"]
    count = 0
    for g in order:
        groups[g].sort(key=lambda x: (get_weight(x["name"], g), x["speed"]))
        seen = set()
        for c in groups[g]:
            key = f"{c['name']}_{c['url']}"
            if key in seen or c["speed"] >= 90: continue # 剔除死链
            seen.add(key)
            
            logo_str = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
            line = f'#EXTINF:-1 tvg-name="{c["name"]}"{logo_str} group-title="{g}",{c["name"]}'
            result.append(line)
            result.append(c["url"])
            count += 1

    if count > 0:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(result) + "\n")
        print(f"✅ 成功! 已生成 {OUTPUT_FILE}，包含 {count} 个频道。")
    else:
        print("❌ 警告: 测速后没有剩余可用频道，不生成文件。")

if __name__ == "__main__":
    main()
