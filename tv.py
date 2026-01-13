#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极修复测速版 · 2026年
- 修正 CCTV 及 凤凰卫视 分组逻辑
- 增加多线程并发测速，延迟最低者排在首位
- 自动清理不可用链接
"""

import re
import subprocess
import concurrent.futures
import time
import os

# 检查并安装依赖 (针对没有 requests 的环境)
try:
    import requests
except ImportError:
    print("正在安装必要的 requests 库...")
    os.system('pip install requests')
    import requests

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"
TIMEOUT = 30  # 下载超时
CHECK_TIMEOUT = 3  # 每个链接测速超时（秒）
MAX_WORKERS = 60  # 并发线程数

def download():
    print(f"正在从源下载数据: {URL}")
    cmd = ["curl", "-fsSL", "-H", "User-Agent: Mozilla/5.0", URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    return r.stdout if r.returncode == 0 else ""

def get_speed(channel_obj):
    """测速函数，返回延迟秒数"""
    url = channel_obj["url"]
    try:
        # 使用 HEAD 请求节省流量，allow_redirects=True 处理重定向
        start_time = time.time()
        res = requests.head(url, timeout=CHECK_TIMEOUT, allow_redirects=True)
        if res.status_code == 200:
            delay = time.time() - start_time
            channel_obj["speed"] = delay
            return channel_obj
    except:
        pass
    channel_obj["speed"] = 999.0  # 失效链接设置极高延迟
    return channel_obj

def main():
    raw = download()
    if not raw:
        print("下载失败，请检查网络或 URL。")
        return

    lines = raw.splitlines()
    channels = []
    
    # --- 1. 解析 M3U ---
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

    # --- 2. 名称统一映射 ---
    name_map = {
        r"(?i)cctv[ -]?(\d+).*": r"CCTV\1",
        r"(?i)凤凰.*": "凤凰卫视中文台",
        r"(?i)无线翡翠.*|(?i)翡翠台.*": "无线翡翠台",
        r"(?i)西安.*": "陕西 西安新闻",
        r"(?i)陕西公共.*": "陕西 公共",
    }

    for c in channels:
        for pattern, std in name_map.items():
            if re.search(pattern, c["name"]):
                # 如果 std 包含正则反向引用
                if r"\1" in std:
                    c["final_name"] = re.sub(pattern, std, c["name"])
                else:
                    c["final_name"] = std
                break

    # --- 3. 多线程测速 ---
    print(f"发现 {len(channels)} 个频道源，开始并发测速 (线程数: {MAX_WORKERS})...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 只保留有效的测速结果
        tested_channels = list(executor.map(get_speed, channels))
    
    # 过滤掉完全无法连接的源 (可选，此处保留 999ms 的源，但排在最后)
    
    # --- 4. 分组逻辑 ---
    order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","山东",
             "四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁",
             "广西","云南","重庆","天津","其他省份"]
    
    groups = {g: [] for g in order}

    def get_group_name(name):
        n = name.lower()
        if "cctv" in n or "中央" in n: return "央视"
        if any(x in n for x in ["凤凰", "香港", "无线", "tvb", "rthk", "翡翠", "明珠"]): return "香港"
        if "卫视" in n: return "卫视"
        if any(x in n for x in ["台", "台灣", "中视", "华视", "民视", "公视", "东森", "三立", "纬来"]): return "台灣"
        if "陕西" in n or any(x in n for x in ["西安", "宝鸡", "咸阳"]): return "陕西"
        # 自动匹配省份
        for p in order[4:-1]:
            if p in n: return p
        return "其他省份"

    for c in tested_channels:
        g_name = get_group_name(c["final_name"])
        groups[g_name].append(c)

    # --- 5. 组内排序 (核心: 频道名优先，速度第二) ---
    for g in groups:
        # 先按频道名称排，名称一样的情况下按速度排
        groups[g].sort(key=lambda x: (x["final_name"], x["speed"]))

    # --- 6. 生成 M3U 文件 ---
    result = ["#EXTM3U"]
    for g in order:
        for c in groups[g]:
            # 跳过彻底超时的（可选）
            if c["speed"] >= 999.0: continue
            
            logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
            ms = int(c["speed"] * 1000)
            # 在名称后面标注延迟，方便查看
            line = f'#EXTINF:-1 tvg-name="{c["final_name"]}"{logo} group-title="{g}",{c["final_name"]} ({ms}ms)'
            result.append(line)
            result.append(c["url"])

    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(result) + "\n")

    print(f"\n处理完成！生成文件: tv.m3u")
    print(f"有效频道源: {len(result)//2} 条")

if __name__ == "__main__":
    main()
