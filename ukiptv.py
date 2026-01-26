import os
import re
import requests
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
IP_DIR = "IP_Lists"
OUTPUT_FILE = "ukiptv.txt"
PAGES_TO_SCAN = 3  
TARGET_ISP = "电信"    # 严格过滤，仅保留电信

# --- 频道映射与分类 ---
# (您可以根据需要在此处扩充 CHANNEL_CATEGORIES 和 CHANNEL_MAPPING)
CHANNEL_CATEGORIES = {
   "央视频道": ["CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV13"],
   "卫视频道": ["湖南卫视", "浙江卫视", "江苏卫视", "东方卫视"]
}

CHANNEL_MAPPING = {
    "CCTV1": ["CCTV-1", "CCTV1综合", "CCTV1高清"],
    "CCTV13": ["CCTV-13", "CCTV13新闻", "CCTV13高清"],
    "湖南卫视": ["湖南卫视", "湖南高清"]
}
ALIAS_INDEX = {alias: std for std, aliases in CHANNEL_MAPPING.items() for alias in aliases}

if not os.path.exists(IP_DIR): os.makedirs(IP_DIR)

# ===============================
# 2. 核心功能函数
# ===============================

def is_reachable(ip_port):
    """测试端口连通性"""
    try:
        ip, port = ip_port.split(':')
        with socket.create_connection((ip, int(port)), timeout=2):
            return True
    except:
        return False

def get_rtp_list(session, ip, tk, page):
    """固定使用 p=2 获取 RTP 列表"""
    api_url = f"http://foodieguide.com/iptvsearch/getall.php?ip={ip}&tk={tk}&p=2"
    try:
        res = session.get(api_url, timeout=10)
        # 匹配格式: 频道名,rtp://地址
        return re.findall(r'([^,\n]+),rtp://([\d\.\:]+)', res.text)
    except:
        return []

# ===============================
# 3. 主程序逻辑
# ===============================

def run():
    session = requests.Session()
    session.headers.update(HEADERS)
    all_combined_channels = []
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> 启动抓取 | 目标运营商: {TARGET_ISP}")

    for page in range(1, PAGES_TO_SCAN + 1):
        print(f"正在扫描第 {page} 页...")
        try:
            # 搜索翻页 page=
            res = session.get(f"{BASE_URL}?page={page}", timeout=20)
            res.encoding = 'utf-8'
            html = res.text

            # 精准匹配: ip, tk 以及 <i> 标签内容
            pattern = re.compile(r'ip=([\d\.]+)&tk=([a-f0-9]+).*?<i>(.*?)</i>', re.S)
            items = pattern.findall(html)
            
            for ip, tk, info_html in items:
                # 过滤掉 HTML 标签和多余空白
                info_text = re.sub(r'<.*?>', '', info_html).replace('&nbsp;', ' ').strip()
                
                # 核心过滤: 必须包含“电信”
                if TARGET_ISP in info_text:
                    # 提取地域标签 (如: 江苏常州电信)
                    tag_match = re.search(r'(\w+省\w+市|\w+市)', info_text)
                    tag = (tag_match.group(1) + "电信") if tag_match else "其他电信"
                    
                    # 抓取 RTP 列表 (固定 p=2)
                    rtp_data = get_rtp_list(session, ip, tk, page)
                    if not rtp_data: continue
                    
                    # 连通性测试 (仅测第一个源)
                    test_addr = rtp_data[0][1]
                    if is_reachable(test_addr):
                        print(f"  [发现有效电信源] {tag} -> {test_addr}")
                        for name, rtp in rtp_data:
                            std_name = ALIAS_INDEX.get(name.strip(), name.strip())
                            all_combined_channels.append({
                                "name": std_name,
                                "url": f"http://{test_addr}/rtp/{rtp}",
                                "region": tag
                            })
                    else:
                        print(f"  [不可用] {tag} ({test_addr})")
        except Exception as e:
            print(f"  ❌ 页码 {page} 处理异常")

    # --- 生成结果文件 ---
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> 正在生成 {OUTPUT_FILE}...")
    bj_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"更新时间: {bj_time}（北京时间）\n\n更新时间,#genre#\n{bj_time},http://logo.mp4\n\n")
        
        for category, std_names in CHANNEL_CATEGORIES.items():
            f.write(f"{category},#genre#\n")
            for target in std_names:
                sources = [c for c in all_combined_channels if c["name"] == target]
                for item in sources[:4]: # 每频道留4个源
                    f.write(f"{item['name']},{item['url']}${item['region']}\n")
            f.write("\n")

    print(f"✅ 任务完成！共捕获 {len(all_combined_channels)} 条电信线路。")

if __name__ == "__main__":
    run()
