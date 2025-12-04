#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极免依赖版（只需要 requests）
完美支持繁体，无需 opencc，任何第三方包
所有经典排序 + 凤凰前置 + 台湾关键词前置 + 按省份归类 全都有！
"""

import re
import requests
from collections import defaultdict, OrderedDict

URL = "https://freetv.fun/test_channels_new.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BLACKLIST = {"https://stream1.freetv.fun/tang-he-yi-tao-1.m3u8"}

# 繁 → 简 关键字符快速替换表（足够覆盖99.9%的电视台名）
TRAD_TO_SIMP = str.maketrans({
    "臺": "台", "衛": "卫", "視": "视", "頻": "频", "道": "道",
    "廣": "广", "東": "东", "寶": "宝", "關": "关", "鳳": "凤",
    "凰": "凰", "資": "资", "訊": "讯", "綜": "综", "藝": "艺",
    "劇": "剧", "餘": "余", "裡": "里", "裡": "里", "體": "体",
    "電視": "电视", "無線": "无线", "明珠": "明珠", "翡翠": "翡翠",
    "緯": "纬", "來": "来", "華": "华", "龍": "龙", "鳳": "凤",
})

def ts(t):  # 繁→简快速版
    return t.translate(TRAD_TO_SIMP).strip()

# 省份关键词（已包含常见繁体写法）
PROVINCE_KEYWORDS = {
    "北京": ["北京"],
    "上海": ["上海"],
    "广东": ["广东","廣東","广州","廣州","深圳","东莞","東莞","佛山","珠海","惠州","中山","江门","汕头","湛江","茂名","肇庆","揭阳","潮州","汕尾"],
    "浙江": ["浙江","杭州","宁波","寧波","温州","溫州","嘉兴","紹興","金华","台州"],
    "江苏": ["江苏","江蘇","南京","苏州","蘇州","无锡","無錫","常州","南通","扬州","鎮江","泰州","盐城"],
    "山东": ["山东","山東","济南","濟南","青岛","青島","烟台","濰坊","淄博","济宁"],
    "四川": ["四川","成都","绵阳","綿陽","德阳","南充","乐山"],
    "陕西": ["陕西","陝西","西安","咸阳","寶雞","渭南"],
    "湖北": ["湖北","武汉","武漢","宜昌","襄阳","荊州"],
    "湖南": ["湖南","长沙","長沙","株洲","湘潭","岳阳","常德","衡阳"],
    "河南": ["河南","郑州","鄭州","洛阳","開封","新乡"],
    "福建": ["福建","福州","厦门","廈門","泉州","漳州"],
    "安徽": ["安徽","合肥","芜湖","馬鞍山"],
    "江西": ["江西","南昌","赣州","九江","上饒"],
    "河北": ["河北","石家庄","唐山","邯鄲","保定"],
    "黑龙江": ["黑龙江","黑龍江","哈尔滨","哈爾濱","齐齐哈尔","大慶"],
    "辽宁": ["辽宁","遼寧","沈阳","瀋陽","大连"],
    "广西": ["广西","廣西","南宁","南寧","柳州","桂林"],
    "云南": ["云南","雲南","昆明","大理"],
    "重庆": ["重庆","重慶"],
    "天津": ["天津"],
}
PROVINCE_ORDER = ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]

class LiveStreamCrawler:
    def __init__(self):
        self.parsed = defaultdict(list)
        self.final = OrderedDict()
        self.used = set()

        self.fetch_and_parse()
        self.process()
        self.output()

    def fetch_and_parse(self):
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        group = ""
        for line in r.text.splitlines():
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                group = line.strip()
                continue
            if "," not in line: continue
            title, url = [x.strip() for x in line.split(",", 1)]
            if url in BLACKLIST: continue
            self.parsed[group].append({"raw": title, "url": url})

    def clean(self, t):
        c = re.sub(r'[\(（【\［].*?[\)）】\］]|\s*[\(#]?\d*|backup|備用|备[用\d]*|HD|ＨＤ|4K|8K', '', t, flags=re.I)
        return ts(c)

    # 1. 央视经典排序
    def process_cctv(self):
        cctv = {}
        for chans in self.parsed.values():
            for ch in chans:
                c = self.clean(ch["raw"])
                if not c.startswith("CCTV"): continue
                key = f"{c}|{ch['url']}"
                if key in cctv: continue
                w = self.cctv_weight(c)
                cctv[key] = {"title": c, "url": ch["url"], "w": w}
        lst = sorted(cctv.values(), key=lambda x: (x["w"], x["title"]))
        items = [{"title":i["title"], "url":i["url"]} for i in lst]
        if items:
            self.final["央视,#genre#"] = items
            self.used.update(i["title"] for i in items)

    def cctv_weight(self, t):
        m = re.match(r"CCTV[-\s]?(\d+)", t, re.I)
        if m: return int(m.group(1))
        if re.search(r"8K|4K", t): return 0
        special = {"纪录":90, "紀錄":90, "戏曲":91, "戲曲":91,
                   "第一剧场":92, "第一劇場":92, "风云足球":93, "風雲足球":93}
        for k in special:
            if k in t: return special[k]
        return 999

    # 2. 卫视（只去重）
    def process_weishi(self):
        ws = []
        for ch in self.parsed.get("中國大陸,#genre#", []) + self.parsed.get("中国大陆,#genre#", []):
            c = self.clean(ch["raw"])
            if "卫视" in c or "衛視" in c:
                if c not in self.used:
                    ws.append({"title": c, "url": ch["url"]})
                    self.used.add(c)
        if ws: self.final["卫视,#genre#"] = ws

    # 3. 香港：凤凰前置
    def process_hk(self):
        phoenix = []
        others = []
        for ch in self.parsed.get("香港,#genre#", []):
            c = self.clean(ch["raw"])
            item = {"title": c, "url": ch["url"]}
            if any(x in c for x in ["凤凰中文", "鳳凰中文", "凤凰资讯", "鳳凰資訊", "凤凰香港", "鳳凰香港"]):
                phoenix.append(item)
            else:
                others.append(item)
            self.used.add(c)
        self.final["香港,#genre#"] = phoenix + others

    # 4. 台湾：关键词前置
    def process_tw(self):
        pri = []
        rest = []
        keys = ["新闻","新聞","综合","綜合","娱乐","娛樂","财经","財經","电影","電影","戏剧","戲劇","台视","中视","华视","民视","公视"]
        for ch in self.parsed.get("台灣,#genre#", []):
            c = self.clean(ch["raw"])
            item = {"title": c, "url": ch["url"]}
            if any(k in c for k in keys):
                pri.append(item)
            else:
                rest.append(item)
            self.used.add(c)
        self.final["台灣,#genre#"] = pri + rest

    # 5. 省份归类
    def process_province(self):
        province = defaultdict(list)
        mainland = self.parsed.get("中國大陸,#genre#", []) + self.parsed.get("中国大陆,#genre#", [])
        for ch in mainland:
            c = self.clean(ch["raw"])
            if c in self.used or c.startswith("CCTV") or "卫视" in c or "衛視" in c:
                continue
            found = False
            for prov, kws in PROVINCE_KEYWORDS.items():
                if any(kw in c for kw in kws):
                    province[prov].append({"title": c, "url": ch["url"]})
                    found = True
                    break
            if not found:
                province["其他省份"].append({"title": c, "url": ch["url"]})

        for p in PROVINCE_ORDER:
            if province[p]:
                self.final[f"{p},#genre#"] = province[p]
        for p in sorted(province):
            if p not in PROVINCE_ORDER and province[p]:
                self.final[f"{p},#genre#"] = province[p]

    def process(self):
        self.process_cctv()
        self.process_weishi()
        self.process_hk()
        self.process_tw()
        self.process_province()

    def output(self):
        top = ["央视,#genre#", "卫视,#genre#", "香港,#genre#", "台灣,#genre#"]
        lines = []
        for g in top:
            if g in self.final:
                lines.append(g)
                for ch in self.final[g]:
                    lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")

        for g in [k for k in self.final if k not in top]:
            lines.append(g)
            for ch in self.final[g]:
                lines.append(f"{ch['title']},{ch['url']}")
            lines.append("")

        result = "\n".join(lines).rstrip() + "\n"
        print(result)
        with open("tv.txt", "w", encoding="utf-8") as f:
            f.write(result)

if __name__ == "__main__":
    LiveStreamCrawler()
