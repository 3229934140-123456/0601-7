import json
import os
import re
import hashlib
from datetime import datetime, date
from typing import Any, Optional
from difflib import SequenceMatcher


def ensure_dir(dir_path: str) -> None:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)


def slugify(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-_')
    return text


def generate_id(title: str, year: Optional[int] = None) -> str:
    raw = f"{title.lower().strip()}_{year or ''}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:16]


def similarity_ratio(str1: str, str2: str) -> float:
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio() * 100


def parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y',
        '%Y年%m月%d日', '%Y',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.date()
        except ValueError:
            continue
    return None


def parse_year(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r'\b(19|20)\d{2}\b', text)
    if match:
        return int(match.group())
    return None


def parse_season_episode(text: str) -> tuple:
    if not text:
        return (None, None)
    patterns = [
        r'[Ss](\d+)[Ee](\d+)',
        r'第\s*(\d+)\s*季.*?第\s*(\d+)\s*集',
        r'第\s*(\d+)\s*季',
        r'Season\s+(\d+).*?Episode\s+(\d+)',
        r'Season\s+(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                return (int(groups[0]), int(groups[1]))
            elif len(groups) == 1:
                return (int(groups[0]), None)
    return (None, None)


def json_serializer(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, 'value'):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def save_json(data: Any, filepath: str) -> None:
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_serializer)


def load_json(filepath: str, default: Any = None) -> Any:
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def format_runtime(minutes: Optional[int]) -> str:
    if not minutes:
        return "未知"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}小时{mins}分钟" if mins > 0 else f"{hours}小时"
    return f"{mins}分钟"


def format_date(d: Optional[date]) -> str:
    if not d:
        return "未知"
    return d.strftime('%Y-%m-%d')
