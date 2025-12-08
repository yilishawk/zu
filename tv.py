#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极多源版 · 2025年12月8日
- 保留所有可用线路（多源存在）
- 名称100%统一（CCTV1就是CCTV1，再无 cctv1综合、8m1080、ipv6）
- 只保留：央视 + 卫视 + 香港 + 台灣 + 各省份地方台
- 彻底不要任何外国台
"""

import re
import subprocess

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"

def download():
    cmd = ["curl", "-fsSL", "-H", "User-Agent: Mozilla/5.0", URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout if r.returncode == 0 else ""

print("正在下载源...")
raw = download()
if not raw:
    print("下载失败")
    exit(1)

lines = raw.splitlines()
channels = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF:-1"):
        line = lines[i]
        tvg_name = re.search(r'tvg-name="([^"]*)"', line)
        tvg_name = tvg_name.group(1) if tvg_name else ""
        tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
        tvg_logo = tvg_logo.group(1) if tvg_logo else ""

        if "," in line:
            raw_title = line.split(",", 1)[1]
            # 彻底清理标题
            clean = re.sub(r'^\s*\[[^\]]*\]\s*', '', raw_title)  # [BD][HD]
            clean = re.sub(r'\s*\([^)]*\)|\s*\[.*?\]|\s*(ipv6|backup|备用|备|4m|8m|1080|720).*', '', clean, flags=re.I)
            clean = re.sub(r'\s+', ' ', clean).strip()
        else:
            clean = ""

        name = clean or tvg_name or "未知"

        if i + 1 < len(lines) and lines[i + 1].startswith("http"):
            url = lines[i + 1].strip()
            channels.append({
                "name": name,
                "clean_name": clean,
                "logo": tvg_logo,
                "url": url
            })
            i += 2
        else:
            i += 1
    else:
        i += 1

print(f"解析到 {len(channels)} 条，开始名称统一 + 过滤外国台...")

# 名称标准化映射表（强制统一）
name_map = {
    # 央视
    **{f"CCTV{i}": f"CCTV{i}" for i in range(1, 18)},
    "CCTV5+": "CCTV5+", "CCTV8K": "CCTV8K", "CCTV4K": "CCTV4K",
    "纪录": "CCTV9 纪录", "戏曲": "CCTV11 戏曲", "第一剧场": "CCTV8 剧场", "风云足球": "CCTV 风云足球",
    # 卫视
    "湖南卫视": "湖南卫视", "浙江卫视": "浙江卫视", "江苏卫视": "江苏卫视", "东方卫视": "东方卫视",
    "北京卫视": "北京卫视", "广东卫视": "广东卫视", "深圳卫视": "深圳卫视", "山东卫视": "山东卫视",
    # 香港
    "凤凰中文": "凤凰卫视中文台", "凤凰香港": "凤凰卫视香港台", "凤凰资讯": "凤凰卫视资讯台",
    "TVB": "无线翡翠台", "明珠台": "无线明珠台", "RTHK": "香港电台",
    # 台灣
    "台视": "台视", "华视": "华视", "中视": "中视", "民视": "民视", "公视": "公视",
    "东森": "东森", "三立": "三立", "纬来": "纬来", "TVBS": "TVBS",
}

# 应用统一命名
final_channels = []
for c in channels:
    name = c["clean_name"]
    found = False
    for key, std in name_map.items():
        if key.lower() in name.lower():
            c["final_name"] = std
            found = True
            break
    if not found:
        # 模糊匹配省份/地区
        if any(p in name for p in ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津","香港","台灣","凤凰","TVB","东森","三立","纬来"]):
            c["final_name"] = name
            found = True
        else:
            continue  # 不要外国台
    if found:
        final_channels.append(c)

print(f"过滤后剩余 {len(final_channels)} 个中国大陆+港台频道，开始分组...")

groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

# 分类（多源全部保留）
def assign_group(name, c):
    if "CCTV" in name or name in ["CCTV8K","CCTV9 纪录","CCTV11 戏曲","CCTV8 剧场","CCTV 风云足球"]:
        groups["央视"].append(c)
    elif "卫视" in name or "衛視" in name:
        groups["卫视"].append(c)
    elif any(x in name for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK","Viu"]):
        groups["香港"].append(c)
    elif any(x in name for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS"]):
        groups["台灣"].append(c)
    elif any(p in name for p in ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]):
        for p in ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]:
            if p in name:
                groups[p].append(c)
                return
        groups["其他省份"].append(c)
    else:
        groups["其他省份"].append(c)

for c in final_channels:
    assign_group(c["final_name"], c)

# 央视排序
cctv_order = ["CCTV1","CCTV2","CCTV3","CCTV4","CCTV5","CCTV5+","CCTV6","CCTV7","CCTV8","CCTV9 纪录","CCTV10","CCTV11 戏曲","CCTV12","CCTV13","CCTV14","CCTV15","CCTV16","CCTV17","CCTV8K","CCTV 风云足球"]
sorted_cctv = []
for std in cctv_order:
    for c in groups["央视"]:
        if c["final_name"] == std:
            sorted_cctv.append(c)
groups["央视"] = sorted_cctv + [c for c in groups["央视"] if c["final_name"] not in cctv_order]

# 输出
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁",
         "广西","云南","重庆","天津","其他省份"]

for g in order:
    for c in groups[g]:
        logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
        line = f'#EXTINF:-1 tvg-name="{c["final_name"]}"{logo} group-title="{g}",{c["final_name"]}'
        result.append(line)
        result.append(c["url"])

with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(result) + "\n")

total = (len(result) - 1) // 2
print(f"\n完美！生成 tv.m3u 共 {total} 个频道（多源保留，名称统一，仅中港台大陆）")
for g in order:
    cnt = len(groups[g])
    if cnt:
        print(f"   {g:<6} → {cnt:>3} 条")
