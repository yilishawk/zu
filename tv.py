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
    print(f"正在下载: {URL}")
    headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    cmd = ["curl", "-fsSLk", "-H", headers, URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else ""

def get_speed(channel_obj):
    url = channel_obj["url"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        start_time = time.time()
        # 使用 stream=True 仅获取头部，提高兼容性
        with requests.get(url, timeout=CHECK_TIMEOUT, stream=True, headers=headers, verify=False) as res:
            if res.status_code == 200:
                channel_obj["speed"] = time.time() - start_time
                return channel_obj
    except:
        pass
    channel_obj["speed"] = 99.0  # 默认失败延迟
    return channel_obj

def main():
    raw = download()
    if not raw or "#EXTM3U" not in raw:
        print("错误: 未能获取有效的 M3U 数据")
        # 即使失败也创建一个空文件防止 CI 报错
        open("tv.m3u", "w").write("#EXTM3U\n")
        return

    lines = raw.splitlines()
    channels = []
    
    print("正在解析频道...")
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF:-1"):
            line = lines[i]
            # 提取名称
            tvg_name = re.search(r'tvg-name="([^"]*)"', line)
            tvg_name = tvg_name.group(1) if tvg_name else ""
            
            name = ""
            if "," in line:
                name = line.split(",", 1)[1].strip()
            name = name or tvg_name or "未知频道"

            # 清洗名称
            name = re.sub(r'\s*(ipv6|backup|备用|备|4m|8m|1080|720).*', '', name, flags=re.I).strip()
            
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                channels.append({
                    "name": name,
                    "url": lines[i + 1].strip(),
                    "final_name": name,
                    "logo": ""
                })

    # 名称规整
    for c in channels:
        if re.search(r'cctv[ -]?(\d+)', c["name"], re.I):
            num = re.search(r'cctv[ -]?(\d+)', c["name"], re.I).group(1)
            c["final_name"] = f"CCTV{num}"
        elif "凤凰" in c["name"]:
            c["final_name"] = "凤凰卫视中文台"

    print(f"解析完成，开始为 {len(channels)} 个源测速...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        tested_channels = list(executor.map(get_speed, channels))
    
    order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","陕西","其他省份"]
    groups = {g: [] for g in order}

    def get_group(name):
        n = name.lower()
        if "cctv" in n: return "央视"
        if any(x in n for x in ["凤凰", "香港", "tvb", "翡翠"]): return "香港"
        if "卫视" in n: return "卫视"
        if any(x in n for x in ["台", "台灣", "中视", "华视"]): return "台灣"
        if any(x in n for x in ["陕西", "西安"]): return "陕西"
        for p in ["北京", "上海", "广东", "浙江", "江苏", "湖南"]:
            if p in n: return p
        return "其他省份"

    for c in tested_channels:
        g = get_group(c["final_name"])
        groups[g].append(c)

    # 排序：名字相同看速度
    result = ["#EXTM3U"]
    for g in order:
        groups[g].sort(key=lambda x: (x["final_name"], x["speed"]))
        for c in groups[g]:
            # 即使测速失败也保留，但标注为 Timeout
            speed_info = f"({int(c['speed']*1000)}ms)" if c['speed'] < 10 else "(Timeout)"
            result.append(f'#EXTINF:-1 group-title="{g}",{c["final_name"]} {speed_info}')
            result.append(c["url"])

    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(result) + "\n")

    print(f"成功导出 {len(result)//2} 个频道到 tv.m3u")

if __name__ == "__main__":
    main()
