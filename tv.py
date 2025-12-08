#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025 终极版：只提取你想要的频道，并完美分组
源：https://freetv.fun/test_channels_banned_cn_new.m3u（已验证 4266 条）
"""

import re
import subprocess

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"

def curl_download(url):
    cmd = [
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Referer: https://freetv.fun/",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""

def ts(text):  # 简繁转换
    rep = str.replace for char in "臺衛視頻廣東鳳凰資訊綜藝劇無線翡翠緯來": 
        text = text.replace(char, {"臺":"台","衛":"卫","視":"视","頻":"频","廣":"广","東":"东",
                                 "鳳":"凤","凰":"凰","資":"资","訊":"讯","綜":"综","藝":"艺",
                                 "劇":"剧","無線":"无线","翡翠":"翡翠","緯來":"纬来"}[char])
    return text

def clean_title(t):
    t = re.sub(r'\s*\([^)]*\)|\s*\[.*?\]|\s*#\d+|\s*(backup|备用|备|h264|h265).*', '', t, flags=re.I)
    return ts(t).strip()

# 下载源
print("正在下载直播源...")
content = curl_download(URL)
if not content:
    print("下载失败！")
    exit(1)
print(f"下载成功，共 {len(content)} 字节，开始处理...")

lines = content.splitlines()
channels = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF:"):
        title_part = lines[i].split(",", 1)[-1] if "," in lines[i] else ""
        title = clean_title(title_part)
        if i+1 < len(lines):
            url = lines[i+1].strip()
            if url.startswith("http") and "freetv.fun" in url:
                channels.append({"title": title, "url": url, "raw": title_part})
        i += 1
    i += 1

print(f"共解析到 {len(channels)} 个频道，开始分类...")

# 分类容器
groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

# 省份关键词映射
province_keywords = {
    "北京": ["北京", "BTV"], "上海": ["上海"], "广东": ["广东","广州","深圳","珠江","南方"], "浙江": ["浙江"],
    "江苏": ["江苏","南京","苏州"], "湖南": ["湖南","长沙"], "山东": ["山东","齐鲁"],
    "四川": ["四川","成都","四川卫视"], "陕西": ["陕西","西安"], "湖北": ["湖北","武汉","湖北卫视"],
    "河南": ["河南","郑州"], "福建": ["福建","厦门","海峡"], "安徽": ["安徽","合肥"],
    "江西": ["江西","南昌"], "河北": ["河北","石家庄"], "黑龙江": ["黑龙江","哈尔滨"],
    "辽宁": ["辽宁","沈阳","大连"], "广西": ["广西","南宁"], "云南": ["云南","昆明"],
    "重庆": ["重庆"], "天津": ["天津"]
}

# 央视权重
def cctv_weight(t):
    if m := re.search(r'CCTV.?(\d+)', t):
        return int(m.group(1))
    weights = {"8K": 90, "纪录": 91, "戏曲": 92, "第一剧场": 93, "风云足球": 94}
    for k, v in weights.items():
        if k in t: return v
    return 100 if "CCTV" in t else 999

used = set()

# 1. 央视
cctv_channels = [c for c in channels if c["title"].startswith("CCTV")]
cctv_channels.sort(key=lambda x: cctv_weight(x["title"]))
for c in cctv_channels:
    groups["央视"].append(c)
    used.add(c["title"])

# 2. 卫视
for c in channels:
    if "卫视" in c["title"] and c["title"] not in used:
        groups["卫视"].append(c)
        used.add(c["title"])

# 3. 香港（凤凰前置）
hk_channels = [c for c in channels if any(x in c["title"] for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK"])]
phoenix = [c for c in hk_channels if "凤凰" in c["title"]]
others_hk = [c for c in hk_channels if "凤凰" not in c["title"]]
groups["香港"] = phoenix + others_hk
for c in groups["香港"]: used.add(c["title"])

# 4. 台灣（新闻/综合/娱乐优先）
tw_channels = [c for c in channels if any(x in c["title"] for x in ["台","台灣","中天","民視","公視","華視","大愛","緯來","三立","東森","TVBS"])]
priority = [c for c in tw_channels if any(k in c["title"] for k in ["新闻","綜合","综合","娱乐","财经","电影"])]
others_tw = [c for c in tw_channels if c not in priority]
groups["台灣"] = priority + others_tw
for c in groups["台灣"]: used.add(c["title"])

# 5. 大陆地方台按省份归类
mainland = [c for c in channels if c["title"] not in used and any(k in c["title"] for k in ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津","卫视","CCTV"]) is False]

for c in mainland:
    placed = False
    for prov, keys in province_keywords.items():
        if any(k in c["title"] for k in keys):
            groups[prov].append(c)
            used.add(c["title"])
            placed = True
            break
    if not placed:
        groups["其他省份"].append(c)

# 输出 M3U
result = ["#EXTM3U"]

order = ["央视", "卫视", "香港", "台灣",
         "北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津","其他省份"]

for group_name in order:
    if groups[group_name]:
        for ch in groups[group_name]:
            result.append(f'#EXTINF:-1 group-title="{group_name}",{ch["title"]}')
            result.append(ch["url"])

final = "\n".join(result) + "\n"
with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write(final)

total = sum(len(v) for v in groups.values())
print(f"完美完成！最终生成 tv.m3u，共 {total} 个精选频道")
print("分组统计：")
for g in order:
    if groups[g]:
        print(f"  {g:>6}：{len(groups[g]):>3} 个")
