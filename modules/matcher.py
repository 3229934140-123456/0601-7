import os
import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from models.media import MediaItem, MediaType, WatchStatus, Season, Episode
from utils.helpers import save_json, load_json, parse_date
from utils.config_manager import config
from utils.database import db
from modules.logger_module import logger


WELL_KNOWN_MEDIA = {
    "肖申克的救赎": {
        "original_title": "The Shawshank Redemption",
        "media_type": "movie",
        "year": 1994,
        "genres": ["剧情", "犯罪"],
        "directors": ["弗兰克·德拉邦特"],
        "cast": ["蒂姆·罗宾斯", "摩根·弗里曼", "鲍勃·冈顿"],
        "rating": 9.7,
        "rating_count": 2800000,
        "runtime": 142,
        "status": "已上映",
        "overview": "一场谋杀案使银行家安迪蒙冤入狱，在监狱的岁月里，他与瑞德结下深厚的友谊，并用智慧和信念诠释了希望的意义。",
    },
    "霸王别姬": {
        "original_title": "霸王别姬",
        "media_type": "movie",
        "year": 1993,
        "genres": ["剧情", "爱情", "同性"],
        "directors": ["陈凯歌"],
        "cast": ["张国荣", "张丰毅", "巩俐", "葛优"],
        "rating": 9.6,
        "rating_count": 2100000,
        "runtime": 171,
        "status": "已上映",
        "overview": "段小楼与程蝶衣是一对打小一起长大的师兄弟，两人一个演生，一个饰旦，一向配合天衣无缝，尤其一出《霸王别姬》，更是誉满京城。",
    },
    "阿甘正传": {
        "original_title": "Forrest Gump",
        "media_type": "movie",
        "year": 1994,
        "genres": ["剧情", "爱情"],
        "directors": ["罗伯特·泽米吉斯"],
        "cast": ["汤姆·汉克斯", "罗宾·怀特", "加里·西尼斯"],
        "rating": 9.5,
        "rating_count": 2200000,
        "runtime": 142,
        "status": "已上映",
        "overview": "阿甘是个智商只有75的低能儿，却用单纯善良和坚定信念，经历了美国数十年的风云变迁，活出了奇迹般的人生。",
    },
    "盗梦空间": {
        "original_title": "Inception",
        "media_type": "movie",
        "year": 2010,
        "genres": ["剧情", "科幻", "悬疑", "冒险"],
        "directors": ["克里斯托弗·诺兰"],
        "cast": ["莱昂纳多·迪卡普里奥", "约瑟夫·高登-莱维特", "艾伦·佩吉"],
        "rating": 9.4,
        "rating_count": 2000000,
        "runtime": 148,
        "status": "已上映",
        "overview": "道姆·柯布是一位经验老道的窃贼，他在梦境共享技术领域是最顶尖的人才。他的专长是在人们做梦时潜入梦境，盗取潜意识中最重要的秘密。",
    },
    "绝命毒师": {
        "original_title": "Breaking Bad",
        "media_type": "tv",
        "year": 2008,
        "genres": ["剧情", "犯罪"],
        "directors": ["文斯·吉里根"],
        "cast": ["布莱恩·克兰斯顿", "亚伦·保尔", "安娜·冈"],
        "rating": 9.5,
        "rating_count": 500000,
        "runtime": 47,
        "status": "已完结",
        "overview": "高中化学老师沃尔特·怀特在被诊断出肺癌后，为了给家人留下财产，利用自己的化学知识制造毒品，并逐渐成为世界顶级毒王。",
        "total_seasons": 5,
    },
    "权力的游戏": {
        "original_title": "Game of Thrones",
        "media_type": "tv",
        "year": 2011,
        "genres": ["剧情", "奇幻", "冒险"],
        "directors": ["大卫·贝尼奥夫", "D·B·威斯"],
        "cast": ["艾米莉亚·克拉克", "基特·哈灵顿", "彼特·丁拉基"],
        "rating": 9.5,
        "rating_count": 800000,
        "runtime": 60,
        "status": "已完结",
        "overview": "七大王国的贵族家族争夺铁王座的控制权，而一个被遗忘的种族在北方苏醒。该剧改编自乔治·R·R·马丁的奇幻小说《冰与火之歌》。",
        "total_seasons": 8,
    },
    "老友记": {
        "original_title": "Friends",
        "media_type": "tv",
        "year": 1994,
        "genres": ["喜剧", "爱情"],
        "directors": ["大卫·克莱恩", "玛尔塔·考夫曼"],
        "cast": ["詹妮弗·安妮斯顿", "柯特妮·考克斯", "丽莎·库卓", "马特·勒布朗", "马修·派瑞", "大卫·修蒙"],
        "rating": 9.8,
        "rating_count": 600000,
        "runtime": 22,
        "status": "已完结",
        "overview": "莫妮卡、钱德勒、瑞秋、菲比、乔伊和罗斯是彼此最好的朋友，一起走过十年岁月的点点滴滴。",
        "total_seasons": 10,
    },
    "黑镜": {
        "original_title": "Black Mirror",
        "media_type": "tv",
        "year": 2011,
        "genres": ["剧情", "科幻", "惊悚"],
        "directors": ["查理·布鲁克"],
        "cast": ["罗里·金尼尔", "鲁伯特·艾弗雷特"],
        "rating": 9.4,
        "rating_count": 400000,
        "runtime": 60,
        "status": "在播",
        "overview": "以现代社会为背景，特别是对新技术的焦虑和不安，每集都是一个独立的故事，探讨了科技对人类生活和社会的影响。",
        "total_seasons": 6,
    },
    "怪奇物语": {
        "original_title": "Stranger Things",
        "media_type": "tv",
        "year": 2016,
        "genres": ["剧情", "科幻", "悬疑", "奇幻"],
        "directors": ["马特·达菲", "罗斯·达菲"],
        "cast": ["米莉·波比·布朗", "薇诺娜·瑞德", "大卫·哈伯"],
        "rating": 9.0,
        "rating_count": 500000,
        "runtime": 50,
        "status": "在播",
        "overview": "印第安纳州霍金斯小镇上，一个小男孩神秘消失，他的朋友、家人和当地警察在寻找他的过程中，卷入了一个充斥着秘密实验和超自然力量的谜团。",
        "total_seasons": 4,
    },
    "三体": {
        "original_title": "三体",
        "media_type": "tv",
        "year": 2023,
        "genres": ["剧情", "科幻"],
        "directors": ["杨磊"],
        "cast": ["张鲁一", "于和伟", "陈瑾", "王子文"],
        "rating": 8.7,
        "rating_count": 900000,
        "runtime": 45,
        "status": "已完结",
        "overview": "纳米科学家汪淼进入神秘的《三体》游戏，并在科学边界组织的调查中，逐渐揭开一个关乎人类命运的巨大秘密。",
        "total_seasons": 1,
    },
    "奥本海默": {
        "original_title": "Oppenheimer",
        "media_type": "movie",
        "year": 2023,
        "genres": ["剧情", "传记", "历史"],
        "directors": ["克里斯托弗·诺兰"],
        "cast": ["基里安·墨菲", "艾米莉·布朗特", "小罗伯特·唐尼"],
        "rating": 8.8,
        "rating_count": 1200000,
        "runtime": 180,
        "status": "已上映",
        "overview": "讲述了美国原子弹之父罗伯特·奥本海默在二战期间领导曼哈顿计划，以及他在面临巨大道德困境时的故事。",
    },
    "沙丘2": {
        "original_title": "Dune: Part Two",
        "media_type": "movie",
        "year": 2024,
        "genres": ["剧情", "科幻", "冒险"],
        "directors": ["丹尼斯·维伦纽瓦"],
        "cast": ["提莫西·查拉梅", "赞达亚", "丽贝卡·弗格森"],
        "rating": 8.4,
        "rating_count": 700000,
        "runtime": 166,
        "status": "已上映",
        "overview": "保罗·厄崔迪与契尼及弗雷曼人一起，踏上复仇之路，与毁灭他家族的阴谋者对抗。面对爱情和宇宙命运的抉择，他必须阻止一个只有他能预见的可怕未来。",
    },
    "流浪地球2": {
        "original_title": "流浪地球2",
        "media_type": "movie",
        "year": 2023,
        "genres": ["科幻", "灾难", "冒险"],
        "directors": ["郭帆"],
        "cast": ["吴京", "刘德华", "李雪健", "沙溢"],
        "rating": 8.3,
        "rating_count": 1500000,
        "runtime": 173,
        "status": "已上映",
        "overview": "太阳即将毁灭，人类在地球表面建造出巨大的推进器，寻找新的家园。然而宇宙之路危机四伏，为了拯救地球，流浪地球时代的年轻人再次挺身而出。",
    },
    "狂飙": {
        "original_title": "狂飙",
        "media_type": "tv",
        "year": 2023,
        "genres": ["剧情", "犯罪"],
        "directors": ["徐纪周"],
        "cast": ["张译", "张颂文", "李一桐", "张志坚"],
        "rating": 8.5,
        "rating_count": 1200000,
        "runtime": 45,
        "status": "已完结",
        "overview": "一部以扫黑除恶为背景的刑侦剧，讲述了刑警安欣与黑恶势力长达二十年的正邪较量。",
        "total_seasons": 1,
    },
    "满江红": {
        "original_title": "满江红",
        "media_type": "movie",
        "year": 2023,
        "genres": ["悬疑", "喜剧", "古装"],
        "directors": ["张艺谋"],
        "cast": ["沈腾", "易烊千玺", "张译", "雷佳音"],
        "rating": 7.0,
        "rating_count": 1000000,
        "runtime": 159,
        "status": "已上映",
        "overview": "南宋绍兴年间，岳飞死后四年，秦桧率兵与金国会谈。会谈前夜，金国使者死在宰相驻地，所携密信也不翼而飞。",
    },
    "漫长的季节": {
        "original_title": "漫长的季节",
        "media_type": "tv",
        "year": 2023,
        "genres": ["剧情", "悬疑", "家庭"],
        "directors": ["辛爽"],
        "cast": ["范伟", "秦昊", "陈明昊"],
        "rating": 9.4,
        "rating_count": 950000,
        "runtime": 45,
        "status": "已完结",
        "overview": "跨越二十余年的小城悬案，几个小人物的命运被彻底改变。一个漫长的季节，一段无法释怀的往事。",
        "total_seasons": 1,
    },
    "蜘蛛侠：纵横宇宙": {
        "original_title": "Spider-Man: Across the Spider-Verse",
        "media_type": "movie",
        "year": 2023,
        "genres": ["动画", "动作", "科幻"],
        "directors": ["乔伊姆·多斯·桑托斯", "凯普·鲍尔斯"],
        "cast": ["沙梅克·摩尔", "海莉·斯坦菲尔德"],
        "rating": 8.5,
        "rating_count": 500000,
        "runtime": 140,
        "status": "已上映",
        "overview": "迈尔斯·莫拉莱斯与关·史黛西重聚，二人穿梭多元宇宙。当他们与其他蜘蛛侠联手，却遇到了来自其他蜘蛛侠的威胁。",
    },
}


