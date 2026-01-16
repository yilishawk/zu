import os
import re
import requests
import time
import subprocess
import concurrent.futures
from datetime import datetime, timezone, timedelta

# ===============================
# 配置区
# ===============================
# 搜索语句：server="udpxy" && country="CN" && region="Shaanxi"
FOFA_URL = "https://fofa.info/result?qbase64=c2VydmVyPSJ1ZHB4eSIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0iU2hhYW54aSI%3D"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 陕西地区 RTP 频道模板（根据实际情况增删）
# 格式: 频道名,rtp地址
RTP_TEMPLATES = [
    "CCTV1,rtp://239.49.8.19:9614",
    "CCTV5,rtp://239.49.8.18:9610",
    "陕西卫视,rtp://239.49.8.48:8000",
    "西安综合,rtp://239.49.1.50:8000",
]

OUTPUT_FILE = "Shaanxi_IPTV.txt"

# ===============================
# 功能函数
# ===============================

def check_stream(url, timeout=6):
    """使用 ffprobe 探测流是否真实可用"""
    try:
        # 探测流信息，只要能读取到 streams 就算成功
        cmd = ["ffprobe", "-v", "error", "-show_streams", "-i", url]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return b"codec_type" in result.stdout
    except:
        return False

def get_isp(ip):
    """简单识别运营商"""
    try:
        # 使用 ip-api 免费接口
        r = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5).json()
        return r.get("isp", "未知")
    except:
        return "未知"

# ===============================
# 主逻辑
# ===============================

def main():
    # 1. 爬取 FOFA 页面
    print("📡 正在从 FOFA 提取陕西 udpxy 节点...")
    try:
        res = requests.get(FOFA_URL, headers=HEADERS, timeout=15)
        # 模仿原脚本的正则提取：寻找页面中所有的 http://IP:PORT
        found_ips = re.findall(r'http://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)', res.text)
        all_nodes = list(set(found_ips))
        print(f"✅ 提取到 {len(all_nodes)} 个唯一节点")
    except Exception as e:
        print(f"❌ 爬取异常: {e}")
        return

    if not all_nodes:
        print("⚠️ 未找到任何节点，请检查 FOFA 页面是否触发验证码。")
        return

    # 2. 多线程检测
    print(f"🚀 启动多线程检测（并发10）...")
    valid_results = []
    
    def verify_node(node):
        # 挑选 CCTV1 作为探测代表
        test_url = f"http://{node}/rtp/239.49.8.19:9614"
        if check_stream(test_url):
            isp = get_isp(node.split(':')[0])
            print(f"🟢 发现存活节点: {node} ({isp})")
            # 存活则组合全量频道
            node_links = []
            for item in RTP_TEMPLATES:
                name, rtp = item.split(',')
                rtp_path = rtp.replace("rtp://", "")
                final_url = f"http://{node}/rtp/{rtp_path}"
                node_links.append(f"{name},{final_url}${isp}")
            return node_links
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(verify_node, n) for n in all_nodes]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                valid_results.extend(res)

    # 3. 写出文件
    bj_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"陕西 udpxy 自动更新,#genre#\n")
        f.write(f"更新时间：{bj_time},http://0.0.0.0\n")
        for line in valid_results:
            f.write(f"{line}\n")
    
    print(f"🎯 任务完成！有效链接：{len(valid_results)} 条。")

if __name__ == "__main__":
    main()

