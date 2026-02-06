import requests
import re
import json
import urllib3
import subprocess
import os

# 屏蔽安全警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置区 ---
BC_CONFIG_URL = 'https://bc.188766.xyz/?ip=&haiwai=true'
MIGU_M3U_URL = 'https://raw.githubusercontent.com/develop202/migu_video/main/interface.txt'
CATVOD_URL = 'https://kwyili.dpdns.org/catvod.php'
BC_UA = 'bingcha/1.1 (mianfeifenxiang)'
BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def get_content_advanced(url, ua=BROWSER_UA):
    """
    尝试多种方式下载内容，解决 GitHub Actions 被屏蔽的问题
    """
    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,en;q=0.5,en-US;q=0.3',
        'Referer': 'https://live.catvod.com/',
        'Connection': 'keep-alive'
    }

    # 方法 A: requests
    try:
        r = requests.get(url, headers=headers, timeout=20, verify=False)
        r.encoding = 'utf-8'
        if r.status_code == 200 and "#EXTM3U" in r.text:
            print(f"成功获取: {url}")
            return r.text
        else:
            print(f"请求 {url} 返回状态码: {r.status_code}")
    except Exception as e:
        print(f"Requests 访问 {url} 出错: {e}")

    # 方法 B: curl 备选
    try:
        print(f"尝试使用系统 curl 下载 {url}...")
        result = subprocess.run(
            ['curl', '-k', '-L', '-H', f'User-Agent: {ua}', '-H', 'Referer: https://live.catvod.com/', url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and "#EXTM3U" in result.stdout:
            return result.stdout
    except Exception as e:
        print(f"Curl 访问 {url} 出错: {e}")
    
    return None

def parse_m3u(content, prefix, include_filter=None, rename_map=None):
    if not content: return {}
    groups = {}
    
    # 使用正则匹配 #EXTINF 行和紧随其后的 URL 行
    pattern = re.compile(r'(#EXTINF:[^\n]+)\n+(http[^\s\n]+)', re.MULTILINE)
    matches = pattern.findall(content)

    for inf, url in matches:
        # 过滤广告和提示
        if any(x in inf for x in ['公告', '分享', '奸商', '提示', '微信', '扫码']):
            continue

        # 提取 group-title
        group_match = re.search(r'group-title="([^"]*)"', inf)
        original_group = group_match.group(1) if group_match else "其他"

        # 过滤关键词
        if include_filter and not any(f in original_group for f in include_filter):
            continue

        # 映射逻辑
        target_group = rename_map.get(original_group, original_group) if rename_map else original_group
        final_group_name = f"{prefix} {target_group}"
        
        # 重新生成 INF 行，确保组名统一
        new_inf = re.sub(r'group-title="[^"]*"', f'group-title="{final_group_name}"', inf)
        
        groups.setdefault(final_group_name, []).append(f"{new_inf}\n{url}")
    
    return groups

def main():
    # 1. 冰茶源
    print("正在处理冰茶源...")
    bc_raw = get_content_advanced(BC_CONFIG_URL, BC_UA)
    bc_groups = {}
    if bc_raw:
        try:
            data = json.loads(bc_raw)
            bc_url = data.get('lives', [{}])[0].get('url')
            if bc_url:
                bc_groups = parse_m3u(get_content_advanced(bc_url, BC_UA), "冰茶", rename_map={"粤语频道": "香港台"})
        except Exception as e:
            print(f"冰茶源解析失败: {e}")

    # 2. 咪咕源
    print("正在处理咪咕源...")
    migu_groups = parse_m3u(get_content_advanced(MIGU_M3U_URL), "咪咕")

    # 3. CatVod 源
    print("正在处理 CatVod 源...")
    cat_raw = get_content_advanced(CATVOD_URL)
    catvod_groups = {}
    if cat_raw:
        catvod_groups = parse_m3u(cat_raw, "Cat", include_filter=["中国", "香港", "台湾"], rename_map={"中国": "央视频道"})
    else:
        print("警告: CatVod 抓取失败，将不包含此来源。")

    # 4. 合并与排序
    all_groups = {**bc_groups, **migu_groups, **catvod_groups}
    if not all_groups:
        print("错误: 未能抓取到任何有效的频道数据，停止写入文件以防止覆盖旧数据。")
        return

    # 定义显示顺序
    priority = ['冰茶 央视频道', '咪咕 央视频道', 'Cat 央视频道', '冰茶 卫视频道', '咪咕 卫视频道', 'Cat 香港', '冰茶 香港台', 'Cat 台湾']

    final_output = ["#EXTM3U x-tvg-url=\"https://static.188766.xyz/e.xml\"\n"]
    
    # 按优先级放入
    for p in priority:
        if p in all_groups:
            for item in all_groups[p]:
                final_output.append(item + "\n")
            del all_groups[p]

    # 剩下的按字母排序放入
    for g in sorted(all_groups.keys()):
        for item in all_groups[g]:
            final_output.append(item + "\n")

    # 写入文件
    with open('live.m3u', 'w', encoding='utf-8') as f:
        f.write("".join(final_output))

    print(f"处理完成！生成频道总数: {len(final_output)-1}")

if __name__ == "__main__":
    main()
