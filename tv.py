#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极完美版：保留原始 #EXTINF 完整字段，只去掉 [BD][HD] 前缀
精准识别央视（靠 tvg-name + 标题双保险）
完美分组：央视 → 卫视 → 香港 → 台灣 → 各省份
"""

import re
import subprocess

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"

def curl_download(url):
    cmd = [
        "curl", "-fsSL",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Referer: https://freetv.fun/",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""

# 简繁转换（只转换必要字符）
def ts(text):
    rep = {"臺":"台","衛":"卫","視":"视","頻":"频","廣":"广","東":"东",
           "鳳":"凤","凰":"凰","資":"资","訊":"讯","綜":"综","藝":"艺","劇":"剧"}
    for a,b in rep.items():
        text = text.replace(a, b)
    return text

print("正在下载直播源...")
raw = curl_download(URL)
if not raw:
    print("下载失败")
    exit(1)

lines = raw.splitlines()
print(f"下载成功，共 {len(lines)} 行，开始解析...")

# 存储所有频道（保留原始 EXTINF 行）
channels = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF:-1"):
        extinf_line = lines[i]
        if i+1 < len(lines) and lines[i+1].startswith("http"):
            url = lines[i+1]
            # 提取标题（逗号后所有内容）
            title_part = extinf_line.split(",", 1)[1] if "," in extinf_line else ""
            # 去掉开头的 [BD] [HD] [4K] [SD] 等标签，但保留后面内容
            clean_title = re.sub(r'^\s*\[[^\]]*\]\s*', '', title_part).strip()
            final_extinf = extinf_line.split(",", 1)[0] + "," + clean_title
            channels.append({"extinf": final_extinf, "url": url, "title": clean_title})
        i += 1
    i += 1

print(f"解析到 {len(channels)} 个频道，开始分类...")

# 分组
groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京":[],"上海":[],"广东":[],"浙江":[],"江苏":[],"湖南":[],"山东":[],
    "四川":[],"陕西":[],"湖北":[],"河南":[],"福建":[],"安徽":[],"江西":[],
    "河北":[],"黑龙江":[],"辽宁":[],"广西":[],"云南":[],"重庆":[],"天津":[], "其他省份":[]
}

# 省份关键词
provinces = {
    "北京":["北京","BTV"],"上海":["上海","东方"],"广东":["广东","广州","深圳","珠江","南方","翡翠"],
    "浙江":["浙江","杭州"],"江苏":["江苏","南京","苏州","无锡"],"湖南":["湖南","长沙","芒果"],
    "山东":["山东","齐鲁","济南"],"四川":["四川","成都"],"陕西":["陕西","西安"],
    "湖北":["湖北","武汉","经视"],"河南":["河南","郑州"],"福建":["福建","厦门","海峡"],
    "安徽":["安徽","合肥"],"江西":["江西","南昌"],"河北":["河北","石家庄"],
    "黑龙江":["黑龙江","哈尔滨"],"辽宁":["辽宁","沈阳","大连"],"广西":["广西","南宁"],
    "云南":["云南","昆明"],"重庆":["重庆"],"天津":["天津"]
}

used = set()

# 1. 央视识别（双保险：tvg-name 含 CCTV 或 标题含 CCTV）
cctv_list = []
for c in channels:
    if ("CCTV" in c["extinf"] or "CCTV" in c["title"]) and "唐河" not in c["title"]:
        cctv_list.append(c)

# 央视排序权重
def cctv_sort_key(ch):
    t = ch["title"]
    if m := re.search(r'CCTV.?(\d+)', t):
        return (0, int(m.group(1)))
    order = {"8K":90,"纪录":91,"戲曲":92,"戏曲":92,"第一剧场":93,"风云足球":94,"军事农业":95}
    for k,v in order.items():
        if k in t: return (0, v)
    return (1, t)

cctv_list.sort(key=cctv_sort_key)
groups["央视"] = cctv_list
for c in cctv_list: used.add(c["url"])

# 2. 卫视
for c in channels:
    if c["url"] in used: continue
    if "卫视" in c["title"] or "衛視" in c["title"]:
        groups["卫视"].append(c)
        used.add(c["url"])

# 3. 香港（凤凰前置）
hk = []
phoenix = []
for c in channels:
    if c["url"] in used: continue
    if any(x in c["title"] for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK","Viu"]):
        if "凤凰" in c["title"]:
            phoenix.append(c)
        else:
            hk.append(c)
        used.add(c["url"])
groups["香港"] = phoenix + hk

# 4. 台灣（新闻综合优先）
tw_priority = []
tw_others = []
for c in channels:
    if c["url"] in used: continue
    if any(x in c["title"] for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS"]):
        if any(k in c["title"] for k in ["新闻","綜合","综合","财经","电影","戏剧"]):
            tw_priority.append(c)
        else:
            tw_others.append(c)
        used.add(c["url"])
groups["台灣"] = tw_priority + tw_others

# 5. 大陆地方台按省份归类
for c in channels:
    if c["url"] in used: continue
    placed = False
    for prov, keys in provinces.items():
        if any(k in c["title"] for k in keys):
            groups[prov].append(c)
            used.add(c["url"])
            placed = True
            break
    if not placed:
        groups["其他省份"].append(c)

# 输出最终 M3U
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣",
         "北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西",
         "河北","黑龙江","辽宁","广西","云南","重庆","天津","其他省份"]

for name in order:
    for ch in groups[name]:
        result.append(ch["extinf"])
        result.append(ch["url"])

with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(result) + "\n")

total = len(result) // 2 - 1
print(f"\n成功！生成 tv.m3u 共 {total} 个频道（保留原始 tvg-name 等信息）")
for name in order:
    if groups[name]:
        print(f"  {name:<6} : {len(groups[name]):>3} 个")
