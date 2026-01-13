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
# 指定需要进行测速排序的分组名称（需与代码生成的 genre 名一致）
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

        # 执行定向测速
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
                    if url.strip() in BLACKLIST: continue
                    self.parsedData[currentGroup].append({"title": title.strip(), "url": url.strip()})

    def cleanTitle(self, title):
        # 1. 移除常见后缀
        patterns = [r'\s*\(backup\)', r'\s*\(h265\)', r'\s*\(h264\)', r'\s*\(备用\)', r'\s*\(备\)', r'\s*\[.*?\]', r'\s*#\d+']
        for p in patterns: title = re.sub(p, '', title, flags=re.I)
        # 2. 繁简转换
        title = ts(title)
        # 3. 核心修改：如果是 CCTV 开头的，去掉横杠（例如 CCTV-1 -> CCTV1）
        if title.upper().startswith("CCTV"):
            title = title.replace("-", "").replace(" ", "")
        return title.strip()

    def getCCTVWeight(self, title):
        cleanTitle = self.cleanTitle(title)
        # 匹配 CCTV1, CCTV2 等
        m = re.match(r'^CCTV(\d+)', cleanTitle, re.I)
        if m: return int(m.group(1))
        special = {"CCTV8K":100, "CCTVDocumentary":101, "CCTV戲曲":102, "CCTV第一劇場":103, "CCTV风云足球":104}
        for k,v in special.items():
            if cleanTitle == k: return v
        return 999 if cleanTitle.startswith("CCTV") else 1000

    def check_url_speed(self, item):
        try:
            start = time.time()
            r = requests.get(item['url'], headers=HEADERS, timeout=TIMEOUT, stream=True)
            if r.status_code == 200:
                return {**item, "speed": time.time() - start}
        except:
            pass
        return None

    def speedTestSelectedGroups(self):
        """只对指定的分组进行测速和排序，其余分组剔除重复但不排序"""
        print("开始定向测速排序...")
        for group_name in list(self.finalGroups.keys()):
            channels = self.finalGroups[group_name]
            if not channels: continue
            
            # 如果该分组在测速名单中
            if group_name in SPEED_TEST_GROUPS:
                print(f"正在测速分组: {group_name}")
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(self.check_url_speed, channels))
                # 过滤掉无效源并按速度（延迟）排序
                valid_sorted = sorted([r for r in results if r], key=lambda x: x['speed'])
                for item in valid_sorted: item.pop('speed', None)
                self.finalGroups[group_name] = valid_sorted
            else:
                # 不在测速名单中的分组，目前逻辑是保留原样。
                # 如果你也想让这些分组剔除死链，可以把它们也加入 SPEED_TEST_GROUPS
                pass

    def processCCTVChannels(self):
        allCCTV = {}
        for channels in self.parsedData.values():
            for ch in channels:
                clean = self.cleanTitle(ch["title"])
                if clean.upper().startswith("CCTV"):
                    # 使用 clean 后的名称作为唯一键，同名同 URL 去重
                    key = f"{clean}|{ch['url']}"
                    if key not in allCCTV:
                        allCCTV[key] = {"title": clean, "url": ch["url"], "weight": self.getCCTVWeight(ch["title"])}
        cctv_list = sorted(allCCTV.values(), key=lambda x: (x["weight"], x["title"]))
        if cctv_list: self.finalGroups["央视,#genre#"] = cctv_list

    def processMainlandChina(self):
        key = "中國大陸,#genre#"
        if key not in self.parsedData: return
        satelliteGroup = []
        cctv_titles = {c["title"] for c in self.finalGroups.get("央视,#genre#", [])}
        for ch in self.parsedData[key]:
            clean = self.cleanTitle(ch["title"])
            if clean in cctv_titles: continue
            if "卫视" in clean:
                satelliteGroup.append({"title": clean, "url": ch["url"]})
        if satelliteGroup: self.finalGroups["卫视,#genre#"] = satelliteGroup

    def processHongKong(self):
        key = "香港,#genre#"
        if key not in self.parsedData: return
        phoenix, others = [], []
        for ch in self.parsedData[key]:
            clean = self.cleanTitle(ch["title"])
            item = {"title": clean, "url": ch["url"]}
            if any(x in clean for x in ["凤凰卫视中文", "凤凰资讯"]): phoenix.append(item)
            else: others.append(item)
        if phoenix + others: self.finalGroups["香港,#genre#"] = phoenix + others

    def processTaiwan(self):
        key = "台灣,#genre#"
        if key not in self.parsedData: return
        priority, others = [], []
        for ch in self.parsedData[key]:
            clean = self.cleanTitle(ch["title"])
            item = {"title": clean, "url": ch["url"]}
            if any(k in clean for k in ["新闻", "综合", "娱乐"]): priority.append(item)
            else: others.append(item)
        if priority + others: self.finalGroups["台灣,#genre#"] = priority + others

    def processProvinceFromMainland(self):
        key = "中國大陸,#genre#"
        if key not in self.parsedData: return
        used = set()
        for g in ["央视,#genre#", "卫视,#genre#"]:
            for c in self.finalGroups.get(g, []): used.add(self.cleanTitle(c["title"]))
        
        province_map = {"北京":["北京"],"上海":["上海"],"重庆":["重庆"],"天津":["天津"],"广东":["广东","广州","深圳"],"浙江":["浙江","杭州","宁波"],"江苏":["江苏","南京","苏州"],"山东":["山东","济南","青岛"],"四川":["四川","成都"],"陕西":["陕西","西安"],"湖北":["湖北","武汉"],"湖南":["湖南","长沙"],"河南":["河南","郑州"],"福建":["福建","福州","厦门"],"安徽":["安徽","合肥"],"江西":["江西","南昌"],"河北":["河北","石家庄"],"黑龙江":["黑龙江","哈尔滨"],"辽宁":["辽宁","沈阳"],"广西":["广西","南宁"],"云南":["云南","昆明"]}
        province_groups = defaultdict(list)
        for ch in self.parsedData[key]:
            clean = self.cleanTitle(ch["title"])
            if clean in used or clean.startswith("CCTV") or "卫视" in clean: continue
            found = False
            for province, keys in province_map.items():
                if any(k in clean for k in keys):
                    province_groups[province].append({"title": clean, "url": ch["url"]})
                    found = True; break
            if not found: province_groups["其他省份"].append({"title": clean, "url": ch["url"]})

        order = ["北京","上海","广东","浙江","江苏","湖南","山东","四川","陕西","湖北","河南","福建","安徽","江西","河北","黑龙江","辽宁","广西","云南","重庆","天津"]
        for p in order:
            if province_groups[p]: self.finalGroups[f"{p},#genre#"] = province_groups[p]
        for p in sorted(province_groups):
            if p not in order: self.finalGroups[f"{p},#genre#"] = province_groups[p]

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
        
        result = "\n".join(lines).rstrip() + "\n"
        with open("tvv.txt", "w", encoding="utf-8") as f: f.write(result)
        print("处理完成，tvv.txt 已更新")

if __name__ == "__main__":
    LiveStreamCrawler()

