#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JST (Japan Standard Time) utility functions.

Use these instead of datetime.now() or SQLite date('now') to avoid UTC
mismatches on Railway (and any other UTC-hosted server).

Usage:
    from jst_utils import now_jst, today_jst_str, jst_isoformat

    # Replace datetime.now() → now_jst()
    # Replace datetime.now().date().isoformat() → today_jst_str()
    # Replace datetime.now().isoformat() → jst_isoformat()

    # In SQLite queries replace date('now') with a parameter:
    #   WHERE forecast_for_date >= date('now')
    #   →
    #   WHERE forecast_for_date >= ?   params: (today_jst_str(),)
"""

import json
from pathlib import Path
from typing import List, Tuple
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo          # Python 3.9+
    _JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz                            # fallback (Python 3.8 / pytz installed)
    _JST = pytz.timezone("Asia/Tokyo")


# ---------------------------------------------------------------------------
# 時刻表ユーティリティ
# 正ソース: skills/ferry-cancellation-research/references/heartland_{year}_timetable.json
# 年が変わったら heartland_{year}_timetable.json を追加するだけでよい。
# ---------------------------------------------------------------------------

_timetable_cache: dict = {}   # {year: timetable_dict}

_TIMETABLE_DIR = (
    Path(__file__).parent
    / 'skills' / 'ferry-cancellation-research' / 'references'
)


def _load_timetable(year: int) -> dict:
    """
    指定年の時刻表 JSON をロードしてキャッシュする。
    当該年の JSON が存在しない場合は最新年の JSON にフォールバックする。
    """
    if year in _timetable_cache:
        return _timetable_cache[year]

    path = _TIMETABLE_DIR / f'heartland_{year}_timetable.json'
    if not path.exists():
        # フォールバック: 最新の heartland_????_timetable.json を使う
        candidates = sorted(
            _TIMETABLE_DIR.glob('heartland_????_timetable.json'),
            reverse=True
        )
        if not candidates:
            _timetable_cache[year] = {}
            return {}
        path = candidates[0]

    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        _timetable_cache[year] = data
        return data
    except Exception as e:
        print(f'[jst_utils] timetable load error ({path}): {e}')
        _timetable_cache[year] = {}
        return {}


def get_timetable_sailings(route: str, date_str: str) -> List[Tuple[str, str]]:
    """
    指定日・航路の時刻表便リストを返す: [(出港時刻, 到着時刻), ...]
    日付から自動的に適切な年の JSON を読み込む。
    """
    year = int(date_str[:4])
    data = _load_timetable(year)
    for schedule in data.get('schedules', []):
        if schedule['start_date'] <= date_str <= schedule['end_date']:
            rows = schedule.get('sailings', {}).get(route, [])
            return [(row[0], row[1]) for row in rows]
    return []


def get_active_routes_on(date_str: str) -> List[str]:
    """
    指定日に運航スケジュールがある航路キーのリストを返す。
    日付から自動的に適切な年の JSON を読み込む。
    """
    year = int(date_str[:4])
    data = _load_timetable(year)
    for schedule in data.get('schedules', []):
        if schedule['start_date'] <= date_str <= schedule['end_date']:
            return list(schedule.get('sailings', {}).keys())
    return []


def now_jst() -> datetime:
    """Return timezone-aware datetime in JST (replaces datetime.now())."""
    return datetime.now(_JST)


def today_jst_str() -> str:
    """Return today's date in JST as ISO string 'YYYY-MM-DD'
    (replaces datetime.now().date().isoformat() and SQLite date('now')).
    """
    return now_jst().date().isoformat()


def jst_isoformat() -> str:
    """Return current JST datetime as ISO 8601 string
    (replaces datetime.now().isoformat() for timestamps stored in DB).
    """
    return now_jst().isoformat()


def days_from_today_jst(days: int) -> str:
    """Return ISO date string N days from today (JST).
    Replaces: (datetime.now().date() + timedelta(days=N)).isoformat()
    """
    return (now_jst().date() + timedelta(days=days)).isoformat()
