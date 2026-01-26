import os, re, requests, socket
from datetime import datetime, timezone, timedelta

# ===============================
# 1. 核心配置区
# ===============================
BASE_URL = "http://foodieguide.com/iptvsearch/iptvmulticast.php"
# 必须使用与 PHP 调试一致的 Referer
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://foodieguide.com/iptvsearch/"
}
OUTPUT_FILE = "ukiptv.txt"
PAGES_TO_SCAN = 5
TARGET_ISP = "电信"

# 频道映射
CHANNEL_MAPPING = {
    "CCTV1": ["CCTV-1", "CCTV1综合", "CCTV1高清"],
    "CCTV13": ["CCTV-13", "CCTV13新闻"],
    "湖南卫视": ["湖南卫视", "湖南高清"]
}
ALIAS_INDEX = {alias: std for std, aliases in CHANNEL_MAPPING.items() for alias in aliases}

# ===============================
# 2. 核心功能
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
            res = session.get(f"{BASE_URL}?page={page}", timeout=20)
            res.encoding = 'utf-8'
            html = res.text

            # --- 核心改进：参照 PHP 成功逻辑的正则 ---
            # 允许 tk 后面有任何字符 ([^']*)，直到遇到单引号
            pattern = re.compile(r"ip=([\d\.]+)&tk=([a-f0-9]+)[^']*?'.*?<i>(.*?)</i>", re.S)
            items = pattern.findall(html)
            
            if not items:
                print(f"  [调试] 第 {page} 页正则未匹配到内容。")
                continue

            for ip, tk, info_html in items:
                # 清洗 ISP 信息
                info_text = re.sub(r'\s+', ' ', re.sub(r'<.*?>', '', info_html)).strip()
                
                if TARGET_ISP in info_text:
                    # 获取 RTP 列表 (固定 p=2)
                    api_url = f"http://foodieguide.com/iptvsearch/getall.php?ip={ip}&tk={tk}&p=2"
                    try:
                        data_res = session.get(api_url, timeout=15).text
                        # 匹配 频道名,rtp://ip:port
                        rtp_matches = re.findall(r'([^,\n\r]+),rtp://([\d\.\:]+)', data_res)
                        
                        if rtp_matches:
                            test_addr = rtp_matches[0][1]
                            if is_reachable(test_addr):
                                print(f"  ✅ [有效] {ip} ({info_text.split()[-1]})")
                                for name, rtp in rtp_matches:
                                    std_name = ALIAS_INDEX.get(name.strip(), name.strip())
                                    all_combined_channels.append(f"{std_name},http://{test_addr}/rtp/{rtp}")
                            else:
                                print(f"  ❌ [断开] {ip}")
                    except: continue
        except Exception as e:
            print(f"  ⚠️ 页码 {page} 访问失败")

    # --- 写入文件 ---
    if all_combined_channels:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("电信列表,#genre#\n")
            # 简单去重并写入
            for line in sorted(list(set(all_combined_channels))):
                f.write(line + "\n")
        print(f"✅ 完成！共抓取 {len(all_combined_channels)} 条线路。")
    else:
        # 为了防止 GitHub Actions 提交报错，即使为空也创建一个空文件
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("未发现有效线路")
        print("最终未发现有效线路。")

if __name__ == "__main__":
    run()
