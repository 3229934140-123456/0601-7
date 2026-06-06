import os
import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from models.media import MediaItem, MediaType, WatchStatus, Episode
from utils.helpers import save_json, load_json
from utils.config_manager import config
from utils.database import db
from modules.logger_module import logger


class SubscriptionModule:
    def __init__(self):
        self.task_name = "subscription"
        self.last_check_file = os.path.join(config.data_dir, 'last_subscription_check.json')
        self.new_episodes: List[Dict] = []
        self.stats = {
            'total_subscribed': 0,
            'new_episodes': 0,
            'updated_shows': 0,
            'failed': 0,
        }

    def run(self, item_ids: Optional[List[str]] = None) -> Dict:
        logger.task_start(self.task_name)
        self.new_episodes = []
        self.stats = {
            'total_subscribed': 0,
            'new_episodes': 0,
            'updated_shows': 0,
            'failed': 0,
        }

        try:
            if item_ids:
                items = [db.get_item(iid) for iid in item_ids if db.get_item(iid)]
            else:
                items = db.get_subscribed_items()

            self.stats['total_subscribed'] = len(items)

            for item in items:
                try:
                    new_eps = self._check_new_episodes(item)
                    if new_eps > 0:
                        self.stats['new_episodes'] += new_eps
                        self.stats['updated_shows'] += 1
                        db.update_item(item)
                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"检查更新失败 {item.title}: {e}", self.task_name)

            if self.stats['updated_shows'] > 0:
                db.save()

            self._save_last_check()

            logger.task_end(self.task_name, True,
                           f"订阅{self.stats['total_subscribed']}部, "
                           f"新集{self.stats['new_episodes']}集, "
                           f"更新{self.stats['updated_shows']}部")
            return self.stats

        except Exception as e:
            logger.error(f"订阅任务失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            return self.stats

    def subscribe(self, item_id: str) -> bool:
        item = db.get_item(item_id)
        if not item:
            logger.warning(f"找不到影视: {item_id}", self.task_name)
            return False

        if item.subscribed:
            logger.info(f"已订阅: {item.title}", self.task_name)
            return True

        item.subscribed = True
        db.update_item(item)
        db.save()
        logger.info(f"订阅成功: {item.title}", self.task_name)
        return True

    def unsubscribe(self, item_id: str) -> bool:
        item = db.get_item(item_id)
        if not item:
            return False

        if not item.subscribed:
            return True

        item.subscribed = False
        db.update_item(item)
        db.save()
        logger.info(f"取消订阅: {item.title}", self.task_name)
        return True

    def _check_new_episodes(self, item: MediaItem) -> int:
        if item.media_type != MediaType.TV:
            return 0

        last_check = self._get_last_check_time(item.id)
        new_count = 0

        for season in item.seasons:
            for ep in season.episodes:
                if ep.air_date:
                    if last_check and ep.air_date > last_check.date():
                        new_count += 1
                        self.new_episodes.append({
                            'item_id': item.id,
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'air_date': ep.air_date.isoformat(),
                        })

        self._update_next_episode(item)

        return new_count

    def _update_next_episode(self, item: MediaItem) -> None:
        today = date.today()
        next_ep = None
        next_date = None

        for season in item.seasons:
            for ep in season.episodes:
                if ep.air_date and ep.air_date >= today:
                    if next_date is None or ep.air_date < next_date:
                        next_date = ep.air_date
                        next_ep = ep

        if next_ep:
            item.next_episode_date = next_date
            item.next_episode_info = f"S{next_ep.season_number:02d}E{next_ep.episode_number:02d} - {next_ep.title}"
        else:
            item.next_episode_date = None
            item.next_episode_info = ""

    def _get_last_check_time(self, item_id: str) -> Optional[datetime]:
        data = load_json(self.last_check_file, {})
        last = data.get(item_id)
        if last:
            return datetime.fromisoformat(last)
        return None

    def _save_last_check(self) -> None:
        data = load_json(self.last_check_file, {})
        now = datetime.now().isoformat()
        subscribed = db.get_subscribed_items()
        for item in subscribed:
            data[item.id] = now
        save_json(data, self.last_check_file)

    def get_wishlist(self) -> List[MediaItem]:
        return db.get_items_by_status(WatchStatus.WISHLIST)

    def get_watching_list(self) -> List[MediaItem]:
        return db.get_items_by_status(WatchStatus.WATCHING)

    def get_new_episodes_since_last_check(self) -> List[Dict]:
        return self.new_episodes

    def get_upcoming_episodes(self, days: int = 7) -> List[Dict]:
        today = date.today()
        end_date = today + timedelta(days=days)
        upcoming = []

        for item in db.get_all_items():
            if item.media_type != MediaType.TV:
                continue
            for season in item.seasons:
                for ep in season.episodes:
                    if ep.air_date and today <= ep.air_date <= end_date:
                        upcoming.append({
                            'item_id': item.id,
                            'title': item.title,
                            'season': season.season_number,
                            'episode': ep.episode_number,
                            'ep_title': ep.title,
                            'air_date': ep.air_date.isoformat(),
                        })

        upcoming.sort(key=lambda x: x['air_date'])
        return upcoming

    def subscribe_all_watching(self) -> int:
        watching = db.get_items_by_status(WatchStatus.WATCHING)
        count = 0
        for item in watching:
            if not item.subscribed and item.media_type == MediaType.TV:
                item.subscribed = True
                db.update_item(item)
                count += 1
        if count > 0:
            db.save()
        logger.info(f"批量订阅 {count} 部在看剧集", self.task_name)
        return count


subscriber = SubscriptionModule()
