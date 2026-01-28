import os
import re
import requests
import time
import socket
from datetime import datetime, timezone, timedelta
import yaml
from collections import defaultdict

BASE_URL = "http://foodieguide.com/iptvsearch/iptvmulticast.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"}
IP_DIR = "IP_Lists"
YAML_FILE = "iptv_sources.yml"
MAX_PAGES = 5
REQUEST_INTERVAL = 0.8  # 稍慢点防封

def get_tag(host):
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
        try:
            res = requests.get(f"http://ip-api.com/json/{host}?lang=zh-CN", timeout=5).json()
            if res.get("status") == "success":
                region = res.get("regionName", "未知")
                isp = res.get("isp", "").lower()
                isp_name = "电信" if "chinanet" in isp or "电信" in isp else \
                           "联通" if "unicom" in isp or "联通" in isp else \
                           "移动" if "mobile" in isp or "移动" in isp else "其他"
                return f"{region}{isp_name}"
        except:
            return "未知IP"
    else:
        return f"域名:{host.split('.')[0]}"

def test_connectivity(host_port, timeout=3):
    try:
        host, port = host_port.split(':', 1)
        start = time.time()
        with socket.create_connection((host, int(port)), timeout=timeout):
            return round((time.time() - start) * 1000)
    except:
        return None

def save_host(tag, host_port):
    os.makedirs(IP_DIR, exist_ok=True)
    path = os.path.join(IP_DIR, f"{tag}.txt")
    hosts = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            hosts = {line.strip() for line in f if line.strip()}
    if host_port not in hosts:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{host_port}\n")
        print(f"新增 {tag:<14} → {host_port}")

def main():
    session = requests.Session()
    all_alive = []  # (tag, host_port, delay)
    found_count = 0

    print("抓取 foodieguide 组播源...")

    for page in range(1, MAX_PAGES + 1):
        print(f"→ 第 {page} 页")
        try:
            res = session.get(f"{BASE_URL}?p={page}", headers=HEADERS, timeout=15)
            entries = re.findall(r"channellist\.html\?ip=([a-zA-Z0-9\.\-:]+)&tk=([a-f0-9]+)&p?=\d*", res.text)
            for host, tk in entries:
                data_url = f"http://foodieguide.com/iptvsearch/getall.php?ip={host}&tk={tk}&p={page}"
                raw = session.get(data_url, headers={"Referer": f"{BASE_URL}?p={page}", **HEADERS}, timeout=10).text
                m = re.search(r'http://([a-zA-Z0-9\.\-:]+)/rtp/', raw)
                if m:
                    host_port = m.group(1)
                    tag = get_tag(host_port.split(':', 1)[0])
                    delay = test_connectivity(host_port)
                    if delay is not None:
                        save_host(tag, host_port)
                        all_alive.append((tag, host_port, delay))
                        print(f"存活 {delay:4}ms  {tag:<14} → {host_port}")
                        found_count += 1
                time.sleep(REQUEST_INTERVAL)
        except Exception as e:
            print(f"异常: {e}")

    now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    print(f"\n完成！找到 {found_count} 个可用源")

    # 生成 YAML
    grouped = defaultdict(list)
    for tag, hp, d in all_alive:
        grouped[tag].append({"host": hp, "delay_ms": d, "alive": True})

    yaml_data = {
        "metadata": {
            "updated_at": now + " (北京时间)",
            "total_alive": found_count,
            "pages_scraped": MAX_PAGES,
            "source": "foodieguide.com/iptvsearch"
        },
        "sources": {}
    }
    for tag in sorted(grouped):
        yaml_data["sources"][tag] = sorted(grouped[tag], key=lambda x: x["delay_ms"])

    with open(YAML_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_data, f, allow_unicode=True, sort_keys=False)

    print(f"生成 {YAML_FILE}")

if __name__ == "__main__":
    main()
