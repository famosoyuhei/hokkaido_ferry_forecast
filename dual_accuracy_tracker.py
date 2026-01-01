#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual Accuracy Tracking System
1. Weather Forecast Accuracy (予報 vs AMeDAS実測)
2. Ferry Operation Forecast Accuracy (運航予報 vs 実運航)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import warnings
warnings.filterwarnings('ignore')

class DualAccuracyTracker:
    """Track both weather forecast and ferry operation forecast accuracy"""

    def __init__(self):
        import os
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
        self.db_file = os.path.join(data_dir, "ferry_weather_forecast.db")

        # AMeDAS observation points
        self.amedas_stations = {
            '稚内': {'station_id': '11001', 'name': 'Wakkanai'},
            '利尻': {'station_id': '11016', 'name': 'Rishiri'},
            '礼文': {'station_id': '11056', 'name': 'Rebun'},
        }

        self.init_accuracy_tables()

    def init_accuracy_tables(self):
        """Initialize dual accuracy tracking tables"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # 1. Weather Forecast Accuracy Table (気象予報精度)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_date DATE NOT NULL,
                observation_hour INTEGER NOT NULL,
                location TEXT NOT NULL,

                -- Forecast values (予報値)
                forecast_wind_speed REAL,
                forecast_wave_height REAL,
                forecast_visibility REAL,
                forecast_temperature REAL,

                -- Actual observed values (実測値 from AMeDAS)
                actual_wind_speed REAL,
                actual_wave_height REAL,
                actual_visibility REAL,
                actual_temperature REAL,

                -- Accuracy metrics (精度指標)
                wind_speed_error REAL,      -- 予報誤差 (m/s)
                wave_height_error REAL,     -- 波高誤差 (m)
                visibility_error REAL,      -- 視程誤差 (km)
                temperature_error REAL,     -- 気温誤差 (℃)

                wind_speed_error_pct REAL,  -- 相対誤差 (%)
                wave_height_error_pct REAL,

                -- Metadata
                forecast_generated_at TEXT,
                actual_collected_at TEXT NOT NULL,
                data_source TEXT,           -- AMeDAS, JMA Marine, etc.

                UNIQUE(observation_date, observation_hour, location)
            )
        ''')

        # 2. Ferry Operation Forecast Accuracy Table (運航予報精度)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_date DATE NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT NOT NULL,

                -- Forecast (予報)
                predicted_risk_level TEXT,      -- HIGH/MEDIUM/LOW/MINIMAL
                predicted_risk_score REAL,
                predicted_wind REAL,
                predicted_wave REAL,
                predicted_visibility REAL,

                -- Actual operation (実運航)
                actual_status TEXT,             -- OPERATED/CANCELLED/DELAYED
                cancellation_reason TEXT,

                -- Actual weather at operation time (運航時の実気象)
                actual_wind_speed REAL,
                actual_wave_height REAL,
                actual_visibility REAL,

                -- Accuracy evaluation (精度評価)
                correct_prediction BOOLEAN,     -- 正解したか
                prediction_type TEXT,           -- TP/TN/FP/FN

                -- TP: True Positive (HIGH予報 → 欠航) 的中
                -- TN: True Negative (LOW予報 → 運航) 的中
                -- FP: False Positive (HIGH予報 → 運航) 外れ（過剰警告）
                -- FN: False Negative (LOW予報 → 欠航) 外れ（警告不足）

                risk_appropriateness_score REAL, -- リスクレベルの妥当性スコア

                -- Metadata
                forecast_generated_at TEXT,
                actual_collected_at TEXT NOT NULL,

                UNIQUE(operation_date, route, departure_time)
            )
        ''')

        # 3. Daily Accuracy Summary (日次精度サマリー)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_accuracy_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date DATE NOT NULL UNIQUE,

                -- Weather forecast accuracy (気象予報精度)
                avg_wind_error REAL,
                avg_wave_error REAL,
                avg_temp_error REAL,
                weather_accuracy_score REAL,   -- 0-100点

                -- Operation forecast accuracy (運航予報精度)
                total_predictions INTEGER,
                correct_predictions INTEGER,
                accuracy_rate REAL,             -- 正解率
                precision REAL,                 -- 適合率
                recall REAL,                    -- 再現率
                f1_score REAL,                  -- F1スコア

                true_positives INTEGER,         -- 欠航的中
                true_negatives INTEGER,         -- 運航的中
                false_positives INTEGER,        -- 過剰警告
                false_negatives INTEGER,        -- 警告不足

                -- Metadata
                calculated_at TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

        print("[OK] Dual accuracy tracking tables initialized")

    def collect_amedas_data(self, date: str, location: str) -> Optional[Dict]:
        """
        Collect AMeDAS observation data for accuracy validation

        Args:
            date: Observation date (YYYY-MM-DD)
            location: Location name ('稚内', '利尻', '礼文')

        Returns:
            Dictionary with hourly weather observations
        """
        if location not in self.amedas_stations:
            print(f"[WARNING] Unknown location: {location}")
            return None

        station_id = self.amedas_stations[location]['station_id']

        # JMA AMeDAS API endpoint
        # Format: https://www.jma.go.jp/bosai/amedas/data/point/{station_id}/{date}.json
        date_obj = datetime.fromisoformat(date)
        date_str = date_obj.strftime('%Y%m%d')

        url = f"https://www.jma.go.jp/bosai/amedas/data/point/{station_id}/{date_str}.json"

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            print(f"[OK] Collected AMeDAS data for {location} on {date}")
            return data

        except Exception as e:
            print(f"[ERROR] Failed to collect AMeDAS data for {location}: {e}")
            return None

    def calculate_weather_accuracy(self, date: str) -> Dict:
        """
        Calculate weather forecast accuracy for a given date

        Compares forecast values with AMeDAS observations
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        results = {
            'date': date,
            'locations': {},
            'overall_accuracy': 0
        }

        for location in self.amedas_stations.keys():
            # Get forecast data
            cursor.execute('''
                SELECT forecast_hour,
                       AVG(COALESCE(wind_speed_max, wind_speed_numeric)) as wind,
                       AVG(wave_height_max) as wave,
                       AVG(temperature) as temp,
                       AVG(visibility) as vis
                FROM weather_forecast
                WHERE forecast_date = ?
                AND location = ?
                GROUP BY forecast_hour
            ''', (date, location))

            forecast_data = {}
            for row in cursor.fetchall():
                hour, wind, wave, temp, vis = row
                forecast_data[hour] = {
                    'wind': wind,
                    'wave': wave,
                    'temp': temp,
                    'visibility': vis
                }

            # Get AMeDAS actual data
            amedas_data = self.collect_amedas_data(date, location)

            if not amedas_data:
                continue

            # Compare and calculate errors
            errors = []
            for hour_str, obs in amedas_data.items():
                hour = int(hour_str.split(':')[0])

                if hour not in forecast_data:
                    continue

                forecast = forecast_data[hour]

                # Extract observed values from AMeDAS data structure
                # AMeDAS format: {"temp": [12.5, 0], "wind": [3.2, 0], ...}
                # [value, quality_flag]

                obs_wind = obs.get('wind', [None])[0] if 'wind' in obs else None
                obs_temp = obs.get('temp', [None])[0] if 'temp' in obs else None

                if obs_wind and forecast['wind']:
                    wind_error = abs(forecast['wind'] - obs_wind)
                    wind_error_pct = (wind_error / obs_wind * 100) if obs_wind > 0 else 0
                    errors.append(('wind', wind_error, wind_error_pct))

                    # Store in database
                    cursor.execute('''
                        INSERT OR REPLACE INTO weather_accuracy
                        (observation_date, observation_hour, location,
                         forecast_wind_speed, actual_wind_speed, wind_speed_error, wind_speed_error_pct,
                         actual_collected_at, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date, hour, location, forecast['wind'], obs_wind, wind_error, wind_error_pct,
                          datetime.now().isoformat(), 'AMeDAS'))

                if obs_temp and forecast['temp']:
                    temp_error = abs(forecast['temp'] - obs_temp)
                    errors.append(('temp', temp_error, 0))

            results['locations'][location] = {
                'samples': len(errors),
                'avg_wind_error': sum(e[1] for e in errors if e[0] == 'wind') / max(sum(1 for e in errors if e[0] == 'wind'), 1),
                'avg_temp_error': sum(e[1] for e in errors if e[0] == 'temp') / max(sum(1 for e in errors if e[0] == 'temp'), 1),
            }

        conn.commit()
        conn.close()

        return results

    def calculate_operation_accuracy(self, date: str) -> Dict:
        """
        Calculate ferry operation forecast accuracy

        Compares sailing risk predictions with actual operations
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get predictions from sailing_forecast
        cursor.execute('''
            SELECT route, departure_time, risk_level, risk_score,
                   wind_forecast, wave_forecast, visibility_forecast
            FROM sailing_forecast
            WHERE forecast_date = ?
        ''', (date,))

        predictions = cursor.fetchall()

        # Get actual operations from heartland_ferry_real_data.db
        # (We'll need to integrate this with improved_ferry_collector.py)

        results = {
            'date': date,
            'total_sailings': len(predictions),
            'evaluated': 0,
            'correct': 0,
            'accuracy': 0
        }

        conn.close()
        return results

if __name__ == "__main__":
    print("=" * 80)
    print("DUAL ACCURACY TRACKING SYSTEM")
    print("=" * 80)

    tracker = DualAccuracyTracker()

    # Calculate accuracy for yesterday
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

    print(f"\n[INFO] Calculating weather forecast accuracy for {yesterday}...")
    weather_accuracy = tracker.calculate_weather_accuracy(yesterday)

    print(f"\n[INFO] Calculating operation forecast accuracy for {yesterday}...")
    operation_accuracy = tracker.calculate_operation_accuracy(yesterday)

    print("\n[SUCCESS] Dual accuracy tracking completed")
