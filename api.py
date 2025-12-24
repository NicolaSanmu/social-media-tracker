"""
Social Media Tracker API

FastAPI 后端，提供数据收集 API 端点
部署到 Railway/Render 后，前端可以调用这些接口触发数据收集
"""

import os
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 确保环境变量存在后再导入 collectors
# collectors.py 会根据环境变量选择 Supabase 或 SQLite
from core.collectors import (
    get_collector,
    collect_all_accounts,
    InstagramCollector,
    TikTokCollector,
    YouTubeCollector,
    TwitterCollector
)
from core.supabase_db import get_db
from core.api_config import get_all_configs, clear_cache

app = FastAPI(
    title="Social Media Tracker API",
    description="API for collecting social media data from Instagram, TikTok, YouTube, and Twitter",
    version="1.0.0"
)

# CORS 配置 - 允许 Lovable 前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.lovable.app",
        "https://*.lovableproject.com",
        "*"  # 开发阶段允许所有来源，生产环境应该限制
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 收集任务状态跟踪
collection_status = {}


class CollectRequest(BaseModel):
    """收集请求模型"""
    post_limit: int = 20


class CollectResponse(BaseModel):
    """收集响应模型"""
    success: bool
    message: str
    platform: Optional[str] = None
    username: Optional[str] = None
    posts_collected: int = 0
    task_id: Optional[str] = None


class AccountResponse(BaseModel):
    """账号响应模型"""
    id: str
    platform: str
    username: str
    display_name: str
    follower_count: int
    following_count: int
    post_count: int
    bio: str


# ===== 健康检查 =====

@app.get("/")
async def root():
    """根路径 - API 信息"""
    return {
        "name": "Social Media Tracker API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "accounts": "/api/accounts",
            "collect": "/api/collect/{platform}/{username}",
            "collect_all": "/api/collect-all",
            "status": "/api/status/{task_id}"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    # 检查数据库连接
    try:
        db = get_db()
        accounts = db.get_all_accounts()
        db_status = "connected"
        account_count = len(accounts)
    except Exception as e:
        db_status = f"error: {str(e)}"
        account_count = 0

    # 检查 API Keys
    api_keys = {
        "instagram": bool(os.environ.get('INSTAGRAM_API_KEY')),
        "tiktok": bool(os.environ.get('TIKTOK_API_KEY')),
        "youtube": bool(os.environ.get('YOUTUBE_API_KEY')),
        "twitter": bool(os.environ.get('TWITTER_API_KEY'))
    }

    # Debug: 检查 Supabase 环境变量
    supabase_url = os.environ.get('SUPABASE_URL', '')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    supabase_debug = {
        "url_set": bool(supabase_url),
        "url_preview": supabase_url[:30] + "..." if len(supabase_url) > 30 else supabase_url,
        "key_set": bool(supabase_key),
        "key_length": len(supabase_key)
    }

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "account_count": account_count,
        "api_keys_configured": api_keys,
        "supabase_debug": supabase_debug
    }


# ===== API Configuration =====

