#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from flask import Flask, render_template, render_template_string, jsonify, request
import folium
import json
import requests
from datetime import datetime
import os
from urllib.parse import quote
import math

app = Flask(__name__)

# API 키를 환경변수로 변경
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
CHANNEL_ID = (os.getenv('CHANNEL_ID') or 'UC82OkWXaNdFQb10wm-OY2YA')


def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]+)',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def format_duration(duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return "0:00"
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def format_view_count(count):
    count = int(count)
    if count >= 10000:
        return f"{count / 10000:.1f}만"
    elif count >= 1000:
        return f"{count / 1000:.1f}천"
    else:
        return str(count)


def format_date(date_str):
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime('%Y년 %m월 %d일')
    except:
        return date_str


def parse_view_count(view_str):
    """조회수 문자열을 숫자로 변환"""
    if not view_str:
        return 0
    view_str = str(view_str).replace(',', '')
    if '만' in view_str:
        return int(float(view_str.replace('만', '')) * 10000)
    elif '천' in view_str:
        return int(float(view_str.replace('천', '')) * 1000)
    return int(view_str) if view_str.isdigit() else 0


def calculate_distance(lat1, lon1, lat2, lon2):
    """두 좌표 간의 거리를 계산 (하버사인 공식)"""
    R = 6371  # 지구 반지름 (km)

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def calculate_route_stats(route_points):
    """경로의 총 거리와 예상 소요시간 계산"""
    if len(route_points) < 2:
        return 0, 0

    total_distance = 0
    for i in range(len(route_points) - 1):
        lat1, lon1 = route_points[i]
        lat2, lon2 = route_points[i + 1]
        total_distance += calculate_distance(lat1, lon1, lat2, lon2)

    # 평균 수영 속도를 2 km/h로 가정하여 소요시간 계산
    swimming_speed_kmh = 2.0
    estimated_time_hours = total_distance / swimming_speed_kmh
    estimated_time_minutes = int(estimated_time_hours * 60)

    return total_distance, estimated_time_minutes


# Metadata is cached across requests; static builds refresh it once in batches.
from youtube_metadata import get_video_info, get_channel_metadata


def get_youtube_video_info(video_url):
    return get_video_info(extract_video_id(video_url))


def get_channel_info():
    return get_channel_metadata(CHANNEL_ID)


def get_difficulty_color(difficulty):
    """난이도별 색상 반환"""
    colors = {
        "초급": "#00ff00",  # 초록색
        "중급": "#ffaa00",  # 주황색
        "고급": "#ff4444"  # 빨간색
    }
    return colors.get(difficulty, "#aaaaaa")


def get_marker_size(rating):
    """통일된 마커 크기 반환"""
    return 30  # 모든 마커 동일 크기


