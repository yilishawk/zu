import re
import requests
import time
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor

# --- 配置区 ---
URL = "https://freetv.fun/test_channels_new.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BLACKLIST = {"https://stream1.freetv.fun/tang-he-yi-tao-1.m3u8"}
MAX_WORKERS = 30 
TIMEOUT = 3 
SPEED_TEST_GROUPS = ["央视,#genre#", "卫视,#genre#", "香港,#genre#"]

def ts(t):
    rep = {"臺":"台","衛":"卫","視":"视","頻":"频","廣":"广","東":"东","鳳":"凤","凰":"凰","資":"资","訊":"讯","綜":"综","藝":"艺","劇":"剧","無線":"无线","翡翠":"翡翠","緯來":"纬来"}
    for a,b in rep.items(): t = t.replace(a,b)
    return t.strip()

class LiveStreamCrawler:
    def __init__(self):
        self.rawContent = ""
        self.parsedData = defaultdict(list)
        self.finalGroups = OrderedDict()

        self.fetchData()
        self.parseData()
        self.processCCTVChannels()
        self.processMainlandChina()
        self.processHongKong()
        self.processTaiwan()
        self.processProvinceFromMainland()

        self.speedTestSelectedGroups()
        self.outputResult()

    def fetchData(self):
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        self.rawContent = r.text

    def parseData(self):
        currentGroup = ""
        for line in self.rawContent.splitlines():
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                currentGroup = line.strip()
                self.parsedData[currentGroup] = []
                continue
            if currentGroup and "," in line:
                parts = line.split(",", 1)
                if len(parts) == 2:
                    title, url = parts
                    self.parsedData[currentGroup].append({"title": title.strip(), "url": url.strip()})

    def cleanTitle(self, title):
        # 1. 统一更名需求：CCTV1(RTHK33) -> CCTV1
        title = re.sub(r'CCTV-?1\(RTHK33\)', 'CCTV1', title, flags=re.I)
        
        # 2. 移除常见后缀
        patterns = [r'\s*\(backup\)', r'\s*\(h265\)', r'\s*\(h264\)', r'\s*\(备用\)', r'\s*\(备\)', r'\s*\[.*?\]', r'\s*#\d+']
        for p in patterns: title = re.sub(p, '', title, flags=re.I)
        
        title = ts(title)
        
        # 3. 移除横杠和空格：CCTV-5 -> CCTV5
        if title.upper().startswith("CCTV"):
            title = title.replace("-", "").replace(" ", "")
        return title.strip()

    def getCCTVWeight(self, title):
        # 提取频道数字用于排序
        m = re.search(r'CCTV(\d+)', title, re.I)
        if m: return int(m.group(1))
        
        special = {"CCTV8K":100, "CCTVDocumentary":101, "CCTV戲曲":102, "CCTV第一劇場":103, "CCTV风云足球":104}
        for k,v in special.items():
            if k in title: return v
        return 999

    def check_url_speed(self, item):
        try:
            start = time.time()
            r = requests.get(item['url'], headers=HEADERS, timeout=TIMEOUT, stream=True)
            if r.status_code == 200:
                # 额外记录一个 weight 用于测速后的二次排序
                return {**item, "speed": time.time() - start, "weight": self.getCCTVWeight(item['title'])}
        except:
            pass
        return None

    def speedTestSelectedGroups(self):
        print("开始定向测速并执行频道优先级排序...")
        for group_name in list(self.finalGroups.keys()):
            channels = self.finalGroups[group_name]
            if not channels: continue
            
            if group_name in SPEED_TEST_GROUPS:
                print(f"正在处理分组: {group_name}")
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(self.check_url_speed, channels))
                
                # 【核心逻辑】双重排序：
                # 1. 先按 weight (频道号) 升序排
                # 2. 同频道号内，按 speed (延迟) 升序排
                valid_sorted = sorted(
                    [r for r in results if r], 
                    key=lambda x: (x['weight'], x['speed'])
                )
                
                for item in valid_sorted: 
                    item.pop('speed', None)
                    item.pop('weight', None)
                self.finalGroups[group_name] = valid_sorted

    def processCCTVChannels(self):
        cctv_list = []
        for channels in self.parsedData.values():
            for ch in channels:
                clean = self.cleanTitle(ch["title"])
                if clean.upper().startswith("CCTV"):
                    cctv_list.append({"title": clean, "url": ch["url"]})
        # 初始分类（此处不排序，由测速函数统一排）
        if cctv_list: self.finalGroups["央视,#genre#"] = cctv_list

    # 卫视、港台、省份逻辑保持不变...
    def processMainlandChina(self):
        key = "中國大陸,#genre#"
        if key not in self.parsedData: return
        satelliteGroup = []
        for ch in self.parsedData[key]:
            clean = self.cleanTitle(ch["title"])
            if "卫视" in clean and not clean.upper().startswith("CCTV"):
                satelliteGroup.append({"title": clean, "url": ch["url"]})
        if satelliteGroup: self.finalGroups["卫视,#genre#"] = satelliteGroup

    def processHongKong(self):
        key = "香港,#genre#"
        if key not in self.parsedData: return
        self.finalGroups["香港,#genre#"] = [{"title": self.cleanTitle(ch["title"]), "url": ch["url"]} for ch in self.parsedData[key]]

    def processTaiwan(self):
        key = "台灣,#genre#"
        if key not in self.parsedData: return
        self.finalGroups["台灣,#genre#"] = [{"title": self.cleanTitle(ch["title"]), "url": ch["url"]} for ch in self.parsedData[key]]

    def processProvinceFromMainland(self):
        # 原有的省份分类逻辑... (篇幅原因略，保持你之前的代码即可)
        pass

    def outputResult(self):
        ordered_top = ["央视,#genre#", "卫视,#genre#", "香港,#genre#", "台灣,#genre#"]
        lines = []
        for g in ordered_top:
            if g in self.finalGroups and self.finalGroups[g]:
                lines.append(g)
                for ch in self.finalGroups[g]: lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")
        
        # 剩下的省份分组
        for g, channels in self.finalGroups.items():
            if g not in ordered_top and channels:
                lines.append(g)
                for ch in channels: lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")
        
        with open("tvv.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")

if __name__ == "__main__":
    LiveStreamCrawler()
