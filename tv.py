import re
import requests
import concurrent.futures
import time
import os

# --- 配置区 ---
URL = "https://freetv.fun/test_channels_banned_cn_new.m3u"
CHECK_TIMEOUT = 3
MAX_WORKERS = 50
# 仅对以下常看的分组进行 1MB 深度下载测速
DEEP_SPEED_GROUPS = ["央视", "卫视", "香港"]

def get_speed_score(c_obj, group_name):
    """
    深度测速：1.5秒内尝试下载1MB。
    返回分值，越小越快。
    """
    url = c_obj["url"]
    # 如果是不常看的组，只做基本连通性测试（0.1s内能连上就算100ms）
    is_deep = group_name in DEEP_SPEED_GROUPS
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        start_time = time.time()
        # verify=False 忽略SSL错误加快速度
        with requests.get(url, timeout=CHECK_TIMEOUT, stream=True, headers=headers, verify=False) as res:
            if res.status_code == 200:
                ttfb = time.time() - start_time # 首字节延迟
                
                if is_deep:
                    downloaded = 0
                    test_start = time.time()
                    for chunk in res.iter_content(chunk_size=1024 * 64):
                        downloaded += len(chunk)
                        # 下载够1MB或耗时超过1.5秒则停止
                        if downloaded >= 1024 * 1024 or (time.time() - test_start) > 1.5:
                            break
                    duration = time.time() - test_start
                    speed = (downloaded / 1024 / 1024) / (duration + 0.001)
                    # 评分公式：延迟30% + 速度倒数70%
                    c_obj["speed"] = ttfb * 0.3 + (1 / (speed + 0.1)) * 0.7
                else:
                    c_obj["speed"] = ttfb
                return c_obj
    except:
        pass
    c_obj["speed"] = 99.0
    return c_obj

def is_pure_abc(name):
    """识别并剔除纯英文ABC台，如 CNN, HBO, BBC"""
    # 移除空格和数字后，如果全是字母且不含汉字
    clean = re.sub(r'[\s\d\-\_\.\(\)\[\]]', '', name)
    if clean.isalpha() and not re.search(r'[\u4e00-\u9fa5]', name):
        return True
    return False

def get_weight(name, group):
    """权重逻辑：越小越靠前"""
    n = name.upper()
    if group == "央视":
        match = re.search(r'CCTV(\d+)', n)
        return int(match.group(1)) if match else 99
    
    if group == "香港":
        if "凤凰" in n or "鳳凰" in n: return 1
        return 10
        
    if group == "台灣":
        if "新闻" in n or "新聞" in n: return 1
        if "综合" in n or "綜合" in n: return 2
        if "娱乐" in n or "娛樂" in n or "综艺" in n: return 3
        return 10
    return 100

def main():
    try:
        r = requests.get(URL, timeout=30, verify=False)
        raw = r.text
    except:
        print("下载失败"); return

    lines = raw.splitlines()
    channels = []
    
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF:-1"):
            line = lines[i]
            logo = re.search(r'tvg-logo="([^"]*)"', line).group(1) if 'tvg-logo="' in line else ""
            name = line.split(",", 1)[1].strip() if "," in line else ""
            
            # 清洗名称
            name = re.sub(r'^\s*\[[^\]]*\]\s*', '', name)
            name = re.sub(r'\s*\([^)]*\)|\s*(ipv6|backup|备用|备|4m|8m|1080|高清|HD).*', '', name, flags=re.I).strip()
            
            # 统一命名
            cctv_m = re.search(r'cctv[ -]?(\d+)', name, re.I)
            if cctv_m: name = f"CCTV{cctv_m.group(1)}"

            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                channels.append({"name": name, "url": lines[i+1].strip(), "logo": logo, "speed": 99.0})

    # 分组排序
    order = ["央视","卫视","香港","台灣","北京","上海","广东","浙江","江苏","湖南","其他省份"]
    groups = {g: [] for g in order}

    def get_group_name(n):
        n_l = n.lower()
        if "cctv" in n_l: return "央视"
        if "卫视" in n_l: return "卫视"
        if any(x in n_l for x in ["凤凰", "翡翠", "tvb", "hks"]): return "香港"
        if any(x in n_l for x in ["台湾", "台灣", "中视", "华视", "民视"]): return "台灣"
        for p in ["北京", "上海", "广东", "浙江", "江苏", "湖南"]:
            if p in n_l: return p
        return "其他省份"

    # 预过滤英文台
    filtered_channels = []
    for c in channels:
        g = get_group_name(c["name"])
        # 香港和台湾组剔除纯ABC电台
        if g in ["香港", "台灣"] and is_pure_abc(c["name"]):
            continue
        filtered_channels.append(c)

    print(f"开始并发处理 {len(filtered_channels)} 个频道...")
    
    # 执行分类测速
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_c = {executor.submit(get_speed_score, c, get_group_name(c["name"])): c for c in filtered_channels}
        tested = [f.result() for f in concurrent.futures.as_completed(future_to_c)]

    for c in tested:
        groups[get_group_name(c["name"])].append(c)

    # 格式化输出
    result = ["#EXTM3U"]
    for g in order:
        # 核心排序：权重(weight)第一，测速(speed)第二
        groups[g].sort(key=lambda x: (get_weight(x["name"], g), x["speed"]))
        
        seen = set() # 简单去重
        for c in groups[g]:
            key = f"{c['name']}_{c['url']}"
            if key in seen or c["speed"] == 99.0: continue
            seen.add(key)
            
            logo_str = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
            # 在名称后标注大概质量（如果是重点组）
            tag = " (Stable)" if c["speed"] < 1.0 and g in DEEP_SPEED_GROUPS else ""
            line = f'#EXTINF:-1 tvg-name="{c["name"]}"{logo_str} group-title="{g}",{c["name"]}{tag}'
            result.append(line)
            result.append(c["url"])

    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(result) + "\n")
    print("更新完成：tv.m3u")

if __name__ == "__main__":
    main()