class MatchModule:
    def __init__(self):
        self.task_name = "match"
        self.stats = {
            'total': 0,
            'matched': 0,
            'updated': 0,
            'failed': 0,
        }

    @property
    def cache_dir(self) -> str:
        cache_path = os.path.join(config.data_dir, 'cache')
        os.makedirs(cache_path, exist_ok=True)
        return cache_path

    def reload(self) -> None:
        pass

    def run(self, item_ids: Optional[List[str]] = None, full_match: bool = False) -> Dict:
        logger.task_start(self.task_name)
        self.stats = {'total': 0, 'matched': 0, 'updated': 0, 'failed': 0}
        sync_notified_count = 0

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
                        old_total = item.total_episodes
                        old_state = self._snapshot_item(item)
                        self._apply_match_result(item, result)
                        if self._has_changed(old_state, item):
                            self.stats['updated'] += 1
                            new_total = item.total_episodes
                            if old_total != new_total and item.subscribed:
                                from modules.subscriber import subscriber
                                cleaned = subscriber.sync_notified_with_item(item.id)
                                sync_notified_count += cleaned
                        db.update_item(item)
                    else:
                        logger.debug(f"未找到匹配: {item.title}", self.task_name)
                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"匹配失败 {item.title}: {e}", self.task_name)

            if self.stats['updated'] > 0:
                db.save()

            extra_info = f", 同步通知记录{sync_notified_count}条" if sync_notified_count > 0 else ""
            logger.task_end(self.task_name, True,
                           f"匹配{self.stats['matched']}条, 更新{self.stats['updated']}条, "
                           f"失败{self.stats['failed']}条{extra_info}")
            return self.stats

        except Exception as e:
            logger.error(f"匹配任务失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            return self.stats

    def _snapshot_item(self, item: MediaItem) -> Dict:
        return {
            'rating': item.rating,
            'genres': list(item.genres),
            'directors': list(item.directors),
            'cast': list(item.cast),
            'media_type': item.media_type.value if item.media_type else None,
            'seasons_count': len(item.seasons),
            'total_episodes': item.total_episodes,
            'status': item.status,
            'runtime': item.runtime,
        }

    def _has_changed(self, old: Dict, item: MediaItem) -> bool:
        if old['rating'] != item.rating:
            return True
        if old['genres'] != item.genres:
            return True
        if old['directors'] != item.directors:
            return True
        if old['cast'] != item.cast:
            return True
        if old['media_type'] != (item.media_type.value if item.media_type else None):
            return True
        if old['seasons_count'] != len(item.seasons):
            return True
        if old['total_episodes'] != item.total_episodes:
            return True
        if old['status'] != item.status:
            return True
        if old['runtime'] != item.runtime:
            return True
        return False

    def _match_item(self, item: MediaItem, full_match: bool = False) -> Optional[Dict]:
        well_known = self._find_well_known(item.title)
        if well_known:
            result = dict(well_known)
            self._enrich_with_seasons(item, result)
            result['_source'] = 'well_known'
            logger.debug(f"命中内置数据库: {item.title}", self.task_name)
            return result

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
            return self._fetch_from_local(item)

    def _fetch_from_tmdb(self, item: MediaItem) -> Optional[Dict]:
        logger.debug(f"从TMDB获取: {item.title}", self.task_name)
        return self._fetch_from_local(item)

    def _fetch_from_douban(self, item: MediaItem) -> Optional[Dict]:
        logger.debug(f"从豆瓣获取: {item.title}", self.task_name)
        return self._fetch_from_local(item)

    def _fetch_from_local(self, item: MediaItem) -> Optional[Dict]:
        well_known = self._find_well_known(item.title)

        if well_known:
            logger.debug(f"命中内置数据库: {item.title}", self.task_name)
            result = dict(well_known)
            self._enrich_with_seasons(item, result)
            return result

        if item.media_type != MediaType.UNKNOWN or item.genres or item.rating or item.directors:
            logger.debug(f"保留用户原始数据: {item.title}", self.task_name)
            return self._build_from_item(item)

        logger.debug(f"无匹配数据: {item.title}", self.task_name)
        return None

    def _find_well_known(self, title: str) -> Optional[Dict]:
        if title in WELL_KNOWN_MEDIA:
            result = dict(WELL_KNOWN_MEDIA[title])
            result['title'] = title
            return result

        for name, data in WELL_KNOWN_MEDIA.items():
            if name in title or title in name:
                result = dict(data)
                result['title'] = name
                return result

        return None

    def _build_from_item(self, item: MediaItem) -> Dict:
        data = {
            'title': item.title,
            'original_title': item.original_title,
            'media_type': item.media_type.value if item.media_type and item.media_type != MediaType.UNKNOWN else None,
            'year': item.year,
            'overview': item.overview,
            'genres': item.genres,
            'directors': item.directors,
            'cast': item.cast,
            'rating': item.rating,
            'rating_count': item.rating_count,
            'runtime': item.runtime,
            'status': item.status,
        }

        if item.media_type == MediaType.TV or len(item.seasons) > 0:
            data['seasons'] = self._build_seasons_from_item(item)
            if not data['media_type']:
                data['media_type'] = 'tv'
        else:
            data['seasons'] = []

        return data

    def _enrich_with_seasons(self, item: MediaItem, data: Dict) -> None:
        if data.get('media_type') != 'tv':
            data['seasons'] = []
            return

        total_seasons = data.get('total_seasons', len(item.seasons) or 1)
        seasons = []
        eps_per_season = self._estimate_eps_per_season(data.get('title', ''), total_seasons)

        user_seasons = {s.season_number: s for s in item.seasons}

        for s_num in range(1, total_seasons + 1):
            num_eps = eps_per_season.get(s_num, 10)
            episodes = []

            user_season = user_seasons.get(s_num)
            user_eps = {}
            if user_season:
                user_eps = {ep.episode_number: ep for ep in user_season.episodes}

            for e_num in range(1, num_eps + 1):
                user_ep = user_eps.get(e_num)
                ep_data = {
                    'season_number': s_num,
                    'episode_number': e_num,
                    'title': f"第{e_num}集",
                }
                if user_ep:
                    if user_ep.watched:
                        ep_data['watched'] = True
                        ep_data['watched_date'] = user_ep.watched_date.isoformat() if user_ep.watched_date else None
                episodes.append(ep_data)

            seasons.append({
                'season_number': s_num,
                'title': f"第{s_num}季",
                'episodes': episodes,
            })

        data['seasons'] = seasons

    def _estimate_eps_per_season(self, title: str, total_seasons: int) -> Dict[int, int]:
        standard_eps = {
            "老友记": {i: 24 for i in range(1, 11)},
            "权力的游戏": {1: 10, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 7, 8: 6},
            "绝命毒师": {1: 7, 2: 13, 3: 13, 4: 13, 5: 16},
            "黑镜": {1: 3, 2: 3, 3: 6, 4: 6, 5: 3, 6: 5},
            "怪奇物语": {1: 8, 2: 9, 3: 8, 4: 9},
            "狂飙": {1: 39},
            "漫长的季节": {1: 12},
            "三体": {1: 30},
        }

        if title in standard_eps:
            return standard_eps[title]

        return {i: 12 for i in range(1, total_seasons + 1)}

    def _build_seasons_from_item(self, item: MediaItem) -> List[Dict]:
        seasons = []
        for s in item.seasons:
            eps = []
            for ep in s.episodes:
                ep_data = {
                    'season_number': ep.season_number,
                    'episode_number': ep.episode_number,
                    'title': ep.title,
                }
                if ep.watched:
                    ep_data['watched'] = True
                    ep_data['watched_date'] = ep.watched_date.isoformat() if ep.watched_date else None
                eps.append(ep_data)
            seasons.append({
                'season_number': s.season_number,
                'title': s.title,
                'episodes': eps,
            })
        return seasons

    def _apply_match_result(self, item: MediaItem, data: Dict) -> None:
        if data.get('original_title') and not item.original_title:
            item.original_title = data['original_title']
        if data.get('overview') and not item.overview:
            item.overview = data['overview']
        if data.get('rating') and not item.rating:
            item.rating = data['rating']
        if data.get('rating_count') and not item.rating_count:
            item.rating_count = data['rating_count']
        if data.get('genres') and not item.genres:
            item.genres = list(data['genres'])
        if data.get('directors') and not item.directors:
            item.directors = list(data['directors'])
        if data.get('cast') and not item.cast:
            item.cast = list(data['cast'])
        if data.get('runtime') and not item.runtime:
            item.runtime = data['runtime']
        if data.get('status') and not item.status:
            item.status = data['status']
        if data.get('year') and not item.year:
            item.year = data['year']

        media_type = data.get('media_type')
        if media_type and item.media_type == MediaType.UNKNOWN:
            if media_type == 'movie':
                item.media_type = MediaType.MOVIE
            elif media_type == 'tv':
                item.media_type = MediaType.TV

        has_seasons = len(item.seasons) > 0
        if has_seasons and item.media_type == MediaType.UNKNOWN:
            item.media_type = MediaType.TV

        if data.get('first_air_date') and not item.first_air_date:
            item.first_air_date = parse_date(data['first_air_date'])
        if data.get('last_air_date') and not item.last_air_date:
            item.last_air_date = parse_date(data['last_air_date'])

        if data.get('seasons') and item.media_type == MediaType.TV:
            sync = data.get('_source') == 'well_known'
            self._apply_seasons(item, data['seasons'], sync_structure=sync)

        if data.get('next_episode_date'):
            item.next_episode_date = parse_date(data['next_episode_date'])
        if data.get('next_episode_info'):
            item.next_episode_info = data['next_episode_info']

    def _apply_seasons(self, item: MediaItem, seasons_data: List[Dict], sync_structure: bool = False) -> None:
        existing_seasons = {s.season_number: s for s in item.seasons}
        data_season_nums = set()

        for s_data in seasons_data:
            s_num = s_data.get('season_number', 1)
            data_season_nums.add(s_num)
            if s_num in existing_seasons:
                season = existing_seasons[s_num]
            else:
                season = Season(
                    season_number=s_num,
                    title=s_data.get('title', f"第{s_num}季"),
                )
                item.seasons.append(season)

            if s_data.get('title') and not season.title:
                season.title = s_data['title']
            if s_data.get('air_date') and not season.air_date:
                season.air_date = parse_date(s_data['air_date'])
            if s_data.get('overview') and not season.overview:
                season.overview = s_data['overview']

            episodes_data = s_data.get('episodes', [])
            existing_eps = {ep.episode_number: ep for ep in season.episodes}
            data_ep_nums = set()

            for ep_data in episodes_data:
                ep_num = ep_data.get('episode_number', 1)
                data_ep_nums.add(ep_num)
                if ep_num in existing_eps:
                    ep = existing_eps[ep_num]
                else:
                    ep = Episode(
                        season_number=s_num,
                        episode_number=ep_num,
                    )
                    season.episodes.append(ep)

                if ep_data.get('title') and not ep.title:
                    ep.title = ep_data['title']
                if ep_data.get('air_date') and not ep.air_date:
                    ep.air_date = parse_date(ep_data['air_date'])
                if ep_data.get('runtime') and not ep.runtime:
                    ep.runtime = ep_data['runtime']
                if ep_data.get('overview') and not ep.overview:
                    ep.overview = ep_data['overview']

            if sync_structure:
                season.episodes = [ep for ep in season.episodes if ep.episode_number in data_ep_nums]

            season.episodes.sort(key=lambda e: e.episode_number)

        if sync_structure:
            item.seasons = [s for s in item.seasons if s.season_number in data_season_nums]

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
