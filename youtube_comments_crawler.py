# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""
YouTube视频评论爬虫脚本
使用YouTube Data API v3获取视频评论
"""

import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

import httpx


def extract_video_id(url: str) -> Optional[str]:
    """
    从YouTube URL中提取视频ID
    
    Args:
        url: YouTube视频URL，支持多种格式：
            - https://youtu.be/JxPe3ZPjvIs
            - https://www.youtube.com/watch?v=JxPe3ZPjvIs
            - https://youtube.com/watch?v=JxPe3ZPjvIs&si=...
    
    Returns:
        视频ID，如果无法提取则返回None
    """
    # 匹配 youtu.be 格式
    match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # 匹配 youtube.com/watch?v= 格式
    match = re.search(r'(?:youtube\.com/watch\?v=|youtube\.com/embed/)([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # 使用urllib解析
    parsed = urlparse(url)
    if 'youtu.be' in parsed.netloc:
        return parsed.path.lstrip('/')
    elif 'youtube.com' in parsed.netloc:
        query_params = parse_qs(parsed.query)
        if 'v' in query_params:
            return query_params['v'][0]
    
    return None


class YouTubeCommentsCrawler:
    """YouTube评论爬虫类"""
    
    def __init__(self, api_key: str):
        """
        初始化爬虫
        
        Args:
            api_key: Google API Key (YouTube Data API v3)
        """
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_video_info(self, video_id: str) -> Optional[Dict]:
        """
        获取视频基本信息
        
        Args:
            video_id: YouTube视频ID
        
        Returns:
            视频信息字典
        """
        url = f"{self.base_url}/videos"
        params = {
            "part": "snippet,statistics",
            "id": video_id,
            "key": self.api_key
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("items"):
                item = data["items"][0]
                return {
                    "video_id": video_id,
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "published_at": item["snippet"]["publishedAt"],
                    "view_count": item["statistics"].get("viewCount", 0),
                    "like_count": item["statistics"].get("likeCount", 0),
                    "comment_count": item["statistics"].get("commentCount", 0),
                }
        except Exception as e:
            print(f"获取视频信息失败: {e}")
            return None
    
    async def get_comments(self, video_id: str, max_results: int = 100, 
                          order: str = "relevance") -> List[Dict]:
        """
        获取视频评论
        
        Args:
            video_id: YouTube视频ID
            max_results: 最大获取评论数量（默认100，API限制单次最多100）
            order: 排序方式，可选值：time（时间）、relevance（相关性）
        
        Returns:
            评论列表
        """
        all_comments = []
        next_page_token = None
        total_fetched = 0
        
        print(f"开始获取视频 {video_id} 的评论...")
        
        while total_fetched < max_results:
            # 计算本次请求的数量
            current_max = min(100, max_results - total_fetched)  # API单次最多100条
            
            url = f"{self.base_url}/commentThreads"
            params = {
                "part": "snippet,replies",
                "videoId": video_id,
                "maxResults": current_max,
                "order": order,
                "key": self.api_key
            }
            
            if next_page_token:
                params["pageToken"] = next_page_token
            
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # 处理评论数据
                items = data.get("items", [])
                for item in items:
                    top_level_comment = item["snippet"]["topLevelComment"]["snippet"]
                    
                    comment_data = {
                        "comment_id": item["snippet"]["topLevelComment"]["id"],
                        "author_name": top_level_comment["authorDisplayName"],
                        "author_channel_id": top_level_comment.get("authorChannelId", {}).get("value", ""),
                        "text": top_level_comment["textDisplay"],
                        "like_count": top_level_comment.get("likeCount", 0),
                        "published_at": top_level_comment["publishedAt"],
                        "updated_at": top_level_comment.get("updatedAt", ""),
                        "reply_count": item["snippet"].get("totalReplyCount", 0),
                        "replies": []
                    }
                    
                    # 获取回复评论
                    if "replies" in item:
                        for reply in item["replies"]["comments"]:
                            reply_snippet = reply["snippet"]
                            comment_data["replies"].append({
                                "comment_id": reply["id"],
                                "author_name": reply_snippet["authorDisplayName"],
                                "author_channel_id": reply_snippet.get("authorChannelId", {}).get("value", ""),
                                "text": reply_snippet["textDisplay"],
                                "like_count": reply_snippet.get("likeCount", 0),
                                "published_at": reply_snippet["publishedAt"],
                                "updated_at": reply_snippet.get("updatedAt", ""),
                                "parent_id": reply_snippet.get("parentId", "")
                            })
                    
                    all_comments.append(comment_data)
                    total_fetched += 1
                
                # 检查是否有下一页
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break
                
                print(f"已获取 {total_fetched} 条评论...")
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", "API访问被拒绝")
                    print(f"API访问错误: {error_msg}")
                    print("请检查：")
                    print("1. API Key是否正确")
                    print("2. 是否已启用YouTube Data API v3")
                    print("3. API配额是否已用完")
                else:
                    print(f"HTTP错误: {e.response.status_code} - {e.response.text}")
                break
            except Exception as e:
                print(f"获取评论时出错: {e}")
                break
        
        print(f"共获取 {len(all_comments)} 条评论")
        return all_comments
    
    async def save_comments(self, video_info: Dict, comments: List[Dict], 
                           output_dir: str = "data/youtube") -> str:
        """
        保存评论到JSON文件
        
        Args:
            video_info: 视频信息
            comments: 评论列表
            output_dir: 输出目录
        
        Returns:
            保存的文件路径
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_id = video_info["video_id"]
        filename = f"{output_dir}/youtube_comments_{video_id}_{timestamp}.json"
        
        # 组织数据
        output_data = {
            "video_info": video_info,
            "comments_count": len(comments),
            "crawled_at": datetime.now().isoformat(),
            "comments": comments
        }
        
        # 保存文件
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"评论已保存到: {filename}")
        return filename
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