@app.get("/api/configs")
async def get_api_configs():
    """Get all API configurations (keys are masked for security)"""
    configs = get_all_configs()

    # Mask API keys for security (show first 8 and last 4 chars)
    masked_configs = {}
    for platform, config in configs.items():
        if config:
            api_key = config.get('api_key', '')
            if len(api_key) > 12:
                masked_key = api_key[:8] + '...' + api_key[-4:]
            else:
                masked_key = '***' if api_key else ''

            masked_configs[platform] = {
                'platform': platform,
                'api_key_masked': masked_key,
                'api_host': config.get('api_host'),
                'enabled': config.get('enabled', False),
                'notes': config.get('notes', ''),
                'source': config.get('source', 'unknown')
            }
        else:
            masked_configs[platform] = {
                'platform': platform,
                'api_key_masked': '',
                'api_host': None,
                'enabled': False,
                'notes': 'Not configured',
                'source': 'none'
            }

    return {
        "configs": masked_configs,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/configs/refresh")
async def refresh_api_configs(platform: Optional[str] = None):
    """Clear API config cache to reload from database"""
    clear_cache(platform)
    return {
        "success": True,
        "message": f"Cache cleared for {'all platforms' if not platform else platform}",
        "timestamp": datetime.now().isoformat()
    }


# ===== 账号管理 =====

@app.get("/api/accounts", response_model=List[AccountResponse])
async def list_accounts(platform: Optional[str] = None):
    """获取所有账号列表"""
    try:
        db = get_db()
        accounts = db.get_all_accounts(platform)
        return [
            AccountResponse(
                id=str(acc.id),
                platform=acc.platform,
                username=acc.username,
                display_name=acc.display_name,
                follower_count=acc.follower_count,
                following_count=acc.following_count,
                post_count=acc.post_count,
                bio=acc.bio
            )
            for acc in accounts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== 数据收集 =====

def run_collection(platform: str, username: str, post_limit: int, task_id: str):
    """后台运行收集任务"""
    try:
        collection_status[task_id] = {
            "status": "running",
            "platform": platform,
            "username": username,
            "started_at": datetime.now().isoformat(),
            "message": "正在收集数据..."
        }

        collector = get_collector(platform)
        result = collector.collect_all(username, post_limit)

        if result['success']:
            collection_status[task_id] = {
                "status": "completed",
                "platform": platform,
                "username": username,
                "completed_at": datetime.now().isoformat(),
                "message": result['message'],
                "posts_collected": len(result.get('posts', []))
            }
        else:
            collection_status[task_id] = {
                "status": "failed",
                "platform": platform,
                "username": username,
                "completed_at": datetime.now().isoformat(),
                "message": result['message']
            }

    except Exception as e:
        collection_status[task_id] = {
            "status": "failed",
            "platform": platform,
            "username": username,
            "completed_at": datetime.now().isoformat(),
            "message": f"收集失败: {str(e)}"
        }


@app.post("/api/collect/{platform}/{username}", response_model=CollectResponse)
async def collect_account(
    platform: str,
    username: str,
    background_tasks: BackgroundTasks,
    request: CollectRequest = CollectRequest()
):
    """
    收集单个账号的数据

    - platform: instagram, tiktok, youtube, twitter
    - username: 账号用户名
    - post_limit: 最多收集多少条帖子 (默认 20)
    """
    # 验证平台
    valid_platforms = ['instagram', 'tiktok', 'youtube', 'twitter']
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {platform}. 支持的平台: {valid_platforms}"
        )

    # 检查 API Key
    api_key_map = {
        'instagram': 'INSTAGRAM_API_KEY',
        'tiktok': 'TIKTOK_API_KEY',
        'youtube': 'YOUTUBE_API_KEY',
        'twitter': 'TWITTER_API_KEY'
    }
    if not os.environ.get(api_key_map[platform]):
        raise HTTPException(
            status_code=400,
            detail=f"未配置 {platform} 的 API Key ({api_key_map[platform]})"
        )

    # 生成任务ID
    task_id = f"{platform}_{username}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # 在后台运行收集任务
    background_tasks.add_task(
        run_collection,
        platform,
        username,
        request.post_limit,
        task_id
    )

    return CollectResponse(
        success=True,
        message=f"已开始收集 {platform} 账号 {username} 的数据",
        platform=platform,
        username=username,
        task_id=task_id
    )


@app.post("/api/collect-sync/{platform}/{username}", response_model=CollectResponse)
async def collect_account_sync(
    platform: str,
    username: str,
    request: CollectRequest = CollectRequest()
):
    """
    同步收集单个账号的数据（等待完成后返回）

    - platform: instagram, tiktok, youtube, twitter
    - username: 账号用户名
    - post_limit: 最多收集多少条帖子 (默认 20)
    """
    # 验证平台
    valid_platforms = ['instagram', 'tiktok', 'youtube', 'twitter']
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {platform}. 支持的平台: {valid_platforms}"
        )

    # 检查 API Key
    api_key_map = {
        'instagram': 'INSTAGRAM_API_KEY',
        'tiktok': 'TIKTOK_API_KEY',
        'youtube': 'YOUTUBE_API_KEY',
        'twitter': 'TWITTER_API_KEY'
    }
    if not os.environ.get(api_key_map[platform]):
        raise HTTPException(
            status_code=400,
            detail=f"未配置 {platform} 的 API Key ({api_key_map[platform]})"
        )

    try:
        collector = get_collector(platform)
        result = collector.collect_all(username, request.post_limit)

        return CollectResponse(
            success=result['success'],
            message=result['message'],
            platform=platform,
            username=username,
            posts_collected=len(result.get('posts', []))
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/collect-all")
async def collect_all(
    background_tasks: BackgroundTasks,
    platform: Optional[str] = None,
    post_limit: int = 20
):
    """
    收集所有账号的数据

    - platform: 可选，只收集指定平台的账号
    - post_limit: 每个账号最多收集多少条帖子
    """
    try:
        db = get_db()
        accounts = db.get_all_accounts(platform)

        if not accounts:
            return {
                "success": False,
                "message": "没有找到要收集的账号"
            }

        task_id = f"all_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 在后台运行所有收集任务
        for account in accounts:
            sub_task_id = f"{account.platform}_{account.username}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            background_tasks.add_task(
                run_collection,
                account.platform,
                account.username,
                post_limit,
                sub_task_id
            )

        return {
            "success": True,
            "message": f"已开始收集 {len(accounts)} 个账号的数据",
            "task_id": task_id,
            "accounts": [
                {"platform": acc.platform, "username": acc.username}
                for acc in accounts
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{task_id}")
async def get_collection_status(task_id: str):
    """获取收集任务状态"""
    if task_id in collection_status:
        return collection_status[task_id]
    else:
        raise HTTPException(status_code=404, detail="任务不存在")


@app.get("/api/status")
async def get_all_status():
    """获取所有任务状态"""
    return {
        "tasks": collection_status,
        "count": len(collection_status)
    }


# ===== 启动服务器 =====

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
