#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill Actual Weather Data (4 ports)
Fetches historical measured weather for all ferry ports from
Open-Meteo Archive + Marine APIs and stores in actual_weather table.

Usage:
    python backfill_actual_weather.py                         # 2026-04-05 to yesterday
    python backfill_actual_weather.py 2025-10-01              # custom start date
    python backfill_actual_weather.py 2025-10-01 2026-01-01  # custom range

Note: default start is 2026-04-05 (first date with reliable ferry status data).
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

LOCATIONS = {
    'wakkanai':   {'lat': 45.415, 'lon': 141.673},
    'oshidomari': {'lat': 45.200, 'lon': 141.216},
    'kutsugata':  {'lat': 45.393, 'lon': 141.107},
    'kafuka':     {'lat': 45.298, 'lon': 141.036},
}

JST = pytz.timezone('Asia/Tokyo')


def get_db_path():
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    return os.path.join(data_dir, 'ferry_weather_forecast.db')


def init_table(db_path):
    """Create or migrate actual_weather table to 4-port schema."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actual_weather'")
    table_exists = cur.fetchone() is not None

    if table_exists:
        cur.execute("PRAGMA table_info(actual_weather)")
        cols = [row[1] for row in cur.fetchall()]
        if 'location' not in cols:
            print("Migrating actual_weather table to 4-port schema...")
            conn.execute("ALTER TABLE actual_weather RENAME TO actual_weather_old")
            conn.execute('''
                CREATE TABLE actual_weather (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    date         TEXT NOT NULL,
                    hour         INTEGER NOT NULL,
                    location     TEXT NOT NULL DEFAULT 'wakkanai',
                    wind_speed   REAL,
                    wave_height  REAL,
                    visibility   REAL,
                    collected_at TEXT NOT NULL,
                    UNIQUE(date, hour, location)
                )
            ''')
            conn.execute('''
                INSERT INTO actual_weather
                    (date, hour, location, wind_speed, wave_height, visibility, collected_at)
                SELECT date, hour, 'wakkanai', wind_speed, wave_height, visibility, collected_at
                FROM actual_weather_old
            ''')
            conn.execute("DROP TABLE actual_weather_old")
            conn.commit()
            print("Migration complete.")
    else:
        conn.execute('''
            CREATE TABLE actual_weather (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         TEXT NOT NULL,
                hour         INTEGER NOT NULL,
                location     TEXT NOT NULL DEFAULT 'wakkanai',
                wind_speed   REAL,
                wave_height  REAL,
                visibility   REAL,
                collected_at TEXT NOT NULL,
                UNIQUE(date, hour, location)
            )
        ''')
        conn.commit()

    conn.close()


def already_collected(db_path, date_str, loc_name):
    """Return True if this date+location already has 20+ records."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(
            'SELECT COUNT(*) FROM actual_weather WHERE date = ? AND location = ?',
            (date_str, loc_name)
        )
        count = cur.fetchone()[0]
    except Exception:
        count = 0
    conn.close()
    return count >= 20


_WIND_VIS_URLS = [
    'https://archive-api.open-meteo.com/v1/archive',   # ERA5 reanalysis (primary)
    'https://api.open-meteo.com/v1/forecast',           # Forecast API fallback (past_days)
]

