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
import json
from datetime import datetime, timedelta
from pathlib import Path
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
        self.port_location_names = {
            'wakkanai': '稚内',
            'oshidomari': '鴛泊',
            'kutsugata': '沓形',
            'kafuka': '香深',
        }
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
                        wind_direction REAL,
                        wind_gusts   REAL,
                        wave_height  REAL,
                        wave_direction REAL,
                        wave_period  REAL,
                        wind_wave_height REAL,
                        wind_wave_direction REAL,
                        wind_wave_period REAL,
                        swell_wave_height REAL,
                        swell_wave_direction REAL,
                        swell_wave_period REAL,
                        sea_surface_temperature REAL,
                        visibility   REAL,
                        precipitation REAL,
                        snowfall     REAL,
                        temperature  REAL,
                        pressure_msl REAL,
                        weather_code INTEGER,
                        data_source  TEXT,
                        valid_time   TEXT,
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
                    wind_direction REAL,
                    wind_gusts   REAL,
                    wave_height  REAL,
                    wave_direction REAL,
                    wave_period  REAL,
                    wind_wave_height REAL,
                    wind_wave_direction REAL,
                    wind_wave_period REAL,
                    swell_wave_height REAL,
                    swell_wave_direction REAL,
                    swell_wave_period REAL,
                    sea_surface_temperature REAL,
                    visibility   REAL,
                    precipitation REAL,
                    snowfall     REAL,
                    temperature  REAL,
                    pressure_msl REAL,
                    weather_code INTEGER,
                    data_source  TEXT,
                    valid_time   TEXT,
                    collected_at TEXT NOT NULL,
                    UNIQUE(date, hour, location)
                )
            ''')
            conn.commit()

        self._add_missing_columns(cur, {
            'wind_direction': 'REAL',
            'wind_gusts': 'REAL',
            'wave_direction': 'REAL',
            'wave_period': 'REAL',
            'wind_wave_height': 'REAL',
            'wind_wave_direction': 'REAL',
            'wind_wave_period': 'REAL',
            'swell_wave_height': 'REAL',
            'swell_wave_direction': 'REAL',
            'swell_wave_period': 'REAL',
            'sea_surface_temperature': 'REAL',
            'precipitation': 'REAL',
            'snowfall': 'REAL',
            'temperature': 'REAL',
            'pressure_msl': 'REAL',
            'weather_code': 'INTEGER',
            'data_source': 'TEXT',
            'valid_time': 'TEXT'
        })

        conn.execute('''
            CREATE TABLE IF NOT EXISTS actual_sailing_weather (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_date TEXT NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                port_role TEXT NOT NULL,
                port_key TEXT NOT NULL,
                port_name TEXT,
                weather_hour INTEGER NOT NULL,
                scheduled_reference_time TEXT,
                window_start_time TEXT,
                window_end_time TEXT,
                minutes_from_departure INTEGER,
                via_oshidomari BOOLEAN DEFAULT 0,

                wind_speed REAL,
                wind_direction REAL,
                wind_gusts REAL,
                wave_height REAL,
                wave_direction REAL,
                wave_period REAL,
                wind_wave_height REAL,
                swell_wave_height REAL,
                visibility REAL,
                precipitation REAL,
                snowfall REAL,
                temperature REAL,
                pressure_msl REAL,
                weather_code INTEGER,

                source TEXT,
                valid_time TEXT,
                assigned_at TEXT,

                UNIQUE(service_date, route, departure_time, port_role, port_key, weather_hour)
            )
        ''')
        self._add_missing_columns_for_table(cur, 'actual_sailing_weather', {
            'window_start_time': 'TEXT',
            'window_end_time': 'TEXT'
        })
        conn.commit()

        conn.close()
        print(f"DB: {self.db_file}")

    def _add_missing_columns(self, cursor, columns: dict):
        """Add backward-compatible columns to actual_weather."""

        self._add_missing_columns_for_table(cursor, 'actual_weather', columns)

    def _add_missing_columns_for_table(self, cursor, table: str, columns: dict):
        """Add backward-compatible columns to a SQLite table."""

        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for column, column_type in columns.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    # ------------------------------------------------------------------
    _ARCHIVE_PARAMS = {
        'hourly': [
            'temperature_2m',
            'precipitation',
            'snowfall',
            'weather_code',
            'pressure_msl',
            'wind_speed_10m',
            'wind_direction_10m',
            'wind_gusts_10m',
            'visibility'
        ],
        'timezone':       'Asia/Tokyo',
        'wind_speed_unit': 'ms',
    }
    _ARCHIVE_URLS = [
        'https://archive-api.open-meteo.com/v1/archive',      # ERA5 reanalysis (primary)
        'https://api.open-meteo.com/v1/forecast',              # Forecast API fallback (past_days)
    ]

    def _fetch_archive(self, date_str: str, loc: dict) -> dict:
        """Weather variables — tries Archive API first, falls back to Forecast API."""
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
                times = h.get('time', [])
                for idx, t in enumerate(times):
                    hour = int(t[11:13])
                    result[hour] = {
                        'temperature': self._hourly_value(h, 'temperature_2m', idx),
                        'precipitation': self._hourly_value(h, 'precipitation', idx),
                        'snowfall': self._snowfall_mm(self._hourly_value(h, 'snowfall', idx)),
                        'weather_code': self._hourly_value(h, 'weather_code', idx),
                        'pressure_msl': self._hourly_value(h, 'pressure_msl', idx),
                        'wind_speed': self._hourly_value(h, 'wind_speed_10m', idx),
                        'wind_direction': self._hourly_value(h, 'wind_direction_10m', idx),
                        'wind_gusts': self._hourly_value(h, 'wind_gusts_10m', idx),
                        'visibility': self._visibility_km(self._hourly_value(h, 'visibility', idx)),
                        'valid_time': t,
                        'data_source': 'Open-Meteo Archive' if i == 0 else 'Open-Meteo Forecast Fallback',
                    }
                if i > 0:
                    print(f"[fallback:{url.split('/')[2]}] ", end='', flush=True)
                return result
            except Exception as e:
                last_exc = e
                continue
        raise last_exc

    def _fetch_marine(self, date_str: str, loc: dict) -> dict:
        """Marine variables from Open-Meteo Marine."""
        hourly_marine = [
            'wave_height',
            'wave_direction',
            'wave_period',
            'wind_wave_height',
            'wind_wave_direction',
            'wind_wave_period',
            'swell_wave_height',
            'swell_wave_direction',
            'swell_wave_period',
            'sea_surface_temperature'
        ]
        r = requests.get(
            'https://marine-api.open-meteo.com/v1/marine',
            params={
                'latitude':   loc['lat'],
                'longitude':  loc['lon'],
                'start_date': date_str,
                'end_date':   date_str,
                'hourly':     hourly_marine,
                'timezone':   'Asia/Tokyo',
            },
            timeout=30
        )
        r.raise_for_status()
        h = r.json()['hourly']
        result = {}
        for idx, t in enumerate(h.get('time', [])):
            hour = int(t[11:13])
            result[hour] = {
                'wave_height': self._hourly_value(h, 'wave_height', idx),
                'wave_direction': self._hourly_value(h, 'wave_direction', idx),
                'wave_period': self._hourly_value(h, 'wave_period', idx),
                'wind_wave_height': self._hourly_value(h, 'wind_wave_height', idx),
                'wind_wave_direction': self._hourly_value(h, 'wind_wave_direction', idx),
                'wind_wave_period': self._hourly_value(h, 'wind_wave_period', idx),
                'swell_wave_height': self._hourly_value(h, 'swell_wave_height', idx),
                'swell_wave_direction': self._hourly_value(h, 'swell_wave_direction', idx),
                'swell_wave_period': self._hourly_value(h, 'swell_wave_period', idx),
                'sea_surface_temperature': self._hourly_value(h, 'sea_surface_temperature', idx),
            }
        return result

    def _hourly_value(self, hourly: dict, key: str, idx: int):
        values = hourly.get(key, [])
        return values[idx] if idx < len(values) else None

    def _visibility_km(self, value):
        return value / 1000 if value is not None else None

    def _snowfall_mm(self, value):
        """Normalize Open-Meteo snowfall from cm to mm."""

        return value * 10 if value is not None else None

    def _load_2026_timetable(self) -> dict:
        timetable_path = Path(__file__).parent / 'skills' / 'ferry-cancellation-research' / 'references' / 'heartland_2026_timetable.json'
        with open(timetable_path, encoding='utf-8') as f:
            return json.load(f)

    def _scheduled_sailings_for_date(self, service_date: str) -> list:
        target = datetime.fromisoformat(service_date).date()
        timetable = self._load_2026_timetable()
        for schedule in timetable.get('schedules', []):
            start = datetime.fromisoformat(schedule['start_date']).date()
            end = datetime.fromisoformat(schedule['end_date']).date()
            if start <= target <= end:
                sailings = []
                for route, rows in schedule.get('sailings', {}).items():
                    for row in rows:
                        meta = row[2] if len(row) > 2 and isinstance(row[2], dict) else {}
                        sailings.append({
                            'service_date': service_date,
                            'route': route,
                            'departure_time': row[0],
                            'arrival_time': row[1],
                            'via_oshidomari': bool(meta.get('via_oshidomari'))
                        })
                return sailings
        return []

    def _route_ports(self, route: str, via_oshidomari: bool = False) -> list:
        departure, arrival = route.split('_', 1)
        ports = [('departure', departure)]
        if via_oshidomari:
            ports.append(('via', 'oshidomari'))
        ports.append(('arrival', arrival))
        return ports

    def _hours_for_window(self, start: datetime, end: datetime) -> list:
        hours = []
        current = start.replace(minute=0, second=0, microsecond=0)
        while current <= end:
            hours.append(current.hour)
            current += timedelta(hours=1)
        return sorted(set(hours))

    def _role_window(self, service_date: str, route: str, departure_time: str, arrival_time: str, role: str) -> tuple:
        departure = datetime.fromisoformat(f'{service_date}T{departure_time}')
        arrival = datetime.fromisoformat(f'{service_date}T{arrival_time}')
        if arrival < departure:
            arrival += timedelta(days=1)
        if role == 'departure':
            return departure, departure
        if role == 'arrival':
            return arrival, arrival
        if route == 'wakkanai_kafuka':
            return departure + timedelta(minutes=100), departure + timedelta(minutes=125)
        if route == 'kafuka_wakkanai':
            return departure + timedelta(minutes=45), departure + timedelta(minutes=70)
        midpoint = departure + ((arrival - departure) / 2)
        return midpoint, midpoint

    def _minutes_from_departure(self, service_date: str, departure_time: str, reference_time: str) -> int:
        departure = datetime.fromisoformat(f'{service_date}T{departure_time}')
        reference = datetime.fromisoformat(f'{service_date}T{reference_time}')
        if reference < departure:
            reference += timedelta(days=1)
        return int((reference - departure).total_seconds() / 60)

    def generate_sailing_weather_actuals(self, service_date: str) -> int:
        """Assign hourly actual/reanalysis weather to scheduled sailing ports and windows."""

        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        generated = 0

        for sailing in self._scheduled_sailings_for_date(service_date):
            route = sailing['route']
            departure_time = sailing['departure_time']
            arrival_time = sailing['arrival_time']
            via_oshidomari = sailing['via_oshidomari']

            for role, port_key in self._route_ports(route, via_oshidomari):
                port_name = self.port_location_names.get(port_key)
                if port_name is None:
                    print(f"[WARNING] Unknown port key for actual sailing assignment: {port_key}")
                    continue

                window_start, window_end = self._role_window(service_date, route, departure_time, arrival_time, role)
                hours = self._hours_for_window(window_start, window_end)
                reference_time = window_start.strftime('%H:%M') if role != 'via' else (
                    window_start + ((window_end - window_start) / 2)
                ).strftime('%H:%M')
                window_start_time = window_start.strftime('%H:%M')
                window_end_time = window_end.strftime('%H:%M')
                minutes_from_departure = self._minutes_from_departure(service_date, departure_time, reference_time)

                for weather_hour in hours:
                    cur.execute('''
                        SELECT
                            wind_speed,
                            wind_direction,
                            wind_gusts,
                            wave_height,
                            wave_direction,
                            wave_period,
                            wind_wave_height,
                            swell_wave_height,
                            visibility,
                            precipitation,
                            snowfall,
                            temperature,
                            pressure_msl,
                            weather_code,
                            data_source,
                            valid_time
                        FROM actual_weather
                        WHERE date = ?
                          AND hour = ?
                          AND location = ?
                        LIMIT 1
                    ''', (service_date, weather_hour, port_key))
                    row = cur.fetchone()
                    if not row:
                        continue

                    cur.execute('''
                        INSERT OR REPLACE INTO actual_sailing_weather (
                            service_date, route, departure_time, arrival_time,
                            port_role, port_key, port_name, weather_hour,
                            scheduled_reference_time, window_start_time, window_end_time,
                            minutes_from_departure, via_oshidomari,
                            wind_speed, wind_direction, wind_gusts,
                            wave_height, wave_direction, wave_period,
                            wind_wave_height, swell_wave_height, visibility,
                            precipitation, snowfall, temperature, pressure_msl,
                            weather_code, source, valid_time, assigned_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        service_date, route, departure_time, arrival_time,
                        role, port_key, port_name, weather_hour,
                        reference_time, window_start_time, window_end_time,
                        minutes_from_departure, int(via_oshidomari),
                        *row,
                        datetime.now(self.jst).isoformat()
                    ))
                    generated += 1

        conn.commit()
        conn.close()
        print(f"  Sailing-time actual weather assignments: {generated}")
        return generated

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
                weather = archive.get(hour, {})
                sea = marine.get(hour, {})
                if not weather and not sea:
                    continue
                conn.execute('''
                    INSERT OR REPLACE INTO actual_weather
                    (
                        date, hour, location,
                        wind_speed, wind_direction, wind_gusts,
                        wave_height, wave_direction, wave_period,
                        wind_wave_height, wind_wave_direction, wind_wave_period,
                        swell_wave_height, swell_wave_direction, swell_wave_period,
                        sea_surface_temperature, visibility,
                        precipitation, snowfall, temperature, pressure_msl,
                        weather_code, data_source, valid_time, collected_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    target_date, hour, loc_name,
                    weather.get('wind_speed'), weather.get('wind_direction'), weather.get('wind_gusts'),
                    sea.get('wave_height'), sea.get('wave_direction'), sea.get('wave_period'),
                    sea.get('wind_wave_height'), sea.get('wind_wave_direction'), sea.get('wind_wave_period'),
                    sea.get('swell_wave_height'), sea.get('swell_wave_direction'), sea.get('swell_wave_period'),
                    sea.get('sea_surface_temperature'), weather.get('visibility'),
                    weather.get('precipitation'), weather.get('snowfall'), weather.get('temperature'),
                    weather.get('pressure_msl'), weather.get('weather_code'), weather.get('data_source'),
                    weather.get('valid_time') or f"{target_date}T{hour:02d}:00", now_str
                ))
                saved += 1

            print(f"{saved} records")
            total_saved += saved

        conn.commit()
        conn.close()
        self.generate_sailing_weather_actuals(target_date)
        print(f"  Total: {total_saved} records saved for {target_date}")
        return total_saved


if __name__ == '__main__':
    collector = ActualWeatherCollector()
    target = sys.argv[1] if len(sys.argv) > 1 else None
    n = collector.collect(target)
    print(f"\nDone: {n} records saved.")
