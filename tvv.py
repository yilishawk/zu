import re
import requests
import time
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor

# --- 配置区 ---
URL = "https://freetv.fun/test_channels_new.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BLACKLIST = {"https://stream1.freetv.fun/tang-he-yi-tao-1.m3u8"}
MAX_WORKERS = 20  # GitHub Actions 环境下不宜过高，避免带宽竞争影响测速
TIMEOUT = 5       # 增加到5秒，确保慢速但稳定的源不被误删
SPEED_TEST_GROUPS = ["央视,#genre#", "卫视,#genre#", "香港,#genre#"]
OUTPUT_FILE = "tvv.txt"

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
        try:
            r = requests.get(URL, headers=HEADERS, timeout=30)
            r.raise_for_status()
            self.rawContent = r.text
        except Exception as e:
            print(f"无法获取源数据: {e}")

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
                    if url.strip() in BLACKLIST: continue
                    self.parsedData[currentGroup].append({"title": title.strip(), "url": url.strip()})

    def cleanTitle(self, title):
        # 统一更名：CCTV1(RTHK33) -> CCTV1
        title = re.sub(r'CCTV-?1\(RTHK33\)', 'CCTV1', title, flags=re.I)
        patterns = [r'\s*\(backup\)', r'\s*\(h265\)', r'\s*\(h264\)', r'\s*\(备用\)', r'\s*\(备\)', r'\s*\[.*?\]', r'\s*#\d+']
        for p in patterns: title = re.sub(p, '', title, flags=re.I)
        title = ts(title)
        if title.upper().startswith("CCTV"):
            title = title.replace("-", "").replace(" ", "")
        return title.strip()

    def getCCTVWeight(self, title):
        m = re.search(r'CCTV(\d+)', title, re.I)
        if m: return int(m.group(1))
        special = {"CCTV8K":100, "CCTVDocumentary":101, "CCTV戲曲":102, "CCTV第一劇場":103, "CCTV风云足球":104}
        for k,v in special.items():
            if k in title: return v
        return 999

    def check_url_speed(self, item):
        """核心改进：读取真实数据块测速"""
        try:
            start = time.time()
            # stream=True 模式开启
            with requests.get(item['url'], headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
                if r.status_code == 200:
                    # 尝试读取前 1024 字节，确保流是活的
                    for _ in r.iter_content(chunk_size=1024):
                        break
                    duration = time.time() - start
                    return {**item, "speed": duration, "weight": self.getCCTVWeight(item['title'])}
        except:
            pass
        return None

    def speedTestSelectedGroups(self):
        print("开始进行真实数据流测速排序...")
        for group_name in list(self.finalGroups.keys()):
            channels = self.finalGroups[group_name]
            if not channels: continue
            
            if group_name in SPEED_TEST_GROUPS:
                print(f"正在测速分组: {group_name}，频道数量: {len(channels)}")
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(self.check_url_speed, channels))
                
                # 双重排序：先频道号 weight，再延迟时间 speed
                valid_sorted = sorted([r for r in results if r], key=lambda x: (x['weight'], x['speed']))
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
        if cctv_list: self.finalGroups["央视,#genre#"] = cctv_list

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
        key = "中國大陸,#genre#"
        if key not in self.parsedData: return
        used = set()
        for g in ["央视,#genre#", "卫视,#genre#"]:
            for c in self.finalGroups.get(g, []): used.add(c["title"])
        
        province_map = {"北京":["北京"],"上海":["上海"],"广东":["广东","广州","深圳"],"浙江":["浙江","杭州","宁波"],"江苏":["江苏","南京","苏州"],"湖南":["湖南","长沙"]}
        province_groups = defaultdict(list)
        for ch in self.parsedData[key]:
            clean = self.cleanTitle(ch["title"])
            if clean in used or clean.upper().startswith("CCTV") or "卫视" in clean: continue
            found = False
            for province, keys in province_map.items():
                if any(k in clean for k in keys):
                    province_groups[province].append({"title": clean, "url": ch["url"]})
                    found = True; break
            if not found: province_groups["其他省份"].append({"title": clean, "url": ch["url"]})
        
        for p in province_map:
            if province_groups[p]: self.finalGroups[f"{p},#genre#"] = province_groups[p]

    def outputResult(self):
        ordered_top = ["央视,#genre#", "卫视,#genre#", "香港,#genre#", "台灣,#genre#"]
        lines = []
        for g in ordered_top:
            if g in self.finalGroups and self.finalGroups[g]:
                lines.append(g)
                for ch in self.finalGroups[g]: lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")
        for g, channels in self.finalGroups.items():
            if g not in ordered_top and channels:
                lines.append(g)
                for ch in channels: lines.append(f"{ch['title']},{ch['url']}")
                lines.append("")
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")
        print(f"成功生成 {OUTPUT_FILE}")

if __name__ == "__main__":
    LiveStreamCrawler()
