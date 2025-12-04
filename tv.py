#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极完整版 —— 100% 忠实还原原始 PHP 经典逻辑（包含所有排序规则）
"""

import re
import requests
from collections import defaultdict, OrderedDict
from opencc import OpenCC
t2s = OpenCC('t2s')  # 繁→简

URL = "https://freetv.fun/test_channels_new.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BLACKLIST = {"https://stream1.freetv.fun/tang-he-yi-tao-1.m3u8"}

# 省份关键词（繁简全覆盖）
PROVINCE_KEYWORDS = {
    "北京": ["北京"], "上海": ["上海"], "重庆": ["重庆"], "天津": ["天津"],
    "广东": ["广东", "廣東", "广州", "廣州", "深圳", "东莞", "東莞", "佛山", "珠海", "惠州", "中山", "江门", "汕头", "湛江", "茂名", "肇庆", "揭阳", "潮州", "汕尾"],
    "浙江": ["浙江", "杭州", "宁波", "寧波", "温州", "溫州", "嘉兴", "紹興", "金华", "台州"],
    "江苏": ["江苏", "江蘇", "南京", "苏州", "蘇州", "无锡", "無錫", "常州", "南通", "扬州", "鎮江", "泰州", "盐城"],
    "山东": ["山东", "山東", "济南", "濟南", "青岛", "青島", "烟台", "濰坊", "淄博", "济宁"],
    "四川": ["四川", "成都", "绵阳", "綿陽", "德阳", "南充", "乐山"],
    "陕西": ["陕西", "陝西", "西安", "咸阳", "寶雞", "渭南"],
    "湖北": ["湖北", "武汉", "武漢", "宜昌", "襄阳", "荊州"],
    "湖南": ["湖南", "长沙", "長沙", "株洲", "湘潭", "岳阳", "常德", "衡阳"],
    "河南": ["河南", "郑州", "鄭州", "洛阳", "開封", "新乡"],
    "福建": ["福建", "福州", "厦门", "廈門", "泉州", "漳州"],
    "安徽": ["安徽", "合肥", "芜湖", "馬鞍山"],
    "江西": ["江西", "南昌", "赣州", "九江", "上饒"],
    "河北": ["河北", "石家庄", "唐山", "邯鄲", "保定"],
    "黑龙江": ["黑龙江", "黑龍江", "哈尔滨", "哈爾濱", "齐齐哈尔", "大慶"],
    "辽宁": ["辽宁", "遼寧", "沈阳", "瀋陽", "大连"],
    "广西": ["广西", "廣西", "南宁", "南寧", "柳州", "桂林"],
    "云南": ["云南", "雲南", "昆明", "大理"],
}
PROVINCE_ORDER = ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]


class LiveStreamCrawler:
    def __init__(self):
        self.raw = ""
        self.parsed = defaultdict(list)
        self.final = OrderedDict()
        self.used = set()  # 已使用的 clean_title（去重用）

        self.fetch()
        self.parse()
        self.process()
        self.output()

    def fetch(self):
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        self.raw = r.text

    def clean(self, t):
        cleaned = re.sub(r'[\(（【\［].*?[\)）】\］]|\s*[\(#]?\d*|backup|備用|备[用\d]*|HD|ＨＤ', '', t, flags=re.I)
        return t2s.convert(cleaned).strip()

    def parse(self):
        group = ""
        for line in self.raw.splitlines():
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                group = line.strip()
                self.parsed[group] = []
                continue
            if "," not in line: continue
            title, url = [x.strip() for x in line.split(",", 1)]
            if url in BLACKLIST: continue
            self.parsed[group].append({"raw": title, "url": url})

    # ==================== 1. 央视严格排序（经典权重） ====================
    def process_cctv(self):
        cctv_channels = {}
        for chans in self.parsed.values():
            for ch in chans:
                c = self.clean(ch["raw"])
                if not c.startswith("CCTV"): continue
                key = f"{c}|{ch['url']}"
                if key in cctv_channels: continue
                weight = self.cctv_weight(c)
                cctv_channels[key] = {"title": c, "url": ch["url"], "weight": weight}

        sorted_cctv = sorted(cctv_channels.values(), key=lambda x: (x["weight"], x["title"]))
        items = [{"title": i["title"], "url": i["url"]} for i in sorted_cctv]
        if items:
            self.final["央视,#genre#"] = items
            for i in items: self.used.add(i["title"])

    def cctv_weight(self, t):
        m = re.match(r"CCTV[-\s]?(\d+)", t, re.I)
        if m: return int(m.group(1))
        special = {
            "CCTV8K": 0, "CCTV4K": 0, "CCTV-8K": 0, "CCTV-4K": 0,
            "CCTV纪录": 90, "CCTV紀錄": 90,
            "CCTV戲曲": 91, "CCTV戏曲": 91,
            "CCTV第一剧场": 92, "CCTV第一劇場": 92,
            "CCTV风云足球": 93, "CCTV風雲足球": 93,
            "CCTV女性时尚": 94, "CCTV婦女時尚": 94,
            "CCTV兵器科技": 95, "CCTV軍事評論": 95,
        }
        for k, v in special.items():
            if k in t: return v
        return 999

    # ==================== 2. 卫视（只去重，不排序） ====================
    def process_weishi(self):
        ws = []
        for key in ["中國大陸,#genre#", "中国大陆,#genre#"]:
            for ch in self.parsed.get(key, []):
                c = self.clean(ch["raw"])
                if "卫视" in c or "衛視" in c or "衛视" in c:
                    if c not in self.used:
                        ws.append({"title": c, "url": ch["url"]})
                        self.used.add(c)
        if ws:
            self.final["卫视,#genre#"] = ws

    # ==================== 3. 香港：凤凰中文、凤凰资讯 强制放最前 ====================
    def process_hongkong(self):
        all_hk = []
        phoenix_first = []
        others = []
        for ch in self.parsed.get("香港,#genre#", []):
            c = self.clean(ch["raw"])
            item = {"title": c, "url": ch["url"]}
            if any(x in c for x in ["凤凰中文", "鳳凰中文", "凤凰资讯", "鳳凰資訊", "凤凰香港", "鳳凰香港"]):
                phoenix_first.append(item)
            else:
                others.append(item)
            self.used.add(c)

        all_hk = phoenix_first + others
        if all_hk:
            self.final["香港,#genre#"] = all_hk

    # ==================== 4. 台湾：含关键词的靠前 ====================
    def process_taiwan(self):
        priority = []
        rest = []
        keywords = ["新闻", "新聞", "綜合", "综合", "娱乐", "娛樂", "财经", "財經", "电影", "電影", "戏剧", "戲劇"]
        for ch in self.parsed.get("台灣,#genre#", []):
            c = self.clean(ch["raw"])
            item = {"title": c, "url": ch["url"]}
            if any(k in c for k in keywords):
                priority.append(item)
            else:
                rest.append(item)
            self.used.add(c)

        final_tw = priority + rest
        if final_tw:
            self.final["台灣,#genre#"] = final_tw

    # ==================== 5. 剩余大陆频道 → 按省份归类 ====================
    def process_province(self):
        province_dict = defaultdict(list)
        mainland = []
        for k in ["中國大陸,#genre#", "中国大陆,#genre#"]:
            mainland.extend(self.parsed.get(k, []))

        for ch in mainland:
            c = self.clean(ch["raw"])
            if c in self.used: continue
            if c.startswith("CCTV"): continue
            if "卫视" in c or "衛視" in c: continue

            found = False
            for prov, kws in PROVINCE_KEYWORDS.items():
                if any(kw in c for kw in kws):
                    province_dict[prov].append({"title": c, "url": ch["url"]})
                    found = True
                    break
            if not found:
                province_dict["其他省份"].append({"title": c, "url": ch["url"]})

        # 固定顺序
        for prov in PROVINCE_ORDER:
            if province_dict[prov]:
                self.final[f"{prov},#genre#"] = province_dict[prov]
        for prov in sorted(province_dict.keys()):
            if prov not in PROVINCE_ORDER and province_dict[prov]:
                self.final[f"{prov},#genre#"] = province_dict[prov]

    def process(self):
        self.process_cctv()       # 经典排序
        self.process_weishi()     # 只去重
        self.process_hongkong()  # 凤凰强制前置
        self.process_taiwan()     # 关键词前置
        self.process_province()   # 省份归类

    def output(self):
        top = ["央视,#genre#", "卫视,#genre#", "香港,#genre#", "台灣,#genre#"]
        lines = []
        for g in top:
            if g in self.final:
                lines.append(g)
                for ch in self.final[g]:
                    lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")

        for g in list(self.final.keys()):
            if g not in top:
                lines.append(g)
                for ch in self.final[g]:
                    lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")

        result = "\n".join(lines).rstrip() + "\n"
        print(result)
        with open("tv.txt", "w", encoding="utf-8") as f:
            f.write(result)


if __name__ == "__main__":
    import sys
    try:
        LiveStreamCrawler()
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