# 새로운 데이터 구조: 경로 정보 포함
SPOT_DATA = {
    "제주도": {
        "spots": {
            "삼양감수탕": {
                "title": "삼양감수탕",
                "description": "제주도 바다수영의 성지",
                "coordinates": [33.525243, 126.583098],
                "distance": "1.9km",
                "rating": 4.1,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.525243, 126.583098], "type": "start"},
                        {"name": "반환지점", "coords": [33.531882, 126.587633], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.529856, 126.584074], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.525243, 126.583098], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/CQ8i9V3n_3U?si=3uqkoRLkfGCWE06a",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/p8YGkJoVPco?si=TUBu_WhH77Sum5oh",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/s29__btHJ-U",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/htnMQwzmdaQ?si=LN7wYmKmdaXzBypw",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/6bWNajCNrt8?si=_Nch-dXXw7K9lq6Z",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/-5QpEY9S5g4?si=LhlIoRejtcO4JCAy",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/dsHFIixRKFw?si=EVZym775mKsRRnSW",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/b1SoJSyZMBw?si=J84yN0XnpaZuSDXk",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/u4A8krlsPNI",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/q9LnrmDmWuw?si=eb8AefK1M522tuS6",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/Xeo94s4KURs?si=9maUUwKZhZzgAyZG",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/M2HNuVOk6tg?si=m7yknyQVioQn1j7s",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/f8rCkjIXzCY?si=gYSOnfPePhoWQcpL",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/X1C9sXAloIg?si=LspNc2b5naScctgf",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/Qsa2CV8yE2o?si=TCycvMNQ-QfbMdii",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/t-UMJz_QSZA?si=WjWrsoMTKml1hCrT",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/wfXuyFK92b0?si=q5RFq90oDz8lQOid",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
                    {
                        "url": "https://youtu.be/s5edMpRVxSc?si=ETiyUA7OLlYw-Bw3",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    },
{
                        "url": "https://youtu.be/htnMQwzmdaQ",
                        "title": "삼양감수탕 첫 방문",
                        "description": "제주도 바다수영 입문자를 위한 완벽한 장소"
                    }
                ]
            },
            "용담포구": {
                "title": "용담포구(용두암)",
                "description": "제주에서의 시티뷰",
                "coordinates": [33.518360, 126.501244],
                "distance": "2km",
                "rating": 3.6,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.518360, 126.501244], "type": "start"},
                        {"name": "반환지점(용두암)", "coords": [33.516918, 126.511891], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.518911, 126.507002], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.518360, 126.501244], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/vrMIBOMAE6Y?si=q7_W4aUSJTpHRmip",
                        "title": "용담포구 수영",
                        "description": "용두암을 배경으로 한 시티뷰 수영"
                    },
                    {
                        "url": "https://youtu.be/dtbjk7aZNeQ",
                        "title": "용담포구 수영",
                        "description": "용두암을 배경으로 한 시티뷰 수영"
                    }
                ]
            },
            "현사포구": {
                "title": "현사포구",
                "description": "500미터 인터벌 훈련",
                "coordinates": [33.498385, 126.449710],
                "distance": "500m",
                "rating": 3.5,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.498385, 126.449710], "type": "start"},
                        {"name": "반환지점", "coords": [33.499037, 126.444161], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.499170, 126.447727], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.498385, 126.449710], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/ZlPalFpXqxc",
                        "title": "현사포구 인터벌 훈련",
                        "description": "500미터 인터벌 훈련 완주 도전"
                    },
                    {
                        "url": "https://youtu.be/gyA6zATW1dM",
                        "title": "현사포구 인터벌 훈련",
                        "description": "500미터 인터벌 훈련 완주 도전"
                    },
                    {
                        "url": "https://youtu.be/eG0j0P4lYPE",
                        "title": "현사포구 인터벌 훈련",
                        "description": "500미터 인터벌 훈련 완주 도전"
                    }
                ]
            },       
            "연대포구": {
                "title": "연대포구",
                "description": "스노클링 최적지",
                "coordinates": [33.495448, 126.427925],
                "distance": "2km",
                "rating": 3.8,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.495448, 126.427925], "type": "start"},
                        {"name": "반환지점", "coords": [33.497345, 126.438021], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.497622, 126.431766], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.495448, 126.427925], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/i4B9aJZrxBY",
                        "title": "연대포구",
                        "description": "스노클링 최적지"
                    },
                    {
                        "url": "https://youtu.be/-1l341tbbJc?si=lOqdpcKEaEWCjjvO",
                        "title": "연대포구",
                        "description": "스노클링 최적지"
                    }
                ]
            },
            "구엄포구": {
                "title": "구엄포구-고내리포구",
                "description": "물고기 천국, 낚시포인트",
                "coordinates": [33.483416, 126.376398],
                "distance": "2.8km",
                "rating": 4.1,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.483416, 126.376398], "type": "start"},
                        {"name": "경유지점", "coords": [33.481277, 126.366813], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.481227, 126.356951], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.478025, 126.351974], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.474076, 126.351352], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/DwlhJyBMp4U",
                        "title": "구엄포구 장거리 수영",
                        "description": "물고기들과 함께하는 2.8km 바다수영"
                    },
                    {
                        "url": "https://youtu.be/jHV5KQXooC0",
                        "title": "구엄포구 장거리 수영",
                        "description": "물고기들과 함께하는 2.8km 바다수영"
                    }
                ]
            },
            "곽지해수욕장": {
                "title": "곽지해수욕장",
                "description": "다양한 바다를 만날 수 있음",
                "coordinates": [33.449486, 126.303061],
                "distance": "3km",
                "rating": 3.7,
                "difficulty": "중급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.449486, 126.303061], "type": "start"},
                        {"name": "경유지점", "coords": [33.451143, 126.301291], "type": "waypoint"},
                        {"name": "반환지점(한담해변)", "coords": [33.462065, 126.309788], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.457977, 126.307925], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.451143, 126.301291], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.449486, 126.303061], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/eKrG--YI7k8",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/H6X039gZHdM?si=u4srpYIX2tR-90GZ",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/iDqkKgDel3M?si=1R--ZZW6BXGhcSYo",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/jsBT-sIBX48?si=YyW_6jCXAd6bBUKO",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/l0lDyQEpB7k?si=U12DHYjkJW7RzM6g",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/kFPZLJFJvFw?si=yqw6GHz51Fy8Q4jn",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/KH6Yam2gxUI?si=0nZPrD3-hieyX6nx",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/QzolOa2Op4Q?si=f8lqVnvicYOnj7x6",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/qJYm2Eqg4fI?si=vdYJBoL98x6YQiA9",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/ST9Q3KQsQr4?si=FyT9I_Rg5rVZEGQy",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/O-So_u-d5Gk",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/S3vaSsJxYoQ",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    },
                    {
                        "url": "https://youtu.be/GWdYBmgyNwM",
                        "title": "곽지해수욕장 수영",
                        "description": "제주 서쪽 바다의 아름다운 색깔들"
                    }                    
                ]
            },
            "비양도": {
                "title": "비양도",
                "description": "섬을 한바퀴 도는 경험",
                "coordinates": [33.406378, 126.231167],
                "distance": "3.8km",
                "rating": 3.9,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.406378, 126.231167], "type": "start"},
                        {"name": "경유지점", "coords": [33.409415, 126.232706], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.412748, 126.230078], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.412205, 126.223494], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.409319, 126.221427], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.405112, 126.222116], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.403674, 126.225357], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.403983, 126.227182], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.404611, 126.229465], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/4G6gIcR9PoQ",
                        "title": "비양도 일주 수영",
                        "description": "작은 섬을 한바퀴 도는 도전"
                    }
                ]   
            
            },
            "두모포구-월령포구": {
                "title": "두모포구-월령포구",
                "description": "최대 난이도",
                "coordinates": [33.356881, 126.179519],
                "distance": "4.5km",
                "rating": 4.2,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.356881, 126.179519], "type": "start"},
                        {"name": "경유지점", "coords": [33.358503, 126.179607], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.360707, 126.183373], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.365678, 126.189974], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.367479, 126.199735], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.375939, 126.206874], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.379331, 126.215157], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/8fqkfpuk2os",
                        "title": "두모포구-월령포구",
                        "description": "최대 난이도의 바다"
                    }
                ]
                
            },
             "차귀도": {
                "title": "자구내포구-와도-차귀도",
                "description": "조류 끝판왕",
                "coordinates": [33.307682, 126.163438],
                "distance": "6.5km",
                "rating": 4.8,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.307682, 126.163438], "type": "start"},
                        {"name": "경유지점", "coords": [33.310319, 126.163701], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.311008, 126.161992], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.310466, 126.160449], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.310643, 126.159211], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.311079, 126.160511], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.311642, 126.159182], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.313004, 126.152549], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.314220, 126.150935], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.312691, 126.143694], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.310506, 126.143740], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.309442, 126.146638], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.309869, 126.150287], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.311218, 126.150549], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.311218, 126.153561], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.311769, 126.159176], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.312073, 126.161677], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.310230, 126.163757], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.307682, 126.163438], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/OAMg4xvu-YA?si=c2-MlvX6I53l_b_y",
                        "title": "자구내포구-와도-차귀도",
                        "description": "조류 끝판왕"
                    }
                ]
                
            },
            "신도포구-엉알해변": {
                "title": "신도포구-엉알해변",
                "description": "수월봉을 따라 가는 바닷길",
                "coordinates": [33.277543, 126.169358],
                "distance": "4km",
                "rating": 3.8,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.277543, 126.169358], "type": "start"},
                        {"name": "경유지점", "coords": [33.277737, 126.167828], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.284948, 126.162228], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.291759, 126.159532], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.296332, 126.160669], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.298538, 126.165304], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.298090, 126.167085], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/8FpRrK_pmrM",
                        "title": "신도포구-엉알해변",
                        "description": "수월봉을 따라 가는 바닷길"
                    }
                ]
                
            },
            "송악산항": {
                "title": "송악산항-하도방파제",
                "description": "서쪽제1경 송악산 한바퀴",
                "coordinates": [33.205401, 126.290239],
                "distance": "3.2km",
                "rating": 3.7,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.205401, 126.290239], "type": "start"},
                        {"name": "경유지점", "coords": [33.203461, 126.293962], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.197824, 126.296642], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.193831, 126.291972], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.196414, 126.285695], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.199959, 126.286154], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.199036, 126.279366], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.199164, 126.276483], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/mW-nnFWoruo",
                        "title": "송악산 해안 수영",
                        "description": "제주 서쪽 절경을 바다에서 감상하기"
                    }
                ]
            },
            "사계항": {
                "title": "사계항(용머리바위)",
                "description": "바다에서 바라보는 용머리바위",
                "coordinates": [33.228517, 126.308868],
                "distance": "2km",
                "rating": 4.0,
                "difficulty": "중급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.228517, 126.308868], "type": "start"},
                        {"name": "경유지점", "coords": [33.228638, 126.310317], "type": "waypoint"},
                        {"name": "경유지점(용머리바위)", "coords": [33.231257, 126.315757], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.232651, 126.315415], "type": "waypoint"},
                        {"name": "반환지점", "coords": [33.232699, 126.314941], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.232651, 126.315415], "type": "waypoint"},
                        {"name": "경유지점(용머리바위)", "coords": [33.231257, 126.315757], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.228638, 126.310317], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.228517, 126.308868], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/EeCD-p8GdZw",
                        "title": "사계항 용머리바위 수영",
                        "description": "바다에서만 볼 수 있는 용머리바위의 진면목"
                    }
                ]
            },
             "대평포구(박수기정)": {
                "title": "대평포구(박수기정)",
                "description": "절벽이 바다와 닿은 곳",
                "coordinates": [33.236450, 126.358639],
                "distance": "3.8km",
                "rating": 4.3,
                "difficulty": "중급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.236450, 126.358639], "type": "start"},
                        {"name": "경유지점", "coords": [33.235266, 126.355441], "type": "waypoint"},
                        {"name": "경유지점(박수기정)", "coords": [33.234153, 126.349841], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.234153, 126.349841], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.236361, 126.344326], "type": "waypoint"},
                        {"name": "반환지점", "coords": [33.237330, 126.344026], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.236361, 126.344326], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.234153, 126.349841], "type": "waypoint"},
                        {"name": "경유지점(박수기정)", "coords": [33.234153, 126.349841], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.235266, 126.355441], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.236450, 126.358639], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/X2sNi8QUA5A",
                        "title": "구석구석 아름다운 곳",
                        "description": "박수기정, 산방산, 푸른바다"
                    }
                ]
            },
             "중문색달해변": {
                "title": "중문색달해변-예래포구",
                "description": "중문이 관광단지인 이유",
                "coordinates": [33.245124, 126.410886],
                "distance": "4km",
                "rating": 4.6,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.245124, 126.410886], "type": "start"},
                        {"name": "경유지점", "coords": [33.244345, 126.410877], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.242892, 126.406221], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.238584, 126.397445], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.231728, 126.385149], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.230580, 126.377940], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.232500, 126.377232], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/xppoi_hcl4U?si=qu1k4geqRwqzfAcD",
                        "title": "천연파도풀",
                        "description": "중문색달해수욕장, 높은 파도, 기가막힌 해선"
                    }
                ]
            },
            "월평포구": {
                "title": "월평포구-해송횟집(진곶내)",
                "description": "오로지 물길로만 가능한 곳, 진곳",
                "coordinates": [33.234547, 126.463455],
                "distance": "3.4km",
                "rating": 3.8,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.234547, 126.463455], "type": "start"},
                        {"name": "경유지점", "coords": [33.233911, 126.462275], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.238654, 126.459735], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.239938, 126.457096], "type": "waypoint"},
                        {"name": "경유지점(진곳내)", "coords": [33.241302, 126.457364], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.239938, 126.457096], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.240250, 126.450465], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.237230, 126.444699], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.238044, 126.443428], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/qDBFv4rKnxQ",
                        "title": "진곶내 수영",
                        "description": "오로지 물길로만 가능한 곳"
                    },
                    {
                        "url": "https://youtu.be/56OoUGdUNFY",
                        "title": "진곶내 수영",
                        "description": "오로지 물길로만 가능한 곳"
                    }
                ]
            },
            "새연교": {
                "title": "새연교-돔베낭골(외돌개)",
                "description": "서귀포 필수코스",
                "coordinates": [33.239074, 126.558384],
                "distance": "3.6km",
                "rating": 3.8,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.239074, 126.558384], "type": "start"},
                        {"name": "경유지점", "coords": [33.238581, 126.555048], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.240302, 126.550501], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.236936, 126.548264], "type": "waypoint"},
                        {"name": "경유지점(외돌개)", "coords": [33.237579, 126.545637], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.238458, 126.541817], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.240648, 126.539500], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.238673, 126.534650], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.239589, 126.533535], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/WwQ7GhNW1dQ",
                        "title": "외돌개 수영",
                        "description": "서귀포 필수코스 바다수영"
                    },
                    {
                        "url": "https://youtu.be/9U04BFmeGis",
                        "title": "외돌개 수영",
                        "description": "서귀포 필수코스 바다수영"
                    }
                ]
            },
            "자구리": {
                "title": "자구리-구두미포구(정방폭포)",
                "description": "바다로 떨어지는 폭포",
                "coordinates": [33.243282, 126.568774],
                "distance": "3.8km",
                "rating": 3.5,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.243282, 126.568774], "type": "start"},
                        {"name": "경유지점", "coords": [33.241359, 126.568938], "type": "waypoint"},
                        {"name": "경유지점(정방폭포)", "coords": [33.243837, 126.572012], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.243126, 126.574402], "type": "waypoint"},
                        {"name": "경유지점(소정방폭포)", "coords": [33.244319, 126.577634], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.243139, 126.578757], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.242333, 126.581594], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.235546, 126.595469], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.236357, 126.596622], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/lWivFkLGLPA",
                        "title": "정방폭포 수영",
                        "description": "바다로 떨어지는 폭포를 보며 수영하기"
                    },
                    {
                        "url": "https://youtu.be/ZOmoD6ffqTw",
                        "title": "정방폭포 수영",
                        "description": "바다로 떨어지는 폭포를 보며 수영하기"
                    }
                ]
            },
            "태웃개": {
                "title": "태웃개",
                "description": "다이빙의 성지에서 바다수영",
                "coordinates": [33.270104, 126.691575],
                "distance": "4km",
                "rating": 3.8,
                "difficulty": "고급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.270104, 126.691575], "type": "start"},
                        {"name": "경유지점", "coords": [33.268405, 126.691174], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.270084, 126.701435], "type": "waypoint"},
                        {"name": "반환지점(로빙화)", "coords": [33.272883, 126.710362], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.269420, 126.702143], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.268405, 126.691174], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.270104, 126.691575], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/HFfRwPig89g",
                        "title": "태웃개 수영",
                        "description": "다이빙의 성지에서 바다수영 도전"
                    }
                ]
            },
            "신양섭지해수욕장": {
                "title": "신양섭지해수욕장(섭지코지)",
                "description": "섭지코지 한바퀴, 바다거북 출현",
                "coordinates": [33.435565, 126.924462],
                "distance": "5km",
                "rating": 4.2,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.435565, 126.924462], "type": "start"},
                        {"name": "경유지점", "coords": [33.437417, 126.930525], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.429918, 126.938157], "type": "waypoint"},
                        {"name": "경유지점(섭지코지)", "coords": [33.421680, 126.934350], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.422464, 126.925870], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.427493, 126.921467], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.433336, 126.921792], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.434601, 126.923704], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/NUhttc9N1Ks",
                        "title": "섭지코지 수영",
                        "description": "섭지코지 한바퀴, 바다거북과의 만남"
                    }
                ]
            },
            "수마포구": {
                "title": "수마포구-우뭇개해안(성산일출봉)",
                "description": "제주 제1경을 바다에서 보는 맛",
                "coordinates": [33.460447, 126.933770],
                "distance": "3.5km",
                "rating": 4.2,
                "difficulty": "고급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.460447, 126.933770], "type": "start"},
                        {"name": "경유지점", "coords": [33.455283, 126.939230], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.454730, 126.944283], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.455666, 126.947473], "type": "waypoint"},
                        {"name": "경유지점(촛대바위)", "coords": [33.457114, 126.947294], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.457803, 126.945917], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.460783, 126.946016], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.462100, 126.940395], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.461995, 126.939069], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/Up1qNF8ES7o",
                        "title": "성산일출봉 수영",
                        "description": "제주 제1경을 바다에서 감상하며"
                    }
                ]
            },
            "하고수동해수욕장": {
                "title": "하고수동해수욕장(우도)",
                "description": "섬속의 섬에서",
                "coordinates": [33.514124, 126.958840],
                "distance": "1.8km",
                "rating": 3.6,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.514124, 126.958840], "type": "start"},
                        {"name": "반환지점", "coords": [33.516485, 126.967573], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.515913, 126.963486], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.514124, 126.958840], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/-m8AwZlrwY4",
                        "title": "우도 수영",
                        "description": "섬속의 섬에서 바다수영"
                    }
                ]
            },
