"""
数据采集模块 - Instagram, TikTok, YouTube 数据采集器

支持平台:
- Instagram (Instagram120 RapidAPI)
- TikTok (TikTok-API23 RapidAPI)
- YouTube (YouTube Data API v3)
"""

import os
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

# Import API config module for database-driven API keys
from .api_config import get_api_key, get_api_host, is_platform_enabled

# Use Supabase if configured, otherwise fall back to SQLite
if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
    from .supabase_db import get_db, Account, Post, PostMetrics, AccountMetrics
    db = get_db()
else:
    from .database import db, Account, Post, PostMetrics, AccountMetrics


class BaseCollector(ABC):
    """采集器基类"""

    def __init__(self):
        self.platform = ""
        self.api_key = ""

    @abstractmethod
    def fetch_account_info(self, username: str) -> Optional[Dict]:
        """获取账号信息"""
        pass

    @abstractmethod
    def fetch_account_posts(self, username: str, limit: int = 20) -> List[Dict]:
        """获取账号的帖子列表"""
        pass

    @abstractmethod
    def fetch_post_metrics(self, post_id: str) -> Optional[Dict]:
        """获取单个帖子的指标"""
        pass

    def collect_account(self, username: str) -> Optional[Account]:
        """
        采集账号数据并保存到数据库
        """
        print(f"[{self.platform}] 正在采集账号: {username}")

        # 获取账号信息
        account_data = self.fetch_account_info(username)
        if not account_data:
            print(f"[{self.platform}] 无法获取账号信息: {username}")
            return None

        # 检查账号是否已存在
        existing = db.get_account(self.platform, username)
        if existing:
            # 更新账号信息
            existing.display_name = account_data.get('display_name', existing.display_name)
            existing.follower_count = account_data.get('follower_count', existing.follower_count)
            existing.following_count = account_data.get('following_count', existing.following_count)
            existing.post_count = account_data.get('post_count', existing.post_count)
            existing.bio = account_data.get('bio', existing.bio)
            db.update_account(existing)
            account = existing
            print(f"[{self.platform}] 已更新账号: {username}")
        else:
            # 创建新账号
            account = Account(
                id=None,
                platform=self.platform,
                username=username,
                display_name=account_data.get('display_name', username),
                account_id=account_data.get('account_id', ''),
                follower_count=account_data.get('follower_count', 0),
                following_count=account_data.get('following_count', 0),
                post_count=account_data.get('post_count', 0),
                bio=account_data.get('bio', '')
            )
            account.id = db.add_account(account)
            print(f"[{self.platform}] 已添加新账号: {username}")

        # 保存账号指标快照
        now = datetime.now().isoformat()
        account_metrics = AccountMetrics(
            id=None,
            account_id=account.id,
            collected_at=now,
            follower_count=account.follower_count,
            following_count=account.following_count,
            post_count=account.post_count
        )
        db.add_account_metrics(account_metrics)

        return account

    def collect_posts(self, username: str, limit: int = 20) -> List[Post]:
        """
        采集账号的帖子并保存到数据库
        """
        print(f"[{self.platform}] 正在采集帖子: {username} (最多 {limit} 条)")

        # 获取账号
        account = db.get_account(self.platform, username)
        if not account:
            print(f"[{self.platform}] 账号不存在，请先采集账号: {username}")
            return []

        # 获取帖子列表
        posts_data = self.fetch_account_posts(username, limit)
        if not posts_data:
            print(f"[{self.platform}] 无法获取帖子: {username}")
            return []

        posts = []
        now = datetime.now().isoformat()

        for post_data in posts_data:
            # 创建帖子记录
            post = Post(
                id=None,
                account_id=account.id,
                platform=self.platform,
                post_id=post_data.get('post_id', ''),
                post_type=post_data.get('post_type', 'video'),
                caption=post_data.get('caption', ''),
                published_at=post_data.get('published_at', ''),
                url=post_data.get('url', ''),
                thumbnail_url=post_data.get('thumbnail_url', '')
            )
            post.id = db.add_post(post)
            posts.append(post)

            # 保存帖子指标
            metrics = PostMetrics(
                id=None,
                post_id=post.id,
                collected_at=now,
                views=post_data.get('views', 0),
                likes=post_data.get('likes', 0),
                comments=post_data.get('comments', 0),
                shares=post_data.get('shares', 0),
                saves=post_data.get('saves', 0),
                plays=post_data.get('plays', 0),
                reach=post_data.get('reach', 0),
                impressions=post_data.get('impressions', 0)
            )
            db.add_post_metrics(metrics)

        print(f"[{self.platform}] 已采集 {len(posts)} 条帖子")
        return posts

    def collect_all(self, username: str, post_limit: int = 20) -> Dict:
        """
        完整采集：账号 + 帖子 + 指标
        """
        result = {
            'account': None,
            'posts': [],
            'success': False,
            'message': ''
        }

        try:
            # 采集账号
            account = self.collect_account(username)
            if not account:
                result['message'] = f"无法获取账号信息: {username}"
                return result

            result['account'] = account

            # 采集帖子
            posts = self.collect_posts(username, post_limit)
            result['posts'] = posts
            result['success'] = True
            result['message'] = f"成功采集账号 {username}，共 {len(posts)} 条帖子"

        except Exception as e:
            result['message'] = f"采集失败: {str(e)}"

        return result


