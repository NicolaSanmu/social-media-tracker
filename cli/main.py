#!/usr/bin/env python3
"""
社媒数据追踪工具 - CLI 入口

使用方法:
    python -m cli.main <command> [options]

命令:
    add       添加要追踪的账号
    remove    移除账号
    list      列出所有账号
    collect   采集数据
    report    生成报表
    dashboard 显示仪表盘
"""

import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db, Account
from core.collectors import get_collector, collect_all_accounts
from core.report import report_generator


def cmd_add(args):
    """添加账号"""
    platform = args.platform.lower()
    username = args.username

    if platform not in ['instagram', 'tiktok', 'youtube', 'twitter']:
        print(f"错误: 不支持的平台 '{platform}'，支持的平台: instagram, tiktok, youtube, twitter")
        return 1

    # 检查是否已存在
    existing = db.get_account(platform, username)
    if existing:
        print(f"账号已存在: [{platform}] @{username}")
        return 0

    # 创建账号记录
    account = Account(
        id=None,
        platform=platform,
        username=username,
        display_name=args.display_name or username,
        account_id='',  # 采集时填充
        bio=''
    )
    account_id = db.add_account(account)
    print(f"✓ 已添加账号: [{platform}] @{username} (ID: {account_id})")

    # 如果指定了立即采集
    if args.collect:
        collector = get_collector(platform)
        result = collector.collect_all(username)
        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"✗ {result['message']}")

    return 0


def cmd_remove(args):
    """移除账号"""
    platform = args.platform.lower()
    username = args.username

    account = db.get_account(platform, username)
    if not account:
        print(f"账号不存在: [{platform}] @{username}")
        return 1

    if not args.force:
        confirm = input(f"确定要删除账号 [{platform}] @{username} 及其所有数据吗? (y/N): ")
        if confirm.lower() != 'y':
            print("已取消")
            return 0

    db.delete_account(account.id)
    print(f"✓ 已删除账号: [{platform}] @{username}")
    return 0


def cmd_list(args):
    """列出所有账号"""
    platform = args.platform.lower() if args.platform else None
    accounts = db.get_all_accounts(platform)

    if not accounts:
        print("没有找到账号")
        return 0

    print(f"\n{'平台':<12} {'用户名':<20} {'显示名':<20} {'粉丝数':<12} {'帖子数':<10}")
    print("-" * 80)

    for account in accounts:
        print(f"{account.platform:<12} @{account.username:<19} {account.display_name:<20} "
              f"{account.follower_count:<12,} {account.post_count:<10}")

    print(f"\n共 {len(accounts)} 个账号")
    return 0


def cmd_collect(args):
    """采集数据"""
    platform = args.platform.lower() if args.platform else None
    username = args.username

    if username:
        # 采集单个账号
        if not platform:
            print("错误: 指定用户名时必须同时指定平台")
            return 1

        collector = get_collector(platform)
        result = collector.collect_all(username, post_limit=args.limit)

        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"✗ {result['message']}")
    else:
        # 采集所有账号
        print("正在采集所有账号...")
        results = collect_all_accounts(platform, post_limit=args.limit)

        success_count = sum(1 for r in results if r['success'])
        print(f"\n采集完成: {success_count}/{len(results)} 成功")

    return 0


def cmd_report(args):
    """生成报表"""
    report_type = args.type

    if report_type == 'weekly':
        filepath = report_generator.generate_weekly_report(
            platform=args.platform.lower() if args.platform else None
        )
    elif report_type == 'posts':
        filepath = report_generator.generate_post_report(
            platform=args.platform.lower() if args.platform else None,
            limit=args.limit
        )
    elif report_type == 'accounts':
        filepath = report_generator.generate_account_summary()
    else:
        print(f"错误: 未知的报表类型 '{report_type}'")
        return 1

    print(f"✓ 报表已生成: {filepath}")
    return 0


def cmd_dashboard(args):
    """显示仪表盘"""
    report_generator.print_dashboard()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='社媒数据追踪工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # add 命令
    parser_add = subparsers.add_parser('add', help='添加要追踪的账号')
    parser_add.add_argument('platform', help='平台 (instagram/tiktok/youtube/twitter)')
    parser_add.add_argument('username', help='用户名')
    parser_add.add_argument('-n', '--display-name', help='显示名称')
    parser_add.add_argument('-c', '--collect', action='store_true', help='添加后立即采集')
    parser_add.set_defaults(func=cmd_add)

    # remove 命令
    parser_remove = subparsers.add_parser('remove', help='移除账号')
    parser_remove.add_argument('platform', help='平台 (instagram/tiktok/youtube/twitter)')
    parser_remove.add_argument('username', help='用户名')
    parser_remove.add_argument('-f', '--force', action='store_true', help='强制删除，不确认')
    parser_remove.set_defaults(func=cmd_remove)

    # list 命令
    parser_list = subparsers.add_parser('list', help='列出所有账号')
    parser_list.add_argument('-p', '--platform', help='按平台筛选')
    parser_list.set_defaults(func=cmd_list)

    # collect 命令
    parser_collect = subparsers.add_parser('collect', help='采集数据')
    parser_collect.add_argument('-p', '--platform', help='平台筛选')
    parser_collect.add_argument('-u', '--username', help='指定用户名（需同时指定平台）')
    parser_collect.add_argument('-l', '--limit', type=int, default=20, help='每账号最大帖子数')
    parser_collect.set_defaults(func=cmd_collect)

    # report 命令
    parser_report = subparsers.add_parser('report', help='生成报表')
    parser_report.add_argument('type', choices=['weekly', 'posts', 'accounts'],
                               help='报表类型: weekly(周报), posts(帖子明细), accounts(账号汇总)')
    parser_report.add_argument('-p', '--platform', help='平台筛选')
    parser_report.add_argument('-l', '--limit', type=int, default=100, help='帖子报表的最大条数')
    parser_report.set_defaults(func=cmd_report)

    # dashboard 命令
    parser_dashboard = subparsers.add_parser('dashboard', help='显示仪表盘')
    parser_dashboard.set_defaults(func=cmd_dashboard)

    # 解析参数
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
