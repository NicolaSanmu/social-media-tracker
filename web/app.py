"""
Social Media Tracker - Web Dashboard

FastAPI 应用主文件
运行: uvicorn web.app:app --reload --port 8000
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Request, Query, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import db, Account, Post, PostMetrics, AccountMetrics
from core.collectors import get_collector

# 支持的平台列表
SUPPORTED_PLATFORMS = ['instagram', 'tiktok', 'youtube', 'twitter']


class AddAccountRequest(BaseModel):
    platform: str
    username: str
    collect_now: bool = False

# 创建 FastAPI 应用
app = FastAPI(
    title="Social Media Tracker",
    description="社媒矩阵数据追踪仪表盘",
    version="1.0.0"
)

# 静态文件和模板
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """仪表盘首页"""
    # 获取所有账号
    accounts = db.get_all_accounts()

    # 平台统计
    platform_stats = {}
    for account in accounts:
        if account.platform not in platform_stats:
            platform_stats[account.platform] = {
                'count': 0,
                'followers': 0,
                'posts': 0
            }
        platform_stats[account.platform]['count'] += 1
        platform_stats[account.platform]['followers'] += account.follower_count or 0
        platform_stats[account.platform]['posts'] += account.post_count or 0

    # 获取最近的帖子（按播放量排序）
    top_posts = _get_top_posts(limit=10)

    # 最近采集时间
    last_collected = _get_last_collection_time()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "accounts": accounts,
        "platform_stats": platform_stats,
        "top_posts": top_posts,
        "last_collected": last_collected,
        "total_accounts": len(accounts)
    })


@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, platform: Optional[str] = None):
    """账号管理页面"""
    accounts = db.get_all_accounts(platform)

    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "accounts": accounts,
        "platform_filter": platform
    })


@app.get("/account/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    account_id: int,
    sort_by: str = "published_at",
    order: str = "desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """单个账号详情页"""
    account = db.get_account_by_id(account_id)
    if not account:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "账号不存在"
        })

    # 获取该账号的帖子（支持排序和日期过滤）
    posts = _get_account_posts_filtered(account_id, sort_by, order, date_from, date_to, limit=500)

    # 获取趋势数据
    trends = _get_account_trends(account_id, days=30)

    return templates.TemplateResponse("account_detail.html", {
        "request": request,
        "account": account,
        "posts": posts,
        "trends": trends,
        "sort_by": sort_by,
        "order": order,
        "date_from": date_from or "",
        "date_to": date_to or ""
    })


# ==================== API 路由 ====================

@app.get("/api/accounts")
async def api_get_accounts(platform: Optional[str] = None):
    """获取账号列表"""
    accounts = db.get_all_accounts(platform)
    return [{
        "id": a.id,
        "platform": a.platform,
        "username": a.username,
        "display_name": a.display_name,
        "follower_count": a.follower_count,
        "following_count": a.following_count,
        "post_count": a.post_count,
        "bio": a.bio
    } for a in accounts]


@app.get("/api/account/{account_id}")
async def api_get_account(account_id: int):
    """获取单个账号信息"""
    account = db.get_account_by_id(account_id)
    if not account:
        return JSONResponse({"error": "账号不存在"}, status_code=404)

    return {
        "id": account.id,
        "platform": account.platform,
        "username": account.username,
        "display_name": account.display_name,
        "follower_count": account.follower_count,
        "following_count": account.following_count,
        "post_count": account.post_count,
        "bio": account.bio
    }


@app.get("/api/account/{account_id}/posts")
async def api_get_account_posts(account_id: int, limit: int = 20):
    """获取账号的帖子列表"""
    posts = _get_account_posts(account_id, limit)
    return posts


@app.get("/api/account/{account_id}/trends")
async def api_get_account_trends(account_id: int, days: int = 30):
    """获取账号趋势数据"""
    trends = _get_account_trends(account_id, days)
    return trends


@app.get("/api/stats")
async def api_get_stats():
    """获取总体统计"""
    accounts = db.get_all_accounts()

    platform_stats = {}
    for account in accounts:
        if account.platform not in platform_stats:
            platform_stats[account.platform] = {
                'count': 0,
                'followers': 0,
                'posts': 0
            }
        platform_stats[account.platform]['count'] += 1
        platform_stats[account.platform]['followers'] += account.follower_count or 0
        platform_stats[account.platform]['posts'] += account.post_count or 0

    return {
        "total_accounts": len(accounts),
        "platform_stats": platform_stats,
        "last_collected": _get_last_collection_time()
    }


@app.get("/api/top-posts")
async def api_get_top_posts(limit: int = 10):
    """获取热门帖子"""
    return _get_top_posts(limit)


@app.get("/api/platforms")
async def api_get_platforms():
    """获取支持的平台列表"""
    return SUPPORTED_PLATFORMS


@app.post("/api/accounts")
async def api_add_account(request: AddAccountRequest, background_tasks: BackgroundTasks):
    """添加新账号"""
    platform = request.platform.lower()
    username = request.username.strip().lstrip('@')

    # 验证平台
    if platform not in SUPPORTED_PLATFORMS:
        return JSONResponse(
            {"error": f"不支持的平台: {platform}，支持的平台: {', '.join(SUPPORTED_PLATFORMS)}"},
            status_code=400
        )

    # 检查是否已存在
    existing = db.get_account(platform, username)
    if existing:
        return JSONResponse(
            {"error": f"账号已存在: [{platform}] @{username}"},
            status_code=400
        )

    # 创建账号记录
    account = Account(
        id=None,
        platform=platform,
        username=username,
        display_name=username,
        account_id='',
        bio=''
    )
    account_id = db.add_account(account)
    account.id = account_id

    result = {
        "success": True,
        "message": f"已添加账号: [{platform}] @{username}",
        "account": {
            "id": account_id,
            "platform": platform,
            "username": username
        }
    }

    # 如果需要立即采集，在后台执行
    if request.collect_now:
        background_tasks.add_task(_collect_account_data, platform, username)
        result["message"] += "，正在后台采集数据..."

    return result


@app.post("/api/account/{account_id}/collect")
async def api_collect_account(account_id: int, background_tasks: BackgroundTasks):
    """触发单个账号的数据采集"""
    account = db.get_account_by_id(account_id)
    if not account:
        return JSONResponse({"error": "账号不存在"}, status_code=404)

    background_tasks.add_task(_collect_account_data, account.platform, account.username)

    return {
        "success": True,
        "message": f"正在后台采集 [{account.platform}] @{account.username} 的数据..."
    }


@app.delete("/api/account/{account_id}")
async def api_delete_account(account_id: int):
    """删除账号"""
    account = db.get_account_by_id(account_id)
    if not account:
        return JSONResponse({"error": "账号不存在"}, status_code=404)

    db.delete_account(account_id)

    return {
        "success": True,
        "message": f"已删除账号: [{account.platform}] @{account.username}"
    }


@app.get("/api/account/{account_id}/posts")
async def api_get_account_posts_with_filter(
    account_id: int,
    sort_by: str = "published_at",
    order: str = "desc",
    limit: int = 100
):
    """获取账号的帖子列表（支持排序）"""
    posts = _get_account_posts_sorted(account_id, sort_by, order, limit)
    return posts


def _collect_account_data(platform: str, username: str):
    """后台采集账号数据"""
    try:
        collector = get_collector(platform)
        collector.collect_all(username, post_limit=20)
    except Exception as e:
        print(f"[Web] 采集失败: {e}")


# ==================== 辅助函数 ====================

def _get_top_posts(limit: int = 10) -> List[dict]:
    """获取播放量最高的帖子"""
    cursor = db._get_conn().cursor()
    cursor.execute('''
        SELECT p.id, p.account_id, p.platform, p.post_id, p.post_type,
               p.caption, p.published_at, p.url,
               pm.views, pm.likes, pm.comments, pm.shares, pm.saves,
               a.username, a.display_name
        FROM posts p
        LEFT JOIN post_metrics pm ON p.id = pm.post_id
        LEFT JOIN accounts a ON p.account_id = a.id
        WHERE pm.id IN (
            SELECT MAX(id) FROM post_metrics GROUP BY post_id
        )
        ORDER BY pm.views DESC, pm.likes DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    posts = []
    for row in rows:
        posts.append({
            "id": row[0],
            "account_id": row[1],
            "platform": row[2],
            "post_id": row[3],
            "post_type": row[4],
            "caption": row[5][:100] + "..." if row[5] and len(row[5]) > 100 else row[5],
            "published_at": row[6],
            "url": row[7],
            "views": row[8] or 0,
            "likes": row[9] or 0,
            "comments": row[10] or 0,
            "shares": row[11] or 0,
            "saves": row[12] or 0,
            "username": row[13],
            "display_name": row[14]
        })

    return posts


def _get_account_posts(account_id: int, limit: int = 50) -> List[dict]:
    """获取账号的帖子列表"""
    return _get_account_posts_filtered(account_id, "published_at", "desc", None, None, limit)


def _get_account_posts_sorted(account_id: int, sort_by: str = "published_at", order: str = "desc", limit: int = 100) -> List[dict]:
    """获取账号的帖子列表（支持排序）"""
    return _get_account_posts_filtered(account_id, sort_by, order, None, None, limit)


def _get_account_posts_filtered(
    account_id: int,
    sort_by: str = "published_at",
    order: str = "desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 500
) -> List[dict]:
    """获取账号的帖子列表（支持排序和日期过滤）"""
    cursor = db._get_conn().cursor()

    # 映射排序字段
    sort_mapping = {
        "published_at": "p.published_at",
        "views": "pm.views",
        "likes": "pm.likes",
        "comments": "pm.comments",
        "shares": "pm.shares",
        "saves": "pm.saves"
    }

    sort_column = sort_mapping.get(sort_by, "p.published_at")
    order_direction = "DESC" if order.lower() == "desc" else "ASC"

    # 构建日期过滤条件
    date_conditions = ""
    params = [account_id]

    if date_from:
        date_conditions += " AND DATE(p.published_at) >= ?"
        params.append(date_from)

    if date_to:
        date_conditions += " AND DATE(p.published_at) <= ?"
        params.append(date_to)

    params.append(limit)

    cursor.execute(f'''
        SELECT p.id, p.post_id, p.post_type, p.caption, p.published_at, p.url,
               pm.views, pm.likes, pm.comments, pm.shares, pm.saves, pm.collected_at
        FROM posts p
        LEFT JOIN post_metrics pm ON p.id = pm.post_id
        WHERE p.account_id = ?
        AND pm.id IN (
            SELECT MAX(id) FROM post_metrics GROUP BY post_id
        )
        {date_conditions}
        ORDER BY {sort_column} {order_direction}
        LIMIT ?
    ''', params)

    rows = cursor.fetchall()
    posts = []
    for row in rows:
        posts.append({
            "id": row[0],
            "post_id": row[1],
            "post_type": row[2],
            "caption": row[3],
            "published_at": row[4],
            "url": row[5],
            "views": row[6] or 0,
            "likes": row[7] or 0,
            "comments": row[8] or 0,
            "shares": row[9] or 0,
            "saves": row[10] or 0,
            "collected_at": row[11]
        })

    return posts


def _get_account_trends(account_id: int, days: int = 30) -> dict:
    """获取账号趋势数据"""
    cursor = db._get_conn().cursor()

    # 获取账号指标历史
    cursor.execute('''
        SELECT collected_at, follower_count, following_count, post_count
        FROM account_metrics
        WHERE account_id = ?
        ORDER BY collected_at ASC
    ''', (account_id,))

    account_history = cursor.fetchall()

    # 获取帖子指标汇总（按日期）
    cursor.execute('''
        SELECT DATE(pm.collected_at) as date,
               SUM(pm.views) as total_views,
               SUM(pm.likes) as total_likes,
               SUM(pm.comments) as total_comments
        FROM posts p
        JOIN post_metrics pm ON p.id = pm.post_id
        WHERE p.account_id = ?
        GROUP BY DATE(pm.collected_at)
        ORDER BY date ASC
    ''', (account_id,))

    daily_metrics = cursor.fetchall()

    return {
        "account_history": [{
            "date": row[0],
            "followers": row[1],
            "following": row[2],
            "posts": row[3]
        } for row in account_history],
        "daily_metrics": [{
            "date": row[0],
            "views": row[1] or 0,
            "likes": row[2] or 0,
            "comments": row[3] or 0
        } for row in daily_metrics]
    }


def _get_last_collection_time() -> Optional[str]:
    """获取最后采集时间"""
    cursor = db._get_conn().cursor()
    cursor.execute('SELECT MAX(collected_at) FROM post_metrics')
    row = cursor.fetchone()
    return row[0] if row else None


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
