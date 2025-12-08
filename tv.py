#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终版 M3U 输出
抓取：https://freetv.fun/test_channels_all_new.m3u
输出：tv.m3u（标准 M3U 格式）
逻辑 100% 保留原版，仅将中国大陆非央视非卫视频道按省份重新归类
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
        "臺":"台","衛":"卫","視":"视","頻":"频","廣":"广","東":"东",
        "鳳":"凤","凰":"凰","資":"资","訊":"讯","綜":"综","藝":"艺",
        "劇":"剧","無線":"无线","翡翠":"翡翠","緯來":"纬来"
    }
    for a, b in rep.items():
        t = t.replace(a, b)
    return t.strip()

class LiveStreamCrawler:
    def __init__(self):
        self.rawContent = ""
        self.parsedData = defaultdict(list)   # group: [ {tvg-name, url}, ... ]
        self.finalGroups = OrderedDict()
        self.fetchData()
        self.parseM3UData()                     # 改为解析 m3u
        self.processCCTVChannels()
        self.processMainlandChina()             # 只提取卫视
        self.finalGroups["卫视"]
        self.processHongKong()
        self.processTaiwan()
        self.processProvinceFromMainland()      # 新增：省份分类
        self.outputM3U()                        # 改为输出 m3u

    def fetchData(self):
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        self.rawContent = r.text

    # 解析标准 m3u（支持 #EXTINF:-1 tvg-name="..." group-title="..."）
    def parseM3UData(self):
        lines = self.rawContent.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                # 提取 tvg-name 或逗号后的标题
                title_part = line.split(",", 1)[-1].strip()
                group = ""
                # 尝试提取 group-title
                m = re.search(r'group-title="([^"]*)"', line)
                if m:
                    group = m.group(1).strip()
                # 下一行应该是 url
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and url not in BLACKLIST:
                        clean_title = self.cleanTitle(title_part)
                        self.parsedData[group or "未分组"].append({
                            "title": clean_title,
                            "original_title": title_part,
                            "url": url
                        })
                i += 1
            i += 1

    def cleanTitle(self, title):
        patterns = [
            r'\s*\(backup\)', r'\s*\(h265\)', r'\s*\(h264\)',
            r'\s*\(备用\)', r'\s*\(备\)', r'\s*\[.*?\]', r'\s*#\d+'
        ]
        for p in patterns:
            title = re.sub(p, '', title, flags=re.I)
        return ts(title).strip()

    def getCCTVWeight(self, title):
        cleanTitle = self.cleanTitle(title)
        m = re.match(r'^CCTV[-\s]?(\d+)', cleanTitle, re.I)
        if m:
            return int(m.group(1))
        special = {
            "CCTV 8K":100, "CCTV-Documentary":101, "CCTV-戲曲":102,
            "CCTV第一劇場":103, "CCTV風雲足球":104, "CCTV第一剧场":103, "CCTV风云足球":104,
        }
        for k, v in special.items():
            if cleanTitle.startswith(k):
                return v
        if cleanTitle.startswith("CCTV"):
            return 999
        return 1000

    # ==================== 原逻辑完全保留 ====================
    def processCCTVChannels(self):
        allCCTV = {}
        for channels in self.parsedData.values():
            for ch in channels:
                clean = self.cleanTitle(ch["original_title"])
                if clean.startswith("CCTV"):
                    key = f"{clean}|{ch['url']}"
                    if key not in allCCTV:
                        weight = self.getCCTVWeight(ch["original_title"])
                        allCCTV[key] = {"title": clean, "url": ch["url"], "weight": weight}
        cctv_list = sorted(allCCTV.values(), key=lambda x: (x["weight"], x["title"]))
        if cctv_list:
            self.finalGroups["央视"] = [{"title": c["title"], "url": c["url"]} for c in cctv_list]

    def processMainlandChina(self):
        # 找出所有包含“中国大陆”或类似组的
        mainland_groups = [g for g in self.parsedData if "大陆" in g or "中國" in g]
        satelliteGroup = []
        cctv_titles = {c["title"] for c in self.finalGroups.get("央视", [])}
        for g in mainland_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                if clean in cctv_titles:
                    continue
                if "衛視" in clean or "卫视" in clean:
                    satelliteGroup.append({"title": clean, "url": ch["url"]})
        if satelliteGroup:
            self.finalGroups["卫视"] = satelliteGroup

    def processHongKong(self):
        hk_groups = [g for g in self.parsedData if "香港" in g or "HK" in g]
        phoenix = []
        others = []
        for g in hk_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                item = {"title": clean, "url": ch["url"]}
                if any(x in clean for x in ["鳳凰衛視中文", "鳳凰資訊", "凤凰卫视中文", "凤凰资讯"]):
                    phoenix.append(item)
                else:
                    others.append(item)
        final_hk = phoenix + others
        if final_hk:
            self.finalGroups["香港"] = final_hk

    def processTaiwan(self):
        tw_groups = [g for g in self.parsedData if "台灣" in g or "台湾" in g or "台" in g]
        priority = []
        others = []
        for g in tw_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                item = {"title": clean, "url": ch["url"]}
                if any(k in clean for k in ["新聞", "綜合", "娛樂", "新闻", "综合", "娱乐"]):
                    priority.append(item)
                else:
                    others.append(item)
        final_tw = priority + others
        if final_tw:
            self.finalGroups["台灣"] = final_tw

    def processProvinceFromMainland(self):
        mainland_groups = [g for g in self.parsedData if "大陆" in g or "中國" in g]
        used = set()
        for g in ["央视", "卫视"]:
            for c in self.finalGroups.get(g, []):
                used.add(c["title"])

        province_map = {
            "北京":["北京"],"上海":["上海"],"重庆":["重庆"],"天津":["天津"],
            "广东":["广东","廣東","广州","廣州","深圳","东莞","東莞","佛山","珠海","惠州","中山","江门","汕头","湛江"],
            "浙江":["浙江","杭州","宁波","寧波","温州","溫州","嘉兴","绍兴","金华","台州"],
            "江苏":["江苏","江蘇","南京","苏州","蘇州","无锡","無錫","常州","南通","扬州","镇江"],
            "山东":["山东","山東","济南","濟南","青岛","青島","烟台","潍坊"],
            "四川":["四川","成都","绵阳","德阳","南充"],
            "陕西":["陕西","陝西","西安","咸阳","宝鸡"],
            "湖北":["湖北","武汉","武漢","宜昌","襄阳"],
            "湖南":["湖南","长沙","長沙","株洲","湘潭","岳阳"],
            "河南":["河南","郑州","鄭州","洛阳"],
            "福建":["福建","福州","厦门","廈門","泉州"],
            "安徽":["安徽","合肥","芜湖"],
            "江西":["江西","南昌","赣州"],
            "河北":["河北","石家庄","唐山"],
            "黑龙江":["黑龙江","黑龍江","哈尔滨","哈爾濱"],
            "辽宁":["辽宁","遼寧","沈阳","瀋陽","大连"],
            "广西":["广西","廣西","南宁","南寧"],
            "云南":["云南","雲南","昆明"],
        }
        province_groups = defaultdict(list)
        for g in mainland_groups:
            for ch in self.parsedData[g]:
                clean = self.cleanTitle(ch["original_title"])
                if clean in used or clean.startswith("CCTV") or ("卫视" in clean or "衛視" in clean):
                    continue
                found = False
                for province, keys in province_map.items():
                    if any(k in clean for k in keys):
                        province_groups[province].append({"title": clean, "url": ch["url"]})
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

    # ==================== 输出标准 M3U ====================
    def outputM3U(self):
        lines = ['#EXTM3U']
        group_order = ["央视", "卫视", "香港", "台灣"]

        # 先输出固定顺序的四大组
        for g in group_order:
            if g in self.finalGroups and self.finalGroups[g]:
                for ch in self.finalGroups[g]:
                    lines.append(f'#EXTINF:-1 group-title="{g}",{ch["title"]}')
                    lines.append(ch["url"])

        # 再输出省份组（保持你原来的顺序）
        province_order = ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]
        for p in province_order:
            if p in self.finalGroups and self.finalGroups[p]:
                for ch in self.finalGroups[p]:
                    lines.append(f'#EXTINF:-1 group-title="{p}",{ch["title"]}')
                    lines.append(ch["url"])

        # 最后输出其他省份（按名称排序）
        for g in sorted(self.finalGroups):
            if g not in group_order and g not in province_order and self.finalGroups[g]:
                for ch in self.finalGroups[g]:
                    lines.append(f'#EXTINF:-1 group-title="{g}",{ch["title"]}')
                    lines.append(ch["url"])

        result = "\n".join(lines) + "\n"
        print(result)
        with open("tv.m3u", "w", encoding="utf-8") as f:
            f.write(result)
        print("已生成 tv.m3u")

if __name__ == "__main__":
    LiveStreamCrawler()