async def main():
    """主函数"""
    # ==================== 配置区域 ====================
    # 视频URL（支持多种格式）
    VIDEO_URL = "https://youtu.be"
    
    # Google API Key (YouTube Data API v3)pip install youtube-transcript-api
    # 获取方式：
    # 1. 访问 https://console.cloud.google.com/
    # 2. 创建项目或选择现有项目
    # 3. 启用 YouTube Data API v3
    # 4. 创建凭据（API密钥）
    API_KEY = "...."  # ⚠️ 请在此处填入您的Google API Key
    
    # 最大获取评论数量（API限制：单次最多100条，脚本会自动分页获取）
    MAX_COMMENTS = 200
    
    # 评论排序方式：time（按时间排序）或 relevance（按相关性排序，默认）
    ORDER = "relevance"
    # ================================================
    
    # 检查API Key
    if not API_KEY:
        print("=" * 60)
        print("错误: 请先设置API_KEY变量")
        print("=" * 60)
        print("\n使用步骤：")
        print("1. 打开脚本文件 youtube_comments_crawler.py")
        print("2. 找到 main() 函数中的 API_KEY 变量")
        print("3. 将您的Google API Key填入: API_KEY = '您的API Key'")
        print("\n获取API Key：")
        print("1. 访问 https://console.cloud.google.com/")
        print("2. 创建项目或选择现有项目")
        print("3. 启用 YouTube Data API v3")
        print("4. 创建凭据（API密钥）")
        print("=" * 60)
        sys.exit(1)
    
    # 提取视频ID
    video_id = extract_video_id(VIDEO_URL)
    if not video_id:
        print(f"错误: 无法从URL中提取视频ID: {VIDEO_URL}")
        sys.exit(1)
    
    print(f"视频ID: {video_id}")
    print(f"视频URL: {VIDEO_URL}")
    print("-" * 50)
    
    # 创建爬虫实例
    crawler = YouTubeCommentsCrawler(api_key=API_KEY)
    
    try:
        # 获取视频信息
        print("正在获取视频信息...")
        video_info = await crawler.get_video_info(video_id)
        if video_info:
            print(f"视频标题: {video_info['title']}")
            print(f"频道: {video_info['channel_title']}")
            print(f"发布时间: {video_info['published_at']}")
            print(f"观看次数: {video_info['view_count']}")
            print(f"点赞数: {video_info['like_count']}")
            print(f"评论数: {video_info['comment_count']}")
            print("-" * 50)
        
        # 获取评论
        comments = await crawler.get_comments(video_id, max_results=MAX_COMMENTS, order=ORDER)
        
        if comments:
            # 保存评论
            output_file = await crawler.save_comments(video_info or {"video_id": video_id}, comments)
            print(f"\n成功! 共获取 {len(comments)} 条评论")
            print(f"数据已保存到: {output_file}")
        else:
            print("未获取到任何评论")
    
    finally:
        await crawler.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

