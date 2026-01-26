import os
import re
import requests
import time
import socket
from datetime import datetime, timezone, timedelta

# ===============================
# 1. 核心配置区
# ===============================
BASE_URL = "http://foodieguide.com/iptvsearch/iptvmulticast.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "http://foodieguide.com/iptvsearch/"
}
IP_DIR = "ip"
OUTPUT_FILE = "ukiptv.txt"
PAGES_TO_SCAN = 5      # 扫描搜索页数
MAX_SOURCES_PER_CHANNEL = 4 # 每个频道保留的源数量
TARGET_ISP = "电信"    # 严格过滤运营商

# --- 频道分类标准 ---
CHANNEL_CATEGORIES = {
   "央视频道": [
        "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV4欧洲", "CCTV4美洲", "CCTV5", "CCTV5+", "CCTV6", "CCTV7",
        "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K"
    ],
    "卫视频道": [
        "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视", "广东卫视", "山东卫视", "安徽卫视"
    ],
    "数字频道": [
        "CHC动作电影", "CHC家庭影院", "CHC影迷电影", "重温经典", "凤凰卫视中文台", "凤凰卫视资讯台", "求索纪录", "五星体育"
    ]
}

# 频道映射逻辑 (缩减版，可根据需要自行增加)
CHANNEL_MAPPING = {
    "CCTV1": ["CCTV-1", "CCTV-1 HD", "CCTV1 HD", "CCTV-1综合"],
    "CCTV2": ["CCTV-2", "CCTV-2 HD", "CCTV2 HD", "CCTV-2财经"],
    "CCTV3": ["CCTV-3", "CCTV-3 HD", "CCTV3 HD", "CCTV-3综艺"],
    "CCTV5": ["CCTV-5", "CCTV-5 HD", "CCTV5 HD", "CCTV-5体育"],
    "CCTV6": ["CCTV-6", "CCTV-6 HD", "CCTV6 HD", "CCTV-6电影"],
    "CCTV13": ["CCTV-13", "CCTV-13 HD", "CCTV13 HD", "CCTV-13新闻"],
    "湖南卫视": ["湖南卫视", "湖南卫视HD", "湖南卫视4K"],
    "凤凰卫视中文台": ["凤凰中文", "凤凰中文台", "凤凰卫视中文"],
}

ALIAS_INDEX = {alias: std for std, aliases in CHANNEL_MAPPING.items() for alias in aliases}

# 目录初始化
if not os.path.exists(IP_DIR): os.makedirs(IP_DIR)

# ===============================
# 2. 核心功能函数
# ===============================

def is_reachable(ip_port):
    """仅测试 TCP 端口连通性"""
    try:
        ip, port = ip_port.split(':')
        with socket.create_connection((ip, int(port)), timeout=2):
            return True
    except:
        return False

def get_rtp_list(session, ip, tk):
    """访问 getall.php 接口获取 RTP 列表，p=2 固定"""
    api_url = f"http://foodieguide.com/iptvsearch/getall.php?ip={ip}&tk={tk}&p=2"
    try:
        res = session.get(api_url, timeout=10)
        # 匹配格式：频道名,rtp://地址
        matches = re.findall(r'(.*?),rtp://([\d\.\:]+)', res.text)
        return matches
    except:
        return []

# ===============================
# 3. 主程序逻辑
# ===============================

def run():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_combined_channels = []
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> 开始抓取 (翻页:page, 数据:p=2)")

    # --- 第一阶段：解析网页并获取源数据 ---
    for page in range(1, PAGES_TO_SCAN + 1):
        print(f"正在处理第 {page} 页...")
        try:
            res = session.get(f"{BASE_URL}?page={page}", timeout=20)
            res.encoding = 'utf-8'
            
            # 正则提取 IP, TK 和地域信息
            pattern = re.compile(r'ip=([\d\.]+)&tk=([a-f0-9]+).*?<i>(.*?)</i>', re.S)
            items = pattern.findall(res.text)
            
            for ip, tk, info in items:
                # 严格过滤电信
                if TARGET_ISP in info:
                    # 提取省市作为标签
                    tag_match = re.search(r'(\w+省\w+市|\w+市)', info)
                    tag = (tag_match.group(1) + "电信") if tag_match else "电信节点"
                    
                    # 获取该 IP 下的 RTP 列表
                    rtp_data = get_rtp_list(session, ip, tk)
                    if not rtp_data: continue
                    
                    # 取第一个通道测试 IP:Port 连通性
                    test_addr = rtp_data[0][1] 
                    if is_reachable(test_addr):
                        print(f"  [有效] {tag} ({test_addr})")
                        # 记录有效源
                        for name, rtp in rtp_data:
                            std_name = ALIAS_INDEX.get(name, name)
                            final_url = f"http://{test_addr.split(':')[0]}:{test_addr.split(':')[1]}/rtp/{rtp}"
                            all_combined_channels.append({
                                "name": std_name, 
                                "url": final_url, 
                                "region": tag
                            })
                    else:
                        print(f"  [断开] {tag} ({test_addr})")
        except Exception as e:
            print(f"  ❌ 第 {page} 页出错: {e}")

    # --- 第二阶段：排序去重并生成文件 ---
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> 正在生成最终文件 {OUTPUT_FILE}...")
    
    bj_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # 头部
        f.write(f"更新时间: {bj_time}（北京时间）\n\n更新时间,#genre#\n{bj_time},http://logo.mp4\n\n")
        
        # 按分类写入
        for category, std_names in CHANNEL_CATEGORIES.items():
            f.write(f"{category},#genre#\n")
            for target in std_names:
                # 筛选属于该标准的频道
                sources = [c for c in all_combined_channels if c["name"] == target]
                # 写入前 N 个
                for item in sources[:MAX_SOURCES_PER_CHANNEL]:
                    f.write(f"{item['name']},{item['url']}${item['region']}\n")
            f.write("\n")

        # 其他频道
        f.write("其他频道,#genre#\n")
        all_std = [n for sub in CHANNEL_CATEGORIES.values() for n in sub]
        others = [c for c in all_combined_channels if c["name"] not in all_std]
        # 简单去重
        unique_names = sorted(list(set([o["name"] for o in others])))
        for ot_name in unique_names:
            ot_sources = [o for o in others if o["name"] == ot_name]
            for item in ot_sources[:2]: # 其他频道每个只留2个源
                f.write(f"{item['name']},{item['url']}${item['region']}\n")

    print(f"✅ 完成！共收集到 {len(all_combined_channels)} 条有效线路。")

if __name__ == "__main__":
    run()