def fetch_chunk(start_str, end_str, loc_name, loc_coords):
    """Fetch wind+visibility+wave for a date range at one location."""
    result = {}

    wind_params = {
        'latitude':       loc_coords['lat'],
        'longitude':      loc_coords['lon'],
        'start_date':     start_str,
        'end_date':       end_str,
        'hourly':         ['windspeed_10m', 'visibility'],
        'timezone':       'Asia/Tokyo',
        'windspeed_unit': 'ms',
    }
    fetched_wind = False
    for url in _WIND_VIS_URLS:
        try:
            r = requests.get(url, params=wind_params, timeout=60)
            r.raise_for_status()
            h = r.json()['hourly']
            for t, w, v in zip(h['time'], h['windspeed_10m'], h['visibility']):
                d, hr = t[:10], int(t[11:13])
                result.setdefault(d, {})[hr] = {
                    'wind_speed': w,
                    'visibility': v / 1000 if v is not None else None,
                }
            source = 'Archive' if url == _WIND_VIS_URLS[0] else f'Forecast(fallback)'
            print(f"    {source}: {len(h['time'])} records", end='')
            fetched_wind = True
            break
        except Exception as e:
            if url == _WIND_VIS_URLS[-1]:
                print(f"    [ERROR] Wind/Vis APIs all failed ({loc_name}): {e}", end='')
            continue

    try:
        r = requests.get(
            'https://marine-api.open-meteo.com/v1/marine',
            params={
                'latitude':   loc_coords['lat'],
                'longitude':  loc_coords['lon'],
                'start_date': start_str,
                'end_date':   end_str,
                'hourly':     ['wave_height'],
                'timezone':   'Asia/Tokyo',
            },
            timeout=60
        )
        r.raise_for_status()
        h = r.json()['hourly']
        for t, w in zip(h['time'], h['wave_height']):
            d, hr = t[:10], int(t[11:13])
            result.setdefault(d, {}).setdefault(hr, {})
            result[d][hr]['wave_height'] = w
        print(f"  Marine: {len(h['time'])} records")
    except Exception as e:
        print(f"  [ERROR] Marine API ({loc_name}): {e}")

    return result


def save_chunk(db_path, chunk_data, loc_name):
    """Save chunk data for one location. Returns count of saved records."""
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
                (date, hour, location, wind_speed, wave_height, visibility, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (date_str, hour, loc_name, wind, wave, vis, now_str))
            saved += 1
    conn.commit()
    conn.close()
    return saved


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        start_str = args[0]
        end_str   = args[1]
    elif len(args) == 1:
        start_str = args[0]
        end_str   = (datetime.now(JST) - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        # Default: 2026-04-05 = first date with reliable ferry scraper data
        start_str = '2026-04-05'
        end_str   = (datetime.now(JST) - timedelta(days=1)).strftime('%Y-%m-%d')

    db_path = get_db_path()
    init_table(db_path)

    start_date = date.fromisoformat(start_str)
    end_date   = date.fromisoformat(end_str)
    total_days = (end_date - start_date).days + 1

    print(f"Backfilling actual weather: {start_str} to {end_str} ({total_days} days, 4 ports)")
    print(f"DB: {db_path}")
    print()

    chunk_days  = 30
    grand_total = 0

    for loc_name, loc_coords in LOCATIONS.items():
        print(f"=== {loc_name} ===")
        current     = start_date
        loc_total   = 0
        chunks_done = 0

        while current <= end_date:
            chunk_end        = min(current + timedelta(days=chunk_days - 1), end_date)
            chunk_start_str  = current.strftime('%Y-%m-%d')
            chunk_end_str    = chunk_end.strftime('%Y-%m-%d')

            # Skip chunks where all dates are already collected
            dates_in_chunk = [(current + timedelta(days=i)).strftime('%Y-%m-%d')
                              for i in range((chunk_end - current).days + 1)]
            if all(already_collected(db_path, d, loc_name) for d in dates_in_chunk):
                print(f"  Chunk {chunks_done+1} ({chunk_start_str}~{chunk_end_str}): already collected, skip")
                current      = chunk_end + timedelta(days=1)
                chunks_done += 1
                continue

            print(f"  Chunk {chunks_done+1}: {chunk_start_str} - {chunk_end_str}", end='  ')
            chunk_data = fetch_chunk(chunk_start_str, chunk_end_str, loc_name, loc_coords)
            saved      = save_chunk(db_path, chunk_data, loc_name)
            loc_total  += saved
            chunks_done += 1
            print(f"  → {saved} records saved")

            current = chunk_end + timedelta(days=1)
            if current <= end_date:
                time.sleep(0.5)

        print(f"  {loc_name}: {loc_total} records total\n")
        grand_total += loc_total

    print(f"Backfill complete: {grand_total} records saved across 4 ports")

    # Summary from DB
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute('''
        SELECT location, MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(*)
        FROM actual_weather
        GROUP BY location
        ORDER BY location
    ''')
    rows = cur.fetchall()
    conn.close()
    if rows:
        print("\nDB coverage per port:")
        for loc, dmin, dmax, days, records in rows:
            print(f"  {loc:12s}: {dmin} ~ {dmax}  ({days} days, {records} hourly records)")


if __name__ == '__main__':
    main()
