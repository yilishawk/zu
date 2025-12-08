#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极完美版（2025-12）
- 源：https://freetv.fun/test_channels_banned_cn_new.m3u
- 输出格式和源 100% 一样（完整保留 tvg-name、tvg-logo、group-title 等所有字段）
- 仅删除标题开头的 [BD] [HD] [4K] [SD] 等标签
- 分组顺序严格按照你最初要求：
  央视 → 卫视 → 香港 → 台灣 → 北京 → 上海 → 广东 → 浙江 → 江苏 → 湖南 → 山东 → 四川 → 陕西 → 湖北 → 河南 → 福建 → 安徽 → 江西 → 河北 → 黑龙江 → 辽宁 → 广西 → 云南 → 重庆 → 天津 → 其他省份
"""

import re
import subprocess

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"

def download():
    cmd = [
        "curl", "-fsSL",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Referer: https://freetv.fun/",
        URL
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""

print("正在下载直播源...")
raw_m3u = download()
if not raw_m3u:
    print("下载失败")
    exit(1)
print(f"下载成功，开始解析 {raw_m3u.count('#EXTINF:')} 个条目...")

# 解析出所有频道，保留原始 EXTINF 行
channels = []
lines = raw_m3u.splitlines()
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith("#EXTINF:-1"):
        orig_extinf = line
        # 提取标题（逗号后全部内容）
        if "," in line:
            title_part = line.split(",", 1)[1]
            # 只去掉开头的 [xx] 标签，保留后面所有内容
            clean_title = re.sub(r'^\s*\[[^\]]*\]\s*', '', title_part).strip()
            # 重新拼成新的 EXTINF 行（保留 tvg-name、tvg-logo 等所有原始字段）
            new_extinf = orig_extinf.split(",", 1)[0] + "," + clean_title
        else:
            new_extinf = orig_extinf

        if i + 1 < len(lines):
            url = lines[i + 1].strip()
            channels.append({
                "extinf": new_extinf,
                "url": url,
                "title": clean_title if "," in line else ""
            })
        i += 1
    i += 1

print(f"解析完成，共 {len(channels)} 个频道，开始分类...")

# 分组容器（顺序严格固定）
groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

used_urls = set()

# 省份关键词表
province_map = {
    "北京": ["北京","BTV"],"上海": ["上海","东方"],"广东": ["广东","广州","深圳","珠江","南方"],
    "浙江": ["浙江","杭州"],"江苏": ["江苏","南京","苏州","无锡"],"湖南": ["湖南","长沙","芒果"],
    "山东": ["山东","齐鲁","济南"],"四川": ["四川","成都","康巴"],"陕西": ["陕西","西安"],
    "湖北": ["湖北","武汉","经视"],"河南": ["河南","郑州"],"福建": ["福建","厦门","海峡"],
    "安徽": ["安徽","合肥"],"江西": ["江西","南昌"],"河北": ["河北","石家庄"],
    "黑龙江": ["黑龙江","哈尔滨"],"辽宁": ["辽宁","沈阳","大连"],"广西": ["广西","南宁"],
    "云南": ["云南","昆明"],"重庆": ["重庆"],"天津": ["天津"]
}

# 1. 央视（双保险：tvg-name 含 CCTV 或 标题含 CCTV，且排除“唐河”这种假的）
for ch in channels:
    if "唐河" in ch["title"]: 
        continue
    if re.search(r'CCTV[\d\- ]|CCTV', ch["extinf"]) or re.search(r'CCTV', ch["title"]):
        groups["央视"].append(ch)
        used_urls.add(ch["url"])

# 央视排序（CCTV1 → CCTV17 → 8K → 纪录 → 戏曲 → 第一剧场 → 风云足球）
def cctv_key(ch):
    t = ch["title"]
    m = re.search(r'CCTV\s*(\d+)', t)
    if m: return (0, int(m.group(1)))
    order = {"8K":90,"纪录":91,"戏曲":92,"第一剧场":93,"风云足球":94,"军事农业":95}
    for k,v in order.items():
        if k in t: return (0, v)
    return (1, t)
groups["央视"].sort(key=cctv_key)

# 2. 卫视
for ch in channels:
    if ch["url"] in used_urls: continue
    if "卫视" in ch["title"] or "衛視" in ch["title"]:
        groups["卫视"].append(ch)
        used_urls.add(ch["url"])

# 3. 香港（凤凰排最前）
phoenix = []
hk_others = []
for ch in channels:
    if ch["url"] in used_urls: continue
    if any(x in ch["title"] for x in ["凤凰","香港","無線","翡翠","明珠","TVB","RTHK","ViuTV"]):
        if "凤凰" in ch["title"]:
            phoenix.append(ch)
        else:
            hk_others.append(ch)
        used_urls.add(ch["url"])
groups["香港"] = phoenix + hk_others

# 4. 台灣（新闻/综合优先）
tw_priority = []
tw_others = []
for ch in channels:
    if ch["url"] in used_urls: continue
    if any(x in ch["title"] for x in ["台","台灣","中视","华视","民视","公视","大爱","三立","东森","纬来","TVBS","中天"]):
        if any(k in ch["title"] for k in ["新闻","新聞","綜合","综合","财经","电影","戏剧","娱乐"]):
            tw_priority.append(ch)
        else:
            tw_others.append(ch)
        used_urls.add(ch["url"])
groups["台灣"] = tw_priority + tw_others

# 5. 大陆地方台按省份归类
for ch in channels:
    if ch["url"] in used_urls: continue
    placed = False
    for prov, keys in province_map.items():
        if any(k in ch["title"] for k in keys):
            groups[prov].append(ch)
            used_urls.add(ch["url"])
            placed = True
            break
    if not placed:
        groups["其他省份"].append(ch)

# 输出（严格顺序）
result = ["#EXTM3U"]
order = ["央视","卫视","香港","台灣",
         "北京","上海","广东","浙江","江苏","湖南","山东",
         "四川","陕西","湖北","河南","福建","安徽","江西",
         "河北","黑龙江","辽宁","广西","云南","重庆","天津","其他省份"]

for g in order:
    for ch in groups[g]:
        result.append(ch["extinf"])
        result.append(ch["url"])

with open("tv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(result) + "\n")

total = (len(result) - 1) // 2
print(f"\n成功！已生成 tv.m3u，共 {total} 个优质频道")
for g in order:
    cnt = len(groups[g])
    if cnt:
        print(f"   {g:<6} → {cnt:>3} 个")
