#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess
import concurrent.futures
import time
import os

# 自动检查并安装 requests
try:
    import requests
except ImportError:
    os.system('pip install requests')
    import requests

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"
CHECK_TIMEOUT = 3
MAX_WORKERS = 50

def download():
    print(f"正在下载源数据: {URL}")
    headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    cmd = ["curl", "-fsSLk", "-H", headers, URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else ""

def get_speed(channel_obj):
    url = channel_obj["url"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        start_time = time.time()
        with requests.get(url, timeout=CHECK_TIMEOUT, stream=True, headers=headers, verify=False) as res:
            if res.status_code == 200:
                channel_obj["speed"] = time.time() - start_time
                return channel_obj
    except:
        pass
    channel_obj["speed"] = 99.0
    return channel_obj

def get_cctv_order(name):
    """为CCTV频道分配排序权重，非CCTV频道排在后面"""
    match = re.search(r'CCTV(\d+)', name, re.I)
    if match:
        return int(match.group(1)) # 返回数字，如 CCTV1 -> 1
    if "CCTV" in name.upper():
        # 处理非数字的CCTV频道，如 CCTV风云足球 等
        return 99
    return 999

def main():
    raw = download()
    if not raw or "#EXTM3U" not in raw:
        print("错误: 未能获取有效的 M3U 数据")
        return

    lines = raw.splitlines()
    channels = []
    
    print("正在解析频道及台标...")
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF:-1"):
            line = lines[i]
            
            # 1. 提取台标
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            logo = logo_match.group(1) if logo_match else ""
            
            # 2. 提取名称并清洗
            raw_name = line.split(",", 1)[1].strip() if "," in line else ""
            clean_name = re.sub(r'^\s*\[[^\]]*\]\s*', '', raw_name)
            clean_name = re.sub(r'\s*\([^)]*\)|\s*(ipv6|backup|备用|备|4m|8m|1080|720|高清|超清|HD|HEVC).*', '', clean_name, flags=re.I).strip()
            
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                url = lines[i + 1].strip()
                channels.append({
                    "final_name": clean_name,
                    "url": url,
                    "logo": logo,
                    "speed": 99.0
                })

    # --- 统一命名映射 ---
    for c in channels:
        cctv_match = re.search(r'cctv[ -]?(\d+)', c["final_name"], re.I)
        if cctv_match:
            c["final_name"] = f"CCTV{cctv_match.group(1)}"
        elif "凤凰" in c["final_name"]:
            if "资讯" in c["final_name"]: c["final_name"] = "凤凰资讯"
            elif "电影" in c["final_name"]: c["final_name"] = "凤凰电影"
            else: c["final_name"] = "凤凰中文"

    print(f"解析完成，开始并发测速...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        tested_channels = list(executor.map(get_speed, channels))
    
    # --- 分组与排序 ---
    order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","陕西","其他省份"]
    groups = {g: [] for g in order}

    def get_group(name):
        n = name.lower()
        if any(x in n for x in ["凤凰", "香港", "tvb", "翡翠"]): return "香港"
        if "cctv" in n: return "央视"
        if "卫视" in n: return "卫视"
        if any(x in n for x in ["台", "台灣", "中视", "华视"]): return "台灣"
        if any(x in n for x in ["陕西", "西安"]): return "陕西"
        for p in ["北京", "上海", "广东", "浙江", "江苏", "湖南"]:
            if p in n: return p
        return "其他省份"

    for c in tested_channels:
        g = get_group(c["final_name"])
        groups[g].append(c)

    # 生成文件
    result = ["#EXTM3U"]
    for g in order:
        # --- 核心修改：复合排序逻辑 ---
        if g == "央视":
            # 央视排序：先按CCTV数字编号排，编号相同（即同频道的不同源）按测速排
            groups[g].sort(key=lambda x: (get_cctv_order(x["final_name"]), x["speed"]))
        else:
            # 其他分组：按名称首字母排，名称相同按测速排
            groups[g].sort(key=lambda x: (x["final_name"], x["speed"]))
        
        for c in groups[g]:
            logo_str = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
            speed_val = f"{int(c['speed']*1000)}ms" if c['speed'] < 10 else "Timeout"
            line = f'#EXTINF:-1 tvg-name="{c["final_name"]}"{logo_str} group-title="{g}",{c["final_name"]} ({speed_val})'
            result.append(line)
            result.append(c["url"])

    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(result) + "\n")

    print(f"\n[完成] 央视已按1-17顺序排列，台标已保留。")

if __name__ == "__main__":
    main()
