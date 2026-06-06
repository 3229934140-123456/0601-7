import os
from typing import List, Dict, Optional
from datetime import datetime
from utils.helpers import save_json, load_json
from models.media import MediaItem, MediaType, WatchStatus, Season, Episode
from utils.config_manager import config


class MediaDatabase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'items'):
            self.items: Dict[str, MediaItem] = {}
            self.load()

    def load(self) -> None:
        db_path = os.path.join(config.data_dir, 'media_database.json')
        data = load_json(db_path, [])
        self.items = {}
        for item_data in data:
            item = self._dict_to_media_item(item_data)
            self.items[item.id] = item

    def save(self) -> None:
        db_path = os.path.join(config.data_dir, 'media_database.json')
        data = [self._media_item_to_dict(item) for item in self.items.values()]
        save_json(data, db_path)

    def _media_item_to_dict(self, item: MediaItem) -> dict:
        return {
            'id': item.id,
            'title': item.title,
            'original_title': item.original_title,
            'media_type': item.media_type.value if item.media_type else 'unknown',
            'year': item.year,
            'overview': item.overview,
            'poster_path': item.poster_path,
            'backdrop_path': item.backdrop_path,
            'genres': item.genres,
            'directors': item.directors,
            'cast': item.cast,
            'rating': item.rating,
            'rating_count': item.rating_count,
            'runtime': item.runtime,
            'status': item.status,
            'first_air_date': item.first_air_date.isoformat() if item.first_air_date else None,
            'last_air_date': item.last_air_date.isoformat() if item.last_air_date else None,
            'seasons': [
                {
                    'season_number': s.season_number,
                    'title': s.title,
                    'air_date': s.air_date.isoformat() if s.air_date else None,
                    'overview': s.overview,
                    'poster_path': s.poster_path,
                    'episodes': [
                        {
                            'season_number': ep.season_number,
                            'episode_number': ep.episode_number,
                            'title': ep.title,
                            'air_date': ep.air_date.isoformat() if ep.air_date else None,
                            'watched': ep.watched,
                            'watched_date': ep.watched_date.isoformat() if ep.watched_date else None,
                            'runtime': ep.runtime,
                            'overview': ep.overview,
                        }
                        for ep in s.episodes
                    ]
                }
                for s in item.seasons
            ],
            'watch_status': item.watch_status.value if item.watch_status else 'wishlist',
            'my_rating': item.my_rating,
            'tags': item.tags,
            'notes': item.notes,
            'source_file': item.source_file,
            'external_ids': item.external_ids,
            'last_updated': item.last_updated.isoformat() if item.last_updated else None,
            'subscribed': item.subscribed,
            'next_episode_date': item.next_episode_date.isoformat() if item.next_episode_date else None,
            'next_episode_info': item.next_episode_info,
        }

    def _dict_to_media_item(self, data: dict) -> MediaItem:
        from datetime import date

        def parse_iso_date(d: Optional[str]) -> Optional[date]:
            if not d:
                return None
            try:
                return date.fromisoformat(d)
            except ValueError:
                return None

        seasons = []
        for s_data in data.get('seasons', []):
            episodes = []
            for ep_data in s_data.get('episodes', []):
                episodes.append(Episode(
                    season_number=ep_data.get('season_number', 1),
                    episode_number=ep_data.get('episode_number', 1),
                    title=ep_data.get('title', ''),
                    air_date=parse_iso_date(ep_data.get('air_date')),
                    watched=ep_data.get('watched', False),
                    watched_date=parse_iso_date(ep_data.get('watched_date')),
                    runtime=ep_data.get('runtime'),
                    overview=ep_data.get('overview', ''),
                ))
            seasons.append(Season(
                season_number=s_data.get('season_number', 1),
                title=s_data.get('title', ''),
                episodes=episodes,
                air_date=parse_iso_date(s_data.get('air_date')),
                overview=s_data.get('overview', ''),
                poster_path=s_data.get('poster_path', ''),
            ))

        media_type_str = data.get('media_type', 'unknown')
        media_type = MediaType(media_type_str) if media_type_str in [e.value for e in MediaType] else MediaType.UNKNOWN

        watch_status_str = data.get('watch_status', 'wishlist')
        watch_status = WatchStatus(watch_status_str) if watch_status_str in [e.value for e in WatchStatus] else WatchStatus.WISHLIST

        return MediaItem(
            id=data.get('id', ''),
            title=data.get('title', ''),
            original_title=data.get('original_title', ''),
            media_type=media_type,
            year=data.get('year'),
            overview=data.get('overview', ''),
            poster_path=data.get('poster_path', ''),
            backdrop_path=data.get('backdrop_path', ''),
            genres=data.get('genres', []),
            directors=data.get('directors', []),
            cast=data.get('cast', []),
            rating=data.get('rating'),
            rating_count=data.get('rating_count'),
            runtime=data.get('runtime'),
            status=data.get('status', ''),
            first_air_date=parse_iso_date(data.get('first_air_date')),
            last_air_date=parse_iso_date(data.get('last_air_date')),
            seasons=seasons,
            watch_status=watch_status,
            my_rating=data.get('my_rating'),
            tags=data.get('tags', []),
            notes=data.get('notes', ''),
            source_file=data.get('source_file', ''),
            external_ids=data.get('external_ids', {}),
            last_updated=datetime.fromisoformat(data['last_updated']) if data.get('last_updated') else None,
            subscribed=data.get('subscribed', False),
            next_episode_date=parse_iso_date(data.get('next_episode_date')),
            next_episode_info=data.get('next_episode_info', ''),
        )

    def add_item(self, item: MediaItem) -> bool:
        if item.id in self.items:
            return False
        item.last_updated = datetime.now()
        self.items[item.id] = item
        return True

    def update_item(self, item: MediaItem) -> None:
        item.last_updated = datetime.now()
        self.items[item.id] = item

    def get_item(self, item_id: str) -> Optional[MediaItem]:
        return self.items.get(item_id)

    def get_all_items(self) -> List[MediaItem]:
        return list(self.items.values())

    def get_items_by_type(self, media_type: MediaType) -> List[MediaItem]:
        return [item for item in self.items.values() if item.media_type == media_type]

    def get_items_by_status(self, watch_status: WatchStatus) -> List[MediaItem]:
        return [item for item in self.items.values() if item.watch_status == watch_status]

    def get_items_by_genre(self, genre: str) -> List[MediaItem]:
        return [item for item in self.items.values() if genre.lower() in [g.lower() for g in item.genres]]

    def get_subscribed_items(self) -> List[MediaItem]:
        return [item for item in self.items.values() if item.subscribed]

    def delete_item(self, item_id: str) -> bool:
        if item_id in self.items:
            del self.items[item_id]
            return True
        return False

    def search(self, keyword: str) -> List[MediaItem]:
        keyword = keyword.lower()
        results = []
        for item in self.items.values():
            if (keyword in item.title.lower() or
                keyword in item.original_title.lower() or
                any(keyword in director.lower() for director in item.directors) or
                any(keyword in actor.lower() for actor in item.cast)):
                results.append(item)
        return results

    @property
    def count(self) -> int:
        return len(self.items)


db = MediaDatabase()