"신동코지": {
                "title": "제주카약체험-신동코지불턱(토끼섬)",
                "description": "토끼섬엔 토끼가 없다",
                "coordinates": [33.514959, 126.902113],
                "distance": "3.4km",
                "rating": 3.9,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.514959, 126.902113], "type": "start"},
                        {"name": "경유지점", "coords": [33.518971, 126.906890], "type": "waypoint"},
                        {"name": "경유지점(토끼섬)", "coords": [33.523907, 126.903573], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.523013, 126.902476], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.525034, 126.900358], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.528750, 126.894261], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.527870, 126.891780], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/46QuKrDwbwo",
                        "title": "토끼섬 수영",
                        "description": "토끼섬엔 토끼가 없다는 이야기"
                    }
                ]
            },
            "세화포구-하도포구": {
                "title": "세화포구-하도포구",
                "description": "해안선을 따라 솟은 평화로운 마을",
                "coordinates": [33.529031, 126.857657],
                "distance": "3.4km",
                "rating": 3.6,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.529031, 126.857657], "type": "start"},
                        {"name": "경유지점", "coords": [33.531095, 126.864998], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.532966, 126.871628], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.533068, 126.880671], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.529716, 126.884798], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.527788, 126.883952], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/zQKfALbIxrA",
                        "title": "세화포구",
                        "description": "맞조류를 견뎌라"
                    }
                ]
            },
            "월정투명카약": {
                "title": "월정투명카약-세기알해변",
                "description": "김녕의 보석",
                "coordinates": [33.565581, 126.779139],
                "distance": "3.1km",
                "rating": 3.4,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.565581, 126.779139], "type": "start"},
                        {"name": "경유지점", "coords": [33.567860, 126.776888], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.568627, 126.761839], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.564176, 126.758231], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.559868, 126.755147], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/Ml7Cb8eoyPQ",
                        "title": "세기알해변 수영",
                        "description": "김녕의 보석 같은 해변"
                    },
                    {
                        "url": "https://youtu.be/JWALemPamVQ?si=-ycb0R2vhCUgvOly",
                        "title": "세기알해변 수영",
                        "description": "김녕의 보석 같은 해변"
                    },
                    {
                        "url": "https://youtu.be/5n2GapfEvR0",
                        "title": "세기알해변 수영",
                        "description": "마라톤대회 후 바다수영"
                    }                    
                ]
            },
            "북촌환해장성": {
                "title": "북촌환해장성-목지섬",
                "description": "다채로운 바다",
                "coordinates": [33.553002, 126.699998],
                "distance": "3.2km",
                "rating": 3.8,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.553002, 126.699998], "type": "start"},
                        {"name": "경유지점(소여도)", "coords": [33.556367, 126.711002], "type": "waypoint"},
                        {"name": "경유지점(목지섬)", "coords": [33.563844, 126.729502], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.560437, 126.737408], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/kKrNavJKpYc",
                        "title": "목지섬 수영",
                        "description": "다채로운 바다색깔을 만날 수 있는 곳"
                    }
                ]
            },
            "함덕해수욕장": {
                "title": "함덕해수욕장-해동포구",
                "description": "최상급 투명도",
                "coordinates": [33.544800, 126.674291],
                "distance": "1.9km",
                "rating": 4.2,
                "difficulty": "초급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.544800, 126.674291], "type": "start"},
                        {"name": "경유지점", "coords": [33.549479, 126.673173], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.553400, 126.677656], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.552498, 126.682030], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.548711, 126.684055], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/fwAW_b_UdH4",
                        "title": "함덕해수욕장 수영",
                        "description": "최상급 투명도의 바다"
                    }
                ]
            },
            "정주항-서우봉": {
                "title": "정주항-서우봉",
                "description": "가볍게 즐기는 함덕바다",
                "coordinates": [33.547626, 126.662014],
                "distance": "2.3km",
                "rating": 4.1,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.547626, 126.662014], "type": "start"},
                        {"name": "반환지점", "coords": [33.546244, 126.674110], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.547626, 126.662014], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/hq9HngNNTuc",
                        "title": "정주항-서우봉",
                        "description": "가볍게 즐기는 함덕바다"
                    }
                ]
            },
            "관곶": {
                "title": "관곶-정주항",
                "description": "섬속을 누비는 즐거움",
                "coordinates": [33.552784, 126.642338],
                "distance": "3km",
                "rating": 3.8,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [33.552784, 126.642338], "type": "start"},
                        {"name": "경유지점(관곶)", "coords": [33.555614, 126.643466], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.556296, 126.644972], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.553518, 126.654119], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.548918, 126.662614], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.547533, 126.662058], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/mt4r9Hx9kBA",
                        "title": "정주항 수영",
                        "description": "섬속을 누비는 즐거운 수영"
                    }
                ]
            },
            "닭머르": {
                "title": "닭머르",
                "description": "아무나 올 수 없는 곳(사유지)",
                "coordinates": [33.535198, 126.603058],
                "distance": "2km",
                "rating": 3.4,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [33.535198, 126.603058], "type": "start"},
                        {"name": "경유지점", "coords": [33.536741, 126.603288], "type": "waypoint"},
                        {"name": "반환지점", "coords": [33.536821, 126.611576], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.537670, 126.606660], "type": "waypoint"},
                        {"name": "경유지점", "coords": [33.536741, 126.603288], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [33.535198, 126.603058], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/KFYn3sPHKkw",
                        "title": "닭머르 수영",
                        "description": "아무나 올 수 없는 특별한 장소"
                    },
{
                        "url": "https://youtu.be/EyEN45fgb0Y",
                        "title": "닭머르 수영",
                        "description": "아무나 올 수 없는 특별한 장소"
                    }
                ]
            }
        }
    },
    "부산": {
        "spots": {
            "해운대해수욕장": {
                "title": "해운대해수욕장",
                "description": "전국 바다수영의 성지",
                "coordinates": [35.157389, 129.157273],
                "distance": "1.5km",
                "rating": 3.7,
                "difficulty": "중급",
                "route": {
                    "type": "편도",
                    "points": [
                        {"name": "입수지점", "coords": [35.157389, 129.157273], "type": "start"},
                        {"name": "경유지점", "coords": [35.154618, 129.158947], "type": "waypoint"},
                        {"name": "경유지점", "coords": [35.157197, 129.167358], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [35.159021, 129.166714], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/tESMnqgBz7E",
                        "title": "해운대 바다수영",
                        "description": "부산 대표 해수욕장에서의 수영"
                    }
                ]
            },
            "송정해수욕장": {
                "title": "송정해수욕장",
                "description": "천지개벽한 송정앞바다",
                "coordinates": [35.180158, 129.203572],
                "distance": "1.5km",
                "rating": 3.2,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [35.180158, 129.203572], "type": "start"},
                        {"name": "경유지점", "coords": [35.177968, 129.205154], "type": "waypoint"},
                        {"name": "반환지점", "coords": [35.174318, 129.199234], "type": "waypoint"},
                        {"name": "경유지점", "coords": [35.177968, 129.205154], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [35.180158, 129.203572], "type": "end"}
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/u6GNpGfimaM",
                        "title": "송정해수욕장 수영",
                        "description": "조용한 송정에서의 바다수영"
                    }
                ]
            },
            "송도해수욕장": {
                "title": "송도해수욕장",
                "description": "시티뷰가 좋은 포인트",
                "coordinates": [35.074453, 129.017126],
                "distance": "1.5km",
                "rating": 3.4,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [35.074453, 129.017126], "type": "start"},
                        {"name": "경유지점", "coords": [35.072117, 129.019679], "type": "waypoint"},
                        {"name": "반환지점", "coords": [35.074751, 129.022082], "type": "waypoint"},
                        {"name": "경유지점", "coords": [35.072117, 129.019679], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [35.074453, 129.017126], "type": "start"},
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/e1Kp4Rzkis0",
                        "title": "송도해수욕장 수영",
                        "description": "시티뷰가 좋은 바다수영 포인트"
                    }
                ]
            }
        }
    },
    "경남": {
        "spots": {
            "구조라해수욕장": {
                "title": "구조라해수욕장",
                "description": "윤돌섬 한바퀴 돌기",
                "coordinates": [34.809356, 128.688286],
                "distance": "3.2km",
                "rating": 3.5,
                "difficulty": "초급",
                "route": {
                    "type": "왕복",
                    "points": [
                        {"name": "입수지점", "coords": [34.809356, 128.688286], "type": "start"},
                        {"name": "경유지점", "coords": [34.805934, 128.681845], "type": "waypoint"},
                        {"name": "경유지점", "coords": [34.804675, 128.681430], "type": "waypoint"},
                        {"name": "경유지점", "coords": [34.804349, 128.680058], "type": "waypoint"},
                        {"name": "경유지점", "coords": [34.807104, 128.680058], "type": "waypoint"},
                        {"name": "퇴수지점", "coords": [34.809356, 128.688286], "type": "start"},
                    ]
                },
                "videos": [
                    {
                        "url": "https://youtu.be/bLmz_DcrTIw",
                        "title": "구조라해수욕장 수영",
                        "description": "거제도의 숨겨진 보석"
                    },
                    {
                        "url": "https://youtu.be/Bc2S6CaO7O8",
                        "title": "구조라해수욕장 수영",
                        "description": "거제도의 숨겨진 보석"
                    }
                ]
            }
        }
    }
}


