#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终稳定版：生成 tv.m3u
源地址：https://freetv.fun/test_channels_all_new.m3u
功能：
  - 央视（权重排序） → 卫视 → 香港（凤凰前置） → 台灣（新闻综合优先） → 各省份地方台
  - 完全去重、简繁转换、清理备用/备份标签
  - 即使某一天源里缺卫视也不会报错
"""

import re
import requests
from collections import defaultdict, OrderedDict

URL = "https://freetv.fun/test_channels_all_new.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BLACKLIST = {"https://stream1.freetv.fun/tang-he-yi-tao-1.m3u8"}

# 简繁快速转换
def ts(t):
    rep = {
        "臺": "台", "衛": "卫", "視": "视", "頻": "频", "廣": "广", "東": "东",
        "鳳": "凤", "凰": "凰", "資": "资", "訊": "讯", "綜": "综", "藝": "艺",
        "劇": "剧", "無線": "无线", "翡翠": "翡翠", "緯來": "纬来"
    }
    for a, b in rep.items():
        t = t.replace(a, b)
    return t.strip()

class LiveStreamCrawler:
    def __init__(self):
        self.rawContent = ""
        self.parsedData = defaultdict(list)    # group → list of channels
        self.finalGroups = OrderedDict()       # 最终输出用的有序组
        self.fetchData()
        self.parseM3UData()
        self.processCCTVChannels()
        self.processMainlandChina()     # 提取卫视
        self.processHongKong()
        self.processTaiwan()
        self.processProvinceFromMainland()
        self.outputM3U()

    def fetchData(self):
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        self.rawContent = r.text

    # 解析标准 m3u（兼容多种写法）
    def parseM3UData(self):
        lines = self.rawContent.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                # 取逗号后的标题
                title = line.split(",", 1)[-1].strip() if "," in line else ""
                # 提取 group-title（如果有）
                group_match = re.search(r'group-title="([^"]*)"', line)
                group = group_match.group(1) if group_match else "未分组"

                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and url not in BLACKLIST:
                        clean_title = self.cleanTitle(title)
                        self.parsedData[group].append({
                            "title": clean_title,
                            "original_title": title,
                            "url": url
                        })
                i += 1
            i += 1

    def cleanTitle(self, title):
        patterns = [
            r'\s*\(backup\)*', r'\s*\(h265\)*', r'\s*\(h264\)*',
            r'\s*\(备用\)*', r'\s*\(备\)*', r'\s*\[.*?\]', r'\s*#\d+'
        ]
        for p in patterns:
            title = re.sub(p, '', title, flags=re.I)
        return ts(title).strip()

    # 央视权重排序
    def getCCTVWeight(self, title):
        clean = self.cleanTitle(title)
        m = re.match(r'^CCTV[-\s]?(\d+)', clean, re.I)
        if m:
            return int(m.group(1))
        special = {
            "CCTV 8K": 100, "CCTV-Documentary": 101, "CCTV-戲曲": 102,
            "CCTV第一劇場": 103, "CCTV風雲足球": 104, "CCTV第一剧场": 103, "CCTV风云足球": 104,
        }
        for k, v in special.items():
            if clean.startswith(k):
                return v
        if clean.startswith("CCTV"):
            return 999
        # 其他 CCTV 放最后
        return 1000

    # 1. 央视
    def processCCTVChannels(self):
        allCCTV = {}
        for channels in self.parsedData.values():
            for ch in channels:
                clean = self.cleanTitle(ch["original_title"])
                if clean.startswith("CCTV"):
                    key = f"{clean}|{ch['url']}"
                    if key not in allCCTV:
                        w = self.getCCTVWeight(ch["original_title"])
                        allCCTV[key] = {"title": clean, "url": ch["url"], "weight": w}
        cctv_list = sorted(allCCTV.values(), key=lambda x: (x["weight"], x["title"]))
        if cctv_list:
            self.finalGroups["央视"] = [ {"title": c["title"], "url": c["url"]} for c in cctv_list ]

    # 2. 卫视
    def processMainlandChina(self):
        mainland_groups = [g for g in self.parsedData if any(x in g for x in ["大陆", "中國", "内地"])]
        satellite = []
        cctv_titles = {c["title"] for c in self.finalGroups.get("央视", [])}

        for g in mainland_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                if clean in cctv_titles:
                    continue
                if "卫视" in clean or "衛視" in clean:
                    satellite.append({"title": clean, "url": ch["url"]})

        # 关键：即使一个卫视都没抓到也要占位，防止后面 KeyError
        self.finalGroups["卫视"] = satellite if satellite else []

    # 3. 香港（凤凰前置）
    def processHongKong(self):
        hk_groups = [g for g in self.parsedData if any(x in g for x in ["香港", "HK", "港"])]
        phoenix = []
        others = []
        for g in hk_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                item = {"title": clean, "url": ch["url"]}
                if any(x in clean for x in ["鳳凰", "凤凰"]):
                    phoenix.append(item)
                else:
                    others.append(item)
        final = phoenix + others
        if final:
            self.finalGroups["香港"] = final

    # 4. 台灣（新闻/综合/娱乐优先）
    def processTaiwan(self):
        tw_groups = [g for g in self.parsedData if any(x in g for x in ["台灣", "台湾", "台"])]
        priority = []
        others = []
        for g in tw_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                item = {"title": clean, "url": ch["url"]}
                if any(k in clean for k in ["新闻", "綜合", "综合", "娛樂", "娱乐"]):
                    priority.append(item)
                else:
                    others.append(item)
        final = priority + others
        if final:
            self.finalGroups["台灣"] = final

    # 5. 剩余大陆地方台 → 按省份归类
    def processProvinceFromMainland(self):
        mainland_groups = [g for g in self.parsedData if any(x in g for x in ["大陆", "中國", "内地"])]
        used_titles = {c["title"] for g in ["央视", "卫视"] for c in self.finalGroups.get(g, [])}

        province_map = {
            "北京": ["北京"], "上海": ["上海"], "重庆": ["重庆"], "天津": ["天津"],
            "广东": ["广东", "廣東", "广州", "廣州", "深圳", "东莞", "東莞", "佛山", "珠海", "惠州", "中山", "江门", "汕头", "湛江"],
            "浙江": ["浙江", "杭州", "宁波", "寧波", "温州", "溫州", "嘉兴", "绍兴", "金华", "台州"],
            "江苏": ["江苏", "江蘇", "南京", "苏州", "蘇州", "无锡", "無錫", "常州", "南通", "扬州", "镇江"],
            "山东": ["山东", "山東", "济南", "濟南", "青岛", "青島", "烟台", "潍坊"],
            "四川": ["四川", "成都", "绵阳", "德阳", "南充"],
            "陕西": ["陕西", "陝西", "西安", "咸阳", "宝鸡"],
            "湖北": ["湖北", "武汉", "武漢", "宜昌", "襄阳"],
            "湖南": ["湖南", "长沙", "長沙", "株洲", "湘潭", "岳阳"],
            "河南": ["河南", "郑州", "鄭州", "洛阳"],
            "福建": ["福建", "福州", "厦门", "廈門", "泉州"],
            "安徽": ["安徽", "合肥", "芜湖"],
            "江西": ["江西", "南昌", "赣州"],
            "河北": ["河北", "石家庄", "唐山"],
            "黑龙江": ["黑龙江", "黑龍江", "哈尔滨", "哈爾濱"],
            "辽宁": ["辽宁", "遼寧", "沈阳", "瀋陽", "大连"],
            "广西": ["广西", "廣西", "南宁", "南寧"],
            "云南": ["云南", "雲南", "昆明"],
        }

        province_groups = defaultdict(list)
        for g in mainland_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                if clean in used_titles or clean.startswith("CCTV") or "卫视" in clean or "衛視" in clean:
                    continue
                found = False
                for prov, keys in province_map.items():
                    if any(k in clean for k in keys):
                        province_groups[prov].append({"title": clean, "url": ch["url"]})
                        found = True
                        break
                if not found:
                    province_groups["其他省份"].append({"title": clean, "url": ch["url"]})

        order = ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]
        for p in order:
            if province_groups[p]:
                self.finalGroups[p] = province_groups[p]
        for p in sorted(province_groups):
            if p not in order:
                self.finalGroups[p] = province_groups[p]

    # 输出标准 M3U
    def outputM3U(self):
        lines = ['#EXTM3U']
        main_order = ["央视", "卫视", "香港", "台灣"]
        province_order = ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]

        # 主组
        for g in main_order:
            for ch in self.finalGroups.get(g, []):
                lines.append(f'#EXTINF:-1 group-title="{g}",{ch["title"]}')
                lines.append(ch["url"])

        # 省份组
        for p in province_order:
            for ch in self.finalGroups.get(p, []):
                lines.append(f'#EXTINF:-1 group-title="{p}",{ch["title"]}')
                lines.append(ch["url"])

        # 其他组（包括“其他省份”等）
        for g in self.finalGroups:
            if g not in main_order and g not in province_order:
                for ch in self.finalGroups[g]:
                    lines.append(f'#EXTINF:-1 group-title="{g}",{ch["title"]}')
                    lines.append(ch["url"])

        result = "\n".join(lines) + "\n"

        print("成功生成 tv.m3u，频道总数：", len(lines)//2 - 1)
        with open("tv.m3u", "w", encoding="utf-8") as f:
            f.write(result)

if __name__ == "__main__":
    LiveStreamCrawler()
