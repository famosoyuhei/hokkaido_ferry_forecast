#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actual Weather Collector
Fetches measured (not forecast) weather for all 4 ferry ports from:
  - Open-Meteo Archive API  : wind speed, visibility (ERA5 reanalysis)
  - Open-Meteo Marine API   : wave height
Stores per-port hourly records in actual_weather table.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import sqlite3
import os
from datetime import datetime, timedelta
import pytz

class ActualWeatherCollector:

    LOCATIONS = {
        'wakkanai':   {'lat': 45.415, 'lon': 141.673},
        'oshidomari': {'lat': 45.200, 'lon': 141.216},
        'kutsugata':  {'lat': 45.393, 'lon': 141.107},
        'kafuka':     {'lat': 45.298, 'lon': 141.036},
    }

    def __init__(self):
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.db_file = os.path.join(data_dir, 'ferry_weather_forecast.db')
        self.jst = pytz.timezone('Asia/Tokyo')
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actual_weather'")
        table_exists = cur.fetchone() is not None

        if table_exists:
            cur.execute("PRAGMA table_info(actual_weather)")
            cols = [row[1] for row in cur.fetchall()]
            if 'location' not in cols:
                # Migrate: old schema had UNIQUE(date, hour); new schema needs (date, hour, location)
                print("  Migrating actual_weather table to add location column...")
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
                print("  Migration complete.")
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
        print(f"DB: {self.db_file}")

    # ------------------------------------------------------------------
    _ARCHIVE_PARAMS = {
        'hourly':         ['windspeed_10m', 'visibility'],
        'timezone':       'Asia/Tokyo',
        'windspeed_unit': 'ms',
    }
    _ARCHIVE_URLS = [
        'https://archive-api.open-meteo.com/v1/archive',      # ERA5 reanalysis (primary)
        'https://api.open-meteo.com/v1/forecast',              # Forecast API fallback (past_days)
    ]

    def _fetch_archive(self, date_str: str, loc: dict) -> dict:
        """Wind + visibility — tries Archive API first, falls back to Forecast API."""
        params = {
            'latitude':       loc['lat'],
            'longitude':      loc['lon'],
            'start_date':     date_str,
            'end_date':       date_str,
            **self._ARCHIVE_PARAMS,
        }
        last_exc = None
        for i, url in enumerate(self._ARCHIVE_URLS):
            # Primary (archive) gets a short timeout so we fail fast to the fallback.
            # The fallback (forecast API) gets the full timeout.
            req_timeout = 5 if i < len(self._ARCHIVE_URLS) - 1 else 30
            try:
                r = requests.get(url, params=params, timeout=req_timeout)
                r.raise_for_status()
                h = r.json()['hourly']
                result = {}
                for t, w, v in zip(h['time'], h['windspeed_10m'], h['visibility']):
                    hour = int(t[11:13])
                    result[hour] = {
                        'wind_speed': w,
                        'visibility': v / 1000 if v is not None else None,  # m -> km
                    }
                if i > 0:
                    print(f"[fallback:{url.split('/')[2]}] ", end='', flush=True)
                return result
            except Exception as e:
                last_exc = e
                continue
        raise last_exc

    def _fetch_marine(self, date_str: str, loc: dict) -> dict:
        """Wave height from Open-Meteo Marine Archive."""
        r = requests.get(
            'https://marine-api.open-meteo.com/v1/marine',
            params={
                'latitude':   loc['lat'],
                'longitude':  loc['lon'],
                'start_date': date_str,
                'end_date':   date_str,
                'hourly':     ['wave_height'],
                'timezone':   'Asia/Tokyo',
            },
            timeout=30
        )
        r.raise_for_status()
        h = r.json()['hourly']
        result = {}
        for t, w in zip(h['time'], h['wave_height']):
            hour = int(t[11:13])
            result[hour] = w
        return result

    # ------------------------------------------------------------------
    def collect(self, target_date: str = None) -> int:
        """Collect actual weather for all 4 ports on target_date (default: yesterday JST)."""
        if target_date is None:
            yesterday = datetime.now(self.jst) - timedelta(days=1)
            target_date = yesterday.strftime('%Y-%m-%d')

        print(f"\nCollecting actual weather for {target_date} (4 ports)...")

        now_str = datetime.now(self.jst).isoformat()
        conn = sqlite3.connect(self.db_file)
        total_saved = 0

        for loc_name, loc_coords in self.LOCATIONS.items():
            print(f"  [{loc_name}] ", end='', flush=True)
            try:
                archive = self._fetch_archive(target_date, loc_coords)
            except Exception as e:
                print(f"Archive error: {e}")
                archive = {}
            try:
                marine = self._fetch_marine(target_date, loc_coords)
            except Exception as e:
                print(f"Marine error: {e}")
                marine = {}

            saved = 0
            for hour in range(24):
                wind = archive.get(hour, {}).get('wind_speed')
                vis  = archive.get(hour, {}).get('visibility')
                wave = marine.get(hour)
                if wind is None and wave is None:
                    continue
                conn.execute('''
                    INSERT OR REPLACE INTO actual_weather
                    (date, hour, location, wind_speed, wave_height, visibility, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (target_date, hour, loc_name, wind, wave, vis, now_str))
                saved += 1

            print(f"{saved} records")
            total_saved += saved

        conn.commit()
        conn.close()
        print(f"  Total: {total_saved} records saved for {target_date}")
        return total_saved


if __name__ == '__main__':
    collector = ActualWeatherCollector()
    target = sys.argv[1] if len(sys.argv) > 1 else None
    n = collector.collect(target)
    print(f"\nDone: {n} records saved.")