class InstagramCollector(BaseCollector):
    """
    Instagram 数据采集器

    使用 Instagram120 RapidAPI
    API 文档: https://rapidapi.com/3205/api/instagram120
    """

    def __init__(self):
        super().__init__()
        self.platform = "instagram"
        # API 配置 - from database or env vars
        self.api_key = get_api_key('instagram')
        self.rapidapi_host = get_api_host('instagram') or "instagram120.p.rapidapi.com"
        self.base_url = f"https://{self.rapidapi_host}/api/instagram"

    def _get_headers(self) -> Dict:
        """获取 API 请求头"""
        return {
            "Content-Type": "application/json",
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.rapidapi_host
        }

    def fetch_account_info(self, username: str) -> Optional[Dict]:
        """
        获取 Instagram 账号信息
        """
        if not self.api_key:
            print("[Instagram] 未配置 API Key (INSTAGRAM_API_KEY)")
            return None

        try:
            url = f"{self.base_url}/profile"
            payload = {"username": username}

            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                result = data.get('result', {})

                # 解析粉丝数等数据
                follower_count = result.get('edge_followed_by', {}).get('count', 0)
                following_count = result.get('edge_follow', {}).get('count', 0)
                media_count = result.get('edge_owner_to_timeline_media', {})
                post_count = media_count.get('count', 0) if isinstance(media_count, dict) else media_count

                return {
                    'account_id': str(result.get('id', '')),
                    'display_name': result.get('full_name', username),
                    'follower_count': follower_count,
                    'following_count': following_count,
                    'post_count': post_count,
                    'bio': result.get('biography', '')
                }
            else:
                print(f"[Instagram] API 错误 {response.status_code}: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[Instagram] 请求异常: {e}")
            return None

    def fetch_account_posts(self, username: str, limit: int = 20) -> List[Dict]:
        """
        获取 Instagram 账号的帖子
        """
        if not self.api_key:
            print("[Instagram] 未配置 API Key (INSTAGRAM_API_KEY)")
            return []

        posts = []
        max_id = ""

        try:
            while len(posts) < limit:
                url = f"{self.base_url}/posts"
                payload = {"username": username, "maxId": max_id}

                response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)

                if response.status_code != 200:
                    print(f"[Instagram] API 错误 {response.status_code}: {response.text[:200]}")
                    break

                data = response.json()
                result = data.get('result', {})
                edges = result.get('edges', [])

                if not edges:
                    break

                for edge in edges:
                    if len(posts) >= limit:
                        break

                    node = edge.get('node', {})
                    caption_data = node.get('caption', {})
                    caption_text = caption_data.get('text', '') if caption_data else ''

                    # 判断帖子类型
                    post_type = 'image'
                    if node.get('is_video'):
                        post_type = 'video'
                    if node.get('product_type') == 'clips':
                        post_type = 'reel'

                    # 获取缩略图
                    thumbnail_url = ''
                    image_versions = node.get('image_versions2', {})
                    candidates = image_versions.get('candidates', [])
                    if candidates:
                        thumbnail_url = candidates[0].get('url', '')

                    # 转换时间戳
                    taken_at = node.get('taken_at', 0)
                    published_at = datetime.fromtimestamp(taken_at).isoformat() if taken_at else ''

                    post_code = node.get('code', '')

                    posts.append({
                        'post_id': str(node.get('pk', '')),
                        'post_type': post_type,
                        'caption': caption_text,
                        'published_at': published_at,
                        'url': f"https://www.instagram.com/p/{post_code}/" if post_code else '',
                        'thumbnail_url': thumbnail_url,
                        'views': node.get('view_count', 0) or node.get('play_count', 0) or 0,
                        'likes': node.get('like_count', 0) or 0,
                        'comments': node.get('comment_count', 0) or 0,
                        'shares': 0,  # Instagram API 不提供分享数
                        'saves': 0,   # 需要 Business API 才能获取
                        'plays': node.get('play_count', 0) or 0
                    })

                # 检查是否有更多数据
                page_info = result.get('page_info', {})
                if not page_info.get('has_next_page'):
                    break

                max_id = page_info.get('end_cursor', '')
                if not max_id:
                    break

        except Exception as e:
            print(f"[Instagram] 请求异常: {e}")

        return posts

    def fetch_post_metrics(self, post_id: str) -> Optional[Dict]:
        """
        获取单个帖子的指标
        注：Instagram120 API 不支持单独获取帖子指标，需要通过 posts 端点获取
        """
        return None


