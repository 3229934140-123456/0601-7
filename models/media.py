from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, date
from enum import Enum


class MediaType(Enum):
    MOVIE = "movie"
    TV = "tv"
    UNKNOWN = "unknown"


class WatchStatus(Enum):
    WISHLIST = "wishlist"
    WATCHING = "watching"
    WATCHED = "watched"
    DROPPED = "dropped"


@dataclass
class Episode:
    season_number: int
    episode_number: int
    title: str = ""
    air_date: Optional[date] = None
    watched: bool = False
    watched_date: Optional[date] = None
    runtime: Optional[int] = None
    overview: str = ""


@dataclass
class Season:
    season_number: int
    title: str = ""
    episodes: List[Episode] = field(default_factory=list)
    air_date: Optional[date] = None
    overview: str = ""
    poster_path: str = ""

    @property
    def total_episodes(self) -> int:
        return len(self.episodes)

    @property
    def watched_episodes(self) -> int:
        return sum(1 for ep in self.episodes if ep.watched)

    @property
    def is_complete(self) -> bool:
        return self.total_episodes > 0 and self.watched_episodes == self.total_episodes


@dataclass
class MediaItem:
    id: str = ""
    title: str = ""
    original_title: str = ""
    media_type: MediaType = MediaType.UNKNOWN
    year: Optional[int] = None
    overview: str = ""
    poster_path: str = ""
    backdrop_path: str = ""
    genres: List[str] = field(default_factory=list)
    directors: List[str] = field(default_factory=list)
    cast: List[str] = field(default_factory=list)
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    runtime: Optional[int] = None
    status: str = ""
    first_air_date: Optional[date] = None
    last_air_date: Optional[date] = None
    seasons: List[Season] = field(default_factory=list)
    watch_status: WatchStatus = WatchStatus.WISHLIST
    my_rating: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    source_file: str = ""
    external_ids: Dict[str, str] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    subscribed: bool = False
    next_episode_date: Optional[date] = None
    next_episode_info: str = ""

    @property
    def total_seasons(self) -> int:
        return len(self.seasons)

    @property
    def total_episodes(self) -> int:
        return sum(s.total_episodes for s in self.seasons)

    @property
    def watched_episodes(self) -> int:
        return sum(s.watched_episodes for s in self.seasons)

    @property
    def is_complete(self) -> bool:
        if self.media_type == MediaType.MOVIE:
            return self.watch_status == WatchStatus.WATCHED
        return self.total_episodes > 0 and self.watched_episodes == self.total_episodes

    @property
    def progress_percent(self) -> float:
        if self.media_type == MediaType.MOVIE:
            return 100.0 if self.watch_status == WatchStatus.WATCHED else 0.0
        if self.total_episodes == 0:
            return 0.0
        return round((self.watched_episodes / self.total_episodes) * 100, 1)

    def get_season(self, season_number: int) -> Optional[Season]:
        for season in self.seasons:
            if season.season_number == season_number:
                return season
        return None

    def get_episode(self, season_number: int, episode_number: int) -> Optional[Episode]:
        season = self.get_season(season_number)
        if season:
            for ep in season.episodes:
                if ep.episode_number == episode_number:
                    return ep
        return None
