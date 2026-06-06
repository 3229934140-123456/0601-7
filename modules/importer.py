import os
import csv
import json
import re
from typing import List, Tuple, Dict, Optional
from models.media import MediaItem, MediaType, WatchStatus
from utils.helpers import (
    generate_id, parse_year, parse_season_episode,
    similarity_ratio, load_json
)
from utils.config_manager import config
from utils.database import db
from modules.logger_module import logger


class ImportModule:
    def __init__(self):
        self.task_name = "import"
        self.imported_items: List[MediaItem] = []
        self.stats = {
            'total': 0,
            'new': 0,
            'duplicates': 0,
            'failed': 0,
        }

    def run(self, file_path: Optional[str] = None) -> Dict:
        logger.task_start(self.task_name)
        self.stats = {'total': 0, 'new': 0, 'duplicates': 0, 'failed': 0}
        self.imported_items = []

        try:
            files_to_import = []
            if file_path:
                files_to_import.append(file_path)
            else:
                files_to_import = config.get('import.watchlist_files', [])

            for f in files_to_import:
                if not os.path.isabs(f):
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    f = os.path.join(base_dir, f)
                if os.path.exists(f):
                    self._import_file(f)
                else:
                    logger.warning(f"文件不存在: {f}", self.task_name)

            if config.get('import.dedup_enabled', True):
                self._deduplicate()

            self._save_to_database()

            logger.task_end(self.task_name, True, f"新增{self.stats['new']}条, 重复{self.stats['duplicates']}条")
            return self.stats

        except Exception as e:
            logger.error(f"导入失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            self.stats['failed'] = 1
            return self.stats

    def _import_file(self, file_path: str) -> None:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.txt':
            items = self._parse_txt(file_path)
        elif ext == '.csv':
            items = self._parse_csv(file_path)
        elif ext == '.json':
            items = self._parse_json(file_path)
        else:
            logger.warning(f"不支持的格式: {ext}", self.task_name)
            return

        for item in items:
            item.source_file = os.path.basename(file_path)
            self.imported_items.append(item)
            self.stats['total'] += 1

        logger.info(f"从 {os.path.basename(file_path)} 导入 {len(items)} 条", self.task_name)

    def _parse_txt(self, file_path: str) -> List[MediaItem]:
        items = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                item = self._parse_title_line(line)
                if item:
                    items.append(item)
        return items

    def _parse_csv(self, file_path: str) -> List[MediaItem]:
        items = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item = self._parse_csv_row(row)
                    if item:
                        items.append(item)
        except Exception as e:
            logger.error(f"CSV解析失败: {e}", self.task_name)
        return items

    def _parse_json(self, file_path: str) -> List[MediaItem]:
        items = []
        data = load_json(file_path, [])
        if isinstance(data, list):
            for item_data in data:
                item = self._dict_to_media_item(item_data)
                if item:
                    items.append(item)
        elif isinstance(data, dict) and 'items' in data:
            for item_data in data['items']:
                item = self._dict_to_media_item(item_data)
                if item:
                    items.append(item)
        return items

    def _parse_title_line(self, line: str) -> Optional[MediaItem]:
        line = line.strip()
        if not line:
            return None

        title = line
        year = parse_year(line)
        season_num, ep_num = parse_season_episode(line)

        title = re.sub(r'\s*\(\d{4}\)\s*', ' ', title).strip()
        title = re.sub(r'\s*[Ss]\d+[Ee]\d+\s*', ' ', title).strip()
        title = re.sub(r'\s*第\s*\d+\s*季.*?第\s*\d+\s*集\s*', ' ', title).strip()
        title = re.sub(r'\s*第\s*\d+\s*季\s*', ' ', title).strip()
        title = re.sub(r'\s+', ' ', title).strip()

        item = MediaItem(
            id=generate_id(title, year),
            title=title,
            year=year,
            media_type=MediaType.TV if season_num else MediaType.UNKNOWN,
            watch_status=WatchStatus.WISHLIST,
        )

        if season_num:
            from models.media import Season, Episode
            season = Season(season_number=season_num, title=f"第{season_num}季")
            if ep_num:
                ep = Episode(season_number=season_num, episode_number=ep_num)
                season.episodes.append(ep)
            item.seasons.append(season)

        return item

    def _parse_csv_row(self, row: Dict) -> Optional[MediaItem]:
        title = row.get('title') or row.get('名称') or row.get('片名') or ''
        if not title:
            return None

        year_str = row.get('year') or row.get('年份') or row.get('年代') or ''
        year = int(year_str) if year_str and year_str.isdigit() else parse_year(title)

        media_type_str = (row.get('type') or row.get('类型') or '').lower()
        if '剧' in media_type_str or 'tv' in media_type_str or 'series' in media_type_str:
            media_type = MediaType.TV
        elif '电' in media_type_str or 'movie' in media_type_str or 'film' in media_type_str:
            media_type = MediaType.MOVIE
        else:
            media_type = MediaType.UNKNOWN

        status_str = (row.get('status') or row.get('状态') or '').lower()
        if '看' in status_str or 'watch' in status_str:
            watch_status = WatchStatus.WATCHING
        elif '完' in status_str or 'done' in status_str or 'watched' in status_str:
            watch_status = WatchStatus.WATCHED
        elif '弃' in status_str or 'drop' in status_str:
            watch_status = WatchStatus.DROPPED
        else:
            watch_status = WatchStatus.WISHLIST

        genres = []
        genres_str = row.get('genres') or row.get('类型') or row.get('类别') or ''
        if genres_str:
            genres = [g.strip() for g in re.split(r'[,，/|]', genres_str) if g.strip()]

        directors = []
        dir_str = row.get('director') or row.get('导演') or ''
        if dir_str:
            directors = [d.strip() for d in re.split(r'[,，/|]', dir_str) if d.strip()]

        cast = []
        cast_str = row.get('cast') or row.get('演员') or row.get('主演') or ''
        if cast_str:
            cast = [c.strip() for c in re.split(r'[,，/|]', cast_str) if c.strip()]

        rating_str = row.get('rating') or row.get('评分') or ''
        rating = float(rating_str) if rating_str else None

        notes = row.get('notes') or row.get('备注') or ''
        tags_str = row.get('tags') or row.get('标签') or ''
        tags = [t.strip() for t in re.split(r'[,，/|]', tags_str) if t.strip()]

        item = MediaItem(
            id=generate_id(title, year),
            title=title,
            year=year,
            media_type=media_type,
            genres=genres,
            directors=directors,
            cast=cast,
            rating=rating,
            watch_status=watch_status,
            notes=notes,
            tags=tags,
        )

        return item

    def _dict_to_media_item(self, data: Dict) -> Optional[MediaItem]:
        title = data.get('title', '')
        if not title:
            return None

        year = data.get('year') or parse_year(title)
        item = MediaItem(
            id=generate_id(title, year),
            title=title,
            original_title=data.get('original_title', ''),
            year=year,
            overview=data.get('overview', ''),
            genres=data.get('genres', []),
            directors=data.get('directors', []),
            cast=data.get('cast', []),
            rating=data.get('rating'),
            tags=data.get('tags', []),
            notes=data.get('notes', ''),
        )

        media_type = data.get('media_type', '')
        if media_type == 'movie':
            item.media_type = MediaType.MOVIE
        elif media_type == 'tv':
            item.media_type = MediaType.TV

        status = data.get('watch_status') or data.get('status') or ''
        if status == 'watched':
            item.watch_status = WatchStatus.WATCHED
        elif status == 'watching':
            item.watch_status = WatchStatus.WATCHING
        elif status == 'dropped':
            item.watch_status = WatchStatus.DROPPED

        return item

    def _deduplicate(self) -> None:
        if len(self.imported_items) <= 1:
            return

        threshold = config.get('import.fuzzy_match_threshold', 85)
        unique_items: Dict[str, MediaItem] = {}
        duplicate_count = 0

        for item in self.imported_items:
            is_duplicate = False
            for existing_id, existing_item in unique_items.items():
                sim = similarity_ratio(item.title, existing_item.title)
                same_year = item.year == existing_item.year if item.year and existing_item.year else True
                if sim >= threshold and same_year:
                    is_duplicate = True
                    duplicate_count += 1
                    self._merge_items(existing_item, item)
                    break

            if not is_duplicate:
                unique_items[item.id] = item

        self.imported_items = list(unique_items.values())
        self.stats['duplicates'] = duplicate_count
        logger.info(f"去重完成, 合并 {duplicate_count} 条重复", self.task_name)

    def _merge_items(self, target: MediaItem, source: MediaItem) -> None:
        if source.original_title and not target.original_title:
            target.original_title = source.original_title
        if source.overview and not target.overview:
            target.overview = source.overview
        if source.year and not target.year:
            target.year = source.year
        if source.rating and not target.rating:
            target.rating = source.rating
        if source.directors:
            for d in source.directors:
                if d not in target.directors:
                    target.directors.append(d)
        if source.cast:
            for c in source.cast:
                if c not in target.cast:
                    target.cast.append(c)
        if source.genres:
            for g in source.genres:
                if g not in target.genres:
                    target.genres.append(g)
        if source.tags:
            for t in source.tags:
                if t not in target.tags:
                    target.tags.append(t)
        if source.seasons:
            for s in source.seasons:
                existing_season = target.get_season(s.season_number)
                if not existing_season:
                    target.seasons.append(s)
                elif s.episodes:
                    for ep in s.episodes:
                        existing_ep = existing_season.episodes
                        if not any(e.episode_number == ep.episode_number for e in existing_ep):
                            existing_season.episodes.append(ep)

    def _save_to_database(self) -> None:
        new_count = 0
        for item in self.imported_items:
            if db.add_item(item):
                new_count += 1
            else:
                self.stats['duplicates'] += 1

        self.stats['new'] = new_count
        if new_count > 0:
            db.save()
        logger.info(f"保存到数据库: 新增 {new_count} 条", self.task_name)


importer = ImportModule()