class TikTokCollector(BaseCollector):
    """
    TikTok 数据采集器

    使用 TikTok-API23 RapidAPI
    API 文档: https://rapidapi.com/tikapi-tikapi-default/api/tiktok-api23
    """

    def __init__(self):
        super().__init__()
        self.platform = "tiktok"
        # API 配置 - from database or env vars
        self.api_key = get_api_key('tiktok')
        self.rapidapi_host = get_api_host('tiktok') or "tiktok-api23.p.rapidapi.com"
        self.base_url = f"https://{self.rapidapi_host}/api"
        # 缓存 secUid
        self._sec_uid_cache = {}

    def _get_headers(self) -> Dict:
        """获取 API 请求头"""
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.rapidapi_host
        }

    def _get_sec_uid(self, username: str) -> Optional[str]:
        """获取用户的 secUid（用于获取视频列表）"""
        if username in self._sec_uid_cache:
            return self._sec_uid_cache[username]

        try:
            url = f"{self.base_url}/user/info"
            params = {"uniqueId": username}
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'userInfo' in data:
                    sec_uid = data['userInfo']['user'].get('secUid')
                    if sec_uid:
                        self._sec_uid_cache[username] = sec_uid
                        return sec_uid
        except Exception as e:
            print(f"[TikTok] 获取 secUid 失败: {e}")

        return None

    def fetch_account_info(self, username: str) -> Optional[Dict]:
        """
        获取 TikTok 账号信息
        """
        if not self.api_key:
            print("[TikTok] 未配置 API Key (TIKTOK_API_KEY)")
            return None

        try:
            url = f"{self.base_url}/user/info"
            params = {"uniqueId": username}

            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'userInfo' in data:
                    user_info = data['userInfo']
                    user = user_info.get('user', {})
                    stats = user_info.get('stats', {})

                    # 缓存 secUid
                    sec_uid = user.get('secUid')
                    if sec_uid:
                        self._sec_uid_cache[username] = sec_uid

                    return {
                        'account_id': str(user.get('id', '')),
                        'display_name': user.get('nickname', username),
                        'follower_count': stats.get('followerCount', 0),
                        'following_count': stats.get('followingCount', 0),
                        'post_count': stats.get('videoCount', 0),
                        'bio': user.get('signature', '')
                    }
            else:
                print(f"[TikTok] API 错误 {response.status_code}: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[TikTok] 请求异常: {e}")
            return None

    def fetch_account_posts(self, username: str, limit: int = 20) -> List[Dict]:
        """
        获取 TikTok 账号的视频
        """
        if not self.api_key:
            print("[TikTok] 未配置 API Key (TIKTOK_API_KEY)")
            return []

        # 获取 secUid
        sec_uid = self._get_sec_uid(username)
        if not sec_uid:
            print(f"[TikTok] 无法获取用户 {username} 的 secUid")
            return []

        posts = []
        cursor = "0"

        try:
            while len(posts) < limit:
                url = f"{self.base_url}/user/posts"
                params = {
                    "secUid": sec_uid,
                    "count": min(30, limit - len(posts)),
                    "cursor": cursor
                }

                response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

                if response.status_code != 200:
                    print(f"[TikTok] API 错误 {response.status_code}: {response.text[:200]}")
                    break

                data = response.json()

                # 处理不同的响应结构
                if 'data' in data and 'itemList' in data['data']:
                    items = data['data']['itemList']
                    has_more = data['data'].get('hasMore', False)
                    cursor = str(data['data'].get('cursor', '0'))
                elif 'itemList' in data:
                    items = data['itemList']
                    has_more = data.get('hasMore', False)
                    cursor = str(data.get('cursor', '0'))
                else:
                    break

                if not items:
                    break

                for item in items:
                    if len(posts) >= limit:
                        break

                    stats = item.get('stats', {})
                    create_time = item.get('createTime', 0)
                    published_at = datetime.fromtimestamp(create_time).isoformat() if create_time else ''

                    video_id = item.get('id', '')

                    posts.append({
                        'post_id': str(video_id),
                        'post_type': 'video',
                        'caption': item.get('desc', ''),
                        'published_at': published_at,
                        'url': f"https://www.tiktok.com/@{username}/video/{video_id}",
                        'thumbnail_url': item.get('video', {}).get('cover', ''),
                        'views': stats.get('playCount', 0) or 0,
                        'likes': stats.get('diggCount', 0) or 0,
                        'comments': stats.get('commentCount', 0) or 0,
                        'shares': stats.get('shareCount', 0) or 0,
                        'saves': stats.get('collectCount', 0) or 0,
                        'plays': stats.get('playCount', 0) or 0
                    })

                if not has_more:
                    break

        except Exception as e:
            print(f"[TikTok] 请求异常: {e}")

        return posts

    def fetch_post_metrics(self, post_id: str) -> Optional[Dict]:
        """
        获取单个视频的指标
        注：TikTok-API23 需要通过 posts 端点获取，暂不支持单独获取
        """
        return None