def get_spot_main_video(spot_videos):
    """조회수가 가장 높은 영상을 메인 영상으로 선택"""
    if not spot_videos:
        return None

    max_views = 0
    main_video = spot_videos[0]

    for video in spot_videos:
        youtube_info = get_youtube_video_info(video['url'])
        views = youtube_info.get('viewCountNum', 0)
        if views > max_views:
            max_views = views
            main_video = video

    return main_video


def enrich_spot_data():
    """장소별 데이터를 YouTube 정보와 함께 enriched"""
    enriched_data = {}
    for location, data in SPOT_DATA.items():
        enriched_spots = []
        for spot_name, spot in data['spots'].items():
            # 메인 영상 선택 (조회수가 가장 높은 영상)
            main_video = get_spot_main_video(spot['videos'])
            if main_video:
                youtube_info = get_youtube_video_info(main_video['url'])
                video_id = extract_video_id(main_video['url'])

                # 경로 통계 계산
                route_points = [(point['coords'][0], point['coords'][1]) for point in
                                spot.get('route', {}).get('points', [])]
                total_distance, estimated_time = calculate_route_stats(route_points)

                enriched_spot = {
                    **spot,
                    'spot_id': spot_name,
                    'thumbnail': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                    'duration': youtube_info['duration'],
                    'views': youtube_info['viewCount'],
                    'date': youtube_info['publishedAt'],
                    'video_count': len(spot['videos']),
                    'main_video_url': main_video['url'],
                    'calculated_distance': f"{total_distance:.1f}km",
                    'estimated_time': f"{estimated_time}분"
                }
                enriched_spots.append(enriched_spot)
        enriched_data[location] = {'spots': enriched_spots}
    return enriched_data


