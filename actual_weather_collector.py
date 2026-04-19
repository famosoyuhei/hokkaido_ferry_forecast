#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actual Weather Collector
Fetches yesterday's measured (not forecast) weather data from:
  - Open-Meteo Archive API  : wind speed, visibility (ERA5 reanalysis)
  - Open-Meteo Marine API   : wave height
Stores results in actual_weather table for use by accuracy tracker.
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

    WAKKANAI = {'lat': 45.415, 'lon': 141.673}

    def __init__(self):
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.db_file = os.path.join(data_dir, 'ferry_weather_forecast.db')
        self.jst = pytz.timezone('Asia/Tokyo')
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_file)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS actual_weather (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                date          TEXT NOT NULL,
                hour          INTEGER NOT NULL,
                wind_speed    REAL,
                wave_height   REAL,
                visibility    REAL,
                collected_at  TEXT NOT NULL,
                UNIQUE(date, hour)
            )
        ''')
        conn.commit()
        conn.close()
        print(f"DB: {self.db_file}")

    # ------------------------------------------------------------------
    def _fetch_archive(self, date_str: str):
        """Wind + visibility from Open-Meteo Archive (ERA5 reanalysis)."""
        url = 'https://archive-api.open-meteo.com/v1/archive'
        params = {
            'latitude':  self.WAKKANAI['lat'],
            'longitude': self.WAKKANAI['lon'],
            'start_date': date_str,
            'end_date':   date_str,
            'hourly': ['windspeed_10m', 'visibility'],
            'timezone': 'Asia/Tokyo',
            'windspeed_unit': 'ms',
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        h = r.json()['hourly']
        result = {}
        for t, w, v in zip(h['time'], h['windspeed_10m'], h['visibility']):
            hour = int(t[11:13])
            result[hour] = {
                'wind_speed':  w,
                'visibility':  v / 1000 if v is not None else None,  # m -> km
            }
        print(f"  Archive API: {len(result)} hourly wind/visibility records")
        return result

    def _fetch_marine(self, date_str: str):
        """Wave height from Open-Meteo Marine Archive."""
        url = 'https://marine-api.open-meteo.com/v1/marine'
        params = {
            'latitude':  self.WAKKANAI['lat'],
            'longitude': self.WAKKANAI['lon'],
            'start_date': date_str,
            'end_date':   date_str,
            'hourly': ['wave_height'],
            'timezone': 'Asia/Tokyo',
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        h = r.json()['hourly']
        result = {}
        for t, w in zip(h['time'], h['wave_height']):
            hour = int(t[11:13])
            result[hour] = w
        print(f"  Marine API:  {len(result)} hourly wave height records")
        return result

    # ------------------------------------------------------------------
    def collect(self, target_date: str = None) -> int:
        """Collect actual weather for target_date (default: yesterday JST)."""
        if target_date is None:
            yesterday = datetime.now(self.jst) - timedelta(days=1)
            target_date = yesterday.strftime('%Y-%m-%d')

        print(f"\nCollecting actual weather for {target_date}...")

        try:
            archive = self._fetch_archive(target_date)
        except Exception as e:
            print(f"  [ERROR] Archive API failed: {e}")
            archive = {}

        try:
            marine = self._fetch_marine(target_date)
        except Exception as e:
            print(f"  [ERROR] Marine API failed: {e}")
            marine = {}

        if not archive and not marine:
            print("  No data retrieved.")
            return 0

        now_str = datetime.now(self.jst).isoformat()
        conn = sqlite3.connect(self.db_file)
        saved = 0
        for hour in range(24):
            wind = archive.get(hour, {}).get('wind_speed')
            vis  = archive.get(hour, {}).get('visibility')
            wave = marine.get(hour)
            if wind is None and wave is None:
                continue
            conn.execute('''
                INSERT OR REPLACE INTO actual_weather
                (date, hour, wind_speed, wave_height, visibility, collected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (target_date, hour, wind, wave, vis, now_str))
            saved += 1

        conn.commit()
        conn.close()
        print(f"  Saved {saved} hourly actual weather records for {target_date}")
        return saved


if __name__ == '__main__':
    import sys
    collector = ActualWeatherCollector()
    target = sys.argv[1] if len(sys.argv) > 1 else None
    n = collector.collect(target)
    print(f"\nDone: {n} records saved.")
