"""
Supabase Database Module - Cloud database for social media data

Uses Supabase (PostgreSQL) instead of local SQLite.
Maintains the same interface as database.py for compatibility.
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from supabase import create_client, Client

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')  # Use service_role key for write access


@dataclass
class Account:
    """Account data model"""
    id: Optional[str]  # UUID in Supabase
    platform: str
    username: str
    display_name: str
    account_id: str
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    bio: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Post:
    """Post/video data model"""
    id: Optional[str]  # UUID in Supabase
    account_id: str    # UUID reference
    platform: str
    post_id: str       # Platform-specific post ID
    post_type: str
    caption: str
    published_at: str
    url: str
    thumbnail_url: str = ""
    created_at: str = ""


@dataclass
class PostMetrics:
    """Post metrics snapshot"""
    id: Optional[str]
    post_id: str       # UUID reference
    collected_at: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    plays: int = 0
    reach: int = 0
    impressions: int = 0


@dataclass
class AccountMetrics:
    """Account metrics snapshot"""
    id: Optional[str]
    account_id: str    # UUID reference
    collected_at: str
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_views: int = 0


class SupabaseDatabase:
    """Supabase database operations - same interface as SQLite Database class"""

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "Supabase credentials not configured. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
            )
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ===== Account Operations =====

    def add_account(self, account: Account) -> str:
        """Add or update account, returns account ID (UUID)"""
        now = datetime.now().isoformat()

        data = {
            'platform': account.platform,
            'username': account.username,
            'display_name': account.display_name,
            'account_id': account.account_id,
            'follower_count': account.follower_count,
            'following_count': account.following_count,
            'post_count': account.post_count,
            'bio': account.bio,
            'updated_at': now
        }

        # Check if exists
        existing = self.get_account(account.platform, account.username)
        if existing:
            # Update
            result = self.client.table('accounts').update(data).eq('id', existing.id).execute()
            return existing.id
        else:
            # Insert
            data['created_at'] = now
            result = self.client.table('accounts').insert(data).execute()
            return result.data[0]['id']

    def get_account(self, platform: str, username: str) -> Optional[Account]:
        """Get account by platform and username"""
        result = self.client.table('accounts').select('*').eq(
            'platform', platform
        ).eq('username', username).execute()

        if result.data:
            return self._row_to_account(result.data[0])
        return None

    def get_account_by_id(self, account_id: str) -> Optional[Account]:
        """Get account by ID"""
        result = self.client.table('accounts').select('*').eq('id', account_id).execute()

        if result.data:
            return self._row_to_account(result.data[0])
        return None

    def get_all_accounts(self, platform: str = None) -> List[Account]:
        """Get all accounts, optionally filtered by platform"""
        query = self.client.table('accounts').select('*')

        if platform:
            query = query.eq('platform', platform)

        result = query.order('created_at', desc=True).execute()
        return [self._row_to_account(row) for row in result.data]

    def update_account(self, account: Account):
        """Update account info"""
        now = datetime.now().isoformat()

        data = {
            'display_name': account.display_name,
            'follower_count': account.follower_count,
            'following_count': account.following_count,
            'post_count': account.post_count,
            'bio': account.bio,
            'updated_at': now
        }

        self.client.table('accounts').update(data).eq('id', account.id).execute()

    def delete_account(self, account_id: str):
        """Delete account and all related data (cascades in Supabase)"""
        self.client.table('accounts').delete().eq('id', account_id).execute()

    # ===== Post Operations =====

    def add_post(self, post: Post) -> str:
        """Add post, returns post ID (UUID)"""
        now = datetime.now().isoformat()

        # Check if post already exists
        existing = self.client.table('posts').select('id').eq(
            'platform', post.platform
        ).eq('post_id', post.post_id).execute()

        if existing.data:
            return existing.data[0]['id']

        data = {
            'account_id': post.account_id,
            'platform': post.platform,
            'post_id': post.post_id,
            'post_type': post.post_type,
            'caption': post.caption,
            'published_at': post.published_at if post.published_at else None,
            'url': post.url,
            'thumbnail_url': post.thumbnail_url,
            'created_at': now
        }

        result = self.client.table('posts').insert(data).execute()
        return result.data[0]['id']

    def get_posts_by_account(self, account_id: str, limit: int = 50) -> List[Post]:
        """Get posts for an account"""
        result = self.client.table('posts').select('*').eq(
            'account_id', account_id
        ).order('published_at', desc=True).limit(limit).execute()

        return [self._row_to_post(row) for row in result.data]

    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """Get post by ID"""
        result = self.client.table('posts').select('*').eq('id', post_id).execute()

        if result.data:
            return self._row_to_post(result.data[0])
        return None

    # ===== Metrics Operations =====

    def add_post_metrics(self, metrics: PostMetrics) -> str:
        """Add post metrics snapshot"""
        data = {
            'post_id': metrics.post_id,
            'collected_at': metrics.collected_at,
            'views': metrics.views,
            'likes': metrics.likes,
            'comments': metrics.comments,
            'shares': metrics.shares,
            'saves': metrics.saves
        }

        result = self.client.table('post_metrics').insert(data).execute()
        return result.data[0]['id']

    def add_account_metrics(self, metrics: AccountMetrics) -> str:
        """Add account metrics snapshot"""
        data = {
            'account_id': metrics.account_id,
            'collected_at': metrics.collected_at,
            'follower_count': metrics.follower_count,
            'following_count': metrics.following_count,
            'post_count': metrics.post_count,
            'total_views': metrics.total_views,
            'total_likes': metrics.total_likes
        }

        result = self.client.table('account_metrics').insert(data).execute()
        return result.data[0]['id']

    def get_post_metrics_history(self, post_id: str, limit: int = 10) -> List[PostMetrics]:
        """Get metrics history for a post"""
        result = self.client.table('post_metrics').select('*').eq(
            'post_id', post_id
        ).order('collected_at', desc=True).limit(limit).execute()

        return [self._row_to_post_metrics(row) for row in result.data]

    def get_latest_post_metrics(self, post_id: str) -> Optional[PostMetrics]:
        """Get latest metrics for a post"""
        result = self.client.table('post_metrics').select('*').eq(
            'post_id', post_id
        ).order('collected_at', desc=True).limit(1).execute()

        if result.data:
            return self._row_to_post_metrics(result.data[0])
        return None

    def get_account_metrics_history(self, account_id: str, limit: int = 10) -> List[AccountMetrics]:
        """Get metrics history for an account"""
        result = self.client.table('account_metrics').select('*').eq(
            'account_id', account_id
        ).order('collected_at', desc=True).limit(limit).execute()

        return [self._row_to_account_metrics(row) for row in result.data]

    # ===== Stats Queries =====

    def get_posts_with_latest_metrics(self, account_id: str = None,
                                       platform: str = None,
                                       limit: int = 50) -> List[Dict]:
        """Get posts with their latest metrics"""
        # Use the view we created in Supabase
        query = self.client.table('posts_with_metrics').select('*')

        if account_id:
            query = query.eq('account_id', account_id)
        if platform:
            query = query.eq('platform', platform)

        result = query.order('published_at', desc=True).limit(limit).execute()
        return result.data

    def get_collection_summary(self) -> Dict:
        """Get data collection summary"""
        # Get accounts by platform
        accounts = self.client.table('accounts').select('platform').execute()
        accounts_by_platform = {}
        for acc in accounts.data:
            p = acc['platform']
            accounts_by_platform[p] = accounts_by_platform.get(p, 0) + 1

        # Get posts by platform
        posts = self.client.table('posts').select('platform').execute()
        posts_by_platform = {}
        for post in posts.data:
            p = post['platform']
            posts_by_platform[p] = posts_by_platform.get(p, 0) + 1

        # Get last collection time
        metrics = self.client.table('post_metrics').select('collected_at').order(
            'collected_at', desc=True
        ).limit(1).execute()
        last_collected = metrics.data[0]['collected_at'] if metrics.data else None

        return {
            'accounts_by_platform': accounts_by_platform,
            'posts_by_platform': posts_by_platform,
            'last_collected': last_collected,
            'collection_count': len(posts.data)
        }

    # ===== Helper Methods =====

    def _row_to_account(self, row: Dict) -> Account:
        """Convert database row to Account object"""
        return Account(
            id=row.get('id'),
            platform=row.get('platform', ''),
            username=row.get('username', ''),
            display_name=row.get('display_name', ''),
            account_id=row.get('account_id', ''),
            follower_count=row.get('follower_count', 0) or 0,
            following_count=row.get('following_count', 0) or 0,
            post_count=row.get('post_count', 0) or 0,
            bio=row.get('bio', '') or '',
            created_at=row.get('created_at', ''),
            updated_at=row.get('updated_at', '')
        )

    def _row_to_post(self, row: Dict) -> Post:
        """Convert database row to Post object"""
        return Post(
            id=row.get('id'),
            account_id=row.get('account_id', ''),
            platform=row.get('platform', ''),
            post_id=row.get('post_id', ''),
            post_type=row.get('post_type', ''),
            caption=row.get('caption', '') or '',
            published_at=row.get('published_at', ''),
            url=row.get('url', '') or '',
            thumbnail_url=row.get('thumbnail_url', '') or '',
            created_at=row.get('created_at', '')
        )

    def _row_to_post_metrics(self, row: Dict) -> PostMetrics:
        """Convert database row to PostMetrics object"""
        return PostMetrics(
            id=row.get('id'),
            post_id=row.get('post_id', ''),
            collected_at=row.get('collected_at', ''),
            views=row.get('views', 0) or 0,
            likes=row.get('likes', 0) or 0,
            comments=row.get('comments', 0) or 0,
            shares=row.get('shares', 0) or 0,
            saves=row.get('saves', 0) or 0,
            plays=row.get('views', 0) or 0,  # Use views as plays
            reach=0,
            impressions=0
        )

    def _row_to_account_metrics(self, row: Dict) -> AccountMetrics:
        """Convert database row to AccountMetrics object"""
        return AccountMetrics(
            id=row.get('id'),
            account_id=row.get('account_id', ''),
            collected_at=row.get('collected_at', ''),
            follower_count=row.get('follower_count', 0) or 0,
            following_count=row.get('following_count', 0) or 0,
            post_count=row.get('post_count', 0) or 0,
            total_likes=row.get('total_likes', 0) or 0,
            total_comments=0,
            total_views=row.get('total_views', 0) or 0
        )


# Global database instance
# Will be initialized when imported with proper env vars
db = None

def get_db() -> SupabaseDatabase:
    """Get or create database instance"""
    global db
    if db is None:
        db = SupabaseDatabase()
    return db