def create_map(spot_data):
    m = folium.Map(
        location=[33.389153, 126.562724],
        zoom_start=9,
        tiles='OpenStreetMap'
    )

    for location, data in spot_data.items():
        for spot in data['spots']:
            # 경로 정보가 있는 경우 경로를 지도에 표시
            if 'route' in SPOT_DATA[location]['spots'][spot['spot_id']]:
                route_info = SPOT_DATA[location]['spots'][spot['spot_id']]['route']
                route_points = [point['coords'] for point in route_info['points']]

                # 경로 타입에 따른 색상 설정
                route_colors = {
                    '왕복': '#fc2e2a',      # 초록색 - 왕복
                    '편도': '#f7fe3e'       # 주황색 - 편도
                }
                route_color = route_colors.get(route_info['type'], '#ffffff')

                # 경로선 그리기

                folium.PolyLine(
                    locations=route_points,
                    color=route_color,
                    weight=4,
                    opacity=0.8,
                    dash_array='5, 20, 10, 30',  # 점선 패턴 (10픽셀 선, 5픽셀 공백)
                    popup=folium.Popup(f"""
                        <div style="font-family: Arial; color: #333;">
                            <b>{spot['title']}</b><br>
                            경로 타입: {route_info['type']}<br>
                            총 거리: {spot.get('calculated_distance', 'N/A')}<br>
                            예상 소요시간: {spot.get('estimated_time', 'N/A')}
                        </div>
                    """, max_width=200)
                ).add_to(m)

                # 경로상의 포인트들에 작은 마커 추가
                '''
                for i, point in enumerate(route_info['points']):
                    if point['type'] == 'start':
                        icon_color = 'green'
                        icon_symbol = 'play'
                    elif point['type'] == 'end':
                        icon_color = 'red'
                        icon_symbol = 'stop'
                    else:  # waypoint
                        icon_color = 'blue'
                        icon_symbol = 'info-sign'

                    folium.Marker(
                        location=point['coords'],
                        popup=f"{point['name']}<br>타입: {point['type']}",
                        icon=folium.Icon(
                            color=icon_color,
                            icon=icon_symbol,
                            prefix='glyphicon'
                        )
                    ).add_to(m)
                '''

            # 메인 마커 (기존 코드)
            popup_html = f"""
            <style>
            .leaflet-popup {{
                border: none !important;
                box-shadow: 0 8px 32px rgba(0,0,0,0.8) !important;
            }}
            .leaflet-popup-content-wrapper {{
                border: none !important;
                background: #181818 !important;
                box-shadow: none !important;
                padding: 0 !important;
                margin: 0 !important;
            }}
            .leaflet-popup-content {{
                margin: 0 !important;
                padding: 0 !important;
                border: none !important;
                background: #181818 !important;
            }}
            .leaflet-popup-tip-container {{
                display: none !important;
            }}
            .leaflet-popup-tip {{
                display: none !important;
            }}
            </style>
            <div style="width: 260px; font-family: 'Roboto', sans-serif; 
                        background: #181818; color: #ffffff; border-radius: 8px; overflow: hidden; margin: 0; padding: 0;">
                <div style="padding: 12px;">
                    <h3 style="margin: 0 0 6px 0; font-size: 14px; color: #ffffff;">
                        {spot['title']}
                    </h3>
                    <div style="color: #aaaaaa; font-size: 13px; margin-bottom: 12px;">
                        조회수 {spot['views']}회 • {spot['date']}
                    </div>
                    <div style="color: #aaaaaa; font-size: 13px; margin-bottom: 12px;">
                        {spot['description']}
                    </div>
                    <div style="display: flex; gap: 12px; margin: 0 0 8px 0; padding: 8px 0; 
                                border-top: 1px solid #3d3d3d; border-bottom: 1px solid #3d3d3d;">
                        <div style="text-align: center; color: #aaaaaa; font-size: 12px;">
                            <div style="color: #ffffff; font-weight: 500;">{spot.get('calculated_distance', spot['distance'])}</div>
                            <div>실제거리</div>
                        </div>
                        <div style="text-align: center; color: #aaaaaa; font-size: 12px;">
                            <div style="color: #ffffff; font-weight: 500;">{spot.get('estimated_time', 'N/A')}</div>
                            <div>예상시간</div>
                        </div>
                        <div style="text-align: center; color: #aaaaaa; font-size: 12px;">
                            <div style="color: {get_difficulty_color(spot['difficulty'])}; font-weight: 500;">{spot['difficulty']}</div>
                            <div>난이도</div>
                        </div>
                        <div style="text-align: center; color: #aaaaaa; font-size: 12px;">
                            <div style="color: #ffaa00; font-weight: 500;">★{spot['rating']}</div>
                            <div>평점</div>
                        </div>
                    </div>
                    <button style="width: 100%; padding: 8px; background: #cc0000; 
                                   color: white; border: none; border-radius: 4px; 
                                   font-size: 12px; cursor: pointer; margin: 0;"
                            onclick="window.open('/spot/{quote(location)}/{quote(spot['spot_id'])}', '_blank')">
                        상세보기
                    </button>
                </div>
            </div>
            """

            marker_size = get_marker_size(spot['rating'])

            marker_html = f'''

            <div style="width: {marker_size}px; height: {marker_size}px; background: #ff0000;
                    border: 1px solid #ffffff; border-radius: 12px; display: flex; align-items: center;
                    justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.4); cursor: pointer;"
                onclick="window.open('/spot/{quote(location)}/{quote(spot['spot_id'])}', '_blank')">               
               <svg width="{int(marker_size*0.5)}" height="{int(marker_size*0.5)}" viewBox="0 0 24 24" fill="white">
                    <path d="M8 5v14l11-7z" stroke="white" stroke-width="1"/>
               </svg>
            </div>
            '''

            folium.Marker(
                location=spot['coordinates'],
                popup=folium.Popup(
                    popup_html,
                    max_width=280,
                    max_height=250,
                    parse_html=False,
                    sticky=True,
                    style="margin: 0; padding: 0;"
                ),
                tooltip=f"📍 {spot['title']} ({location}) - {spot['video_count']}개 영상",
                icon=folium.DivIcon(html=marker_html, icon_size=(marker_size, marker_size),
                                    icon_anchor=(marker_size // 2, marker_size // 2))
            ).add_to(m)
    
    return m


@app.before_request
def prepare_metadata():
    from youtube_metadata import refresh
    refresh(
        [extract_video_id(video['url'])
         for data in SPOT_DATA.values() for spot in data['spots'].values()
         for video in spot['videos']],
        CHANNEL_ID,
    )


@app.route('/')
def index():
    spots = []
    for region, data in enrich_spot_data().items():
        for spot in data['spots']:
            videos = []
            for video in spot['videos']:
                info = get_youtube_video_info(video['url'])
                videos.append({**video, **info,
                               'title': info.get('title') or video['title'],
                               'thumbnail': f"https://img.youtube.com/vi/{extract_video_id(video['url'])}/hqdefault.jpg"})
            spots.append({**spot, 'region': region, 'videos': videos,
                          'detail_url': f"/spot/{quote(region, safe='')}/{quote(spot['spot_id'], safe='')}/"})
    return render_template('explorer.html', spots=spots, channel=get_channel_info())


@app.route('/spot/<location>/<spot_id>')
def spot_detail(location, spot_id):
    """개별 장소의 상세 페이지 - 경로 정보 포함"""
    try:
        spot_data = SPOT_DATA.get(location, {}).get('spots', {}).get(spot_id)
        if not spot_data:
            return "장소를 찾을 수 없습니다", 404

        # 해당 장소의 모든 영상 정보 가져오기
        enriched_videos = []
        for video in spot_data['videos']:
            youtube_info = get_youtube_video_info(video['url'])
            video_id = extract_video_id(video['url'])
            enriched_videos.append({
                **video,
                'video_id': video_id,
                'thumbnail': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                'duration': youtube_info['duration'],
                'views': youtube_info['viewCount'],
                'date': youtube_info['publishedAt'],
                'title': youtube_info.get('title') or video['title'],
                'original_title': video['title']
            })

        # 경로 정보 계산
        route_info = spot_data.get('route', {})
        route_points = [(point['coords'][0], point['coords'][1]) for point in route_info.get('points', [])]
        total_distance, estimated_time = calculate_route_stats(route_points)

        # 채널 정보
        channel_info = get_channel_info()

        # 경로 전용 지도 생성
        if route_info:
            route_map = folium.Map(
                location=spot_data['coordinates'],
                zoom_start=14,
                tiles='OpenStreetMap'
            )

            # 경로선 그리기
            route_colors = {'왕복': '#fc2e2a', '편도': '#f7fe3e'}
            route_color = route_colors.get(route_info['type'], '#ffffff')

            folium.PolyLine(
                locations=[point['coords'] for point in route_info['points']],
                color=route_color,
                weight=5,
                opacity=0.8,
                dash_array='5, 20, 10, 30'  # 점선 패턴 추가
            ).add_to(route_map)

            '''
            # 경로 포인트 마커
            for i, point in enumerate(route_info['points']):
                if point['type'] == 'start':
                    marker_style = """
                    <div style="width: 24px; height: 24px; background: linear-gradient(45deg, #00ff41, #00cc33); 
                                border: 2px solid #ffffff; border-radius: 50%; display: flex; align-items: center; 
                                justify-content: center; box-shadow: 0 0 15px #00ff41;">
                        <span style="color: black; font-weight: bold; font-size: 12px;">S</span>
                    </div>"""
                elif point['type'] == 'end':
                    marker_style = """
                    <div style="width: 24px; height: 24px; background: linear-gradient(45deg, #ff0080, #cc0066); 
                                border: 2px solid #ffffff; border-radius: 50%; display: flex; align-items: center; 
                                justify-content: center; box-shadow: 0 0 15px #ff0080;">
                        <span style="color: white; font-weight: bold; font-size: 12px;">E</span>
                    </div>"""
                else:  # waypoint
                    marker_style = """
                    <div style="width: 20px; height: 20px; background: linear-gradient(45deg, #00d4ff, #0099cc); 
                                border: 2px solid #ffffff; border-radius: 6px; display: flex; align-items: center; 
                                justify-content: center; box-shadow: 0 0 12px #00d4ff;">
                        <span style="color: black; font-weight: bold; font-size: 12px;">""" + str(i) + """</span>
                    </div>"""

                folium.Marker(
                    location=point['coords'],
                    popup=f"{point['name']}<br>타입: {point['type']}",
                    icon=folium.DivIcon(html=marker_style, icon_size=(24, 24))
                ).add_to(m)

                folium.Marker(
                    location=point['coords'],
                    popup=f"<b>{point['name']}</b><br>포인트 {i + 1}: {point['type']}",
                    icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix='glyphicon')
                ).add_to(route_map)
            '''

            route_map_html = route_map._repr_html_()
        else:
            route_map_html = "<p>이 장소에는 경로 정보가 없습니다.</p>"  # <- 12칸(또는 3탭) 들여쓰기 추가

        detail_html = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ spot.title }} - ICKOST</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Roboto', sans-serif; background-color: #0f0f0f; color: #ffffff; line-height: 1.4; }

        .header { 
            background: #212121; 
            padding: 12px 16px; 
            display: flex; 
            align-items: center; 
            position: sticky; 
            top: 0; 
            z-index: 100; 
            border-bottom: 1px solid #3d3d3d; 
        }
        .back-btn {
            background: #3d3d3d;
            color: white;
            border: none;
            padding: 8px 16px; /* 패딩 약간 증가 */
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            margin-right: 16px;
            transition: background 0.2s ease;
            display: flex;
            align-items: center;
            gap: 4px; /* 아이콘과 텍스트 간격 */
        }
        .back-btn:hover { background: #555; }
        .channel-info { display: flex; align-items: center; gap: 12px; flex: 1; }
        .channel-avatar { width: 40px; height: 40px; border-radius: 50%; overflow: hidden; }
        .channel-avatar img { width: 100%; height: 100%; object-fit: cover; }
        .channel-details h1 { font-size: 18px; font-weight: 600; color: #ffffff; margin-bottom: 2px; }
        .channel-meta { color: #aaaaaa; font-size: 12px; }

        .container { 
            max-width: 1280px; 
            margin: 0 auto; 
            padding: 16px; 
        }

        .spot-header {
            background: #181818;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 32px;
            border: 1px solid #3d3d3d;
        }
        .spot-title { font-size: 24px; font-weight: 600; color: #ffffff; margin-bottom: 8px; }
        .spot-description { color: #aaaaaa; font-size: 16px; margin-bottom: 16px; }
        .spot-info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        .info-item {
            text-align: center;
            padding: 12px;
            background: #212121;
            border-radius: 8px;
        }
        .info-value { font-size: 18px; font-weight: 600; color: #ffffff; margin-bottom: 4px; }
        .info-label { font-size: 12px; color: #aaaaaa; }
        .difficulty-초급 { color: #00ff00; }
        .difficulty-중급 { color: #ffaa00; }
        .difficulty-고급 { color: #ff4444; }

        .route-section {
            background: #181818;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 32px;
            border: 1px solid #3d3d3d;
        }
        .route-title { font-size: 20px; font-weight: 600; color: #ffffff; margin-bottom: 16px; }
        .route-map-container {
            background: #212121;
            border-radius: 8px;
            overflow: hidden;
            height: 200px;
            margin-bottom: 16px;
        }
        .route-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }
        .route-stat-item {
            background: #212121;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }
        .route-stat-value { font-size: 20px; font-weight: 600; color: #ffffff; margin-bottom: 4px; }
        .route-stat-label { font-size: 12px; color: #aaaaaa; }

        .route-points {
            background: #212121;
            border-radius: 8px;
            padding: 16px;
        }
        .route-points h4 { color: #ffffff; margin-bottom: 12px; }
        .route-point {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px;
            margin-bottom: 8px;
            background: #2d2d2d;
            border-radius: 6px;
        }
        .route-point-marker {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            color: white;
        }
        .marker-start { background: #00aa00; }
        .marker-end { background: #aa0000; }
        .marker-waypoint { background: #0066aa; }
        .route-point-name { color: #ffffff; font-weight: 500; }
        .route-point-coords { color: #aaaaaa; font-size: 12px; }

        .videos-section h2 { font-size: 20px; font-weight: 600; margin-bottom: 20px; color: #ffffff; }
        .videos-grid { 
            display: grid; 
            grid-template-columns: 1fr; 
            gap: 20px; 
        }
        .video-card { 
            background: #181818; 
            border-radius: 12px; 
            overflow: hidden; 
            border: 1px solid #3d3d3d;
            transition: transform 0.2s ease;
            cursor: pointer;
        }
        .video-card:hover { transform: translateY(-2px); }
        .video-thumbnail { 
            position: relative; 
            width: 100%; 
            height: 200px; 
        }
        .video-thumbnail img { width: 100%; height: 100%; object-fit: cover; }
        .video-duration { 
            position: absolute; 
            bottom: 8px; 
            right: 8px; 
            background: rgba(0,0,0,0.8); 
            color: white; 
            padding: 3px 6px; 
            border-radius: 4px; 
            font-size: 12px; 
        }
        .video-overlay { 
            position: absolute; 
            top: 0; 
            left: 0; 
            right: 0; 
            bottom: 0; 
            background: rgba(0,0,0,0.3); 
            opacity: 0; 
            transition: opacity 0.2s ease; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
        }
        .video-card:hover .video-overlay { opacity: 1; }
        .play-btn { 
            width: 48px; 
            height: 48px; 
            background: rgba(255,255,255,0.9); 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
        }
        .video-info { padding: 16px; }
        .video-title { 
            font-size: 16px; 
            font-weight: 600; 
            color: #ffffff; 
            margin-bottom: 8px; 
            line-height: 1.3; 
        }
        .video-description { 
            color: #aaaaaa; 
            font-size: 14px; 
            margin-bottom: 8px; 
            line-height: 1.4; 
        }
        .video-meta { color: #aaaaaa; font-size: 13px; }

        @media (min-width: 768px) {
            .container { padding: 24px; }
            .spot-title { font-size: 28px; }
            .route-map-container { height: 500px; }
            .videos-grid { grid-template-columns: repeat(2, 1fr); gap: 24px; }
        }

        @media (min-width: 1024px) {
            .videos-grid { grid-template-columns: repeat(3, 1fr); }
        }
    </style>
</head>
<body>
    <header class="header">
        <button class="back-btn" onclick="window.location.href='/'">← 홈으로</button>
        <div class="channel-info">
            <div class="channel-avatar"><img src="{{ channel_info.thumbnail }}" alt="{{ channel_info.title }}"></div>
            <div class="channel-details">
                <h1>{{ channel_info.title }}</h1>
                <div class="channel-meta">{{ spot.title }} 상세보기</div>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="spot-header">
            <h1 class="spot-title">{{ spot.title }}</h1>
            <p class="spot-description">{{ spot.description }}</p>
            <div class="spot-info-grid">
                <div class="info-item">
                    <div class="info-value">{{ calculated_distance }}</div>
                    <div class="info-label">계산된 거리</div>
                </div>
                <div class="info-item">
                    <div class="info-value">{{ estimated_time }}분</div>
                    <div class="info-label">예상 소요시간</div>
                </div>
                <div class="info-item">
                    <div class="info-value difficulty-{{ spot.difficulty }}">{{ spot.difficulty }}</div>
                    <div class="info-label">난이도</div>
                </div>
                <div class="info-item">
                    <div class="info-value">★ {{ spot.rating }}</div>
                    <div class="info-label">평점</div>
                </div>
                <div class="info-item">
                    <div class="info-value">{{ videos|length }}개</div>
                    <div class="info-label">영상 수</div>
                </div>
                {% if route_info %}
                <div class="info-item">
                    <div class="info-value">
                        {% if route_info.type == '왕복' %}왕복
                        {% elif route_info.type == '편도' %}편도
                        {% endif %}
                    </div>
                    <div class="info-label">경로 타입</div>
                </div>
                {% endif %}
            </div>
        </div>
        
       

        {% if route_info %}
        <section class="route-section">
    
            <h2 class="route-title">수영 경로 정보</h2>
            <div class="route-map-container">{{ route_map_html|safe }}</div>        
                    
            <div class="route-points">
                <h4>경로 포인트 상세</h4>
                {% for point in route_info.points %}
                <div class="route-point">
                    <div class="route-point-marker marker-{{ point.type }}">
                        {% if point.type == 'start' %}S
                        {% elif point.type == 'end' %}E
                        {% else %}{{ loop.index }}
                        {% endif %}
                    </div>
                    <div>
                        <div class="route-point-name">{{ point.name }}</div>
                        <div class="route-point-coords">{{ "%.6f"|format(point.coords[0]) }}, {{ "%.6f"|format(point.coords[1]) }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}

        <section class="videos-section">
            <h2>이 장소의 수영 영상들</h2>
            <div class="videos-grid">
                {% for video in videos %}
                <div class="video-card" onclick="window.open('{{ video.url }}', '_blank')">
                    <div class="video-thumbnail">
                        <img src="{{ video.thumbnail }}" alt="{{ video.title }}">
                        <div class="video-duration">{{ video.duration }}</div>
                        <div class="video-overlay">
                            <div class="play-btn">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="#181818"><path d="M8 5v14l11-7z"/></svg>
                            </div>
                        </div>
                    </div>
                    <div class="video-info">
                        <h3 class="video-title">{{ video.title }}</h3>
                        <p class="video-description">{{ video.description }}</p>
                        <div class="video-meta">조회수 {{ video.views }}회 • {{ video.date }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
    </div>
</body>
</html>'''

        return render_template_string(detail_html,
                                      spot=spot_data,
                                      videos=enriched_videos,
                                      location=location,
                                      channel_info=channel_info,
                                      route_info=route_info,
                                      route_map_html=route_map_html,
                                      total_distance=total_distance,
                                      estimated_time=estimated_time,
                                      calculated_distance=f"{total_distance:.1f}km")

    except Exception as e:
        print(f"Spot detail error: {e}")
        return f"오류가 발생했습니다: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