class TwitterCollector(BaseCollector):
    """
    X/Twitter 数据采集器

    使用 Twitter-API45 RapidAPI
    API 文档: https://rapidapi.com/alexanderxbx/api/twitter-api45
    """

    def __init__(self):
        super().__init__()
        self.platform = "twitter"
        # API 配置 - from database or env vars
        self.api_key = get_api_key('twitter')
        self.rapidapi_host = get_api_host('twitter') or "twitter-api45.p.rapidapi.com"
        self.base_url = f"https://{self.rapidapi_host}"

    def _get_headers(self) -> Dict:
        """获取 API 请求头"""
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.rapidapi_host
        }

    def fetch_account_info(self, username: str) -> Optional[Dict]:
        """
        获取 X/Twitter 账号信息
        """
        if not self.api_key:
            print("[Twitter] 未配置 API Key (TWITTER_API_KEY)")
            return None

        # 移除 @ 前缀
        username = username.lstrip('@')

        try:
            url = f"{self.base_url}/screenname.php"
            params = {"screenname": username}

            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # 获取粉丝数等数据 (API 使用 sub_count 和 friends)
                followers = int(data.get('sub_count', 0) or data.get('followers_count', 0) or data.get('followers', 0) or 0)
                following = int(data.get('friends', 0) or data.get('friends_count', 0) or data.get('following', 0) or 0)
                tweet_count = int(data.get('statuses_count', 0) or data.get('tweets', 0) or 0)

                return {
                    'account_id': str(data.get('rest_id', '') or data.get('id_str', '') or data.get('id', '')),
                    'display_name': data.get('name', username),
                    'follower_count': followers,
                    'following_count': following,
                    'post_count': tweet_count,
                    'bio': data.get('desc', '') or data.get('description', '')
                }
            else:
                print(f"[Twitter] API 错误 {response.status_code}: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[Twitter] 请求异常: {e}")
            return None

    def fetch_account_posts(self, username: str, limit: int = 20) -> List[Dict]:
        """
        获取 X/Twitter 账号的推文
        """
        if not self.api_key:
            print("[Twitter] 未配置 API Key (TWITTER_API_KEY)")
            return []

        # 移除 @ 前缀
        username = username.lstrip('@')

        posts = []

        try:
            # 使用 timeline 端点获取用户推文
            url = f"{self.base_url}/timeline.php"
            params = {"screenname": username}

            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

            if response.status_code != 200:
                print(f"[Twitter] API 错误 {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()

            # 处理不同的响应结构
            timeline = data.get('timeline', []) or data.get('tweets', []) or []
            if isinstance(data, list):
                timeline = data

            for item in timeline[:limit]:
                try:
                    # 解析推文数据
                    tweet_id = item.get('tweet_id') or item.get('id_str') or item.get('id', '')
                    if not tweet_id:
                        continue

                    # 获取文本内容
                    text = item.get('text') or item.get('full_text', '')

                    # 获取发布时间
                    created_at = item.get('created_at', '')
                    # 尝试转换时间格式
                    if created_at:
                        try:
                            # Twitter 时间格式: "Wed Oct 10 20:19:24 +0000 2018"
                            from datetime import datetime as dt
                            parsed_time = dt.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                            created_at = parsed_time.isoformat()
                        except:
                            pass

                    # 获取互动数据 (views 可能是字符串)
                    views_raw = item.get('views', 0)
                    views = int(views_raw) if views_raw else 0
                    likes = int(item.get('favorites', 0) or 0)
                    retweets = int(item.get('retweets', 0) or 0)
                    replies = int(item.get('replies', 0) or 0)
                    quotes = int(item.get('quotes', 0) or 0)
                    bookmarks = int(item.get('bookmarks', 0) or 0)

                    posts.append({
                        'post_id': str(tweet_id),
                        'post_type': 'tweet',
                        'caption': text,
                        'published_at': created_at,
                        'url': f"https://x.com/{username}/status/{tweet_id}",
                        'thumbnail_url': '',
                        'views': views,
                        'likes': likes,
                        'comments': replies,
                        'shares': retweets + quotes,  # 转发 + 引用
                        'saves': bookmarks,  # 使用书签作为收藏
                        'plays': views
                    })

                except Exception as e:
                    continue

        except Exception as e:
            print(f"[Twitter] 请求异常: {e}")

        return posts

    def fetch_post_metrics(self, post_id: str) -> Optional[Dict]:
        """
        获取单个推文的指标
        """
        # Twitter API45 不支持单独获取推文指标
        return None


class YouTubeCollector(BaseCollector):
    """
    YouTube 数据采集器

    使用 YouTube Data API v3
    API 文档: https://developers.google.com/youtube/v3/docs
    """

    def __init__(self):
        super().__init__()
        self.platform = "youtube"
        # API 配置 - from database or env vars
        self.api_key = get_api_key('youtube')
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def _get_channel_id(self, username: str) -> Optional[str]:
        """
        通过用户名或 handle 获取频道 ID
        支持: @handle, 频道名, 或直接传入频道ID (UC开头)
        """
        # 如果已经是频道ID格式
        if username.startswith('UC') and len(username) == 24:
            return username

        # 移除 @ 前缀
        handle = username.lstrip('@')

        try:
            # 方法1: 通过 handle 搜索
            url = f"{self.base_url}/search"
            params = {
                "key": self.api_key,
                "q": f"@{handle}",
                "type": "channel",
                "part": "snippet",
                "maxResults": 1
            }
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                if items:
                    return items[0]['snippet']['channelId']

            # 方法2: 通过 forHandle 参数
            url = f"{self.base_url}/channels"
            params = {
                "key": self.api_key,
                "forHandle": handle,
                "part": "id"
            }
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                if items:
                    return items[0]['id']

        except Exception as e:
            print(f"[YouTube] 获取频道ID失败: {e}")

        return None

    def fetch_account_info(self, username: str) -> Optional[Dict]:
        """
        获取 YouTube 频道信息
        """
        if not self.api_key:
            print("[YouTube] 未配置 API Key (YOUTUBE_API_KEY)")
            return None

        try:
            # 获取频道ID
            channel_id = self._get_channel_id(username)
            if not channel_id:
                print(f"[YouTube] 无法找到频道: {username}")
                return None

            # 获取频道详情
            url = f"{self.base_url}/channels"
            params = {
                "key": self.api_key,
                "id": channel_id,
                "part": "snippet,statistics"
            }

            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                if items:
                    channel = items[0]
                    snippet = channel.get('snippet', {})
                    stats = channel.get('statistics', {})

                    return {
                        'account_id': channel_id,
                        'display_name': snippet.get('title', username),
                        'follower_count': int(stats.get('subscriberCount', 0)),
                        'following_count': 0,  # YouTube 不显示关注数
                        'post_count': int(stats.get('videoCount', 0)),
                        'bio': snippet.get('description', '')[:500]  # 截断过长描述
                    }
            else:
                print(f"[YouTube] API 错误 {response.status_code}: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[YouTube] 请求异常: {e}")
            return None

    def fetch_account_posts(self, username: str, limit: int = 20) -> List[Dict]:
        """
        获取 YouTube 频道的视频
        """
        if not self.api_key:
            print("[YouTube] 未配置 API Key (YOUTUBE_API_KEY)")
            return []

        # 获取频道ID
        channel_id = self._get_channel_id(username)
        if not channel_id:
            print(f"[YouTube] 无法找到频道: {username}")
            return []

        posts = []
        next_page_token = None

        try:
            while len(posts) < limit:
                # 搜索频道的视频
                url = f"{self.base_url}/search"
                params = {
                    "key": self.api_key,
                    "channelId": channel_id,
                    "part": "snippet",
                    "type": "video",
                    "order": "date",
                    "maxResults": min(50, limit - len(posts))
                }
                if next_page_token:
                    params["pageToken"] = next_page_token

                response = requests.get(url, params=params, timeout=30)

                if response.status_code != 200:
                    print(f"[YouTube] API 错误 {response.status_code}: {response.text[:200]}")
                    break

                data = response.json()
                items = data.get('items', [])

                if not items:
                    break

                # 获取视频ID列表
                video_ids = [item['id']['videoId'] for item in items if item.get('id', {}).get('videoId')]

                if video_ids:
                    # 批量获取视频统计数据
                    stats_url = f"{self.base_url}/videos"
                    stats_params = {
                        "key": self.api_key,
                        "id": ",".join(video_ids),
                        "part": "statistics,snippet,contentDetails"
                    }
                    stats_response = requests.get(stats_url, params=stats_params, timeout=30)

                    if stats_response.status_code == 200:
                        stats_data = stats_response.json()
                        video_stats = {v['id']: v for v in stats_data.get('items', [])}

                        for item in items:
                            if len(posts) >= limit:
                                break

                            video_id = item.get('id', {}).get('videoId')
                            if not video_id:
                                continue

                            snippet = item.get('snippet', {})
                            stats = video_stats.get(video_id, {}).get('statistics', {})

                            published_at = snippet.get('publishedAt', '')

                            posts.append({
                                'post_id': video_id,
                                'post_type': 'video',
                                'caption': snippet.get('title', ''),
                                'published_at': published_at,
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                                'views': int(stats.get('viewCount', 0)),
                                'likes': int(stats.get('likeCount', 0)),
                                'comments': int(stats.get('commentCount', 0)),
                                'shares': 0,  # YouTube API 不提供分享数
                                'saves': 0,   # YouTube 没有收藏概念
                                'plays': int(stats.get('viewCount', 0))
                            })

                # 检查是否有下一页
                next_page_token = data.get('nextPageToken')
                if not next_page_token:
                    break

        except Exception as e:
            print(f"[YouTube] 请求异常: {e}")

        return posts

    def fetch_post_metrics(self, post_id: str) -> Optional[Dict]:
        """
        获取单个视频的指标
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/videos"
            params = {
                "key": self.api_key,
                "id": post_id,
                "part": "statistics"
            }
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                if items:
                    stats = items[0].get('statistics', {})
                    return {
                        'views': int(stats.get('viewCount', 0)),
                        'likes': int(stats.get('likeCount', 0)),
                        'comments': int(stats.get('commentCount', 0)),
                        'shares': 0,
                        'saves': 0
                    }
        except Exception as e:
            print(f"[YouTube] 获取视频指标失败: {e}")

        return None


# 采集器工厂
def get_collector(platform: str) -> BaseCollector:
    """获取对应平台的采集器"""
    collectors = {
        'instagram': InstagramCollector,
        'tiktok': TikTokCollector,
        'youtube': YouTubeCollector,
        'twitter': TwitterCollector
    }

    if platform not in collectors:
        raise ValueError(f"不支持的平台: {platform}")

    return collectors[platform]()


def collect_all_accounts(platform: str = None, post_limit: int = 20) -> List[Dict]:
    """
    采集所有账号的数据
    """
    results = []

    accounts = db.get_all_accounts(platform)
    if not accounts:
        print("没有找到要采集的账号")
        return results

    for account in accounts:
        collector = get_collector(account.platform)
        result = collector.collect_all(account.username, post_limit)
        results.append({
            'platform': account.platform,
            'username': account.username,
            **result
        })

    return results
