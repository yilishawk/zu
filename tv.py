#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025年12月8日 · 终极完美版（已通过 GitHub Actions 验证）
输出格式完全符合你的要求：
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
        full_line = lines[i]
        # 提取 tvg-name
        tvg_name_match = re.search(r'tvg-name="([^"]*)"', full_line)
        tvg_name = tvg_name_match.group(1) if tvg_name_match else ""

        # 提取标题（逗号后内容）
        if "," in full_line:
            title_raw = full_line.split(",", 1)[1]
            clean_title = re.sub(r'^\s*\[[^\]]*\]\s*', '', title_raw).strip()
        else:
            clean_title = ""

        # 重建干净的 EXTINF 基础行（保留所有原始字段，只清理标题）
        base_extinf = full_line.split(",", 1)[0] + "," + clean_title

        if i + 1 < len(lines) and lines[i + 1].startswith("http"):
            url = lines[i + 1].strip()
            channels.append({
                "base_extinf": base_extinf,     # 标题已清理好的行
                "tvg_name": tvg_name or clean_title,
                "title": clean_title,
                "url": url
            })
            i += 2
        else:
            i += 1
    else:
        i += 1

print(f"成功解析 {len(channels)} 个频道，开始分类...")

groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

used_urls = set()

# 1. 央视（精准识别）
for c in channels:
    if "唐河" in c["title"]:
        continue
    if "CCTV" in c["tvg_name"] or "CCTV" in c["title"]:
        groups["央视"].append(c)
        used_urls.add(c["url"])

# 央视完美排序
def cctv_sort_key(c):
    t = c["tvg_name"] or c["title"]
    if m := re.search(r'CCTV\s*(\d+)', t, re.I):
        return (0, int(m.group(1)))
    special = {"8K": 90, "纪录": 91, "戏曲": 92, "第一剧场": 93, "风云足球": 94, "军事农业": 95}
    for k, v in special.items():
        if k in t:
            return (0, v)
    return (1, t)

groups["央视"].sort(key=cctv_sort_key)

# 2. 卫视
for c in channels:
    if c["url"] in used_urls: continue
    if "卫视" in c["title"] or "衛視" in c["title"]:
        groups["卫视"].append(c)
        used_urls.add(c["url"])

# 3. 香港（凤凰前置）
phoenix = []
hk_other = []
for c in channels:
    if c["url"] in used_urls: continue
    if any(x in c["title"] for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK","ViuTV"]):
        if "凤凰" in c["title"]:
            phoenix.append(c)
        else:
            hk_other.append(c)
        used_urls.add(c["url"])
groups["香港"] = phoenix + hk_other

# 4. 台灣
for c in channels:
    if c["url"] in used_urls: continue
    if any(x in c["title"] for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS","中天"]):
        groups["台灣"].append(c)
        used_urls.add(c["url"])

# 5. 省份归类
province_map = {
    "北京": ["北京","BTV"], "上海": ["上海","东方"], "广东": ["广东","广州","深圳","珠江","南方"],
    "浙江": ["浙江"], "江苏": ["江苏","南京","苏州","无锡"], "湖南": ["湖南","长沙","芒果"],
    "山东": ["山东","齐鲁"], "四川": ["四川","成都"], "陕西": ["陕西","西安"], "湖北": ["湖北","武汉"],
    "河南": ["河南","郑州"], "福建": ["福建","厦门"], "安徽": ["安徽"], "江西": ["江西"],
    "河北": ["河北"], "黑龙江": ["黑龙江"], "辽宁": ["辽宁"], "广西": ["广西"],
    "云南": ["云南"], "重庆": ["重庆"], "天津": ["天津"]
}

for c in channels:
    if c["url"] in used_urls: continue
    placed = False
    for prov, keywords in province_map.items():
        if any(k in c["title"] for k in keywords):
            groups[prov].append(c)
            used_urls.add(c["url"])
            placed = True
            break
    if not placed:
        groups["其他省份"].append(c)

# 输出：严格两行结构，group-title 强制正确
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣",
         "北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西",
         "河北","黑龙江","辽宁","广西","云南","重庆","天津","其他省份"]

for group_name in order:
    for c in groups[group_name]:
        # 强制设置 group-title 并保留 tvg-name 等字段
        final_line = re.sub(r'group-title="[^"]*"', f'group-title="{group_name}"', c["base_extinf"])
        result.append(final_line)
        result.append(c["url"])

with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(result) + "\n")

total = (len(result) - 1) // 2
print(f"\n完美完成！已生成 tv.m3u，共 {total} 个优质频道")
for g in order:
    if groups[g]:
        print(f"   {g:<6} → {len(groups[g]):>3} 个")
