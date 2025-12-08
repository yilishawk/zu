#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极完美版 · 2025年12月8日
输出格式严格如下：
#EXTINF:-1 tvg-name="CCTV1" tvg-logo="..." group-title="央视",CCTV1
https://...
"""

import re
import subprocess

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"

def download():
    cmd = ["curl", "-fsSL", "-H", "User-Agent: Mozilla/5.0", URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout if r.returncode == 0 else ""

print("正在下载直播源...")
raw = download()
if not raw:
    print("下载失败")
    exit(1)

lines = raw.splitlines()
print(f"下载成功，开始解析...")

channels = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF:-1"):
        orig = lines[i]

        # 提取 tvg-name 和 tvg-logo
        tvg_name = re.search(r'tvg-name="([^"]*)"', orig)
        tvg_name = tvg_name.group(1) if tvg_name else ""
        tvg_logo = re.search(r'tvg-logo="([^"]*)"', orig)
        tvg_logo = tvg_logo.group(1) if tvg_logo else ""

        # 提取逗号后原始标题并彻底清理
        if "," in orig:
            raw_title = orig.split(",", 1)[1]
            # 去掉所有垃圾：[BD] (RTHK33) [ipv6] (备用) 等
            clean_title = re.sub(r'\[.*?\]|\(.*?\)|（.*?）|【.*?】|\s+', ' ', raw_title)
            clean_title = re.sub(r'(?i)(ipv6|backup|备用|备|ipv4)', '', clean_title)
            clean_title = clean_title.strip()
        else:
            clean_title = tvg_name

        # 如果 tvg-name 为空，用清理后的标题
        final_name = clean_title or tvg_name or "未知频道"

        if i + 1 < len(lines) and lines[i + 1].startswith("http"):
            url = lines[i + 1].strip()
            channels.append({
                "name": final_name,      # 最终用于 tvg-name 和标题
                "logo": tvg_logo,
                "url": url
            })
            i += 2
        else:
            i += 1
    else:
        i += 1

print(f"解析完成，共 {len(channels)} 个频道，开始分类...")

groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

used = set()

# 1. 央视
for c in channels:
    if "唐河" in c["name"]: continue
    if re.search(r'CCTV', c["name"], re.I):
        groups["央视"].append(c)
        used.add(c["url"])

# 央视排序
def cctv_key(c):
    n = c["name"]
    if m := re.search(r'CCTV\s*(\d+)', n, re.I):
        return (0, int(m.group(1)))
    order = {"8K":90, "纪录":91, "戏曲":92, "第一剧场":93, "风云足球":94}
    for k,v in order.items():
        if k in n: return (0, v)
    return (1, n)
groups["央视"].sort(key=cctv_key)

# 2. 卫视
for c in channels:
    if c["url"] in used: continue
    if "卫视" in c["name"] or "衛視" in c["name"]:
        groups["卫视"].append(c)
        used.add(c["url"])

# 3. 香港（凤凰前置）
phoenix = []
hk_other = []
for c in channels:
    if c["url"] in used: continue
    if any(x in c["name"] for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK","ViuTV"]):
        if "凤凰" in c["name"]:
            phoenix.append(c)
        else:
            hk_other.append(c)
        used.add(c["url"])
groups["香港"] = phoenix + hk_other

# 4. 台灣
for c in channels:
    if c["url"] in used: continue
    if any(x in c["name"] for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS","中天"]):
        groups["台灣"].append(c)
        used.add(c["url"])

# 5. 省份归类
province_map = {
    "北京":["北京","BTV"],"上海":["上海","东方"],"广东":["广东","广州","深圳","珠江","南方"],
    "浙江":["浙江"],"江苏":["江苏","南京","苏州"],"湖南":["湖南","长沙"],"山东":["山东","齐鲁"],
    "四川":["四川","成都"],"陕西":["陕西","西安"],"湖北":["湖北","武汉"],"河南":["河南","郑州"],
    "福建":["福建","厦门"],"安徽":["安徽"],"江西":["江西"],"河北":["河北"],"黑龙江":["黑龙江"],
    "辽宁":["辽宁"],"广西":["广西"],"云南":["云南"],"重庆":["重庆"],"天津":["天津"]
}

for c in channels:
    if c["url"] in used: continue
    placed = False
    for p, ks in province_map.items():
        if any(k in c["name"] for k in ks):
            groups[p].append(c)
            used.add(c["url"])
            placed = True
            break
    if not placed:
        groups["其他省份"].append(c)

# 输出：极致简洁完美格式
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁",
         "广西","云南","重庆","天津","其他省份"]

for gname in order:
    for c in groups[gname]:
        logo_part = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
        line = f'#EXTINF:-1 tvg-name="{c["name"]}"{logo_part} group-title="{gname}",{c["name"]}'
        result.append(line)
        result.append(c["url"])

with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(result) + "\n")

total = (len(result) - 1) // 2
print(f"\n完美完成！生成 tv.m3u 共 {total} 个频道")
for g in order:
    if groups[g]:
        print(f"   {g:<6} → {len(groups[g]):>3} 个")
