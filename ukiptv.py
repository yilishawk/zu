import os
import re
import requests
import socket
from datetime import datetime, timezone, timedelta

# ===============================
# 1. 核心配置区
# ===============================
BASE_URL = "http://foodieguide.com/iptvsearch/iptvmulticast.php"
# 这里的 Referer 必须与 PHP 调试成功的一致
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://foodieguide.com/iptvsearch/"
}
IP_DIR = "ip"
OUTPUT_FILE = "ukiptv.txt"
PAGES_TO_SCAN = 5      # 扫描页数
TARGET_ISP = "电信"

# 频道分类与映射逻辑
CHANNEL_CATEGORIES = {
   "央视频道": ["CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV13", "CCTV16"],
   "卫视频道": ["湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视"]
}
CHANNEL_MAPPING = {
    "CCTV1综合": "CCTV1", "CCTV-1": "CCTV1", "CCTV1高清": "CCTV1",
    "CCTV13新闻": "CCTV13", "CCTV-13": "CCTV13",
    "湖南卫视高清": "湖南卫视", "湖南高清": "湖南卫视"
}

if not os.path.exists(IP_DIR): os.makedirs(IP_DIR)

# ===============================
# 2. 功能函数
# ===============================

def is_reachable(ip_port):
    """TCP 连通性测试"""
    try:
        ip, port = ip_port.split(':')
        with socket.create_connection((ip, int(port)), timeout=2):
            return True
    except:
        return False

def run():
    session = requests.Session()
    session.headers.update(HEADERS)
    all_combined_channels = []
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> 开始正式抓取...")

    for page in range(1, PAGES_TO_SCAN + 1):
        print(f"正在扫描第 {page} 页...")
        try:
            # 1. 请求搜索页 (page=参数)
            res = session.get(f"{BASE_URL}?page={page}", timeout=20)
            res.encoding = 'utf-8'
            
            # 2. 改进后的正则：精准匹配 ip, tk 和 <i> 标签
            # 匹配逻辑：找 ip=...&tk=... 直到引号结束，然后找后续 <i> 内容
            pattern = re.compile(r"ip=([\d\.]+)&tk=([a-f0-9]+).*?<i>(.*?)</i>", re.S)
            items = pattern.findall(res.text)
            
            if not items:
                print(f"  [调试] 第 {page} 页未匹配到节点。")
                continue

            for ip, tk, info_html in items:
                # 清洗归属地信息
                info_text = re.sub(r'\s+', ' ', re.sub(r'<.*?>', '', info_html)).strip()
                
                # 3. 只取电信
                if TARGET_ISP in info_text:
                    tag_match = re.search(r'(\w+省\w+市|\w+市)', info_text)
                    tag = (tag_match.group(1) + "电信") if tag_match else "电信节点"
                    
                    # 4. 请求 getall 接口 (固定 p=2)
                    api_url = f"http://foodieguide.com/iptvsearch/getall.php?ip={ip}&tk={tk}&p=2"
                    try:
                        data_res = session.get(api_url, timeout=15).text
                        # 匹配 频道,rtp://ip:port
                        rtp_matches = re.findall(r'([^,\n\r]+),rtp://([\d\.\:]+)', data_res)
                        
                        if rtp_matches:
                            # 提取第一个源的 IP:Port 进行测活
                            test_addr = rtp_matches[0][1]
                            if is_reachable(test_addr):
                                print(f"  ✅ [有效] {tag} -> {test_addr}")
                                for name, rtp in rtp_matches:
                                    clean_name = name.strip()
                                    std_name = CHANNEL_MAPPING.get(clean_name, clean_name)
                                    all_combined_channels.append({
                                        "name": std_name,
                                        "url": f"http://{test_addr}/rtp/{rtp}",
                                        "region": tag
                                    })
                            else:
                                print(f"  ❌ [断开] {tag} ({test_addr})")
                    except: continue
        except Exception as e:
            print(f"  ⚠️ 页码 {page} 处理异常")

    # --- 生成 ukiptv.txt ---
    if not all_combined_channels:
        print("最终未发现有效线路。")
        return

    print(f"\n>>> 正在写入最终列表...")
    bj_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"更新时间: {bj_time}（北京时间）\n\n更新时间,#genre#\n{bj_time},http://logo.mp4\n\n")
        
        for category, std_names in CHANNEL_CATEGORIES.items():
            f.write(f"{category},#genre#\n")
            # 去重处理，避免同名频道刷屏
            for target in std_names:
                sources = [c for c in all_combined_channels if c["name"] == target]
                for item in sources[:4]: # 每个频道保留4个电信源
                    f.write(f"{item['name']},{item['url']}${item['region']}\n")
            f.write("\n")

    print(f"✅ 完成！已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
