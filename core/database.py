"""
数据库模块 - 使用 SQLite 存储社媒数据
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DB_PATH = os.path.join(DATA_DIR, 'social_media.db')


@dataclass
class Account:
    """账号数据模型"""
    id: Optional[int]
    platform: str          # 'instagram' 或 'tiktok'
    username: str          # 用户名
    display_name: str      # 显示名称
    account_id: str        # 平台账号ID
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    bio: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Post:
    """帖子/视频数据模型"""
    id: Optional[int]
    account_id: int        # 关联的账号ID（本地数据库ID）
    platform: str          # 'instagram' 或 'tiktok'
    post_id: str           # 平台帖子ID
    post_type: str         # 'video', 'image', 'reel', 'carousel'
    caption: str           # 标题/描述
    published_at: str      # 发布时间
    url: str               # 帖子链接
    thumbnail_url: str = ""
    created_at: str = ""


@dataclass
class PostMetrics:
    """帖子指标数据模型（每次采集的快照）"""
    id: Optional[int]
    post_id: int           # 关联的帖子ID（本地数据库ID）
    collected_at: str      # 采集时间
    views: int = 0         # 浏览量
    likes: int = 0         # 点赞数
    comments: int = 0      # 评论数
    shares: int = 0        # 分享数
    saves: int = 0         # 收藏数
    plays: int = 0         # 播放次数（视频）
    reach: int = 0         # 触达人数
    impressions: int = 0   # 曝光次数


@dataclass
class AccountMetrics:
    """账号指标数据模型（每次采集的快照）"""
    id: Optional[int]
    account_id: int        # 关联的账号ID
    collected_at: str      # 采集时间
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_views: int = 0


class Database:
    """数据库操作类"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 账号表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                username TEXT NOT NULL,
                display_name TEXT,
                account_id TEXT NOT NULL,
                follower_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                post_count INTEGER DEFAULT 0,
                bio TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(platform, username)
            )
        ''')

        # 帖子表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                post_id TEXT NOT NULL,
                post_type TEXT,
                caption TEXT,
                published_at TEXT,
                url TEXT,
                thumbnail_url TEXT,
                created_at TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                UNIQUE(platform, post_id)
            )
        ''')

        # 帖子指标表（每次采集的快照）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS post_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                collected_at TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                saves INTEGER DEFAULT 0,
                plays INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        ''')

        # 账号指标表（每次采集的快照）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                collected_at TEXT NOT NULL,
                follower_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                post_count INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_account ON posts(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_metrics_post ON post_metrics(post_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_metrics_date ON post_metrics(collected_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_metrics_account ON account_metrics(account_id)')

        conn.commit()
        conn.close()

    # ===== 账号操作 =====

    def add_account(self, account: Account) -> int:
        """添加账号，返回账号ID"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO accounts
            (platform, username, display_name, account_id, follower_count,
             following_count, post_count, bio, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (account.platform, account.username, account.display_name,
              account.account_id, account.follower_count, account.following_count,
              account.post_count, account.bio, now, now))

        account_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return account_id

    def get_account(self, platform: str, username: str) -> Optional[Account]:
        """获取账号"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM accounts WHERE platform = ? AND username = ?',
            (platform, username)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return Account(**dict(row))
        return None

    def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """通过ID获取账号"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Account(**dict(row))
        return None

    def get_all_accounts(self, platform: str = None) -> List[Account]:
        """获取所有账号"""
        conn = self._get_conn()
        cursor = conn.cursor()

        if platform:
            cursor.execute('SELECT * FROM accounts WHERE platform = ?', (platform,))
        else:
            cursor.execute('SELECT * FROM accounts')

        rows = cursor.fetchall()
        conn.close()
        return [Account(**dict(row)) for row in rows]

    def update_account(self, account: Account):
        """更新账号信息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            UPDATE accounts SET
                display_name = ?, follower_count = ?, following_count = ?,
                post_count = ?, bio = ?, updated_at = ?
            WHERE id = ?
        ''', (account.display_name, account.follower_count, account.following_count,
              account.post_count, account.bio, now, account.id))

        conn.commit()
        conn.close()

    def delete_account(self, account_id: int):
        """删除账号及其所有数据"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 删除帖子指标
        cursor.execute('''
            DELETE FROM post_metrics WHERE post_id IN
            (SELECT id FROM posts WHERE account_id = ?)
        ''', (account_id,))

        # 删除帖子
        cursor.execute('DELETE FROM posts WHERE account_id = ?', (account_id,))

        # 删除账号指标
        cursor.execute('DELETE FROM account_metrics WHERE account_id = ?', (account_id,))

        # 删除账号
        cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))

        conn.commit()
        conn.close()

    # ===== 帖子操作 =====

    def add_post(self, post: Post) -> int:
        """添加帖子，返回帖子ID"""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR IGNORE INTO posts
            (account_id, platform, post_id, post_type, caption,
             published_at, url, thumbnail_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (post.account_id, post.platform, post.post_id, post.post_type,
              post.caption, post.published_at, post.url, post.thumbnail_url, now))

        # 如果是重复的，获取已存在的ID
        if cursor.lastrowid == 0:
            cursor.execute(
                'SELECT id FROM posts WHERE platform = ? AND post_id = ?',
                (post.platform, post.post_id)
            )
            post_id = cursor.fetchone()[0]
        else:
            post_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return post_id

    def get_posts_by_account(self, account_id: int, limit: int = 50) -> List[Post]:
        """获取账号的帖子"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM posts WHERE account_id = ?
            ORDER BY published_at DESC LIMIT ?
        ''', (account_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [Post(**dict(row)) for row in rows]

    def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """通过ID获取帖子"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Post(**dict(row))
        return None

    # ===== 指标操作 =====

    def add_post_metrics(self, metrics: PostMetrics) -> int:
        """添加帖子指标快照"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO post_metrics
            (post_id, collected_at, views, likes, comments, shares, saves, plays, reach, impressions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (metrics.post_id, metrics.collected_at, metrics.views, metrics.likes,
              metrics.comments, metrics.shares, metrics.saves, metrics.plays,
              metrics.reach, metrics.impressions))

        metrics_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return metrics_id

    def add_account_metrics(self, metrics: AccountMetrics) -> int:
        """添加账号指标快照"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO account_metrics
            (account_id, collected_at, follower_count, following_count,
             post_count, total_likes, total_comments, total_views)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (metrics.account_id, metrics.collected_at, metrics.follower_count,
              metrics.following_count, metrics.post_count, metrics.total_likes,
              metrics.total_comments, metrics.total_views))

        metrics_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return metrics_id

    def get_post_metrics_history(self, post_id: int, limit: int = 10) -> List[PostMetrics]:
        """获取帖子的指标历史"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM post_metrics WHERE post_id = ?
            ORDER BY collected_at DESC LIMIT ?
        ''', (post_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [PostMetrics(**dict(row)) for row in rows]

    def get_latest_post_metrics(self, post_id: int) -> Optional[PostMetrics]:
        """获取帖子最新指标"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM post_metrics WHERE post_id = ?
            ORDER BY collected_at DESC LIMIT 1
        ''', (post_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return PostMetrics(**dict(row))
        return None

    def get_account_metrics_history(self, account_id: int, limit: int = 10) -> List[AccountMetrics]:
        """获取账号的指标历史"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM account_metrics WHERE account_id = ?
            ORDER BY collected_at DESC LIMIT ?
        ''', (account_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [AccountMetrics(**dict(row)) for row in rows]

    # ===== 统计查询 =====

    def get_posts_with_latest_metrics(self, account_id: int = None,
                                       platform: str = None,
                                       limit: int = 50) -> List[Dict]:
        """获取帖子及其最新指标"""
        conn = self._get_conn()
        cursor = conn.cursor()

        query = '''
            SELECT p.*, pm.views, pm.likes, pm.comments, pm.shares, pm.saves,
                   pm.plays, pm.reach, pm.impressions, pm.collected_at as metrics_collected_at,
                   a.username, a.display_name as account_display_name
            FROM posts p
            LEFT JOIN (
                SELECT post_id, MAX(collected_at) as max_collected
                FROM post_metrics GROUP BY post_id
            ) latest ON p.id = latest.post_id
            LEFT JOIN post_metrics pm ON p.id = pm.post_id AND pm.collected_at = latest.max_collected
            LEFT JOIN accounts a ON p.account_id = a.id
            WHERE 1=1
        '''
        params = []

        if account_id:
            query += ' AND p.account_id = ?'
            params.append(account_id)

        if platform:
            query += ' AND p.platform = ?'
            params.append(platform)

        query += ' ORDER BY p.published_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_collection_summary(self) -> Dict:
        """获取数据采集摘要"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 账号数量
        cursor.execute('SELECT platform, COUNT(*) as count FROM accounts GROUP BY platform')
        accounts_by_platform = {row['platform']: row['count'] for row in cursor.fetchall()}

        # 帖子数量
        cursor.execute('SELECT platform, COUNT(*) as count FROM posts GROUP BY platform')
        posts_by_platform = {row['platform']: row['count'] for row in cursor.fetchall()}

        # 最近采集时间
        cursor.execute('SELECT MAX(collected_at) as last_collected FROM post_metrics')
        last_collected = cursor.fetchone()['last_collected']

        # 总采集次数
        cursor.execute('SELECT COUNT(DISTINCT collected_at) as count FROM post_metrics')
        collection_count = cursor.fetchone()['count']

        conn.close()

        return {
            'accounts_by_platform': accounts_by_platform,
            'posts_by_platform': posts_by_platform,
            'last_collected': last_collected,
            'collection_count': collection_count
        }


# 全局数据库实例
db = Database()
