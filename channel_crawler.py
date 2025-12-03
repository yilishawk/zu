#!/usr/bin/env python3
"""
直播源整理爬虫 (Python版)
功能：从指定URL获取直播源数据，按规则整理分组，保留多源
"""

import re
import requests
from typing import Dict, List, Tuple
from urllib.parse import urlparse

class LiveStreamCrawler:
    def __init__(self):
        self.url = 'https://freetv.fun/test_channels_new.txt'
        self.raw_content = ''
        self.parsed_data = {}
        self.final_groups = {}
        
    def fetch_data(self) -> None:
        """获取远程数据"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            self.raw_content = response.text
        except requests.RequestException as e:
            print(f"获取数据失败: {e}")
            exit(1)
    
    def parse_data(self) -> None:
        """解析原始数据"""
        current_group = ''
        
        for line in self.raw_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 检测是否是分组行
            if '#genre#' in line:
                current_group = line
                self.parsed_data[current_group] = []
                continue
            
            # 如果是频道行
            if current_group and ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    title, url = parts
                    self.parsed_data[current_group].append({
                        'title': title.strip(),
                        'url': url.strip(),
                        'original_title': title.strip()
                    })
    
    def clean_title(self, title: str) -> str:
        """清理频道标题"""
        # 去除(backup)、(h265)等后缀
        patterns = [
            r'\s*\(backup\)', r'\s*\(h265\)', r'\s*\(h264\)',
            r'\s*\(备用\)', r'\s*\(备\)', r'\s*\[.*?\]'
        ]
        
        clean_title = title
        for pattern in patterns:
            clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
        
        return clean_title.strip()
    
    def get_cctv_weight(self, title: str) -> int:
        """获取CCTV频道排序权重"""
        clean_title = self.clean_title(title)
        
        # 提取CCTV后面的数字
        cctv_match = re.match(r'^CCTV[-\s]?(\d+)', clean_title, re.IGNORECASE)
        if cctv_match:
            return int(cctv_match.group(1))
        
        # 为特殊CCTV频道分配权重
        special_weights = {
            'CCTV 8K': 100,
            'CCTV-Documentary': 101,
            'CCTV-戲曲': 102,
            'CCTV第一劇場': 103,
            'CCTV風雲足球': 104,
            'CCTV第一剧场': 103,
            'CCTV风云足球': 104,
        }
        
        for pattern, weight in special_weights.items():
            if clean_title.startswith(pattern):
                return weight
        
        # 其他CCTV频道放在最后
        if clean_title.startswith('CCTV'):
            return 999
        
        # 非CCTV频道
        return 1000
    
    def process_cctv_channels(self) -> None:
        """处理所有分组中的CCTV频道"""
        all_cctv_channels = {}
        
        # 遍历所有分组，提取CCTV频道
        for group_name, channels in self.parsed_data.items():
            for channel in channels:
                clean_title = self.clean_title(channel['title'])
                
                # 判断是否为CCTV频道
                if clean_title.startswith('CCTV'):
                    weight = self.get_cctv_weight(clean_title)
                    
                    # 检查是否已存在相同的标题和URL组合
                    key = f"{clean_title}|{channel['url']}"
                    if key not in all_cctv_channels:
                        all_cctv_channels[key] = {
                            'title': clean_title,
                            'url': channel['url'],
                            'original_title': channel['original_title'],
                            'weight': weight
                        }
        
        # 按权重排序（CCTV1,2,3...的顺序）
        sorted_channels = sorted(
            all_cctv_channels.values(),
            key=lambda x: (x['weight'], x['title'])
        )
        
        # 添加到央视分组
        if sorted_channels:
            self.final_groups['央视,#genre#'] = sorted_channels
    
    def process_mainland_china(self) -> None:
        """处理中国大陆分组（去除CCTV频道后）"""
        mainland_key = '中國大陸,#genre#'
        if mainland_key not in self.parsed_data:
            return
        
        channels = self.parsed_data[mainland_key]
        
        # 提取所有CCTV标题用于过滤
        cctv_titles = set()
        if '央视,#genre#' in self.final_groups:
            for cctv_channel in self.final_groups['央视,#genre#']:
                cctv_titles.add(cctv_channel['title'])
        
        satellite_group = []  # 卫视组
        city_groups = {}      # 城市分组
        xian_group = []       # 西安分组
        other_channels = []   # 其他频道
        
        # 先收集所有频道，然后按规则分组
        for channel in channels:
            clean_title = self.clean_title(channel['title'])
            
            # 跳过CCTV频道（已经提取到央视分组）
            if clean_title in cctv_titles:
                continue
            
            new_channel = {
                'title': clean_title,
                'url': channel['url'],
                'original_title': channel['original_title']
            }
            
            # 先判断是否为西安频道（优先级最高）
            if '西安' in clean_title:
                xian_group.append(new_channel)
                continue
            
            # 判断是否为卫视频道
            if '衛視' in clean_title or '卫视' in clean_title:
                satellite_group.append(new_channel)
                continue
            
            # 判断是否为城市频道（如"哈爾濱娛樂"、"哈爾濱影視"）
            city_match = re.match(r'^([\u4e00-\u9fa5]+)[娛樂影視]', clean_title)
            if city_match:
                city_name = city_match.group(1)
                if city_name not in city_groups:
                    city_groups[city_name] = []
                city_groups[city_name].append(new_channel)
                continue
            
            # 其他频道
            other_channels.append(new_channel)
        
        # 添加西安分组
        if xian_group:
            self.final_groups['西安,#genre#'] = xian_group
        
        # 添加卫视组
        if satellite_group:
            self.final_groups['卫视,#genre#'] = satellite_group
        
        # 添加城市分组（各省地方台）
        sorted_city_names = sorted(city_groups.keys())
        for city_name in sorted_city_names:
            # 跳过西安，因为西安已经单独分组
            if city_name != '西安':
                self.final_groups[f"{city_name},#genre#"] = city_groups[city_name]
        
        # 添加其他频道
        if other_channels:
            self.final_groups['中國大陸其他,#genre#'] = other_channels
    
    def process_hong_kong(self) -> None:
        """处理香港分组"""
        hk_key = '香港,#genre#'
        if hk_key not in self.parsed_data:
            return
        
        channels = self.parsed_data[hk_key]
        phoenix_channels = []
        other_hk_channels = []
        
        for channel in channels:
            clean_title = self.clean_title(channel['title'])
            new_channel = {
                'title': clean_title,
                'url': channel['url'],
                'original_title': channel['original_title']
            }
            
            # 判断是否为凤凰频道
            phoenix_keywords = ['鳳凰衛視中文', '鳳凰資訊', '凤凰卫视中文', '凤凰资讯']
            if any(keyword in clean_title for keyword in phoenix_keywords):
                phoenix_channels.append(new_channel)
            else:
                other_hk_channels.append(new_channel)
        
        # 合并凤凰频道和其他香港频道
        final_hk_channels = phoenix_channels + other_hk_channels
        if final_hk_channels:
            self.final_groups[hk_key] = final_hk_channels
    
    def process_taiwan(self) -> None:
        """处理台湾分组"""
        tw_key = '台灣,#genre#'
        if tw_key not in self.parsed_data:
            return
        
        channels = self.parsed_data[tw_key]
        priority_channels = []
        other_tw_channels = []
        
        for channel in channels:
            clean_title = self.clean_title(channel['title'])
            new_channel = {
                'title': clean_title,
                'url': channel['url'],
                'original_title': channel['original_title']
            }
            
            # 判断是否为优先频道（新闻、综合、娱乐）
            priority_keywords = ['新聞', '綜合', '娛樂', '新闻', '综合', '娱乐']
            if any(keyword in clean_title for keyword in priority_keywords):
                priority_channels.append(new_channel)
            else:
                other_tw_channels.append(new_channel)
        
        # 合并优先频道和其他台湾频道
        final_tw_channels = priority_channels + other_tw_channels
        if final_tw_channels:
            self.final_groups[tw_key] = final_tw_channels
    
    def run(self) -> None:
        """执行完整的处理流程"""
        self.fetch_data()
        self.parse_data()
        
        # 处理所有分组
        self.process_cctv_channels()
        self.process_mainland_china()
        self.process_hong_kong()
        self.process_taiwan()
        
        # 按指定顺序输出
        self.output_result()
    
    def output_result(self) -> None:
        """按指定顺序输出结果"""
        output_lines = []
        
        # 按指定顺序定义分组
        ordered_groups = [
            '央视,#genre#',
            '西安,#genre#',
            '香港,#genre#',
            '卫视,#genre#',
            '台灣,#genre#',
            '中國大陸其他,#genre#'
        ]
        
        # 先输出固定顺序的分组
        for group_name in ordered_groups:
            if group_name in self.final_groups and self.final_groups[group_name]:
                output_lines.append(group_name)
                for channel in self.final_groups[group_name]:
                    output_lines.append(f"{channel['title']},{channel['url']}")
                output_lines.append("")
        
        # 输出各省地方台分组（排除已处理的）
        processed_groups = set(ordered_groups)
        
        for group_name, channels in self.final_groups.items():
            # 跳过已处理的分组
            if group_name in processed_groups:
                continue
            
            # 只输出以城市名开头的分组（各省地方台）
            if channels and re.match(r'^[\u4e00-\u9fa5]+,#genre#$', group_name):
                output_lines.append(group_name)
                for channel in channels:
                    output_lines.append(f"{channel['title']},{channel['url']}")
                output_lines.append("")
        
        # 输出结果
        print('\n'.join(output_lines))

def main():
    """主函数"""
    try:
        crawler = LiveStreamCrawler()
        crawler.run()
    except Exception as e:
        print(f"程序执行出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
