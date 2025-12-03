#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完全忠实还原你原始 PHP 版本的直播源整理爬虫（Python 版）
功能、分组、顺序、去重逻辑全部一致
"""

import re
import requests
from collections import defaultdict, OrderedDict

URL = "https://freetv.fun/test_channels_new.txt"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class LiveStreamCrawler:
    def __init__(self):
        self.rawContent = ""
        self.parsedData = defaultdict(list)   # {group_name: [channels]}
        self.finalGroups = OrderedDict()

        self.fetchData()
        self.parseData()
        self.processGroups()
        self.outputResult()

    def fetchData(self):
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        self.rawContent = r.text

    def parseData(self):
        currentGroup = ""
        for line in self.rawContent.splitlines():
            line = line.strip()
            if not line:
                continue
            if "#genre#" in line:
                currentGroup = line.strip()
                self.parsedData[currentGroup] = []
                continue
            if currentGroup and "," in line:
                title, url = line.split(",", 1)
                self.parsedData[currentGroup].append({
                    "title": title.strip(),
                    "url": url.strip(),
                    "original_title": title.strip()
                })

    def cleanTitle(self, title):
        patterns = [
            r'\s*\(backup\)', r'\s*\(h265\)', r'\s*\(h264\)',
            r'\s*\(备用\)', r'\s*\(备\)', r'\s*\[.*?\]'
        ]
        for p in patterns:
            title = re.sub(p, '', title, flags=re.I)
        return title.strip()

    def getCCTVWeight(self, title):
        cleanTitle = self.cleanTitle(title)

        # CCTV-数字
        m = re.match(r'^CCTV[-\s]?(\d+)', cleanTitle, re.I)
        if m:
            return int(m.group(1))

        special = {
            "CCTV 8K": 100,
            "CCTV-Documentary": 101,
            "CCTV-戲曲": 102,
            "CCTV第一劇場": 103,
            "CCTV風雲足球": 104,
            "CCTV第一剧场": 103,
            "CCTV风云足球": 104,
        }
        for k, v in special.items():
            if cleanTitle.startswith(k):
                return v

        if cleanTitle.startswith("CCTV"):
            return 999
        return 1000

    def processCCTVChannels(self):
        allCCTV = {}

        for channels in self.parsedData.values():
            for ch in channels:
                clean = self.cleanTitle(ch["title"])
                if clean.startswith("CCTV"):
                    key = f"{clean}|{ch['url']}"
                    if key not in allCCTV:
                        weight = self.getCCTVWeight(ch["title"])
                        allCCTV[key] = {
                            "title": clean,
                            "url": ch["url"],
                            "original_title": ch["original_title"],
                            "weight": weight
                        }

        cctv_list = sorted(allCCTV.values(),
                           key=lambda x: (x["weight"], x["title"]))

        if cctv_list:
            self.finalGroups["央视,#genre#"] = [ {"title": c["title"], "url": c["url"]} for c in cctv_list ]

    def processMainlandChina(self):
        key = "中國大陸,#genre#"
        if key not in self.parsedData:
            return

        channels = self.parsedData[key]

        # 已提取的央视标题（用于过滤）
        cctv_titles = {c["title"] for c in self.finalGroups.get("央视,#genre#", [])}

        xianGroup = []
        satelliteGroup = []
        cityGroups = defaultdict(list)
        otherChannels = []

        for ch in channels:
            clean = self.cleanTitle(ch["title"])

            if clean in cctv_titles:
                continue

            new_ch = {
                "title": clean,
                "url": ch["url"],
                "original_title": ch["original_title"]
            }

            # 西安优先
            if "西安" in clean:
                xianGroup.append(new_ch)
                continue

            # 卫视
            if "衛視" in clean or "卫视" in clean:
                satelliteGroup.append(new_ch)
                continue

            # 城市台（如 哈尔滨影视）
            m = re.match(r'^([\u4e00-\u9fa5]+)[娛樂影視]', clean)
            if m:
                city = m.group(1)
                if city != "西安":
                    cityGroups[city].append(new_ch)
                continue

            # 其他
            otherChannels.append(new_ch)

        if xianGroup:
            self.finalGroups["西安,#genre#"] = xianGroup
        if satelliteGroup:
            self.finalGroups["卫视,#genre#"] = satelliteGroup

        # 各省地方台（按城市名字母序）
        for city in sorted(cityGroups.keys()):
            self.finalGroups[f"{city},#genre#"] = cityGroups[city]

        if otherChannels:
            self.finalGroups["中國大陸其他,#genre#"] = otherChannels

    def processHongKong(self):
        key = "香港,#genre#"
        if key not in self.parsedData:
            return

        channels = self.parsedData[key]
        phoenix = []
        others = []

        for ch in channels:
            clean = self.cleanTitle(ch["title"])
            item = {"title": clean, "url": ch["url"]}

            if any(x in clean for x in ["鳳凰衛視中文", "鳳凰資訊", "凤凰卫视中文", "凤凰资讯"]):
                phoenix.append(item)
            else:
                others.append(item)

        final_hk = phoenix + others
        if final_hk:
            self.finalGroups["香港,#genre#"] = final_hk

    def processTaiwan(self):
        key = "台灣,#genre#"
        if key not in self.parsedData:
            return

        channels = self.parsedData[key]
        priority = []
        others = []

        for ch in channels:
            clean = self.cleanTitle(ch["title"])
            item = {"title": clean, "url": ch["url"]}

            if any(k in clean for k in ["新聞", "綜合", "娛樂", "新闻", "综合", "娱乐"]):
                priority.append(item)
            else:
                others.append(item)

        final_tw = priority + others
        if final_tw:
            self.finalGroups["台灣,#genre#"] = final_tw

    def processGroups(self):
        self.processCCTVChannels()
        self.processMainlandChina()
        self.processHongKong()
        self.processTaiwan()

    def outputResult(self):
        ordered = [
            "央视,#genre#",
            "西安,#genre#",
            "香港,#genre#",
            "卫视,#genre#",
            "台灣,#genre#",
            "中國大陸其他,#genre#"
        ]

        lines = []

        # 固定顺序
        for g in ordered:
            if g in self.finalGroups and self.finalGroups[g]:
                lines.append(g)
                for ch in self.finalGroups[g]:
                    lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")

        # 各省地方台（城市名,#genre#）
        for g in self.finalGroups:
            if g not in ordered and re.match(r'^[\u4e00-\u9fa5]+,#genre#$', g):
                lines.append(g)
                for ch in self.finalGroups[g]:
                    lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")

        result = "\n".join(lines).rstrip() + "\n"
        print(result)

        # 保存文件（方便 GitHub Actions）
        with open("tv.txt", "w", encoding="utf-8") as f:
            f.write(result)


if __name__ == "__main__":
    try:
        LiveStreamCrawler()
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        raise
