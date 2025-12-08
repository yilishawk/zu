#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025 最终版：只保留央视/卫视/香港/台湾 + 大陆地方台按省份完美分组
源：https://freetv.fun/test_channels_banned_cn_new.m3u（已验证可用）
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

# 简繁转换表（修复版）
def ts(text):
    rep = {
        "臺": "台", "衛": "卫", "視": "视", "頻": "频", "廣": "广", "東": "东",
        "鳳": "凤", "凰": "凰", "資": "资", "訊": "讯", "綜": "综", "藝": "艺",
        "劇": "剧", "無線": "无线", "翡翠": "翡翠", "緯來": "纬来"
    }
    for a, b in rep.items():
        text = text.replace(a, b)
    return text.strip()

def clean_title(t):
    t = re.sub(r'\s*\([^)]*\)|[[^]]*\]|#\d+|backup|备用|备|h265|h264|4K|1080p|720p', '', t, flags=re.I)
    return ts(t).strip()

# 下载
print("正在下载直播源...")
content = curl_download(URL)
if not content:
    print("下载失败！")
    exit(1)
print(f"下载成功，{len(content)//1024} KB，开始解析...")

lines = content.splitlines()
channels = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith("#EXTINF:"):
        title_raw = line.split(",", 1)[-1] if "," in line else ""
        title = clean_title(title_raw)
        if i+1 < len(lines):
            url = lines[i+1].strip()
            if url.startswith("http") and "freetv.fun" in url:
                channels.append({"title": title, "url": url, "raw": title_raw})
        i += 1
    i += 1

print(f"解析到 {len(channels)} 个频道，开始分类...")

# 分组容器
groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

# 省份关键词
province_map = {
    "北京": ["北京","BTV"], "上海": ["上海","东方"], "广东": ["广东","广州","深圳","珠江","南方","翡翠"],
    "浙江": ["浙江","杭州"], "江苏": ["江苏","南京","苏州","无锡"], "湖南": ["湖南","长沙","芒果"],
    "山东": ["山东","齐鲁","济南"], "四川": ["四川","成都","康巴"], "陕西": ["陕西","西安"],
    "湖北": ["湖北","武汉","经视"], "河南": ["河南","郑州"], "福建": ["福建","厦门","海峡"],
    "安徽": ["安徽","合肥"], "江西": ["江西","南昌"], "河北": ["河北","石家庄"],
    "黑龙江": ["黑龙江","哈尔滨"], "辽宁": ["辽宁","沈阳","大连"], "广西": ["广西","南宁"],
    "云南": ["云南","昆明"], "重庆": ["重庆"], "天津": ["天津"]
}

def cctv_weight(t):
    m = re.search(r'CCTV.?(\d+)', t)
    if m: return int(m.group(1))
    order = {"8K":90, "纪录":91, "戏曲":92, "第一剧场":93, "风云足球":94, "军事":95, "农业":96}
    for k,v in order.items():
        if k in t: return v
    return 100 if "CCTV" in t else 999

used_titles = set()

# 1. 央视（权重排序）
cctv_list = [c for c in channels if c["title"].startswith("CCTV")]
cctv_list.sort(key=lambda x: cctv_weight(x["title"]))
groups["央视"] = cctv_list
for c in cctv_list: used_titles.add(c["title"])

# 2. 卫视
for c in channels:
    if "卫视" in c["title"] and c["title"] not in used_titles:
        groups["卫视"].append(c)
        used_titles.add(c["title"])

# 3. 香港（凤凰前置）
hk_list = [c for c in channels if any(x in c["title"] for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK","Viu"])]
phoenix = [c for c in hk_list if "凤凰" in c["title"]]
others_hk = [c for c in hk_list if c not in phoenix]
groups["香港"] = phoenix + others_hk
for c in groups["香港"]: used_titles.add(c["title"])

# 4. 台灣（新闻/综合/娱乐优先）
tw_list = [c for c in channels if any(x in c["title"] for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS","中天"])]
priority = [c for c in tw_list if any(k in c["title"] for k in ["新闻","綜合","综合","财经","电影","戏剧","娱乐"])]
others_tw = [c for c in tw_list if c not in priority]
groups["台灣"] = priority + others_tw
for c in groups["台灣"]: used_titles.add(c["title"])

# 5. 大陆地方台按省份归类
for c in channels:
    if c["title"] in used_titles:
        continue
    placed = False
    for prov, keys in province_map.items():
        if any(k in c["title"] for k in keys):
            groups[prov].append(c)
            used_titles.add(c["title"])
            placed = True
            break
    if not placed:
        # 再兜底一下常见省份
        if any(x in c["title"] for x in ["卫视","CCTV"]):
            continue
        groups["其他省份"].append(c)

# 输出 M3U
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣",
         "北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西",
         "河北","黑龙江","辽宁","广西","云南","重庆","天津","其他省份"]

for g in order:
    for ch in groups[g]:
        result.append(f'#EXTINF:-1 group-title="{g}",{ch["title"]}')
        result.append(ch["url"])

final_content = "\n".join(result) + "\n"
with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write(final_content)

total = sum(len(groups[g]) for g in order)
print(f"\n大功告成！生成 tv.m3u 成功，共 {total} 个精选频道")
for g in order:
    if groups[g]:
        print(f"   {g:<6} : {len(groups[g]):>3} 个")
