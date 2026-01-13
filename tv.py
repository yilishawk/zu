#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极修复测速版 (Fixed Regex Error)
- 解决 Python 3.11+ re.error: global flags 错误
- 强化 CCTV 和 凤凰卫视 分类
- 异步并发测速
"""

import re
import subprocess
import concurrent.futures
import time
import os

# 自动检查并安装 requests
try:
    import requests
except ImportError:
    print("正在安装必要的 requests 库...")
    os.system('pip install requests')
    import requests

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"
TIMEOUT = 30
CHECK_TIMEOUT = 3
MAX_WORKERS = 60

def download():
    print(f"正在从源下载数据: {URL}")
    # 使用 -k 忽略 SSL 证书错误（部分 IPTV 源证书过期）
    cmd = ["curl", "-fsSLk", "-H", "User-Agent: Mozilla/5.0", URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    return r.stdout if r.returncode == 0 else ""

def get_speed(channel_obj):
    url = channel_obj["url"]
    try:
        start_time = time.time()
        # 使用 GET 请求前几个字节，比 HEAD 更准确但比全量下载快
        res = requests.get(url, timeout=CHECK_TIMEOUT, stream=True, allow_redirects=True)
        if res.status_code == 200:
            delay = time.time() - start_time
            channel_obj["speed"] = delay
            res.close()
            return channel_obj
    except:
        pass
    channel_obj["speed"] = 999.0
    return channel_obj

def main():
    raw = download()
    if not raw:
        print("下载失败")
        return

    lines = raw.splitlines()
    channels = []
    
    print("正在解析频道信息...")
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF:-1"):
            line = lines[i]
            tvg_name = re.search(r'tvg-name="([^"]*)"', line)
            tvg_name = tvg_name.group(1) if tvg_name else ""
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo.group(1) if tvg_logo else ""

            if "," in line:
                raw_title = line.split(",", 1)[1]
                clean = re.sub(r'^\s*\[[^\]]*\]\s*', '', raw_title)
                clean = re.sub(r'\s*\([^)]*\)|\s*(ipv6|backup|备用|备|4m|8m|1080|720).*', '', clean, flags=re.I)
                clean = re.sub(r'\s+', ' ', clean).strip()
            else:
                clean = ""

            name = clean or tvg_name or "未知"
            
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                url = lines[i + 1].strip()
                channels.append({
                    "name": name,
                    "logo": tvg_logo,
                    "url": url,
                    "final_name": name
                })

    # --- 修正后的名称映射 (移除了内嵌标志，改用 re.I) ---
    name_map = [
        (r"cctv[ -]?(\d+).*", r"CCTV\1"),
        (r"凤凰.*", "凤凰卫视中文台"),
        (r"无线翡翠.*|翡翠台.*", "无线翡翠台"),
        (r"西安.*", "陕西 西安新闻"),
        (r"陕西公共.*", "陕西 公共"),
    ]

    for c in channels:
        for pattern, std in name_map:
            # 在 re.search 中传入 re.IGNORECASE 替代 (?i)
            match = re.search(pattern, c["name"], re.IGNORECASE)
            if match:
                if r"\1" in std:
                    c["final_name"] = re.sub(pattern, std, c["name"], flags=re.IGNORECASE)
                else:
                    c["final_name"] = std
                break

    print(f"解析到 {len(channels)} 个频道，开始并发测速...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        tested_channels = list(executor.map(get_speed, channels))
    
    order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","山东",
             "四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁",
             "广西","云南","重庆","天津","其他省份"]
    
    groups = {g: [] for g in order}

    def get_group_name(name):
        n = name.lower()
        # 优先级判断：先判断凤凰/香港，再判断央视
        if any(x in n for x in ["凤凰", "香港", "无线", "tvb", "rthk", "翡翠", "明珠"]): 
            return "香港"
        if "cctv" in n or "中央" in n: 
            return "央视"
        if "卫视" in n: 
            return "卫视"
        if any(x in n for x in ["台", "台灣", "中视", "华视", "民视", "公视", "东森", "三立", "纬来"]): 
            return "台灣"
        if "陕西" in n or any(x in n for x in ["西安", "宝鸡", "咸阳"]): 
            return "陕西"
        for p in order[4:-1]:
            if p in n: return p
        return "其他省份"

    for c in tested_channels:
        g_name = get_group_name(c["final_name"])
        groups[g_name].append(c)

    # 排序：频道名第一，延迟第二
    for g in groups:
        groups[g].sort(key=lambda x: (x["final_name"], x["speed"]))

    result = ["#EXTM3U"]
    for g in order:
        for c in groups[g]:
            if c["speed"] >= 999.0: 
                continue
            
            logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
            ms = int(c["speed"] * 1000)
            line = f'#EXTINF:-1 tvg-name="{c["final_name"]}"{logo} group-title="{g}",{c["final_name"]} ({ms}ms)'
            result.append(line)
            result.append(c["url"])

    output_file = "tv.m3u"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(result) + "\n")

    print(f"\n[成功] 生成文件: {output_file}")
    print(f"有效低延迟频道: {len(result)//2} 条")

if __name__ == "__main__":
    main()
