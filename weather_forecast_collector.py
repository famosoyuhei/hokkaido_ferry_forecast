#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Weather Forecast Collector with JMA API Integration
Collects 7-day weather forecasts for ferry cancellation prediction
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import sqlite3
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')
from jst_utils import now_jst, today_jst_str, jst_isoformat, get_active_routes_on
from flight_timetable_utils import (
    get_active_flights_on, crosswind_component, calculate_flight_risk,
    get_rishiri_weather_hour,
)

class WeatherForecastCollector:
    """Integrated weather forecast collector using JMA + Open-Meteo APIs"""

    def __init__(self):
        # JMA API configuration
        self.jma_base_url = "https://www.jma.go.jp/bosai/forecast/data/forecast"
        self.jma_area_codes = {
            'wakkanai_soya': '011000',      # Wakkanai/Soya region
            'rishiri_rebun': '011000'       # Rishiri/Rebun (same area)
        }

        # Open-Meteo configuration
        self.openmeteo_url = "https://api.open-meteo.com/v1/forecast"
        self.openmeteo_marine_url = "https://marine-api.open-meteo.com/v1/marine"
        self.locations = {
            'wakkanai': {'lat': 45.415, 'lon': 141.673, 'name': '稚内'},
            'oshidomari': {'lat': 45.200, 'lon': 141.216, 'name': '鴛泊'},
            'kutsugata': {'lat': 45.393, 'lon': 141.107, 'name': '沓形'},
            'kafuka': {'lat': 45.298, 'lon': 141.036, 'name': '香深'}
        }
        self.port_location_names = {key: value['name'] for key, value in self.locations.items()}

        # Database - use volume path if available
        import os
        # Support both RAILWAY_VOLUME_MOUNT_PATH and RAILWAY_VOLUME_MOUNT
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
        self.db_file = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.init_database()

        # Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def init_database(self):
        """Initialize forecast database"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Weather forecast table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_forecast (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_date DATE,
                forecast_hour INTEGER,
                location TEXT,

                -- JMA data
                wind_speed_text TEXT,
                wind_speed_min REAL,
                wind_speed_max REAL,
                wind_direction TEXT,
                wave_height_min REAL,
                wave_height_max REAL,
                weather_code TEXT,
                weather_text TEXT,
                pop REAL,
                reliability TEXT,

                -- Open-Meteo data
                temperature REAL,
                visibility REAL,
                wind_speed_numeric REAL,
                wind_direction_deg REAL,

                -- Metadata
                jma_issued_at TEXT,
                collected_at TEXT,
                forecast_horizon INTEGER,
                data_source TEXT
            )
        ''')
        self._add_missing_columns(cursor, 'weather_forecast', {
            'wind_gusts': 'REAL',
            'precipitation': 'REAL',
            'snowfall': 'REAL',
            'pressure_msl': 'REAL',
            'source_time': 'TEXT',
            'valid_time': 'TEXT',
            'wave_direction': 'REAL',
            'wave_period': 'REAL',
            'wind_wave_height': 'REAL',
            'wind_wave_direction': 'REAL',
            'wind_wave_period': 'REAL',
            'swell_wave_height': 'REAL',
            'swell_wave_direction': 'REAL',
            'swell_wave_period': 'REAL',
            'sea_surface_temperature': 'REAL'
        })

        # Cancellation risk forecast table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cancellation_forecast (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_for_date DATE,
                forecast_hour INTEGER,
                route TEXT,

                risk_level TEXT,
                risk_score REAL,
                risk_factors TEXT,

                wind_forecast REAL,
                wave_forecast REAL,
                visibility_forecast REAL,
                temperature_forecast REAL,

                recommended_action TEXT,
                confidence REAL,

                generated_at TEXT
            )
        ''')

        # Sailing-time weather assignment table. Each scheduled sailing is expanded
        # into departure/destination/via ports and hourly records across the sailing window.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sailing_weather_forecast (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_date TEXT NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                port_role TEXT NOT NULL,
                port_key TEXT NOT NULL,
                port_name TEXT,
                forecast_hour INTEGER NOT NULL,
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
                weather_code TEXT,

                source TEXT,
                source_time TEXT,
                valid_time TEXT,
                assigned_at TEXT,

                UNIQUE(service_date, route, departure_time, port_role, port_key, forecast_hour)
            )
        ''')
        self._add_missing_columns(cursor, 'sailing_weather_forecast', {
            'window_start_time': 'TEXT',
            'window_end_time': 'TEXT'
        })

        # Collection log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forecast_collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                data_source TEXT,
                status TEXT,
                records_added INTEGER,
                error_message TEXT
            )
        ''')

        # 飛行機欠航リスク予報テーブル（利尻空港発着便）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flight_cancellation_forecast (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_for_date DATE NOT NULL,
                forecast_hour INTEGER NOT NULL,
                route_key TEXT NOT NULL,
                flight_no TEXT,
                airline TEXT,
                aircraft TEXT,
                rishiri_time TEXT,
                rishiri_role TEXT,
                risk_level TEXT NOT NULL,
                risk_score REAL NOT NULL,
                risk_factors TEXT,
                wind_speed REAL,
                wind_direction REAL,
                crosswind_component REAL,
                visibility REAL,
                generated_at TEXT NOT NULL,
                UNIQUE(forecast_for_date, forecast_hour, route_key, flight_no)
            )
        ''')

        conn.commit()
        conn.close()
        print("[OK] Forecast database initialized")

    def _add_missing_columns(self, cursor, table: str, columns: Dict[str, str]):
        """Add backward-compatible columns to an existing SQLite table."""

        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for column, column_type in columns.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def _snowfall_mm(self, value):
        """Normalize Open-Meteo snowfall from cm to mm."""

        return value * 10 if value is not None else None

    def _get_json_with_retry(self, url: str, params: Dict, timeout: int = 30, attempts: int = 3):
        """Fetch JSON with short retries for API throttling or transient gateway errors."""

        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(url, params=params, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                last_error = Exception(f"HTTP {response.status_code}")
                if response.status_code not in (429, 502, 503, 504):
                    break
            except Exception as e:
                last_error = e

            if attempt < attempts:
                time.sleep(2 * attempt)

        raise last_error

    def parse_wind_speed(self, wind_text: str) -> Tuple[float, float]:
        """Parse JMA wind speed text to numeric range"""

        wind_patterns = {
            '非常に強く': (25.0, 30.0),
            '強く': (20.0, 25.0),
            'やや強く': (15.0, 20.0),
            '強い': (20.0, 25.0),
            'やや強い': (15.0, 20.0)
        }

        # Default moderate wind
        default = (10.0, 15.0)

        if not wind_text:
            return default

        for pattern, (min_speed, max_speed) in wind_patterns.items():
            if pattern in wind_text:
                return (min_speed, max_speed)

        # If no strong wind indicator, assume light to moderate
        return (5.0, 10.0)

    def parse_wave_height(self, wave_text: str) -> Tuple[float, float]:
        """Parse JMA wave height text to numeric range"""

        if not wave_text:
            return (1.0, 2.0)

        # Extract numbers from text like "1.5 メートル" or "1から2メートル"
        numbers = re.findall(r'(\d+\.?\d*)', wave_text)

        if len(numbers) >= 2:
            # Range like "1から2メートル"
            return (float(numbers[0]), float(numbers[1]))
        elif len(numbers) == 1:
            # Single value like "1.5メートル"
            height = float(numbers[0])
            return (height, height)
        else:
            return (1.0, 2.0)

    def collect_jma_forecast(self, area_code: str = '011000') -> List[Dict]:
        """Collect JMA weather forecast"""

        print(f"\n[INFO] Collecting JMA forecast for area {area_code}")

        try:
            url = f"{self.jma_base_url}/{area_code}.json"
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            data = response.json()
            forecasts = []

            # Get the latest forecast (first element is most recent)
            if not data or len(data) == 0:
                raise Exception("No forecast data available")

            latest = data[0]
            publishing_office = latest.get('publishingOffice', 'Unknown')
            report_datetime = latest.get('reportDatetime', jst_isoformat())

            print(f"[OK] Forecast from: {publishing_office}")
            print(f"[OK] Issued at: {report_datetime}")

            # Parse time series data
            time_series = latest.get('timeSeries', [])

            for ts_idx, ts in enumerate(time_series):
                areas = ts.get('areas', [])
                time_defines = ts.get('timeDefines', [])

                for area in areas:
                    area_name = area.get('area', {}).get('name', 'Unknown')

                    # Extract weather elements
                    weathers = area.get('weathers', [])
                    winds = area.get('winds', [])
                    waves = area.get('waves', [])
                    pops = area.get('pops', [])  # Probability of precipitation
                    temps = area.get('temps', [])

                    # Naive reference time (JST) for timedelta comparisons
                    _now_naive = now_jst().replace(tzinfo=None)

                    # Process each time point
                    for i, time_define in enumerate(time_defines):
                        # Parse time string — always produce a naive datetime
                        if '+' in time_define or 'Z' in time_define:
                            time_str = time_define.replace('Z', '+00:00')
                            _aware = datetime.fromisoformat(time_str)
                            # Convert aware UTC/+09:00 → naive JST equivalent
                            from datetime import timezone as _tz
                            utc_offset = _aware.utcoffset()
                            if utc_offset is not None:
                                _aware_utc = _aware - utc_offset
                                import pytz as _pytz
                                forecast_time = _aware_utc.replace(tzinfo=_tz.utc).astimezone(
                                    _pytz.timezone('Asia/Tokyo')
                                ).replace(tzinfo=None)
                            else:
                                forecast_time = _aware.replace(tzinfo=None)
                        else:
                            forecast_time = datetime.fromisoformat(time_define)

                        # Get data for this time point
                        weather = weathers[i] if i < len(weathers) else None
                        wind = winds[i] if i < len(winds) else None
                        wave = waves[i] if i < len(waves) else None
                        pop = pops[i] if i < len(pops) else None
                        temp = temps[i] if i < len(temps) else None

                        # Parse wind speed
                        wind_min, wind_max = self.parse_wind_speed(wind) if wind else (10.0, 15.0)

                        # Parse wave height
                        wave_min, wave_max = self.parse_wave_height(wave) if wave else (1.0, 2.0)

                        # Calculate hours ahead (both naive)
                        hours_ahead = int((forecast_time - _now_naive).total_seconds() / 3600)

                        forecast_record = {
                            'forecast_date': forecast_time.date().isoformat(),
                            'forecast_hour': forecast_time.hour,
                            'location': area_name,
                            'valid_time': forecast_time.isoformat(),
                            'wind_speed_text': wind,
                            'wind_speed_min': wind_min,
                            'wind_speed_max': wind_max,
                            'wave_height_min': wave_min,
                            'wave_height_max': wave_max,
                            'weather_text': weather,
                            'pop': float(pop) if pop and pop != '' else None,
                            'jma_issued_at': report_datetime,
                            'source_time': report_datetime,
                            'collected_at': jst_isoformat(),
                            'forecast_horizon': hours_ahead,
                            'data_source': 'JMA'
                        }

                        forecasts.append(forecast_record)

                        print(f"  [{forecast_time.date()} {forecast_time.hour:02d}:00] "
                              f"Wind: {wind_min}-{wind_max}m/s, Wave: {wave_min}-{wave_max}m, "
                              f"Weather: {weather if weather else 'N/A'}")

            print(f"[OK] Collected {len(forecasts)} JMA forecast records")
            return forecasts

        except Exception as e:
            print(f"[ERROR] JMA forecast collection failed: {e}")
            self.log_collection('JMA', 'FAILED', 0, str(e))
            return []

    def collect_openmeteo_forecast(self, location_key: str = 'wakkanai') -> List[Dict]:
        """Collect Open-Meteo forecast data"""

        location = self.locations.get(location_key)
        if not location:
            print(f"[ERROR] Unknown location: {location_key}")
            return []

        print(f"\n[INFO] Collecting Open-Meteo forecast for {location['name']}")

        try:
            # Fetch weather forecast variables required by the AI employee rules.
            hourly_weather = [
                'temperature_2m',
                'precipitation',
                'snowfall',
                'weather_code',
                'pressure_msl',
                'wind_speed_10m',
                'wind_direction_10m',
                'wind_gusts_10m',
                'visibility'
            ]
            params = {
                'latitude': location['lat'],
                'longitude': location['lon'],
                'hourly': hourly_weather,
                'forecast_days': 7,
                'timezone': 'Asia/Tokyo',
                'wind_speed_unit': 'ms'
            }
            data = self._get_json_with_retry(self.openmeteo_url, params=params, timeout=30)
            hourly = data.get('hourly', {})

            times = hourly.get('time', [])
            temps = hourly.get('temperature_2m', [])
            precipitations = hourly.get('precipitation', [])
            snowfalls = hourly.get('snowfall', [])
            weather_codes = hourly.get('weather_code', [])
            pressures = hourly.get('pressure_msl', [])
            wind_speeds = hourly.get('wind_speed_10m', [])
            wind_dirs = hourly.get('wind_direction_10m', [])
            wind_gusts = hourly.get('wind_gusts_10m', [])
            visibilities = hourly.get('visibility', [])

            # Fetch marine variables from Marine API (separate endpoint)
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
            marine_params = {
                'latitude': location['lat'],
                'longitude': location['lon'],
                'hourly': hourly_marine,
                'forecast_days': 7,
                'timezone': 'Asia/Tokyo'
            }
            marine_by_time = {}
            try:
                marine_data = self._get_json_with_retry(self.openmeteo_marine_url, params=marine_params, timeout=30)
                marine_hourly = marine_data.get('hourly', {})
                marine_times = marine_hourly.get('time', [])
                for idx, marine_time in enumerate(marine_times):
                    marine_by_time[marine_time] = {
                        key: values[idx] if idx < len(values) else None
                        for key, values in marine_hourly.items()
                        if key != 'time'
                    }
                print(f"[OK] Marine API: {len(marine_by_time)} marine records")
            except Exception as e:
                print(f"[WARNING] Marine API failed, marine variables unavailable: {e}")

            _now_naive = now_jst().replace(tzinfo=None)
            forecasts = []
            for i, time_str in enumerate(times):
                forecast_time = datetime.fromisoformat(time_str)
                # Open-Meteo times are naive ISO strings — compare against naive JST
                hours_ahead = int((forecast_time - _now_naive).total_seconds() / 3600)
                if hours_ahead < 0:
                    continue

                # Use real marine values; fall back to None (not defaults)
                marine = marine_by_time.get(time_str, {})
                wave_height = marine.get('wave_height')

                forecast_record = {
                    'forecast_date': forecast_time.date().isoformat(),
                    'forecast_hour': forecast_time.hour,
                    'location': location['name'],
                    'valid_time': time_str,
                    'temperature': temps[i] if i < len(temps) else None,
                    'precipitation': precipitations[i] if i < len(precipitations) else None,
                    'snowfall': self._snowfall_mm(snowfalls[i]) if i < len(snowfalls) else None,
                    'weather_code': weather_codes[i] if i < len(weather_codes) else None,
                    'pressure_msl': pressures[i] if i < len(pressures) else None,
                    'visibility': visibilities[i] / 1000 if i < len(visibilities) else None,
                    'wind_speed_numeric': wind_speeds[i] if i < len(wind_speeds) else None,
                    'wind_direction_deg': wind_dirs[i] if i < len(wind_dirs) else None,
                    'wind_gusts': wind_gusts[i] if i < len(wind_gusts) else None,
                    'wave_height_min': wave_height,
                    'wave_height_max': wave_height,
                    'wave_direction': marine.get('wave_direction'),
                    'wave_period': marine.get('wave_period'),
                    'wind_wave_height': marine.get('wind_wave_height'),
                    'wind_wave_direction': marine.get('wind_wave_direction'),
                    'wind_wave_period': marine.get('wind_wave_period'),
                    'swell_wave_height': marine.get('swell_wave_height'),
                    'swell_wave_direction': marine.get('swell_wave_direction'),
                    'swell_wave_period': marine.get('swell_wave_period'),
                    'sea_surface_temperature': marine.get('sea_surface_temperature'),
                    'collected_at': jst_isoformat(),
                    'source_time': jst_isoformat(),
                    'forecast_horizon': hours_ahead,
                    'data_source': 'Open-Meteo'
                }
                forecasts.append(forecast_record)

            print(f"[OK] Collected {len(forecasts)} Open-Meteo forecast records")
            return forecasts

        except Exception as e:
            print(f"[ERROR] Open-Meteo forecast collection failed: {e}")
            self.log_collection('Open-Meteo', 'FAILED', 0, str(e))
            return []

    def save_forecasts(self, forecasts: List[Dict]):
        """Save forecast data to database"""

        if not forecasts:
            return 0

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        saved = 0

        writable_columns = [
            'forecast_date', 'forecast_hour', 'location',
            'wind_speed_text', 'wind_speed_min', 'wind_speed_max',
            'wind_direction', 'wave_height_min', 'wave_height_max',
            'weather_code', 'weather_text', 'pop', 'reliability',
            'temperature', 'visibility', 'wind_speed_numeric',
            'wind_direction_deg', 'wind_gusts', 'precipitation',
            'snowfall', 'pressure_msl', 'source_time', 'valid_time',
            'wave_direction', 'wave_period', 'wind_wave_height',
            'wind_wave_direction', 'wind_wave_period', 'swell_wave_height',
            'swell_wave_direction', 'swell_wave_period',
            'sea_surface_temperature', 'jma_issued_at', 'collected_at',
            'forecast_horizon', 'data_source'
        ]

        for forecast in forecasts:
            try:
                # Check if record already exists
                cursor.execute('''
                    SELECT id FROM weather_forecast
                    WHERE forecast_date = ? AND forecast_hour = ?
                    AND location = ? AND data_source = ?
                ''', (
                    forecast.get('forecast_date'),
                    forecast.get('forecast_hour'),
                    forecast.get('location'),
                    forecast.get('data_source')
                ))

                if cursor.fetchone():
                    # Update existing
                    update_columns = [
                        column for column in writable_columns
                        if column not in ('forecast_date', 'forecast_hour', 'location', 'data_source')
                    ]
                    assignments = ', '.join(f'{column} = ?' for column in update_columns)
                    cursor.execute('''
                        UPDATE weather_forecast SET
                            __ASSIGNMENTS__
                        WHERE forecast_date = ? AND forecast_hour = ?
                        AND location = ? AND data_source = ?
                    '''.replace('__ASSIGNMENTS__', assignments), (
                        *[forecast.get(column) for column in update_columns],
                        forecast.get('forecast_date'),
                        forecast.get('forecast_hour'),
                        forecast.get('location'),
                        forecast.get('data_source')
                    ))
                else:
                    # Insert new
                    placeholders = ', '.join('?' for _ in writable_columns)
                    column_names = ', '.join(writable_columns)
                    cursor.execute('''
                        INSERT INTO weather_forecast (__COLUMNS__)
                        VALUES (__PLACEHOLDERS__)
                    '''.replace('__COLUMNS__', column_names).replace('__PLACEHOLDERS__', placeholders),
                    tuple(forecast.get(column) for column in writable_columns))

                saved += 1

            except Exception as e:
                print(f"[WARNING] Failed to save forecast record: {e}")

        conn.commit()
        conn.close()

        print(f"[OK] Saved {saved} forecast records to database")
        return saved

    def calculate_cancellation_risk(self, wind_speed: float, wave_height: Optional[float],
                                    visibility: Optional[float] = None,
                                    forecast_date: Optional[str] = None) -> Tuple[str, float, List[str]]:
        """
        Calculate cancellation risk based on weather conditions with seasonal adjustment

        Args:
            wind_speed: Wind speed in m/s
            wave_height: Wave height in meters
            visibility: Visibility in km (optional)
            forecast_date: Date string (optional, for seasonal adjustment)
        """

        risk_score = 0
        risk_factors = []

        # Determine season (winter = Dec-Mar)
        is_winter = False
        if forecast_date:
            try:
                is_winter = int(forecast_date[5:7]) in (12, 1, 2, 3)
            except (ValueError, IndexError):
                pass

        if is_winter:
            # ---- Winter scoring (single branch — no double counting) ----
            # Wind: starts at 8 m/s; same high-end table as summer
            if wind_speed >= 35:
                risk_score += 70
                risk_factors.append(f"Extreme wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 30:
                risk_score += 60
                risk_factors.append(f"Very dangerous wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 25:
                risk_score += 50
                risk_factors.append(f"Very strong wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 20:
                risk_score += 35
                risk_factors.append(f"Strong wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 15:
                risk_score += 20
                risk_factors.append(f"Moderate wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 12:
                risk_score += 15          # winter-only threshold (< 15 m/s tier)
                risk_factors.append(f"Winter moderate wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 8:
                risk_score += 10          # winter-only threshold
                risk_factors.append(f"Winter light wind ({wind_speed:.1f} m/s)")

            # Wave: extended thresholds for winter sea state
            if wave_height is not None:
                if wave_height >= 4.0:
                    risk_score += 40
                    risk_factors.append(f"Very high waves ({wave_height:.1f} m)")
                elif wave_height >= 3.0:
                    risk_score += 35      # winter: higher than summer's 30
                    risk_factors.append(f"High waves ({wave_height:.1f} m) [winter]")
                elif wave_height >= 2.0:
                    risk_score += 20      # winter: higher than summer's 15
                    risk_factors.append(f"Moderate-high waves ({wave_height:.1f} m) [winter]")
                elif wave_height >= 1.5:
                    risk_score += 10      # winter-only threshold
                    risk_factors.append(f"Winter swell ({wave_height:.1f} m)")

            # Apply ×1.2 multiplier (wind + wave only)
            risk_score = int(risk_score * 1.2)

            # Visibility applied after multiplier but before level determination
            if visibility is not None:
                if visibility < 1.0:
                    risk_score += 20
                    risk_factors.append(f"Very poor visibility ({visibility:.1f} km)")
                elif visibility < 3.0:
                    risk_score += 10
                    risk_factors.append(f"Poor visibility ({visibility:.1f} km)")

            if risk_score >= 60:
                risk_level = "HIGH"
            elif risk_score >= 35:
                risk_level = "MEDIUM"
            elif risk_score >= 15:
                risk_level = "LOW"
            else:
                risk_level = "MINIMAL"

        else:
            # ---- Summer / standard scoring ----
            if wind_speed >= 35:
                risk_score += 70
                risk_factors.append(f"Extreme wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 30:
                risk_score += 60
                risk_factors.append(f"Very dangerous wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 25:
                risk_score += 50
                risk_factors.append(f"Very strong wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 20:
                risk_score += 35
                risk_factors.append(f"Strong wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 15:
                risk_score += 20
                risk_factors.append(f"Moderate wind ({wind_speed:.1f} m/s)")
            elif wind_speed >= 10:
                risk_score += 10

            if wave_height is not None:
                if wave_height >= 4.0:
                    risk_score += 40
                    risk_factors.append(f"Very high waves ({wave_height:.1f} m)")
                elif wave_height >= 3.0:
                    risk_score += 30
                    risk_factors.append(f"High waves ({wave_height:.1f} m)")
                elif wave_height >= 2.0:
                    risk_score += 15
                    risk_factors.append(f"Moderate-high waves ({wave_height:.1f} m)")

            # Visibility applied before level determination
            if visibility is not None:
                if visibility < 1.0:
                    risk_score += 20
                    risk_factors.append(f"Very poor visibility ({visibility:.1f} km)")
                elif visibility < 3.0:
                    risk_score += 10
                    risk_factors.append(f"Poor visibility ({visibility:.1f} km)")

            if risk_score >= 70:
                risk_level = "HIGH"
            elif risk_score >= 40:
                risk_level = "MEDIUM"
            elif risk_score >= 20:
                risk_level = "LOW"
            else:
                risk_level = "MINIMAL"

        return risk_level, risk_score, risk_factors

    def _load_timetable_for_year(self, year: int) -> Dict:
        """
        指定年の時刻表 JSON をロードする。
        当該年の JSON が存在しない場合は最新年の JSON にフォールバックする。
        年が変わったら heartland_{year}_timetable.json を追加するだけでよい。
        """
        ref_dir = Path(__file__).parent / 'skills' / 'ferry-cancellation-research' / 'references'
        path = ref_dir / f'heartland_{year}_timetable.json'
        if not path.exists():
            # フォールバック: 最新の heartland_????_timetable.json を使う
            candidates = sorted(ref_dir.glob('heartland_????_timetable.json'), reverse=True)
            if not candidates:
                return {}
            path = candidates[0]
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def _scheduled_sailings_for_date(self, service_date: str) -> List[Dict]:
        target = datetime.fromisoformat(service_date).date()
        year = int(service_date[:4])
        timetable = self._load_timetable_for_year(year)
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

    def _route_ports(self, route: str, via_oshidomari: bool = False) -> List[Tuple[str, str]]:
        departure, arrival = route.split('_', 1)
        ports = [('departure', departure)]
        if via_oshidomari:
            ports.append(('via', 'oshidomari'))
        ports.append(('arrival', arrival))
        return ports

    def _hours_for_window(self, start: datetime, end: datetime) -> List[int]:
        hours = []
        current = start.replace(minute=0, second=0, microsecond=0)
        while current <= end:
            hours.append(current.hour)
            current += timedelta(hours=1)
        return sorted(set(hours))

    def _role_window(self, service_date: str, route: str, departure_time: str, arrival_time: str, role: str) -> Tuple[datetime, datetime]:
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

    def generate_sailing_weather_forecasts(self):
        """Assign hourly port forecasts to each scheduled sailing's ports and sailing window."""

        print("\n[INFO] Generating sailing-time weather assignments")
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        generated = 0
        start_date = datetime.fromisoformat(today_jst_str()).date()
        service_dates = [(start_date + timedelta(days=offset)).isoformat() for offset in range(7)]

        for service_date in service_dates:
            for sailing in self._scheduled_sailings_for_date(service_date):
                route = sailing['route']
                departure_time = sailing['departure_time']
                arrival_time = sailing['arrival_time']
                via_oshidomari = sailing['via_oshidomari']
                for role, port_key in self._route_ports(route, via_oshidomari):
                    port_name = self.port_location_names.get(port_key)
                    if port_name is None:
                        print(f"[WARNING] Unknown port key for sailing assignment: {port_key}")
                        continue

                    window_start, window_end = self._role_window(
                        service_date, route, departure_time, arrival_time, role
                    )
                    hours = self._hours_for_window(window_start, window_end)
                    reference_time = window_start.strftime('%H:%M') if role != 'via' else (
                        window_start + ((window_end - window_start) / 2)
                    ).strftime('%H:%M')
                    window_start_time = window_start.strftime('%H:%M')
                    window_end_time = window_end.strftime('%H:%M')
                    minutes_from_departure = self._minutes_from_departure(
                        service_date, departure_time, reference_time
                    )

                    for forecast_hour in hours:
                        cursor.execute('''
                            SELECT
                                COALESCE(wind_speed_numeric, wind_speed_max) AS wind_speed,
                                wind_direction_deg,
                                wind_gusts,
                                wave_height_max,
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
                                source_time,
                                valid_time
                            FROM weather_forecast
                            WHERE forecast_date = ?
                              AND forecast_hour = ?
                              AND location = ?
                            ORDER BY
                                CASE data_source WHEN 'Open-Meteo' THEN 0 ELSE 1 END,
                                collected_at DESC
                            LIMIT 1
                        ''', (service_date, forecast_hour, port_name))
                        row = cursor.fetchone()
                        if not row:
                            continue

                        cursor.execute('''
                            INSERT OR REPLACE INTO sailing_weather_forecast (
                                service_date, route, departure_time, arrival_time,
                                port_role, port_key, port_name, forecast_hour,
                                scheduled_reference_time, window_start_time, window_end_time,
                                minutes_from_departure, via_oshidomari,
                                wind_speed, wind_direction, wind_gusts,
                                wave_height, wave_direction, wave_period,
                                wind_wave_height, swell_wave_height, visibility,
                                precipitation, snowfall, temperature, pressure_msl,
                                weather_code, source, source_time, valid_time, assigned_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            service_date, route, departure_time, arrival_time,
                            role, port_key, port_name, forecast_hour,
                            reference_time, window_start_time, window_end_time,
                            minutes_from_departure, int(via_oshidomari),
                            *row,
                            jst_isoformat()
                        ))
                        generated += 1

        conn.commit()
        conn.close()
        print(f"[OK] Generated {generated} sailing-time weather assignments")
        return generated

    def generate_cancellation_forecasts(self):
        """Generate cancellation risk forecasts from weather data"""

        print("\n[INFO] Generating cancellation risk forecasts")

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get forecast data grouped by date and hour
        cursor.execute('''
            SELECT
                forecast_date,
                forecast_hour,
                location,
                AVG(COALESCE(wind_speed_max, wind_speed_numeric)) as wind_speed,
                AVG(wave_height_max) as wave_height,
                AVG(visibility) as visibility,
                AVG(temperature) as temperature
            FROM weather_forecast
            WHERE forecast_date >= ?
            GROUP BY forecast_date, forecast_hour, location
            HAVING wind_speed IS NOT NULL OR wave_height IS NOT NULL
            ORDER BY forecast_date, forecast_hour
        ''', (today_jst_str(),))

        forecasts = cursor.fetchall()
        generated = 0

        # 日付ごとのアクティブ航路キャッシュ（時刻表 JSON から動的取得）
        # wakkanai_kutsugata / kutsugata_wakkanai は存在しない航路なので使わない。
        # 沓形-香深便（kutsugata_kafuka / kafuka_kutsugata）は 6/1〜9/30 のみ自動追加される。
        # 年が変わっても heartland_{year}_timetable.json を追加するだけで対応できる。
        _routes_cache: dict = {}

        for forecast_date, forecast_hour, location, wind_speed, wave_height, visibility, temperature in forecasts:
            if wind_speed is None and wave_height is None:
                continue

            # Use defaults if data is missing (wave_height stays None if unavailable)
            wind_speed = wind_speed if wind_speed is not None else 10.0
            wave_height = wave_height if wave_height is not None else None

            # Calculate risk (with seasonal adjustment)
            risk_level, risk_score, risk_factors = self.calculate_cancellation_risk(
                wind_speed, wave_height, visibility, forecast_date
            )

            # Determine recommended action
            if risk_level == "HIGH":
                action = "High cancellation risk - Consider alternative dates"
            elif risk_level == "MEDIUM":
                action = "Moderate risk - Monitor weather updates"
            elif risk_level == "LOW":
                action = "Low risk - Normal operations expected"
            else:
                action = "Minimal risk - Good conditions"

            # Calculate confidence based on forecast horizon
            # Confidence decreases with time
            # forecast_date is a naive date string; compare against naive today
            horizon_days = (datetime.fromisoformat(forecast_date) - datetime.fromisoformat(today_jst_str())).days
            confidence = max(0.5, 1.0 - (horizon_days * 0.07))

            # 当日の運航便を時刻表から動的取得（キャッシュ済み）
            if forecast_date not in _routes_cache:
                _routes_cache[forecast_date] = get_active_routes_on(forecast_date)
            active_routes = _routes_cache[forecast_date]

            # Save forecast for each route
            for route in active_routes:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO cancellation_forecast (
                            forecast_for_date, forecast_hour, route,
                            risk_level, risk_score, risk_factors,
                            wind_forecast, wave_forecast, visibility_forecast, temperature_forecast,
                            recommended_action, confidence, generated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        forecast_date, forecast_hour, route,
                        risk_level, risk_score, json.dumps(risk_factors),
                        wind_speed, wave_height, visibility, temperature,
                        action, confidence, jst_isoformat()
                    ))
                    generated += 1

                except Exception as e:
                    print(f"[WARNING] Failed to save cancellation forecast: {e}")

        conn.commit()
        conn.close()

        print(f"[OK] Generated {generated} cancellation risk forecasts")
        return generated

    def log_collection(self, data_source: str, status: str, records: int, error: Optional[str] = None):
        """Log collection attempt"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO forecast_collection_log (timestamp, data_source, status, records_added, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (jst_isoformat(), data_source, status, records, error))

        conn.commit()
        conn.close()

    def generate_flight_forecasts(self) -> int:
        """
        weather_forecast の鴛泊データを使って flight_cancellation_forecast を生成する。
        flight_timetable_utils の横風計算ロジックを適用し、利尻空港の飛行機欠航リスクを算出。
        """
        print("\n[INFO] Generating flight cancellation forecasts (Rishiri Airport)")

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        generated = 0
        now_str = jst_isoformat()

        # 今日から7日分の日付ループ
        from datetime import timedelta
        today = today_jst_str()
        dates = [
            (now_jst() + timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(8)
        ]

        for forecast_date in dates:
            flights = get_active_flights_on(forecast_date)
            if not flights:
                continue

            # 鴛泊（oshidomari）の時間別天気予報を取得（最新レコードを使用）
            cursor.execute('''
                SELECT forecast_hour,
                       AVG(COALESCE(wind_speed_max, wind_speed_numeric)) as wind_speed,
                       AVG(wind_direction_deg) as wind_dir,
                       AVG(visibility) as visibility
                FROM weather_forecast
                WHERE forecast_date = ?
                  AND location = 'oshidomari'
                  AND id IN (
                      SELECT MAX(id) FROM weather_forecast
                      WHERE forecast_date = ? AND location = 'oshidomari'
                      GROUP BY forecast_hour
                  )
                GROUP BY forecast_hour
                ORDER BY forecast_hour
            ''', (forecast_date, forecast_date))

            hourly_weather = {row[0]: row[1:] for row in cursor.fetchall()}

            # 各便のリスク計算
            for flight in flights:
                rishiri_hour = get_rishiri_weather_hour(flight['rishiri_time'])

                # ±1h で最悪ケースの気象を取得
                best_wind, best_dir, best_vis = None, None, None
                for h_offset in [0, -1, 1]:
                    h = rishiri_hour + h_offset
                    if h in hourly_weather:
                        w_spd, w_dir, vis = hourly_weather[h]
                        if w_spd is not None:
                            if best_wind is None or w_spd > best_wind:
                                best_wind = w_spd
                                best_dir = w_dir
                                best_vis = vis

                if best_wind is None:
                    continue  # 気象データなし → スキップ

                # forecast_hour は予報生成時刻（now_jst の時）
                forecast_hour = now_jst().hour

                # 横風成分を計算
                cw = crosswind_component(best_wind, best_dir) if best_dir is not None else None

                risk_level, risk_score, risk_factors = calculate_flight_risk(
                    best_wind, best_dir, best_vis, flight['aircraft']
                )

                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO flight_cancellation_forecast
                        (forecast_for_date, forecast_hour, route_key, flight_no, airline,
                         aircraft, rishiri_time, rishiri_role, risk_level, risk_score,
                         risk_factors, wind_speed, wind_direction, crosswind_component,
                         visibility, generated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        forecast_date, forecast_hour,
                        flight['route_key'], flight['flight_no'], flight['airline'],
                        flight['aircraft'], flight['rishiri_time'], flight['rishiri_role'],
                        risk_level, risk_score, str(risk_factors),
                        best_wind, best_dir, cw, best_vis, now_str,
                    ))
                    generated += 1
                except Exception as e:
                    print(f"  [WARNING] flight forecast insert error: {e}")

        conn.commit()
        conn.close()
        print(f"[OK] Generated {generated} flight cancellation forecasts")
        return generated

    def run_full_collection(self):
        """Run complete forecast collection process"""

        print("=" * 80)
        print("WEATHER FORECAST COLLECTION - JMA + OPEN-METEO INTEGRATION")
        print(f"Collection time: {now_jst().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        total_saved = 0

        # Collect JMA forecast
        jma_forecasts = self.collect_jma_forecast()
        if jma_forecasts:
            saved = self.save_forecasts(jma_forecasts)
            total_saved += saved
            self.log_collection('JMA', 'SUCCESS', saved)

        # Collect Open-Meteo forecasts for each location
        for location_key in self.locations.keys():
            openmeteo_forecasts = self.collect_openmeteo_forecast(location_key)
            if openmeteo_forecasts:
                saved = self.save_forecasts(openmeteo_forecasts)
                total_saved += saved
                self.log_collection('Open-Meteo', 'SUCCESS', saved)

        # Generate cancellation risk forecasts
        risk_count = self.generate_cancellation_forecasts()
        sailing_weather_count = self.generate_sailing_weather_forecasts()
        flight_count = self.generate_flight_forecasts()

        print("\n" + "=" * 80)
        print(f"[SUCCESS] Collection completed")
        print(f"  Weather forecasts saved: {total_saved}")
        print(f"  Cancellation forecasts generated: {risk_count}")
        print(f"  Sailing-time weather assignments generated: {sailing_weather_count}")
        print(f"  Flight forecasts generated: {flight_count}")
        print(f"  Database: {self.db_file}")
        print("=" * 80)

        return total_saved > 0

def main():
    """Main execution"""

    collector = WeatherForecastCollector()
    success = collector.run_full_collection()

    if success:
        print("\n✅ Weather forecast collection successful")
        print("   7-day ferry cancellation predictions are now available!")
    else:
        print("\n❌ Weather forecast collection failed")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
