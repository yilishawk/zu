#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极完美版 · 2025年12月8日
输出格式严格要求：
#EXTINF:-1 tvg-name="CCTV9" tvg-logo="..." group-title="央视",CCTV9
https://...
https://stream1.freetv.fun/cctv9-1.m3u8
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
print(f"下载成功，开始解析 {len(lines)} 行...")

channels = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF:-1"):
        full_line = lines[i]
        # 提取 tvg-name（如果有的话）
        tvg_name = ""
        m = re.search(r'tvg-name="([^"]*)"', full_line)
        if m:
            tvg_name = m.group(1)

        # 提取原始标题（逗号后全部）
        title_raw = full_line.split(",",  # 保留完整原始行用于后面重建
        if "," in full_line:
            title_raw_after_comma = full_line.split(",", 1)[1]
            # 去掉开头的 [BD] [HD] [4K] 等标签
            clean_title = re.sub(r'^\s*\[[^\]]*\]\s*', '', title_raw_after_comma).strip()
        else:
            clean_title = ""

        # 重建标准 EXTINF 行（保留 tvg-name、tvg-logo 等所有字段，只改 group-title 和标题）
        new_extinf = re.sub(r'group-title="[^"]*"', 'group-title="待分类"', full_line)  # 先占位
        new_extinf = new_extinf.split(",", 1)[0] + "," + clean_title

        if i + 1 < len(lines) and lines[i + 1].startswith("http"):
            url = lines[i + 1]
            channels.append({
                "extinf_raw": full_line,      # 原始完整行
                "tvg_name": tvg_name or clean_title,
                "title": clean_title,
                "url": url,
                "new_extinf_base": new_extinf   # 已经清理好标题的行（待填 group-title）
            })
            i += 2
            continue
    i += 1

print(f"成功解析 {len(channels)} 个频道，开始分类并强制设置 group-title...")

# 分组
groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

used = set()

# 1. 央视（靠 tvg-name 或标题识别）
for cctv_channels = []
for c in channels:
    if "唐河" in c["title"]: continue
    if "CCTV" in c["tvg_name"] or "CCTV" in c["title"]:
        cctv_channels.append(c)
        used.add(c["url"])

# 央视排序
def cctv_order(c):
    t = c["tvg_name"] or c["title"]
    if m := re.search(r'CCTV\s*(\d+)', t, re.I):
        return (0, int(m.group(1)))
    order = {"8K":90":90,"纪录":91,"戲曲":92,"戏曲":92,"第一剧场":93,"风云足球":94}
    for k,v in order.items():
        if k in t: return (0, v)
    return (1, t)

cctv_channels.sort(key=cctv_order)
groups["央视"] = cctv_channels

# 2. 卫视
for c in channels:
    if c["url"] in used: continue
    if "卫视" in c["title"] or "衛視" in c["title"]:
        groups["卫视"].append(c)
        used.add(c["url"])

# 3. 香港（凤凰前置）
phoenix = []
hk_other = []
for c in channels:
    if c["url"] in used: continue
    if any(x in c["title"] for x in ["凤凰","香港","無線","翡","翡翠","明珠","TVB","RTHK","ViuTV"]):
        if "凤凰" in c["title"]:
            phoenix.append(c)
        else:
            hk_other.append(c)
        used.add(c["url"])
groups["香港"] = phoenix + hk_other

# 4. 台灣
for c in channels:
    if c["url"] in used: continue
    if any(x in c["title"] for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS","中天"]):
        groups["台灣"].append(c)
        used.add(c["url"])

# 5. 省份
province_map = {
    "北京":["北京","BTV"],"上海":["上海","东方"],"广东":["广东","广州","深圳","珠江","南方"],
    "浙江":["浙江","江苏":["江苏","南京","苏州"],"湖南":["湖南","长沙"],"山东":["山东","齐鲁"],
    "四川":["四川","成都"],"陕西":["陕西","西安"],"湖北":["湖北","武汉"],"河南":["河南","郑州"],
    "福建":["福建","厦门"],"安徽":["安徽"],"江西":["江西"],"河北":["河北"],"黑龙江":["黑龙江"],
    "辽宁":["辽宁"],"广西":["广西"],"云南":["云南"],"重庆":["重庆"],"天津":["天津"]
}

for c in channels:
    if c["url"] in used: continue
    placed = False
    for p, ks in province_map.items():
        if any(k in c["title"] for k in ks):
            groups[p].append(c)
            used.add(c["url"])
            placed = True
            break
    if not placed:
        groups["其他省份"].append(c)

# 最终输出：严格两行结构，group-title 强制正确
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁",
         "广西","云南","重庆","天津","其他省份"]

for group_name in order:
    for c in groups[group_name]:
        # 强制写入你想要的 group-title
        final_extinf = c["new_extinf_base"].split('group-title="待分类"', 1)[0] + f'group-title="{group_name}",{c["title"]}'
        result.append(final_extinf)
        result.append(c["url"])

with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(result) + "\n")

total = (len(result) - 1) // 2
print(f"\n大功告成！已生成 tv.m3u，包含 {total} 个频道")
for g in order:
    if groups[g]:
        print(f"   {g:<6} → {len(groups[g]):>3} 个")
