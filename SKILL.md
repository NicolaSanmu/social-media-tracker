---
name: social-media-tracker
description: 社媒矩阵数据追踪工具 - 追踪 Instagram 和 TikTok 账号的视频数据（浏览量、点赞、评论等）
---

# 社媒数据追踪工具

追踪你的社媒矩阵账号数据，支持 Instagram 和 TikTok。

## 功能

- **账号管理**: 添加/删除要追踪的社媒账号
- **数据采集**: 定时或手动采集视频/帖子数据
- **指标追踪**: 浏览量、点赞、评论、分享、收藏等
- **报表生成**: 周报、帖子明细、账号汇总
- **趋势分析**: 粉丝变化、互动率计算

## 支持的平台

| 平台 | 状态 | 数据类型 |
|------|------|----------|
| Instagram | ✓ | Reels, Posts, Stories |
| TikTok | ✓ | Videos |
| YouTube | ✓ | Videos |
| X/Twitter | ✓ | Tweets |

## 使用方法

### 在 Claude Code 中使用

```
# 查看仪表盘
帮我查看社媒数据仪表盘

# 添加账号
帮我添加一个 TikTok 账号 @username

# 采集数据
帮我更新所有账号的数据

# 生成周报
帮我生成本周的社媒周报
```

### CLI 命令

```bash
cd ~/creator-tools/social-media-tracker

# 设置 API Key (必须)
export INSTAGRAM_API_KEY="你的API密钥"

# 添加账号
python3 -m cli.main add instagram username
python3 -m cli.main add tiktok username
python3 -m cli.main add youtube @handle          # YouTube 频道 handle
python3 -m cli.main add twitter @handle          # X/Twitter 用户名

# 列出账号
python3 -m cli.main list

# 采集数据
python3 -m cli.main collect                     # 采集所有账号
python3 -m cli.main collect -p instagram        # 只采集 Instagram
python3 -m cli.main collect -p instagram -u xxx # 采集指定账号
python3 -m cli.main collect -l 10               # 每账号最多采集10条帖子

# 生成报表
python3 -m cli.main report weekly               # 周报
python3 -m cli.main report posts                # 帖子明细
python3 -m cli.main report accounts             # 账号汇总

# 显示仪表盘
python3 -m cli.main dashboard
```

### Web 仪表盘

启动 Web 可视化界面：

```bash
cd ~/creator-tools/social-media-tracker

# 启动 Web 服务
uvicorn web.app:app --port 8000

# 访问浏览器
open http://localhost:8000
```

**Web 功能：**
- `/` - 仪表盘首页（账号概览、热门帖子）
- `/accounts` - 账号管理页面
- `/account/<id>` - 单账号详情 + 趋势图表
- `/api/*` - REST API 端点

## 数据存储

- 数据库: `data/social_media.db` (SQLite)
- 报表: `reports/` 目录下的 CSV 文件

## API 配置

### Instagram (Instagram120 RapidAPI)

1. 注册 RapidAPI: https://rapidapi.com/
2. 订阅 Instagram120 API: https://rapidapi.com/3205/api/instagram120
3. 获取 API Key 后设置环境变量:

```bash
export INSTAGRAM_API_KEY="你的RapidAPI密钥"
```

**支持的端点:**
- `profile` - 获取用户信息（粉丝数、关注数、简介等）
- `posts` - 获取用户帖子（Reels、图片、视频及互动数据）

### TikTok (TikTok-API23 RapidAPI)

1. 注册 RapidAPI: https://rapidapi.com/
2. 订阅 TikTok-API23: https://rapidapi.com/tikapi-tikapi-default/api/tiktok-api23
3. 获取 API Key 后设置环境变量:

```bash
export TIKTOK_API_KEY="你的RapidAPI密钥"
```

**支持的数据:**
- 用户信息（粉丝数、关注数、视频数等）
- 视频列表（播放量、点赞、评论、分享、收藏）

### YouTube (YouTube Data API v3)

1. 前往 Google Cloud Console: https://console.cloud.google.com/
2. 创建项目并启用 YouTube Data API v3
3. 创建 API Key 后设置环境变量:

```bash
export YOUTUBE_API_KEY="你的GoogleAPI密钥"
```

**支持的数据:**
- 频道信息（订阅数、视频数）
- 视频列表（播放量、点赞、评论）

**用户名格式:**
- `@handle` - YouTube handle (如 @MrBeast)
- `UCxxxxxx` - 频道 ID

### X/Twitter (Twitter-API45 RapidAPI)

1. 注册 RapidAPI: https://rapidapi.com/
2. 订阅 Twitter-API45: https://rapidapi.com/alexanderxbx/api/twitter-api45
3. 获取 API Key 后设置环境变量:

```bash
export TWITTER_API_KEY="你的RapidAPI密钥"
```

**支持的数据:**
- 账号信息（粉丝数、关注数、推文数）
- 推文列表（浏览量、点赞、转发、评论）

## 定时采集

使用 cron 设置每周自动采集:

```bash
# 每周一早上 9 点采集
0 9 * * 1 cd ~/creator-tools/social-media-tracker && python -m cli.main collect
```

## 数据指标说明

| 指标 | 说明 |
|------|------|
| views | 浏览量/播放量 |
| likes | 点赞数 |
| comments | 评论数 |
| shares | 分享数 |
| saves | 收藏数 |
| plays | 播放次数（视频） |
| reach | 触达人数 |
| impressions | 曝光次数 |
