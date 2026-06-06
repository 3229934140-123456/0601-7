import calendar
from datetime import date, timedelta
from typing import List, Dict, Optional
from models.media import MediaItem, MediaType, WatchStatus
from utils.database import db
from modules.logger_module import logger


class CalendarModule:
    def __init__(self):
        self.task_name = "calendar"

    def run(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict:
        logger.task_start(self.task_name)
        try:
            today = date.today()
            if year is None:
                year = today.year
            if month is None:
                month = today.month

            cal_data = self.generate_month_calendar(year, month)

            logger.task_end(self.task_name, True,
                           f"生成 {year}年{month}月 追剧日历, 共{len(cal_data['episodes'])}集")
            return cal_data

        except Exception as e:
            logger.error(f"日历生成失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            return {}

    def generate_month_calendar(self, year: int, month: int) -> Dict:
        cal = calendar.monthcalendar(year, month)
        episodes_by_day: Dict[str, List[Dict]] = {}

        for item in db.get_all_items():
            if item.media_type != MediaType.TV:
                continue

            for season in item.seasons:
                for ep in season.episodes:
                    if not ep.air_date:
                        continue
                    if ep.air_date.year == year and ep.air_date.month == month:
                        day_key = ep.air_date.isoformat()
                        if day_key not in episodes_by_day:
                            episodes_by_day[day_key] = []
                        episodes_by_day[day_key].append({
                            'item_id': item.id,
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'watched': ep.watched,
                        })

        weeks = []
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'day': 0, 'episodes': []})
                else:
                    day_date = date(year, month, day)
                    day_key = day_date.isoformat()
                    week_data.append({
                        'day': day,
                        'date': day_key,
                        'episodes': episodes_by_day.get(day_key, []),
                        'is_today': day_date == date.today(),
                    })
            weeks.append(week_data)

        all_episodes = []
        for day_eps in episodes_by_day.values():
            all_episodes.extend(day_eps)
        all_episodes.sort(key=lambda x: (x['season'], x['episode']))

        return {
            'year': year,
            'month': month,
            'month_name': f"{year}年{month}月",
            'weeks': weeks,
            'episodes': all_episodes,
            'total_episodes': len(all_episodes),
        }

    def generate_week_calendar(self, start_date: Optional[date] = None) -> Dict:
        if start_date is None:
            today = date.today()
            start_date = today - timedelta(days=today.weekday())

        days = []
        episodes_by_day: Dict[str, List[Dict]] = {}

        for i in range(7):
            d = start_date + timedelta(days=i)
            days.append({
                'date': d.isoformat(),
                'weekday': d.strftime('%A'),
                'weekday_cn': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()],
                'is_today': d == date.today(),
            })

        for item in db.get_all_items():
            if item.media_type != MediaType.TV:
                continue

            for season in item.seasons:
                for ep in season.episodes:
                    if not ep.air_date:
                        continue
                    if start_date <= ep.air_date < start_date + timedelta(days=7):
                        day_key = ep.air_date.isoformat()
                        if day_key not in episodes_by_day:
                            episodes_by_day[day_key] = []
                        episodes_by_day[day_key].append({
                            'item_id': item.id,
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'watched': ep.watched,
                        })

        for day in days:
            day['episodes'] = episodes_by_day.get(day['date'], [])

        total_eps = sum(len(d['episodes']) for d in days)

        return {
            'start_date': start_date.isoformat(),
            'end_date': (start_date + timedelta(days=6)).isoformat(),
            'days': days,
            'total_episodes': total_eps,
        }

    def get_today_episodes(self) -> List[Dict]:
        today = date.today()
        episodes = []

        for item in db.get_all_items():
            if item.media_type != MediaType.TV:
                continue

            for season in item.seasons:
                for ep in season.episodes:
                    if ep.air_date and ep.air_date == today:
                        episodes.append({
                            'item_id': item.id,
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'watched': ep.watched,
                        })

        return episodes

    def filter_by_genre(self, genre: str) -> List[MediaItem]:
        return db.get_items_by_genre(genre)

    def filter_by_status(self, status: WatchStatus) -> List[MediaItem]:
        return db.get_items_by_status(status)

    def filter_by_type(self, media_type: MediaType) -> List[MediaItem]:
        return db.get_items_by_type(media_type)

    def get_all_genres(self) -> List[str]:
        genres = set()
        for item in db.get_all_items():
            for g in item.genres:
                genres.add(g)
        return sorted(list(genres))

    def search_shows(self, keyword: str) -> List[MediaItem]:
        return db.search(keyword)

    def print_text_calendar(self, year: int, month: int) -> str:
        cal_data = self.generate_month_calendar(year, month)
        lines = []
        lines.append(f"{'='*50}")
        lines.append(f"{cal_data['month_name']} 追剧日历")
        lines.append(f"{'='*50}")
        lines.append(f"一  二  三  四  五  六  日")

        for week in cal_data['weeks']:
            line = ""
            for day in week:
                if day['day'] == 0:
                    line += "   "
                else:
                    marker = "*" if day.get('is_today') else " "
                    ep_count = len(day.get('episodes', []))
                    if ep_count > 0:
                        line += f"{day['day']:2d}{marker}({ep_count})"
                    else:
                        line += f"{day['day']:2d}{marker}  "
            lines.append(line)

        lines.append("")
        lines.append(f"本月共 {cal_data['total_episodes']} 集更新")
        lines.append(f"{'='*50}")

        if cal_data['episodes']:
            lines.append("\n剧集详情:")
            for ep in cal_data['episodes'][:10]:
                lines.append(f"  {ep['title']} S{ep['season']:02d}E{ep['episode']:02d}")
            if len(cal_data['episodes']) > 10:
                lines.append(f"  ... 还有 {len(cal_data['episodes']) - 10} 集")

        return "\n".join(lines)


calendar_mod = CalendarModule()
