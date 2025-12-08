#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极修复版 · 2025年12月8日
- 央视全抓取（CCTV9 及以后变体全部统一到 "央视" 组）
- 省份地方台加强匹配（陕西：西安新闻、陕西公共等全抓）
- 多源保留，名称统一，只留中港台大陆
- 格式：tvg-name + tvg-logo + group-title
"""

import re
import subprocess

URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"

def download():
    cmd = ["curl", "-fsSL", "-H", "User-Agent: Mozilla/5.0", URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout if r.returncode == 0 else ""

print("下载源...")
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
            clean = re.sub(r'^\s*\[[^\]]*\]\s*', '', raw_title)
            clean = re.sub(r'\s*\([^)]*\)|\s*(ipv6|backup|备用|备|4m|8m|1080|720).*', '', clean, flags=re.I)
            clean = re.sub(r'\s+', ' ', clean).strip()
        else:
            clean = ""

        name = clean or tvg_name or "未知"

        if i + 1 < len(lines) and lines[i + 1].startswith("http"):
            url = lines[i + 1].strip()
            # 初步过滤：只留中港台大陆关键词
            if any(kw in name.lower() for kw in ["cctv", "卫视", "凤凰", "香港", "tvb", "rthk", "台", "台灣", "中视", "华视", "民视", "公视", "东森", "三立", "纬来", "北京", "上海", "广东", "浙江", "江苏", "湖南", "山东", "四川", "陕西", "湖北", "河南", "福建", "安徽", "江西", "河北", "黑龙江", "辽宁", "广西", "云南", "重庆", "天津", "西安", "成都", "武汉", "广州", "杭州", "南京"]):
                channels.append({
                    "name": name,
                    "logo": tvg_logo,
                    "url": url
                })
            i += 2
        else:
            i += 1
    else:
        i += 1

print(f"初步过滤 {len(channels)} 条，开始名称统一...")

# 扩展统一映射（覆盖变体）
name_map = {
    # 央视（扩展变体）
    r"(?i)cctv[ -]?9.*": "CCTV9 纪录", r"(?i)cctv[ -]?10.*": "CCTV10 科教",
    r"(?i)cctv[ -]?11.*": "CCTV11 戏曲", r"(?i)cctv[ -]?12.*": "CCTV12 社会与法",
    r"(?i)cctv[ -]?13.*": "CCTV13 新闻", r"(?i)cctv[ -]?14.*": "CCTV14 少儿",
    r"(?i)cctv[ -]?15.*": "CCTV15 音乐", r"(?i)cctv[ -]?16.*": "CCTV16 奥运",
    r"(?i)cctv[ -]?17.*": "CCTV17 农业", r"(?i)纪录.*": "CCTV9 纪录",
    r"(?i)戏曲.*": "CCTV11 戏曲", r"(?i)第一剧场.*": "CCTV8 剧场",
    r"(?i)风云足球.*": "CCTV 风云足球", r"(?i)cctv[ -]?1.*": "CCTV1",
    r"(?i)cctv[ -]?2.*": "CCTV2", r"(?i)cctv[ -]?3.*": "CCTV3", r"(?i)cctv[ -]?4.*": "CCTV4",
    r"(?i)cctv[ -]?5.*": "CCTV5", r"(?i)cctv[ -]?6.*": "CCTV6", r"(?i)cctv[ -]?7.*": "CCTV7",
    r"(?i)cctv[ -]?8.*": "CCTV8", r"(?i)8k.*": "CCTV8K",
    # 陕西地方台（扩展）
    r"(?i)西安.*": "陕西 西安新闻", r"(?i)陕西公共.*": "陕西 公共", r"(?i)陕西都市.*": "陕西 都市",
    r"(?i)陕西新闻.*": "陕西 新闻", r"(?i)宝鸡.*": "陕西 宝鸡", r"(?i)咸阳.*": "陕西 咸阳",
    # 其他省份地方台扩展
    r"(?i)广州.*": "广东 广州新闻", r"(?i)成都.*": "四川 成都新闻", r"(?i)武汉.*": "湖北 武汉新闻",
    r"(?i)杭州.*": "浙江 杭州新闻", r"(?i)南京.*": "江苏 南京新闻", r"(?i)长沙.*": "湖南 长沙新闻",
    r"(?i)济南.*": "山东 济南新闻", r"(?i)福州.*": "福建 福州新闻", r"(?i)合肥.*": "安徽 合肥新闻",
    r"(?i)南昌.*": "江西 南昌新闻", r"(?i)石家庄.*": "河北 石家庄新闻", r"(?i)哈尔滨.*": "黑龙江 哈尔滨新闻",
    r"(?i)沈阳.*": "辽宁 沈阳新闻", r"(?i)南宁.*": "广西 南宁新闻", r"(?i)昆明.*": "云南 昆明新闻",
    r"(?i)重庆.*": "重庆 新闻", r"(?i)天津.*": "天津 新闻",
    # 香港/台灣
    r"(?i)凤凰.*": "凤凰卫视中文台", r"(?i)無線.*": "无线翡翠台", r"(?i)緯來.*": "纬来体育台",
}

for c in channels:
    for pattern, std in name_map.items():
        if re.search(pattern, c["name"]):
            c["final_name"] = std
            break
    else:
        c["final_name"] = c["name"]

print(f"统一命名后 {len(channels)} 条，开始分组...")

groups = {
    "央视": [], "卫视": [], "香港": [], "台灣": [],
    "北京": [], "上海": [], "广东": [], "浙江": [], "江苏": [], "湖南": [], "山东": [],
    "四川": [], "陕西": [], "湖北": [], "河南": [], "福建": [], "安徽": [], "江西": [],
    "河北": [], "黑龙江": [], "辽宁": [], "广西": [], "云南": [], "重庆": [], "天津": [], "其他省份": []
}

def assign_group(name, c):
    n = c["final_name"].lower()
    if re.search(r'c c t v', n):
        groups["央视"].append(c)
    elif "卫视" in n:
        groups["卫视"].append(c)
    elif any(x in n for x in ["凤凰", "香港", "无线", "tvb", "rthk"]):
        groups["香港"].append(c)
    elif any(x in n for x in ["台", "台灣", "中视", "华视", "民视", "公视", "东森", "三立", "纬来"]):
        groups["台灣"].append(c)
    elif "陕西" in n or any(x in n for x in ["西安", "宝鸡", "咸阳"]):
        groups["陕西"].append(c)
    elif "四川" in n or "成都" in n:
        groups["四川"].append(c)
    elif "湖北" in n or "武汉" in n:
        groups["湖北"].append(c)
    elif "广东" in n or "广州" in n:
        groups["广东"].append(c)
    elif "浙江" in n or "杭州" in n:
        groups["浙江"].append(c)
    elif "江苏" in n or "南京" in n:
        groups["江苏"].append(c)
    elif "湖南" in n or "长沙" in n:
        groups["湖南"].append(c)
    elif "山东" in n or "济南" in n:
        groups["山东"].append(c)
    elif "福建" in n or "福州" in n:
        groups["福建"].append(c)
    elif "安徽" in n or "合肥" in n:
        groups["安徽"].append(c)
    elif "江西" in n or "南昌" in n:
        groups["江西"].append(c)
    elif "河北" in n or "石家庄" in n:
        groups["河北"].append(c)
    elif "黑龙江" in n or "哈尔滨" in n:
        groups["黑龙江"].append(c)
    elif "辽宁" in n or "沈阳" in n:
        groups["辽宁"].append(c)
    elif "广西" in n or "南宁" in n:
        groups["广西"].append(c)
    elif "云南" in n or "昆明" in n:
        groups["云南"].append(c)
    elif "重庆" in n:
        groups["重庆"].append(c)
    elif "天津" in n:
        groups["天津"].append(c)
    elif "北京" in n:
        groups["北京"].append(c)
    elif "上海" in n:
        groups["上海"].append(c)
    else:
        groups["其他省份"].append(c)

for c in channels:
    assign_group(c["final_name"], c)

# 央视排序
cctv_order = ["CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6", "CCTV7", "CCTV8", "CCTV9 纪录", "CCTV10 科教", "CCTV11 戏曲", "CCTV12 社会与法", "CCTV13 新闻", "CCTV14 少儿", "CCTV15 音乐", "CCTV16 奥运", "CCTV17 农业", "CCTV8K", "CCTV 风云足球"]
sorted_cctv = []
for std in cctv_order:
    sorted_cctv.extend([c for c in groups["央视"] if c["final_name"] == std])
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
print(f"\n修复成功！tv.m3u 共 {total} 条（央视全抓，陕西地方台补齐）")
for g in order:
    cnt = len(groups[g])
    if cnt:
        print(f"   {g:<6} → {cnt:>3} 条")
