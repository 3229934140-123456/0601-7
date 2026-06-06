import os
import csv
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from models.media import MediaItem, MediaType, WatchStatus
from utils.config_manager import config
from utils.database import db
from utils.helpers import ensure_dir, format_date, format_runtime, save_json
from modules.logger_module import logger

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class ExportModule:
    def __init__(self):
        self.task_name = "export"
        ensure_dir(config.export_dir)

    def run(self, fmt: str = "all") -> Dict:
        logger.task_start(self.task_name)
        stats = {'files_exported': 0, 'items_exported': 0, 'format': fmt}

        try:
            list_formats = ['xlsx', 'csv', 'json']

            if fmt in list_formats:
                if self._export_list(fmt):
                    stats['files_exported'] += 1
            elif fmt == "all":
                for f in list_formats:
                    if f == 'xlsx' and not PANDAS_AVAILABLE:
                        continue
                    if self._export_list(f):
                        stats['files_exported'] += 1
                report = self.generate_weekly_report()
                if report:
                    stats['files_exported'] += 1
                    stats['weekly_report'] = report
            elif fmt == "list":
                for f in list_formats:
                    if f == 'xlsx' and not PANDAS_AVAILABLE:
                        continue
                    if self._export_list(f):
                        stats['files_exported'] += 1
            elif fmt == "weekly":
                report = self.generate_weekly_report()
                if report:
                    stats['files_exported'] += 1
                    stats['weekly_report'] = report

            stats['items_exported'] = db.count

            logger.task_end(self.task_name, True,
                           f"导出 {stats['files_exported']} 个文件, "
                           f"共 {stats['items_exported']} 条记录")
            return stats

        except Exception as e:
            logger.error(f"导出任务失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            return stats

    def _export_list(self, file_format: str) -> bool:
        items = db.get_all_items()
        if not items:
            logger.warning("没有数据可导出", self.task_name)
            return False

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"media_list_{timestamp}.{file_format}"
        filepath = os.path.join(config.export_dir, filename)

        try:
            if file_format == 'csv':
                self._export_csv(items, filepath)
            elif file_format == 'xlsx' and PANDAS_AVAILABLE:
                self._export_xlsx(items, filepath)
            elif file_format == 'xlsx' and not PANDAS_AVAILABLE:
                logger.warning("pandas未安装, 跳过xlsx导出", self.task_name)
                return False
            elif file_format == 'json':
                self._export_json(items, filepath)
            else:
                logger.warning(f"不支持的格式: {file_format}", self.task_name)
                return False

            logger.info(f"导出 {file_format.upper()}: {filename}", self.task_name)
            return True
        except Exception as e:
            logger.error(f"导出{file_format}失败: {e}", self.task_name)
            return False

    def _export_csv(self, items: List[MediaItem], filepath: str) -> None:
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                '标题', '原名', '类型', '年份', '状态', '评分',
                '我的评分', '观看状态', '进度', '总集数', '已看集数',
                '类型标签', '导演', '主演', '简介', '备注', '标签'
            ])

            for item in items:
                writer.writerow([
                    item.title,
                    item.original_title,
                    self._type_cn(item.media_type),
                    item.year or '',
                    item.status,
                    item.rating or '',
                    item.my_rating or '',
                    self._status_cn(item.watch_status),
                    f"{item.progress_percent}%",
                    item.total_episodes or '',
                    item.watched_episodes or '',
                    '、'.join(item.genres),
                    '、'.join(item.directors),
                    '、'.join(item.cast),
                    item.overview,
                    item.notes,
                    '、'.join(item.tags),
                ])

    def _export_xlsx(self, items: List[MediaItem], filepath: str) -> None:
        data = []
        for item in items:
            data.append({
                '标题': item.title,
                '原名': item.original_title,
                '类型': self._type_cn(item.media_type),
                '年份': item.year or '',
                '状态': item.status,
                '评分': item.rating or '',
                '我的评分': item.my_rating or '',
                '观看状态': self._status_cn(item.watch_status),
                '进度': f"{item.progress_percent}%",
                '总集数': item.total_episodes or '',
                '已看集数': item.watched_episodes or '',
                '类型标签': '、'.join(item.genres),
                '导演': '、'.join(item.directors),
                '主演': '、'.join(item.cast),
                '时长': format_runtime(item.runtime),
                '首播日期': format_date(item.first_air_date),
                '简介': item.overview,
                '备注': item.notes,
                '标签': '、'.join(item.tags),
                '是否订阅': '是' if item.subscribed else '否',
            })

        df = pd.DataFrame(data)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='全部影视', index=False)

            tv_items = [item for item in items if item.media_type == MediaType.TV]
            if tv_items:
                tv_data = [{
                    '标题': item.title,
                    '状态': item.status,
                    '总季数': item.total_seasons,
                    '总集数': item.total_episodes,
                    '已看集数': item.watched_episodes,
                    '进度': f"{item.progress_percent}%",
                    '下一集': format_date(item.next_episode_date),
                    '下集信息': item.next_episode_info,
                } for item in tv_items]
                pd.DataFrame(tv_data).to_excel(writer, sheet_name='剧集详情', index=False)

            wishlist = [item for item in items if item.watch_status == WatchStatus.WISHLIST]
            if wishlist:
                wish_data = [{
                    '标题': item.title,
                    '类型': self._type_cn(item.media_type),
                    '年份': item.year or '',
                    '评分': item.rating or '',
                    '类型标签': '、'.join(item.genres),
                } for item in wishlist]
                pd.DataFrame(wish_data).to_excel(writer, sheet_name='想看清单', index=False)

    def _export_json(self, items: List[MediaItem], filepath: str) -> None:
        from utils.database import MediaDatabase
        db_temp = MediaDatabase.__new__(MediaDatabase)
        db_temp.items = {item.id: item for item in items}
        data = [db_temp._media_item_to_dict(item) for item in items]
        save_json(data, filepath)

    def _type_cn(self, media_type: MediaType) -> str:
        mapping = {
            MediaType.MOVIE: '电影',
            MediaType.TV: '剧集',
            MediaType.UNKNOWN: '未知',
        }
        return mapping.get(media_type, '未知')

    def _status_cn(self, status: WatchStatus) -> str:
        mapping = {
            WatchStatus.WISHLIST: '想看',
            WatchStatus.WATCHING: '在看',
            WatchStatus.WATCHED: '已看',
            WatchStatus.DROPPED: '弃坑',
        }
        return mapping.get(status, '未知')

    def generate_weekly_report(self) -> Dict:
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        report = {
            'generated_at': datetime.now().isoformat(),
            'period': {
                'start': start_of_week.isoformat(),
                'end': end_of_week.isoformat(),
            },
            'summary': {
                'total_items': db.count,
                'movies': len(db.get_items_by_type(MediaType.MOVIE)),
                'tv_shows': len(db.get_items_by_type(MediaType.TV)),
                'wishlist': len(db.get_items_by_status(WatchStatus.WISHLIST)),
                'watching': len(db.get_items_by_status(WatchStatus.WATCHING)),
                'watched': len(db.get_items_by_status(WatchStatus.WATCHED)),
                'subscribed': len(db.get_subscribed_items()),
            },
            'this_week_episodes': [],
            'upcoming_episodes': [],
            'top_rated': [],
            'progress_summary': {},
        }

        for item in db.get_all_items():
            if item.media_type != MediaType.TV:
                continue

            for season in item.seasons:
                for ep in season.episodes:
                    if not ep.air_date:
                        continue
                    if start_of_week <= ep.air_date <= end_of_week:
                        report['this_week_episodes'].append({
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'air_date': ep.air_date.isoformat(),
                            'watched': ep.watched,
                        })
                    elif ep.air_date > end_of_week:
                        report['upcoming_episodes'].append({
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'air_date': ep.air_date.isoformat(),
                        })

        all_items = db.get_all_items()
        rated = [i for i in all_items if i.rating]
        rated.sort(key=lambda x: x.rating or 0, reverse=True)
        report['top_rated'] = [
            {'title': i.title, 'rating': i.rating, 'year': i.year}
            for i in rated[:10]
        ]

        total_eps = sum(i.total_episodes for i in all_items if i.media_type == MediaType.TV)
        watched_eps = sum(i.watched_episodes for i in all_items if i.media_type == MediaType.TV)
        report['progress_summary'] = {
            'total_episodes': total_eps,
            'watched_episodes': watched_eps,
            'progress_percent': round((watched_eps / total_eps * 100), 1) if total_eps > 0 else 0,
        }

        report['this_week_episodes'].sort(key=lambda x: x['air_date'])
        report['upcoming_episodes'].sort(key=lambda x: x['air_date'])
        report['upcoming_episodes'] = report['upcoming_episodes'][:20]

        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"weekly_report_{timestamp}.json"
        filepath = os.path.join(config.export_dir, filename)
        save_json(report, filepath)

        logger.info(f"生成周报: {filename}", self.task_name)
        return report

    def print_weekly_report_text(self, report: Optional[Dict] = None) -> str:
        if report is None:
            report = self.generate_weekly_report()

        lines = []
        lines.append("="*60)
        lines.append("[周报] 影视追踪周报")
        lines.append("="*60)

        period = report.get('period', {})
        lines.append(f"统计周期: {period.get('start', '')} 至 {period.get('end', '')}")
        lines.append("")

        summary = report.get('summary', {})
        lines.append("[片库] 片库统计")
        lines.append(f"  总数量: {summary.get('total_items', 0)} 部")
        lines.append(f"  电影: {summary.get('movies', 0)} 部")
        lines.append(f"  剧集: {summary.get('tv_shows', 0)} 部")
        lines.append(f"  想看: {summary.get('wishlist', 0)} 部")
        lines.append(f"  在看: {summary.get('watching', 0)} 部")
        lines.append(f"  已看: {summary.get('watched', 0)} 部")
        lines.append(f"  订阅更新: {summary.get('subscribed', 0)} 部")
        lines.append("")

        this_week = report.get('this_week_episodes', [])
        lines.append(f"[本周] 本周更新 ({len(this_week)} 集)")
        for ep in this_week[:10]:
            watched_mark = "x" if ep.get('watched') else " "
            lines.append(f"  [{watched_mark}] {ep['air_date']} "
                        f"{ep['title']} S{ep['season']:02d}E{ep['episode']:02d} "
                        f"- {ep.get('ep_title', '')}")
        if len(this_week) > 10:
            lines.append(f"  ... 还有 {len(this_week) - 10} 集")
        lines.append("")

        upcoming = report.get('upcoming_episodes', [])
        lines.append(f"[即将] 即将上映 ({len(upcoming)} 集)")
        for ep in upcoming[:10]:
            lines.append(f"  {ep['air_date']} "
                        f"{ep['title']} S{ep['season']:02d}E{ep['episode']:02d} "
                        f"- {ep.get('ep_title', '')}")
        lines.append("")

        progress = report.get('progress_summary', {})
        lines.append("[进度] 观看进度")
        lines.append(f"  总集数: {progress.get('total_episodes', 0)}")
        lines.append(f"  已看: {progress.get('watched_episodes', 0)}")
        lines.append(f"  进度: {progress.get('progress_percent', 0)}%")
        lines.append("")

        top_rated = report.get('top_rated', [])
        lines.append("[评分] 评分TOP10")
        for i, item in enumerate(top_rated[:10], 1):
            lines.append(f"  {i:2d}. {item['title']} ({item.get('year', '未知')}) - {item['rating']}分")
        lines.append("")

        lines.append("="*60)
        return "\n".join(lines)


exporter = ExportModule()
