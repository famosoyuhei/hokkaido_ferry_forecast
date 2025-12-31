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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

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
        self.locations = {
            'wakkanai': {'lat': 45.415, 'lon': 141.673, 'name': '稚内'},
            'rishiri': {'lat': 45.180, 'lon': 141.240, 'name': '利尻'},
            'rebun': {'lat': 45.300, 'lon': 141.040, 'name': '礼文'}
        }

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

        conn.commit()
        conn.close()
        print("[OK] Forecast database initialized")

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
            report_datetime = latest.get('reportDatetime', datetime.now().isoformat())

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

                    # Process each time point
                    for i, time_define in enumerate(time_defines):
                        # Parse time string - handle both formats
                        if '+' in time_define or 'Z' in time_define:
                            time_str = time_define.replace('Z', '+00:00')
                            forecast_time = datetime.fromisoformat(time_str)
                            # Convert to naive datetime (JST)
                            forecast_time = forecast_time.replace(tzinfo=None)
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

                        # Calculate hours ahead
                        hours_ahead = int((forecast_time - datetime.now()).total_seconds() / 3600)

                        forecast_record = {
                            'forecast_date': forecast_time.date().isoformat(),
                            'forecast_hour': forecast_time.hour,
                            'location': area_name,
                            'wind_speed_text': wind,
                            'wind_speed_min': wind_min,
                            'wind_speed_max': wind_max,
                            'wave_height_min': wave_min,
                            'wave_height_max': wave_max,
                            'weather_text': weather,
                            'pop': float(pop) if pop and pop != '' else None,
                            'jma_issued_at': report_datetime,
                            'collected_at': datetime.now().isoformat(),
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
            params = {
                'latitude': location['lat'],
                'longitude': location['lon'],
                'hourly': ['temperature_2m', 'windspeed_10m', 'winddirection_10m', 'visibility'],
                'forecast_days': 7,
                'timezone': 'Asia/Tokyo'
            }

            response = requests.get(self.openmeteo_url, params=params, timeout=30)

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            data = response.json()
            hourly = data.get('hourly', {})

            times = hourly.get('time', [])
            temps = hourly.get('temperature_2m', [])
            wind_speeds = hourly.get('windspeed_10m', [])
            wind_dirs = hourly.get('winddirection_10m', [])
            visibilities = hourly.get('visibility', [])

            forecasts = []

            for i, time_str in enumerate(times):
                forecast_time = datetime.fromisoformat(time_str)
                hours_ahead = int((forecast_time - datetime.now()).total_seconds() / 3600)

                # Skip past times
                if hours_ahead < 0:
                    continue

                forecast_record = {
                    'forecast_date': forecast_time.date().isoformat(),
                    'forecast_hour': forecast_time.hour,
                    'location': location['name'],
                    'temperature': temps[i] if i < len(temps) else None,
                    'visibility': visibilities[i] / 1000 if i < len(visibilities) else None,  # Convert to km
                    'wind_speed_numeric': wind_speeds[i] if i < len(wind_speeds) else None,
                    'wind_direction_deg': wind_dirs[i] if i < len(wind_dirs) else None,
                    'collected_at': datetime.now().isoformat(),
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
                    cursor.execute('''
                        UPDATE weather_forecast SET
                            wind_speed_text = ?,
                            wind_speed_min = ?,
                            wind_speed_max = ?,
                            wave_height_min = ?,
                            wave_height_max = ?,
                            weather_text = ?,
                            pop = ?,
                            temperature = ?,
                            visibility = ?,
                            wind_speed_numeric = ?,
                            wind_direction_deg = ?,
                            collected_at = ?
                        WHERE forecast_date = ? AND forecast_hour = ?
                        AND location = ? AND data_source = ?
                    ''', (
                        forecast.get('wind_speed_text'),
                        forecast.get('wind_speed_min'),
                        forecast.get('wind_speed_max'),
                        forecast.get('wave_height_min'),
                        forecast.get('wave_height_max'),
                        forecast.get('weather_text'),
                        forecast.get('pop'),
                        forecast.get('temperature'),
                        forecast.get('visibility'),
                        forecast.get('wind_speed_numeric'),
                        forecast.get('wind_direction_deg'),
                        forecast.get('collected_at'),
                        forecast.get('forecast_date'),
                        forecast.get('forecast_hour'),
                        forecast.get('location'),
                        forecast.get('data_source')
                    ))
                else:
                    # Insert new
                    cursor.execute('''
                        INSERT INTO weather_forecast (
                            forecast_date, forecast_hour, location,
                            wind_speed_text, wind_speed_min, wind_speed_max,
                            wave_height_min, wave_height_max,
                            weather_text, pop,
                            temperature, visibility,
                            wind_speed_numeric, wind_direction_deg,
                            jma_issued_at, collected_at,
                            forecast_horizon, data_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        forecast.get('forecast_date'),
                        forecast.get('forecast_hour'),
                        forecast.get('location'),
                        forecast.get('wind_speed_text'),
                        forecast.get('wind_speed_min'),
                        forecast.get('wind_speed_max'),
                        forecast.get('wave_height_min'),
                        forecast.get('wave_height_max'),
                        forecast.get('weather_text'),
                        forecast.get('pop'),
                        forecast.get('temperature'),
                        forecast.get('visibility'),
                        forecast.get('wind_speed_numeric'),
                        forecast.get('wind_direction_deg'),
                        forecast.get('jma_issued_at'),
                        forecast.get('collected_at'),
                        forecast.get('forecast_horizon'),
                        forecast.get('data_source')
                    ))

                saved += 1

            except Exception as e:
                print(f"[WARNING] Failed to save forecast record: {e}")

        conn.commit()
        conn.close()

        print(f"[OK] Saved {saved} forecast records to database")
        return saved

    def calculate_cancellation_risk(self, wind_speed: float, wave_height: float,
                                    visibility: Optional[float] = None) -> Tuple[str, float, List[str]]:
        """Calculate cancellation risk based on weather conditions"""

        risk_score = 0
        risk_factors = []

        # Wind speed risk (improved scale)
        # Extreme winds alone warrant HIGH risk
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

        # Wave height risk
        if wave_height >= 4.0:
            risk_score += 40
            risk_factors.append(f"Very high waves ({wave_height:.1f} m)")
        elif wave_height >= 3.0:
            risk_score += 30
            risk_factors.append(f"High waves ({wave_height:.1f} m)")
        elif wave_height >= 2.0:
            risk_score += 15
            risk_factors.append(f"Moderate waves ({wave_height:.1f} m)")

        # Visibility risk
        if visibility is not None:
            if visibility < 1.0:
                risk_score += 20
                risk_factors.append(f"Very poor visibility ({visibility:.1f} km)")
            elif visibility < 3.0:
                risk_score += 10
                risk_factors.append(f"Poor visibility ({visibility:.1f} km)")

        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        elif risk_score >= 20:
            risk_level = "LOW"
        else:
            risk_level = "MINIMAL"

        return risk_level, risk_score, risk_factors

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
            WHERE forecast_date >= date('now')
            GROUP BY forecast_date, forecast_hour, location
            HAVING wind_speed IS NOT NULL OR wave_height IS NOT NULL
            ORDER BY forecast_date, forecast_hour
        ''')

        forecasts = cursor.fetchall()
        generated = 0

        ferry_routes = [
            'wakkanai_oshidomari', 'wakkanai_kafuka',
            'oshidomari_wakkanai', 'kafuka_wakkanai',
            'oshidomari_kafuka', 'kafuka_oshidomari'
        ]

        for forecast_date, forecast_hour, location, wind_speed, wave_height, visibility, temperature in forecasts:
            if wind_speed is None and wave_height is None:
                continue

            # Use defaults if data is missing
            wind_speed = wind_speed if wind_speed is not None else 10.0
            wave_height = wave_height if wave_height is not None else 1.5

            # Calculate risk
            risk_level, risk_score, risk_factors = self.calculate_cancellation_risk(
                wind_speed, wave_height, visibility
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
            horizon_days = (datetime.fromisoformat(forecast_date) - datetime.now()).days
            confidence = max(0.5, 1.0 - (horizon_days * 0.07))

            # Save forecast for each route
            for route in ferry_routes:
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
                        action, confidence, datetime.now().isoformat()
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
        ''', (datetime.now().isoformat(), data_source, status, records, error))

        conn.commit()
        conn.close()

    def run_full_collection(self):
        """Run complete forecast collection process"""

        print("=" * 80)
        print("WEATHER FORECAST COLLECTION - JMA + OPEN-METEO INTEGRATION")
        print(f"Collection time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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

        print("\n" + "=" * 80)
        print(f"[SUCCESS] Collection completed")
        print(f"  Weather forecasts saved: {total_saved}")
        print(f"  Cancellation forecasts generated: {risk_count}")
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
