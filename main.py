#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import date

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules import importer, matcher, subscriber, calendar_mod, notifier, exporter, logger, scheduler
from utils.database import db
from models.media import MediaType, WatchStatus


class MovieTrackerCLI:
    def __init__(self):
        self._register_scheduler_tasks()

    def _register_scheduler_tasks(self):
        scheduler.register_task('import', self._task_import)
        scheduler.register_task('match', self._task_match)
        scheduler.register_task('subscription', self._task_subscription)
        scheduler.register_task('export', self._task_export)

    def _task_import(self):
        return importer.run()

    def _task_match(self):
        return matcher.run()

    def _task_subscription(self):
        result = subscriber.run()
        new_eps = subscriber.get_new_episodes_since_last_check()
        if new_eps:
            notifier.notify_new_episodes(new_eps)
        return result

    def _task_export(self):
        return exporter.run()

    def cmd_import(self, args):
        file_path = args.file if hasattr(args, 'file') and args.file else None
        result = importer.run(file_path)
        print(f"\n导入完成: 总计{result['total']}条, 新增{result['new']}条, "
              f"重复{result['duplicates']}条, 失败{result['failed']}条")

    def cmd_match(self, args):
        item_ids = args.ids if hasattr(args, 'ids') and args.ids else None
        full = args.full if hasattr(args, 'full') else False
        result = matcher.run(item_ids, full)
        print(f"\n匹配完成: 总计{result['total']}条, 匹配{result['matched']}条, "
              f"更新{result['updated']}条, 失败{result['failed']}条")

    def cmd_watch(self, args):
        item_id = args.id
        season = args.season if hasattr(args, 'season') else None
        episode = args.episode if hasattr(args, 'episode') else None
        success = matcher.mark_watched(item_id, season, episode)
        if success:
            print("标记成功")
        else:
            print("标记失败")

    def cmd_subscribe(self, args):
        action = args.action
        if action == 'add':
            success = subscriber.subscribe(args.id)
            print("订阅成功" if success else "订阅失败")
        elif action == 'remove':
            success = subscriber.unsubscribe(args.id)
            print("取消成功" if success else "取消失败")
        elif action == 'all':
            count = subscriber.subscribe_all_watching()
            print(f"订阅了 {count} 部剧集")
        elif action == 'check':
            result = subscriber.run()
            print(f"检查完成: {result['new_episodes']} 集新内容")

    def cmd_calendar(self, args):
        view = args.view if hasattr(args, 'view') else 'month'
        if view == 'month':
            year = args.year if hasattr(args, 'year') and args.year else date.today().year
            month = args.month if hasattr(args, 'month') and args.month else date.today().month
            cal_text = calendar_mod.print_text_calendar(year, month)
            print(cal_text)
        elif view == 'week':
            week_data = calendar_mod.generate_week_calendar()
            print(f"\n本周追剧日历 ({week_data['start_date']} ~ {week_data['end_date']})")
            print(f"共 {week_data['total_episodes']} 集更新\n")
            for day in week_data['days']:
                marker = " [今天]" if day['is_today'] else ""
                print(f"{day['weekday_cn']} ({day['date']}){marker}")
                for ep in day['episodes']:
                    print(f"  - {ep['title']} S{ep['season']:02d}E{ep['episode']:02d}")
                if not day['episodes']:
                    print("  (无更新)")
                print()

    def cmd_list(self, args):
        filter_type = args.filter if hasattr(args, 'filter') else 'all'

        if filter_type == 'all':
            items = db.get_all_items()
        elif filter_type == 'wishlist':
            items = db.get_items_by_status(WatchStatus.WISHLIST)
        elif filter_type == 'watching':
            items = db.get_items_by_status(WatchStatus.WATCHING)
        elif filter_type == 'watched':
            items = db.get_items_by_status(WatchStatus.WATCHED)
        elif filter_type == 'subscribed':
            items = db.get_subscribed_items()
        elif filter_type == 'movies':
            items = db.get_items_by_type(MediaType.MOVIE)
        elif filter_type == 'tv':
            items = db.get_items_by_type(MediaType.TV)
        elif filter_type == 'genre' and hasattr(args, 'genre'):
            items = db.get_items_by_genre(args.genre)
        else:
            items = db.get_all_items()

        print(f"\n影视列表 (共 {len(items)} 部)\n")
        print(f"{'标题':<30} {'类型':<6} {'年份':<6} {'状态':<6} {'评分':<6} {'进度':<8}")
        print("-" * 70)
        for item in items:
            type_str = '电影' if item.media_type == MediaType.MOVIE else '剧集' if item.media_type == MediaType.TV else '未知'
            status_map = {
                WatchStatus.WISHLIST: '想看',
                WatchStatus.WATCHING: '在看',
                WatchStatus.WATCHED: '已看',
                WatchStatus.DROPPED: '弃坑',
            }
            status_str = status_map.get(item.watch_status, '未知')
            rating_str = f"{item.rating}" if item.rating else '-'
            progress_str = f"{item.progress_percent}%"
            print(f"{item.title[:28]:<30} {type_str:<6} {item.year or '-':<6} "
                  f"{status_str:<6} {rating_str:<6} {progress_str:<8}")
        print()

    def cmd_search(self, args):
        keyword = args.keyword
        results = db.search(keyword)
        print(f"\n搜索结果: 找到 {len(results)} 部\n")
        for item in results:
            print(f"  [{item.id}] {item.title} ({item.year or '未知'}) - "
                  f"{'电影' if item.media_type == MediaType.MOVIE else '剧集' if item.media_type == MediaType.TV else '未知'}")
        print()

    def cmd_export(self, args):
        fmt = args.format if hasattr(args, 'format') else 'all'
        result = exporter.run(fmt)
        print(f"\n导出完成: {result.get('files_exported', 0)} 个文件")

    def cmd_report(self, args):
        report = exporter.generate_weekly_report()
        text = exporter.print_weekly_report_text(report)
        print(text)

    def cmd_wishlist(self, args):
        action = args.action
        if action == 'add':
            title = args.title
            year = args.year if hasattr(args, 'year') else None
            item = matcher.add_to_wishlist(title, year)
            if item:
                print(f"已添加: {item.title}")
        elif action == 'list':
            items = subscriber.get_wishlist()
            print(f"\n想看清单 (共 {len(items)} 部)\n")
            for i, item in enumerate(items, 1):
                print(f"  {i:2d}. {item.title} ({item.year or '未知'})")
            print()

    def cmd_notify(self, args):
        title = args.title
        message = args.message if hasattr(args, 'message') else ''
        result = notifier.send_notification(title, message)

        print("\n通知发送结果:")
        print(f"  总体状态: {'成功' if result.get('success') else '失败'}")
        print(f"  成功渠道: {result.get('success_count', 0)}/{result.get('total_channels', 0)}")

        channels = result.get('channels', {})
        if channels:
            print("\n  各渠道详情:")
            for ch_name, ch_result in channels.items():
                status = "成功" if ch_result.get('success') else "失败"
                error = f" - {ch_result.get('error', '')}" if not ch_result.get('success') else ""
                print(f"    {ch_name}: {status}{error}")

        if result.get('error'):
            print(f"  错误: {result['error']}")
        print()

    def cmd_logs(self, args):
        lines = args.lines if hasattr(args, 'lines') else 50
        level = args.level if hasattr(args, 'level') else None
        logs = logger.get_recent_logs(lines, level)
        print(f"\n最近日志 (显示 {len(logs)} 条)\n")
        for log in logs:
            print(log.rstrip())
        print()

    def cmd_daemon(self, args):
        action = args.action
        if action == 'start':
            success = scheduler.start_scheduler()
            if success:
                print("调度器已启动, 按 Ctrl+C 停止")
                try:
                    while True:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    scheduler.stop_scheduler()
                    print("\n已停止")
            else:
                print("启动失败")
        elif action == 'stop':
            scheduler.stop_scheduler()
            print("调度器已停止")
        elif action == 'status':
            if scheduler.is_running:
                print("调度器运行中")
            else:
                print("调度器未运行")
            print(f"已注册任务: {', '.join(scheduler.task_names)}")

    def cmd_run(self, args):
        tasks = args.tasks if hasattr(args, 'tasks') and args.tasks else None
        if tasks:
            for task in tasks:
                result = scheduler.run_task(task)
                print(f"{task}: {'成功' if result['success'] else '失败'}")
        else:
            results = scheduler.run_all_tasks()
            print("\n任务执行结果:")
            for name, result in results.items():
                status = "[OK] 成功" if result['success'] else "[FAIL] 失败"
                print(f"  {name}: {status}")

    def cmd_stats(self, args):
        all_items = db.get_all_items()
        movies = db.get_items_by_type(MediaType.MOVIE)
        tv = db.get_items_by_type(MediaType.TV)
        wishlist = db.get_items_by_status(WatchStatus.WISHLIST)
        watching = db.get_items_by_status(WatchStatus.WATCHING)
        watched = db.get_items_by_status(WatchStatus.WATCHED)
        subscribed = db.get_subscribed_items()

        total_eps = sum(i.total_episodes for i in tv)
        watched_eps = sum(i.watched_episodes for i in tv)

        print("\n" + "="*50)
        print("[统计] 片库统计")
        print("="*50)
        print(f"  总数量: {len(all_items)} 部")
        print(f"  电影: {len(movies)} 部")
        print(f"  剧集: {len(tv)} 部")
        print()
        print(f"  想看: {len(wishlist)} 部")
        print(f"  在看: {len(watching)} 部")
        print(f"  已看: {len(watched)} 部")
        print()
        print(f"  订阅更新: {len(subscribed)} 部")
        print(f"  剧集总集数: {total_eps} 集")
        print(f"  已看集数: {watched_eps} 集")
        print(f"  观看进度: {watched_eps/total_eps*100:.1f}%" if total_eps > 0 else "  观看进度: -")
        print("="*50 + "\n")

    def run(self):
        parser = argparse.ArgumentParser(
            description='影视追踪自动化工具 - 给重度影迷整理片单和提醒更新',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
示例:
  python main.py import                        # 导入片单
  python main.py match                         # 匹配影视信息
  python main.py subscribe add <id>            # 订阅更新
  python main.py calendar                      # 查看追剧日历
  python main.py list wishlist                 # 查看想看清单
  python main.py export                        # 导出表格
  python main.py report                        # 生成周报
  python main.py run                           # 执行全部任务
  python main.py daemon start                  # 启动定时任务
            """
        )
        subparsers = parser.add_subparsers(dest='command', help='可用命令')

        import_parser = subparsers.add_parser('import', help='导入本地片单')
        import_parser.add_argument('-f', '--file', help='指定导入文件路径')
        import_parser.set_defaults(func=self.cmd_import)

        match_parser = subparsers.add_parser('match', help='匹配影视信息')
        match_parser.add_argument('--ids', nargs='*', help='指定影视ID')
        match_parser.add_argument('--full', action='store_true', help='完整匹配(忽略缓存)')
        match_parser.set_defaults(func=self.cmd_match)

        watch_parser = subparsers.add_parser('watch', help='标记观看进度')
        watch_parser.add_argument('id', help='影视ID')
        watch_parser.add_argument('-s', '--season', type=int, help='季数')
        watch_parser.add_argument('-e', '--episode', type=int, help='集数')
        watch_parser.set_defaults(func=self.cmd_watch)

        sub_parser = subparsers.add_parser('subscribe', help='订阅管理')
        sub_parser.add_argument('action', choices=['add', 'remove', 'all', 'check'], help='操作')
        sub_parser.add_argument('id', nargs='?', help='影视ID')
        sub_parser.set_defaults(func=self.cmd_subscribe)

        cal_parser = subparsers.add_parser('calendar', help='追剧日历')
        cal_parser.add_argument('--view', choices=['month', 'week'], default='month', help='视图')
        cal_parser.add_argument('--year', type=int, help='年份')
        cal_parser.add_argument('--month', type=int, help='月份')
        cal_parser.set_defaults(func=self.cmd_calendar)

        list_parser = subparsers.add_parser('list', help='影视列表')
        list_parser.add_argument('filter', nargs='?', default='all',
                                choices=['all', 'wishlist', 'watching', 'watched',
                                        'subscribed', 'movies', 'tv', 'genre'],
                                help='筛选条件')
        list_parser.add_argument('--genre', help='类型筛选')
        list_parser.set_defaults(func=self.cmd_list)

        search_parser = subparsers.add_parser('search', help='搜索影视')
        search_parser.add_argument('keyword', help='关键词')
        search_parser.set_defaults(func=self.cmd_search)

        export_parser = subparsers.add_parser('export', help='导出数据')
        export_parser.add_argument('--format', choices=['all', 'xlsx', 'csv', 'json', 'weekly'],
                                  default='all', help='导出格式')
        export_parser.set_defaults(func=self.cmd_export)

        report_parser = subparsers.add_parser('report', help='生成周报')
        report_parser.set_defaults(func=self.cmd_report)

        wish_parser = subparsers.add_parser('wishlist', help='想看清单')
        wish_parser.add_argument('action', choices=['add', 'list'], help='操作')
        wish_parser.add_argument('title', nargs='?', help='影视标题')
        wish_parser.add_argument('--year', type=int, help='年份')
        wish_parser.set_defaults(func=self.cmd_wishlist)

        notif_parser = subparsers.add_parser('notify', help='发送通知')
        notif_parser.add_argument('title', help='通知标题')
        notif_parser.add_argument('message', nargs='?', default='', help='通知内容')
        notif_parser.set_defaults(func=self.cmd_notify)

        log_parser = subparsers.add_parser('logs', help='查看日志')
        log_parser.add_argument('-n', '--lines', type=int, default=50, help='显示行数')
        log_parser.add_argument('--level', choices=['debug', 'info', 'warning', 'error'], help='日志级别')
        log_parser.set_defaults(func=self.cmd_logs)

        daemon_parser = subparsers.add_parser('daemon', help='定时任务守护进程')
        daemon_parser.add_argument('action', choices=['start', 'stop', 'status'], help='操作')
        daemon_parser.set_defaults(func=self.cmd_daemon)

        run_parser = subparsers.add_parser('run', help='执行任务')
        run_parser.add_argument('tasks', nargs='*', help='指定任务')
        run_parser.set_defaults(func=self.cmd_run)

        stats_parser = subparsers.add_parser('stats', help='片库统计')
        stats_parser.set_defaults(func=self.cmd_stats)

        args = parser.parse_args()

        if args.command is None:
            parser.print_help()
            return

        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()


def main():
    cli = MovieTrackerCLI()
    cli.run()


if __name__ == '__main__':
    main()
