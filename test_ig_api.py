#!/usr/bin/env python3
"""
测试 Instagram120 API 端点
"""

import requests
import json

RAPIDAPI_KEY = "17d0e288d7msh5355181d7156fe1p146aabjsneee5f190c89e"
RAPIDAPI_HOST = "instagram120.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}/api/instagram"

headers = {
    "Content-Type": "application/json",
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST
}

def test_profile(username):
    """测试 profile 端点"""
    print(f"\n=== 测试 profile: {username} ===")
    url = f"{BASE_URL}/profile"
    payload = {"username": username}

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Keys: {list(data.keys())}")
        # 提取关键信息
        if 'result' in data:
            result = data['result']
            print(f"\n用户信息:")
            print(f"  ID: {result.get('id', 'N/A')}")
            print(f"  用户名: {result.get('username', 'N/A')}")
            print(f"  全名: {result.get('full_name', 'N/A')}")
            print(f"  粉丝数: {result.get('follower_count', 'N/A')}")
            print(f"  关注数: {result.get('following_count', 'N/A')}")
            print(f"  帖子数: {result.get('media_count', 'N/A')}")
            print(f"  简介: {result.get('biography', 'N/A')[:100]}")
        return data
    else:
        print(f"Error: {response.text[:500]}")
        return None

def test_posts(username, max_id=""):
    """测试 posts 端点"""
    print(f"\n=== 测试 posts: {username} ===")
    url = f"{BASE_URL}/posts"
    payload = {"username": username, "maxId": max_id}

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Keys: {list(data.keys())}")

        if 'result' in data and 'edges' in data['result']:
            edges = data['result']['edges']
            print(f"\n帖子数量: {len(edges)}")

            for i, edge in enumerate(edges[:3]):  # 只显示前3条
                node = edge.get('node', {})
                caption = node.get('caption', {})
                caption_text = caption.get('text', '') if caption else ''

                print(f"\n帖子 {i+1}:")
                print(f"  ID: {node.get('pk', 'N/A')}")
                print(f"  Code: {node.get('code', 'N/A')}")
                print(f"  发布时间: {node.get('taken_at', 'N/A')}")
                print(f"  描述: {caption_text[:50]}...")

                # 查找互动数据
                print(f"  点赞数: {node.get('like_count', 'N/A')}")
                print(f"  评论数: {node.get('comment_count', 'N/A')}")
                print(f"  播放数: {node.get('play_count', 'N/A')}")
                print(f"  浏览数: {node.get('view_count', 'N/A')}")

        return data
    else:
        print(f"Error: {response.text[:500]}")
        return None

if __name__ == "__main__":
    # 测试 Instagram 官方账号
    test_profile("instagram")
    test_posts("instagram")
