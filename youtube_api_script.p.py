import googleapiclient.discovery
import json

# 在这里替换成您的API Key
API_KEY = "..." 
VIDEO_ID = "G3F1dbgBFsQ"  # 在这里替换成您要查询的视频ID

def get_youtube_data(api_key, video_id, max_comment_results_per_page=100, total_comments_limit=500):
    """
    获取YouTube视频的基本信息和评论。

    Args:
        api_key (str): 您的YouTube Data API Key。
        video_id (str): 要查询的YouTube视频ID。
        max_comment_results_per_page (int): 每次API请求获取的最大评论数（1-100）。
        total_comments_limit (int): 设定的评论总获取上限，防止无限循环和超出配额。

    Returns:
        dict: 包含视频信息和评论数据的字典。如果发生错误，可能返回部分数据或None。
    """
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    
    video_data = {}
    all_comments = []

    # --- 1. 获取视频基本信息 ---
    print(f"--- 正在获取视频 '{video_id}' 的基本信息 ---")
    try:
        video_request = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        )
        video_response = video_request.execute()

        if not video_response['items']:
            print(f"错误：未能找到视频 ID 为 '{video_id}' 的视频。")
            return None

        item = video_response['items'][0]
        video_data = {
            'title': item['snippet']['title'],
            'publishedAt': item['snippet']['publishedAt'],
            'description': item['snippet']['description'],
            'channelTitle': item['snippet']['channelTitle'],
            'viewCount': item['statistics'].get('viewCount', 0),
            'likeCount': item['statistics'].get('likeCount', 0),
            'commentCount': item['statistics'].get('commentCount', 0)
        }
        print(f"视频标题: {video_data['title']}")
        print(f"发布日期: {video_data['publishedAt']}")
        print(f"频道名称: {video_data['channelTitle']}")
        print(f"观看次数: {video_data['viewCount']}")
        print(f"点赞次数: {video_data['likeCount']}")
        print(f"评论总数 (API报告): {video_data['commentCount']}")

    except Exception as e:
        print(f"获取视频信息时发生错误: {e}")
        # 即使获取视频信息失败，也尝试获取评论，如果可能的话
        
    print("\n--- 正在获取视频评论 ---")
    # --- 2. 获取视频评论 ---
    next_page_token = None
    comments_fetched = 0

    try:
        while comments_fetched < total_comments_limit:
            comment_request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=max_comment_results_per_page,
                pageToken=next_page_token,
                textFormat="plainText"
            )
            comment_response = comment_request.execute()

            for item in comment_response['items']:
                comment_snippet = item['snippet']['topLevelComment']['snippet']
                all_comments.append({
                    "comment_id": item['id'], # 评论线程ID
                    "author": comment_snippet['authorDisplayName'],
                    "text": comment_snippet['textDisplay'],
                    "published_at": comment_snippet['publishedAt'],
                    "like_count": comment_snippet['likeCount'],
                    "reply_count": item['snippet']['totalReplyCount'] # 该评论的回复数量
                })
                comments_fetched += 1
                if comments_fetched >= total_comments_limit:
                    break # 达到上限，停止获取

            next_page_token = comment_response.get('nextPageToken')

            if not next_page_token:
                print("已获取所有可用的评论 (或达到API分页末尾)。")
                break
            
            print(f"已获取 {comments_fetched} 条评论，继续获取...")

    except Exception as e:
        print(f"获取评论时发生错误: {e}")
        print("注意：API配额可能已用尽，或视频禁用了评论。")

    print(f"\n--- 获取完成 ---")
    print(f"共实际获取到 {len(all_comments)} 条评论。")

    # 将所有数据组织成一个字典
    full_data = {
        "video_info": video_data,
        "comments": all_comments
    }
    return full_data

# --- 主程序执行 ---
if __name__ == "__main__":
    # 您可以根据需要调整每次请求和总体的评论数量
    # max_comment_results_per_page 建议设置为100（API最大值）
    # total_comments_limit 可以设置为几百到几千，根据您的研究需求和API配额
    retrieved_data = get_youtube_data(
        API_KEY, 
        VIDEO_ID, 
        max_comment_results_per_page=100, 
        total_comments_limit=500
    )

    if retrieved_data:
        # 可以选择将所有数据保存到JSON文件
        output_filename = f"youtube_data_{VIDEO_ID}.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(retrieved_data, f, ensure_ascii=False, indent=4)
        print(f"\n所有数据已保存到 '{output_filename}' 文件。")

        # 也可以在这里直接处理或打印部分评论
        print("\n--- 示例：打印前5条评论 ---")
        for i, comment in enumerate(retrieved_data['comments'][:5]):
            print(f"\n评论 {i+1}:")
            print(f"  作者: {comment['author']}")
            print(f"  时间: {comment['published_at']}")
            print(f"  点赞: {comment['like_count']}")
            print(f"  内容: {comment['text']}")
    else:
        print("未能成功获取数据。请检查视频ID和API Key是否正确，并确认API配额充足。")
