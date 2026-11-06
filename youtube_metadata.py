"""YouTube metadata cache. Missing data is shown honestly, never invented."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

CACHE_PATH = Path(os.getenv('YOUTUBE_CACHE_PATH', '.youtube-cache.json'))
try:
    CACHE = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
except (OSError, ValueError):
    CACHE = {}
CACHE.setdefault('videos', {})
CACHE.setdefault('channels', {})
_loaded = False


def _fetch(resource, ids, key):
    response = requests.get(
        f'https://www.googleapis.com/youtube/v3/{resource}',
        params={'part': 'snippet,statistics,contentDetails' if resource == 'videos'
                else 'snippet,statistics', 'id': ','.join(ids), 'key': key},
        timeout=20,
    )
    # Do not include request URLs (which contain the API key) in errors/logs.
    if response.status_code != 200:
        raise RuntimeError(f'YouTube {resource}: HTTP {response.status_code}')
    data = response.json()
    if 'items' not in data:
        raise RuntimeError(f'YouTube {resource}: invalid response')
    return data['items']


def refresh(video_ids, channel_id):
    global _loaded
    if _loaded:
        return
    _loaded = True
    key = os.getenv('YOUTUBE_API_KEY')
    if not key:
        print('YouTube API key absent: using cached metadata or unavailable labels.')
        return
    try:
        ids = sorted(set(filter(None, video_ids)))
        for start in range(0, len(ids), 50):
            for item in _fetch('videos', ids[start:start + 50], key):
                CACHE['videos'][item['id']] = item
        for item in _fetch('channels', [channel_id], key):
            CACHE['channels'][item['id']] = item
        CACHE['updated_at'] = datetime.now(timezone.utc).isoformat()
    except (requests.RequestException, RuntimeError, ValueError) as error:
        # Preserve prior successful results during outages or quota exhaustion.
        print(f'Metadata refresh incomplete ({type(error).__name__}); keeping available cache.')
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(CACHE, ensure_ascii=False), encoding='utf-8')


def get_video_info(video_id):
    from ickost_final import format_view_count, format_duration, format_date
    item = CACHE['videos'].get(video_id, {})
    snippet = item.get('snippet', {})
    count = item.get('statistics', {}).get('viewCount')
    duration = item.get('contentDetails', {}).get('duration')
    return {
        'duration': format_duration(duration) if duration else '—',
        'viewCount': format_view_count(int(count)) if count is not None else '—',
        'viewCountNum': int(count) if count is not None else 0,
        'publishedAt': format_date(snippet['publishedAt']) if snippet.get('publishedAt') else '정보 없음',
        'title': snippet.get('title'),
        'description': snippet.get('description', '')[:100],
    }


def get_channel_metadata(channel_id):
    from ickost_final import format_view_count
    item = CACHE['channels'].get(channel_id, {})
    snippet, stats = item.get('snippet', {}), item.get('statistics', {})
    thumbs = snippet.get('thumbnails', {})
    thumbnail = next((thumbs[size]['url'] for size in ('high', 'medium', 'default') if size in thumbs),
                     'https://yt3.googleusercontent.com/2pvoyX_JUZFcrn1RD1I9SCIUF62jvpkxaK77UNs50TtM8GkjyprLPu5cIPcmE9ribNOGqL9kRA=s160-c-k-c0x00ffffff-no-rj')
    subscribers = stats.get('subscriberCount')
    return {
        'subscriberCount': format_view_count(int(subscribers)) if subscribers is not None else '—',
        'videoCount': stats.get('videoCount', '—'),
        'title': snippet.get('title', 'ICKOST'), 'thumbnail': thumbnail,
    }
