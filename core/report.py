"""
报表生成模块 - 生成社媒数据报表
"""

import os
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import asdict

from .database import db, Account, Post, PostMetrics, AccountMetrics

# 报表目录
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')


class ReportGenerator:
    """报表生成器"""

    def __init__(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)

    def generate_weekly_report(self, platform: str = None,
                                start_date: str = None,
                                end_date: str = None) -> str:
        """
        生成周报

        Args:
            platform: 平台筛选 ('instagram', 'tiktok', None=全部)
            start_date: 开始日期 (ISO格式)
            end_date: 结束日期 (ISO格式)

        Returns:
            生成的报表文件路径
        """
        # 默认为过去7天
        if not end_date:
            end_date = datetime.now().isoformat()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()

        # 获取数据
        accounts = db.get_all_accounts(platform)
        report_data = []

        for account in accounts:
            # 获取账号指标历史
            account_metrics = db.get_account_metrics_history(account.id, limit=2)

            # 获取帖子及指标
            posts_with_metrics = db.get_posts_with_latest_metrics(account_id=account.id)

            # 计算汇总数据
            total_views = sum(p.get('views', 0) or 0 for p in posts_with_metrics)
            total_likes = sum(p.get('likes', 0) or 0 for p in posts_with_metrics)
            total_comments = sum(p.get('comments', 0) or 0 for p in posts_with_metrics)
            total_shares = sum(p.get('shares', 0) or 0 for p in posts_with_metrics)

            # 粉丝变化
            follower_change = 0
            if len(account_metrics) >= 2:
                follower_change = account_metrics[0].follower_count - account_metrics[1].follower_count

            report_data.append({
                'platform': account.platform,
                'username': account.username,
                'display_name': account.display_name,
                'follower_count': account.follower_count,
                'follower_change': follower_change,
                'post_count': len(posts_with_metrics),
                'total_views': total_views,
                'total_likes': total_likes,
                'total_comments': total_comments,
                'total_shares': total_shares,
                'avg_views': total_views // len(posts_with_metrics) if posts_with_metrics else 0,
                'avg_likes': total_likes // len(posts_with_metrics) if posts_with_metrics else 0,
                'engagement_rate': self._calc_engagement_rate(total_likes, total_comments, account.follower_count)
            })

        # 生成报表文件
        filename = f"weekly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(REPORTS_DIR, filename)

        self._write_csv(filepath, report_data, [
            'platform', 'username', 'display_name', 'follower_count', 'follower_change',
            'post_count', 'total_views', 'total_likes', 'total_comments', 'total_shares',
            'avg_views', 'avg_likes', 'engagement_rate'
        ])

        print(f"周报已生成: {filepath}")
        return filepath

    def generate_post_report(self, platform: str = None,
                              account_username: str = None,
                              limit: int = 100) -> str:
        """
        生成帖子明细报表

        Args:
            platform: 平台筛选
            account_username: 账号筛选
            limit: 最大帖子数

        Returns:
            生成的报表文件路径
        """
        # 获取账号ID
        account_id = None
        if account_username and platform:
            account = db.get_account(platform, account_username)
            if account:
                account_id = account.id

        # 获取帖子数据
        posts = db.get_posts_with_latest_metrics(
            account_id=account_id,
            platform=platform,
            limit=limit
        )

        # 准备报表数据
        report_data = []
        for post in posts:
            report_data.append({
                'platform': post.get('platform', ''),
                'account': post.get('username', ''),
                'post_id': post.get('post_id', ''),
                'post_type': post.get('post_type', ''),
                'caption': (post.get('caption', '') or '')[:100],  # 截断
                'published_at': post.get('published_at', ''),
                'url': post.get('url', ''),
                'views': post.get('views', 0) or 0,
                'likes': post.get('likes', 0) or 0,
                'comments': post.get('comments', 0) or 0,
                'shares': post.get('shares', 0) or 0,
                'saves': post.get('saves', 0) or 0,
                'collected_at': post.get('metrics_collected_at', '')
            })

        # 生成报表文件
        filename = f"post_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(REPORTS_DIR, filename)

        self._write_csv(filepath, report_data, [
            'platform', 'account', 'post_id', 'post_type', 'caption',
            'published_at', 'url', 'views', 'likes', 'comments',
            'shares', 'saves', 'collected_at'
        ])

        print(f"帖子报表已生成: {filepath}")
        return filepath

    def generate_account_summary(self) -> str:
        """
        生成账号汇总报表

        Returns:
            生成的报表文件路径
        """
        accounts = db.get_all_accounts()
        report_data = []

        for account in accounts:
            # 获取最新指标
            metrics_history = db.get_account_metrics_history(account.id, limit=7)

            # 计算7天粉丝变化
            follower_change_7d = 0
            if len(metrics_history) >= 2:
                follower_change_7d = metrics_history[0].follower_count - metrics_history[-1].follower_count

            # 获取帖子统计
            posts = db.get_posts_with_latest_metrics(account_id=account.id, limit=1000)
            total_views = sum(p.get('views', 0) or 0 for p in posts)
            total_likes = sum(p.get('likes', 0) or 0 for p in posts)

            report_data.append({
                'platform': account.platform,
                'username': account.username,
                'display_name': account.display_name,
                'follower_count': account.follower_count,
                'following_count': account.following_count,
                'post_count': account.post_count,
                'follower_change_7d': follower_change_7d,
                'total_views': total_views,
                'total_likes': total_likes,
                'bio': (account.bio or '')[:100],
                'last_updated': account.updated_at
            })

        # 生成报表文件
        filename = f"account_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(REPORTS_DIR, filename)

        self._write_csv(filepath, report_data, [
            'platform', 'username', 'display_name', 'follower_count',
            'following_count', 'post_count', 'follower_change_7d',
            'total_views', 'total_likes', 'bio', 'last_updated'
        ])

        print(f"账号汇总报表已生成: {filepath}")
        return filepath

    def get_dashboard_data(self) -> Dict:
        """
        获取仪表盘数据（用于 Claude Code 展示）

        Returns:
            仪表盘数据字典
        """
        summary = db.get_collection_summary()
        accounts = db.get_all_accounts()

        # 按平台统计
        platform_stats = {}
        for account in accounts:
            platform = account.platform
            if platform not in platform_stats:
                platform_stats[platform] = {
                    'accounts': 0,
                    'total_followers': 0,
                    'total_posts': 0
                }
            platform_stats[platform]['accounts'] += 1
            platform_stats[platform]['total_followers'] += account.follower_count
            platform_stats[platform]['total_posts'] += account.post_count

        # 最近采集的帖子
        recent_posts = db.get_posts_with_latest_metrics(limit=10)

        # Top 帖子（按播放量）
        all_posts = db.get_posts_with_latest_metrics(limit=1000)
        top_posts = sorted(all_posts, key=lambda x: x.get('views', 0) or 0, reverse=True)[:5]

        return {
            'summary': summary,
            'platform_stats': platform_stats,
            'recent_posts': recent_posts,
            'top_posts_by_views': top_posts,
            'total_accounts': len(accounts)
        }

    def print_dashboard(self):
        """打印仪表盘到控制台"""
        data = self.get_dashboard_data()

        print("\n" + "=" * 60)
        print("               社媒数据追踪仪表盘")
        print("=" * 60)

        # 总览
        print(f"\n📊 数据总览")
        print(f"   总账号数: {data['total_accounts']}")
        print(f"   最近采集: {data['summary'].get('last_collected', '无')}")
        print(f"   采集次数: {data['summary'].get('collection_count', 0)}")

        # 平台统计
        print(f"\n📱 平台统计")
        for platform, stats in data['platform_stats'].items():
            print(f"   [{platform.upper()}]")
            print(f"      账号: {stats['accounts']} 个")
            print(f"      粉丝: {stats['total_followers']:,}")
            print(f"      帖子: {stats['total_posts']} 条")

        # Top 帖子
        if data['top_posts_by_views']:
            print(f"\n🔥 Top 5 帖子（按播放量）")
            for i, post in enumerate(data['top_posts_by_views'], 1):
                views = post.get('views', 0) or 0
                likes = post.get('likes', 0) or 0
                username = post.get('username', 'unknown')
                caption = (post.get('caption', '') or '')[:30]
                print(f"   {i}. @{username}: {views:,} 播放 / {likes:,} 赞")
                print(f"      \"{caption}...\"")

        print("\n" + "=" * 60)

    def _calc_engagement_rate(self, likes: int, comments: int, followers: int) -> float:
        """计算互动率"""
        if followers == 0:
            return 0.0
        return round((likes + comments) / followers * 100, 2)

    def _write_csv(self, filepath: str, data: List[Dict], columns: List[str]):
        """写入 CSV 文件"""
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)


# 全局报表生成器实例
report_generator = ReportGenerator()
