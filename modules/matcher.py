import os
import json
import random
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from models.media import MediaItem, MediaType, WatchStatus, Season, Episode
from utils.helpers import save_json, load_json, parse_date
from utils.config_manager import config
from utils.database import db
from modules.logger_module import logger


class MatchModule:
    def __init__(self):
        self.task_name = "match"
        self.cache_dir = os.path.join(config.data_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.stats = {
            'total': 0,
            'matched': 0,
            'updated': 0,
            'failed': 0,
        }

    def run(self, item_ids: Optional[List[str]] = None, full_match: bool = False) -> Dict:
        logger.task_start(self.task_name)
        self.stats = {'total': 0, 'matched': 0, 'updated': 0, 'failed': 0}

        try:
            if item_ids:
                items = [db.get_item(iid) for iid in item_ids if db.get_item(iid)]
            else:
                items = db.get_all_items()

            self.stats['total'] = len(items)

            for item in items:
                try:
                    result = self._match_item(item, full_match)
                    if result:
                        self.stats['matched'] += 1
                        if self._is_updated(item, result):
                            self.stats['updated'] += 1
                        self._apply_match_result(item, result)
                        db.update_item(item)
                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"匹配失败 {item.title}: {e}", self.task_name)

            if self.stats['updated'] > 0:
                db.save()

            logger.task_end(self.task_name, True,
                           f"匹配{self.stats['matched']}条, 更新{self.stats['updated']}条, 失败{self.stats['failed']}条")
            return self.stats

        except Exception as e:
            logger.error(f"匹配任务失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            return self.stats

    def _match_item(self, item: MediaItem, full_match: bool = False) -> Optional[Dict]:
        cache_key = f"match_{item.id}"
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        cache_ttl = config.get('match.cache_ttl_hours', 24)

        cached = load_json(cache_file)
        if cached and config.get('match.cache_enabled', True):
            cache_time = datetime.fromisoformat(cached.get('_cached_at', '')) if cached.get('_cached_at') else None
            if cache_time and (datetime.now() - cache_time) < timedelta(hours=cache_ttl) and not full_match:
                logger.debug(f"使用缓存: {item.title}", self.task_name)
                return cached

        result = self._fetch_media_info(item)

        if result and config.get('match.cache_enabled', True):
            result['_cached_at'] = datetime.now().isoformat()
            save_json(result, cache_file)

        return result

    def _fetch_media_info(self, item: MediaItem) -> Optional[Dict]:
        if config.get('match.tmdb_enabled', False) and config.get('match.tmdb_api_key'):
            return self._fetch_from_tmdb(item)
        elif config.get('match.douban_enabled', False):
            return self._fetch_from_douban(item)
        else:
            return self._generate_demo_data(item)

    def _fetch_from_tmdb(self, item: MediaItem) -> Optional[Dict]:
        logger.debug(f"从TMDB获取: {item.title}", self.task_name)
        return self._generate_demo_data(item)

    def _fetch_from_douban(self, item: MediaItem) -> Optional[Dict]:
        logger.debug(f"从豆瓣获取: {item.title}", self.task_name)
        return self._generate_demo_data(item)

    def _generate_demo_data(self, item: MediaItem) -> Dict:
        data = {
            'title': item.title,
            'original_title': item.original_title or item.title,
            'overview': item.overview or f"这是《{item.title}》的简介。",
            'rating': item.rating or round(random.uniform(6.0, 9.5), 1),
            'rating_count': item.rating_count or random.randint(1000, 100000),
            'genres': item.genres or self._random_genres(),
            'directors': item.directors or self._random_directors(),
            'cast': item.cast or self._random_cast(),
            'runtime': item.runtime or random.randint(90, 150),
            'status': item.status or self._guess_status(item),
        }

        if item.media_type == MediaType.TV or (item.media_type == MediaType.UNKNOWN and len(item.seasons) > 0):
            data['media_type'] = 'tv'
            data['seasons'] = self._generate_tv_seasons(item)
            data['first_air_date'] = item.first_air_date.isoformat() if item.first_air_date else self._random_past_date(5)
            data['last_air_date'] = date.today().isoformat()
            next_ep = self._generate_next_episode(item)
            data['next_episode_date'] = next_ep['date']
            data['next_episode_info'] = next_ep['info']
        else:
            data['media_type'] = 'movie'
            data['first_air_date'] = item.first_air_date.isoformat() if item.first_air_date else self._random_past_date(10)
            data['seasons'] = []

        return data

    def _random_genres(self) -> List[str]:
        all_genres = ['剧情', '喜剧', '动作', '科幻', '悬疑', '犯罪', '爱情', '恐怖', '动画', '纪录片', '冒险', '奇幻']
        num = random.randint(1, 3)
        return random.sample(all_genres, num)

    def _random_directors(self) -> List[str]:
        directors = ['导演甲', '导演乙', '导演丙', '导演丁']
        num = random.randint(1, 2)
        return random.sample(directors, num)

    def _random_cast(self) -> List[str]:
        cast = ['演员A', '演员B', '演员C', '演员D', '演员E', '演员F']
        num = random.randint(3, 5)
        return random.sample(cast, num)

    def _guess_status(self, item: MediaItem) -> str:
        if item.watch_status == WatchStatus.WATCHED:
            return "已完结"
        return "在播" if item.media_type == MediaType.TV else "已上映"

    def _random_past_date(self, years_ago: int) -> str:
        today = date.today()
        days = random.randint(0, years_ago * 365)
        past_date = today - timedelta(days=days)
        return past_date.isoformat()

    def _generate_tv_seasons(self, item: MediaItem) -> List[Dict]:
        existing_seasons = len(item.seasons)
        num_seasons = max(existing_seasons, random.randint(1, 5))
        seasons = []

        for s in range(1, num_seasons + 1):
            num_eps = random.randint(8, 24)
            episodes = []
            start_date = date.today() - timedelta(days=random.randint(365, 365 * 3))

            for e in range(1, num_eps + 1):
                air_date = start_date + timedelta(days=(e - 1) * 7)
                episodes.append({
                    'season_number': s,
                    'episode_number': e,
                    'title': f"第{e}集",
                    'air_date': air_date.isoformat(),
                    'runtime': random.randint(40, 60),
                    'overview': f"第{s}季第{e}集的剧情简介。",
                })

            seasons.append({
                'season_number': s,
                'title': f"第{s}季",
                'air_date': start_date.isoformat(),
                'overview': f"第{s}季的简介。",
                'episodes': episodes,
            })

        return seasons

    def _generate_next_episode(self, item: MediaItem) -> Dict:
        max_season = 0
        max_ep = 0

        for s in item.seasons:
            if s.season_number > max_season:
                max_season = s.season_number
                max_ep = s.total_episodes

        if max_season == 0:
            max_season = 1
            max_ep = 0

        next_ep_date = date.today() + timedelta(days=random.randint(1, 30))
        return {
            'date': next_ep_date.isoformat(),
            'info': f"S{max_season:02d}E{max_ep + 1:02d}",
        }

    def _is_updated(self, old_item: MediaItem, new_data: Dict) -> bool:
        if new_data.get('rating') != old_item.rating:
            return True
        if new_data.get('status') != old_item.status:
            return True
        if len(new_data.get('seasons', [])) != len(old_item.seasons):
            return True
        return False

    def _apply_match_result(self, item: MediaItem, data: Dict) -> None:
        if data.get('title') and not item.title:
            item.title = data['title']
        if data.get('original_title'):
            item.original_title = data['original_title']
        if data.get('overview'):
            item.overview = data['overview']
        if data.get('rating'):
            item.rating = data['rating']
        if data.get('rating_count'):
            item.rating_count = data['rating_count']
        if data.get('genres'):
            item.genres = data['genres']
        if data.get('directors'):
            item.directors = data['directors']
        if data.get('cast'):
            item.cast = data['cast']
        if data.get('runtime'):
            item.runtime = data['runtime']
        if data.get('status'):
            item.status = data['status']

        media_type = data.get('media_type', '')
        if media_type == 'movie':
            item.media_type = MediaType.MOVIE
        elif media_type == 'tv':
            item.media_type = MediaType.TV

        if data.get('first_air_date'):
            item.first_air_date = parse_date(data['first_air_date'])
        if data.get('last_air_date'):
            item.last_air_date = parse_date(data['last_air_date'])

        if data.get('seasons') and item.media_type == MediaType.TV:
            self._apply_seasons(item, data['seasons'])

        if data.get('next_episode_date'):
            item.next_episode_date = parse_date(data['next_episode_date'])
        if data.get('next_episode_info'):
            item.next_episode_info = data['next_episode_info']

    def _apply_seasons(self, item: MediaItem, seasons_data: List[Dict]) -> None:
        existing_seasons = {s.season_number: s for s in item.seasons}

        for s_data in seasons_data:
            s_num = s_data.get('season_number', 1)
            if s_num in existing_seasons:
                season = existing_seasons[s_num]
            else:
                season = Season(
                    season_number=s_num,
                    title=s_data.get('title', f"第{s_num}季"),
                )
                item.seasons.append(season)

            if s_data.get('title'):
                season.title = s_data['title']
            if s_data.get('air_date'):
                season.air_date = parse_date(s_data['air_date'])
            if s_data.get('overview'):
                season.overview = s_data['overview']

            episodes_data = s_data.get('episodes', [])
            existing_eps = {ep.episode_number: ep for ep in season.episodes}

            for ep_data in episodes_data:
                ep_num = ep_data.get('episode_number', 1)
                if ep_num in existing_eps:
                    ep = existing_eps[ep_num]
                else:
                    ep = Episode(
                        season_number=s_num,
                        episode_number=ep_num,
                    )
                    season.episodes.append(ep)

                if ep_data.get('title'):
                    ep.title = ep_data['title']
                if ep_data.get('air_date'):
                    ep.air_date = parse_date(ep_data['air_date'])
                if ep_data.get('runtime'):
                    ep.runtime = ep_data['runtime']
                if ep_data.get('overview'):
                    ep.overview = ep_data['overview']

            season.episodes.sort(key=lambda e: e.episode_number)

        item.seasons.sort(key=lambda s: s.season_number)

    def mark_watched(self, item_id: str, season: Optional[int] = None, episode: Optional[int] = None) -> bool:
        item = db.get_item(item_id)
        if not item:
            logger.warning(f"找不到影视: {item_id}", self.task_name)
            return False

        try:
            if item.media_type == MediaType.MOVIE or (season is None and episode is None):
                item.watch_status = WatchStatus.WATCHED
                for s in item.seasons:
                    for ep in s.episodes:
                        ep.watched = True
                        ep.watched_date = date.today()
                logger.info(f"标记已看完: {item.title}", self.task_name)
            elif season is not None and episode is None:
                s = item.get_season(season)
                if s:
                    for ep in s.episodes:
                        ep.watched = True
                        ep.watched_date = date.today()
                    if item.watch_status == WatchStatus.WISHLIST:
                        item.watch_status = WatchStatus.WATCHING
                    logger.info(f"标记已看: {item.title} S{season:02d}", self.task_name)
            elif season is not None and episode is not None:
                ep = item.get_episode(season, episode)
                if ep:
                    ep.watched = True
                    ep.watched_date = date.today()
                    if item.watch_status == WatchStatus.WISHLIST:
                        item.watch_status = WatchStatus.WATCHING
                    if item.is_complete:
                        item.watch_status = WatchStatus.WATCHED
                    logger.info(f"标记已看: {item.title} S{season:02d}E{episode:02d}", self.task_name)

            db.update_item(item)
            db.save()
            return True
        except Exception as e:
            logger.error(f"标记观看失败: {e}", self.task_name)
            return False

    def set_my_rating(self, item_id: str, rating: float) -> bool:
        item = db.get_item(item_id)
        if not item:
            return False
        try:
            item.my_rating = rating
            db.update_item(item)
            db.save()
            logger.info(f"设置评分: {item.title} - {rating}", self.task_name)
            return True
        except Exception as e:
            logger.error(f"设置评分失败: {e}", self.task_name)
            return False

    def add_to_wishlist(self, title: str, year: Optional[int] = None) -> Optional[MediaItem]:
        from utils.helpers import generate_id
        item_id = generate_id(title, year)
        existing = db.get_item(item_id)
        if existing:
            if existing.watch_status == WatchStatus.WISHLIST:
                logger.info(f"已在想看清单: {title}", self.task_name)
                return existing
            existing.watch_status = WatchStatus.WISHLIST
            db.update_item(existing)
            db.save()
            logger.info(f"加入想看清单: {title}", self.task_name)
            return existing

        item = MediaItem(
            id=item_id,
            title=title,
            year=year,
            watch_status=WatchStatus.WISHLIST,
        )
        db.add_item(item)
        db.save()
        logger.info(f"新增想看: {title}", self.task_name)
        return item


matcher = MatchModule()
