#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill Actual Weather Data
Fetches historical measured weather (wind, wave, visibility) from
Open-Meteo Archive + Marine APIs and stores in actual_weather table.

Usage:
    python backfill_actual_weather.py                  # 2025-10-01 to yesterday
    python backfill_actual_weather.py 2025-08-01       # custom start date
    python backfill_actual_weather.py 2025-10-01 2026-01-01  # custom range
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import sqlite3
import os
import time
from datetime import datetime, timedelta, date
import pytz

WAKKANAI = {'lat': 45.415, 'lon': 141.673}
JST = pytz.timezone('Asia/Tokyo')


def get_db_path():
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    return os.path.join(data_dir, 'ferry_weather_forecast.db')


def init_table(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS actual_weather (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT NOT NULL,
            hour         INTEGER NOT NULL,
            wind_speed   REAL,
            wave_height  REAL,
            visibility   REAL,
            collected_at TEXT NOT NULL,
            UNIQUE(date, hour)
        )
    ''')
    conn.commit()
    conn.close()


def already_collected(db_path, date_str):
    """Return True if this date already has 20+ records (already backfilled)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM actual_weather WHERE date = ?', (date_str,))
    count = cur.fetchone()[0]
    conn.close()
    return count >= 20


def fetch_chunk(start_str, end_str):
    """Fetch wind+visibility and wave height for a date range. Returns dict[date][hour]."""
    result = {}

    # Wind + visibility (Archive API)
    try:
        r = requests.get(
            'https://archive-api.open-meteo.com/v1/archive',
            params={
                'latitude': WAKKANAI['lat'],
                'longitude': WAKKANAI['lon'],
                'start_date': start_str,
                'end_date': end_str,
                'hourly': ['windspeed_10m', 'visibility'],
                'timezone': 'Asia/Tokyo',
                'windspeed_unit': 'ms',
            },
            timeout=60
        )
        r.raise_for_status()
        h = r.json()['hourly']
        for t, w, v in zip(h['time'], h['windspeed_10m'], h['visibility']):
            d, hr = t[:10], int(t[11:13])
            result.setdefault(d, {})[hr] = {
                'wind_speed': w,
                'visibility': v / 1000 if v is not None else None,
            }
        print(f"  Archive:  {len(h['time'])} records ({start_str} - {end_str})")
    except Exception as e:
        print(f"  [ERROR] Archive API: {e}")

    # Wave height (Marine API)
    try:
        r = requests.get(
            'https://marine-api.open-meteo.com/v1/marine',
            params={
                'latitude': WAKKANAI['lat'],
                'longitude': WAKKANAI['lon'],
                'start_date': start_str,
                'end_date': end_str,
                'hourly': ['wave_height'],
                'timezone': 'Asia/Tokyo',
            },
            timeout=60
        )
        r.raise_for_status()
        h = r.json()['hourly']
        for t, w in zip(h['time'], h['wave_height']):
            d, hr = t[:10], int(t[11:13])
            result.setdefault(d, {}).setdefault(hr, {})
            result[d][hr]['wave_height'] = w
        print(f"  Marine:   {len(h['time'])} records ({start_str} - {end_str})")
    except Exception as e:
        print(f"  [ERROR] Marine API: {e}")

    return result


def save_chunk(db_path, chunk_data):
    """Save chunk data to actual_weather table. Returns count of saved records."""
    now_str = datetime.now(JST).isoformat()
    conn = sqlite3.connect(db_path)
    saved = 0
    for date_str, hours in chunk_data.items():
        for hour, vals in hours.items():
            wind = vals.get('wind_speed')
            wave = vals.get('wave_height')
            vis  = vals.get('visibility')
            if wind is None and wave is None:
                continue
            conn.execute('''
                INSERT OR REPLACE INTO actual_weather
                (date, hour, wind_speed, wave_height, visibility, collected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (date_str, hour, wind, wave, vis, now_str))
            saved += 1
    conn.commit()
    conn.close()
    return saved


def main():
    # Parse arguments
    args = sys.argv[1:]
    if len(args) >= 2:
        start_str = args[0]
        end_str = args[1]
    elif len(args) == 1:
        start_str = args[0]
        end_str = (datetime.now(JST) - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        start_str = '2025-10-01'
        end_str = (datetime.now(JST) - timedelta(days=1)).strftime('%Y-%m-%d')

    db_path = get_db_path()
    init_table(db_path)

    start_date = date.fromisoformat(start_str)
    end_date   = date.fromisoformat(end_str)
    total_days = (end_date - start_date).days + 1

    print(f"Backfilling actual weather: {start_str} to {end_str} ({total_days} days)")
    print(f"DB: {db_path}")
    print()

    # Process in 30-day chunks to stay within API limits
    chunk_days = 30
    current = start_date
    total_saved = 0
    chunks_done = 0

    while current <= end_date:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end_date)
        chunk_start_str = current.strftime('%Y-%m-%d')
        chunk_end_str   = chunk_end.strftime('%Y-%m-%d')

        print(f"Chunk {chunks_done+1}: {chunk_start_str} - {chunk_end_str}")

        chunk_data = fetch_chunk(chunk_start_str, chunk_end_str)
        saved = save_chunk(db_path, chunk_data)
        total_saved += saved
        chunks_done += 1

        print(f"  Saved {saved} records this chunk")

        current = chunk_end + timedelta(days=1)

        # Brief pause between chunks to be polite to the API
        if current <= end_date:
            time.sleep(1)

    print()
    print(f"Backfill complete: {total_saved} total records saved across {chunks_done} chunks")

    # Summary from DB
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        SELECT MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(*)
        FROM actual_weather
    ''')
    row = cur.fetchone()
    conn.close()
    if row[0]:
        print(f"DB now covers: {row[0]} to {row[1]} ({row[2]} days, {row[3]} hourly records)")


if __name__ == '__main__':
    main()
