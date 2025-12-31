"""
Sailing-by-Sailing Forecast System
便ごとの欠航リスク予報システム

This module extends the daily forecast to provide predictions for each individual ferry sailing.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

class SailingForecastSystem:
    """便ごとの予報を生成・管理するシステム"""

    def __init__(self):
        # Use volume path if available
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
        self.db_file = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.init_tables()

    def init_tables(self):
        """Initialize ferry timetable and sailing forecast tables"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Ferry timetable master table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ferry_timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                season TEXT NOT NULL,
                season_start TEXT NOT NULL,
                season_end TEXT NOT NULL,
                active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(route, departure_time, season)
            )
        ''')

        # Sailing-by-sailing forecast table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sailing_forecast (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_date TEXT NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                risk_score REAL NOT NULL,
                wind_forecast REAL,
                wave_forecast REAL,
                visibility_forecast REAL,
                temperature_forecast REAL,
                risk_factors TEXT,
                recommended_action TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(forecast_date, route, departure_time)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sailing_forecast_date ON sailing_forecast(forecast_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sailing_forecast_route ON sailing_forecast(route)')

        conn.commit()
        conn.close()

        print("[OK] Sailing forecast tables initialized")

    def populate_timetable(self, start_year: Optional[int] = None, end_year: Optional[int] = None):
        """
        Populate ferry timetable with Heartland Ferry schedule data

        Args:
            start_year: Start year for timetable (default: current year)
            end_year: End year for timetable (default: current year + 1)
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Default to current year and next year
        if start_year is None:
            start_year = datetime.now().year
        if end_year is None:
            end_year = start_year + 1

        # ハートランドフェリー 基本ダイヤパターン（年度非依存）
        # 各年度分を自動生成します
        base_schedules = [
            # 稚内→鴛泊（利尻島）冬季・早春 (1/1-4/27)
            {
                'route': 'wakkanai_oshidomari',
                'sailings': [
                    ('06:55', '08:35'),
                    ('14:00', '15:40'),
                    ('17:30', '19:10'),
                ],
                'season_pattern': 'winter',
                'month_day_start': '01-01',
                'month_day_end': '04-27'
            },
            # 春・秋 (4/28-5/31)
            {
                'route': 'wakkanai_oshidomari',
                'sailings': [
                    ('06:45', '08:25'),
                    ('08:55', '10:35'),
                    ('10:10', '11:50'),
                    ('14:35', '16:15'),
                    ('16:40', '18:20'),
                ],
                'season_pattern': 'spring',
                'month_day_start': '04-28',
                'month_day_end': '05-31'
            },
            # 夏季 (6/1-9/30)
            {
                'route': 'wakkanai_oshidomari',
                'sailings': [
                    ('07:15', '08:55'),
                    ('08:25', '10:05'),
                    ('11:15', '12:55'),
                    ('12:05', '13:45'),
                    ('16:40', '18:20'),
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 秋 (10/1-10/31)
            {
                'route': 'wakkanai_oshidomari',
                'sailings': [
                    ('06:45', '08:25'),
                    ('08:55', '10:35'),
                    ('10:10', '11:50'),
                    ('14:35', '16:15'),
                    ('16:40', '18:20'),
                ],
                'season_pattern': 'autumn',
                'month_day_start': '10-01',
                'month_day_end': '10-31'
            },
            # 晩秋 (11/1-12/31)
            {
                'route': 'wakkanai_oshidomari',
                'sailings': [
                    ('06:55', '08:35'),
                    ('14:00', '15:40'),
                    ('17:30', '19:10'),
                ],
                'season_pattern': 'late_autumn',
                'month_day_start': '11-01',
                'month_day_end': '12-31'
            },

            # 稚内→香深（礼文島）冬季・早春 (1/1-4/27)
            {
                'route': 'wakkanai_kafuka',
                'sailings': [
                    ('06:35', '10:05'),
                    ('14:10', '17:40'),
                    ('17:05', '20:35'),
                ],
                'season_pattern': 'winter',
                'month_day_start': '01-01',
                'month_day_end': '04-27'
            },
            # 稚内→香深 春 (4/28-5/31)
            {
                'route': 'wakkanai_kafuka',
                'sailings': [
                    ('06:30', '10:00'),
                    ('08:55', '12:25'),  # 直行便
                    ('10:10', '13:40'),  # 利尻経由
                    ('14:45', '18:15'),
                    ('17:05', '20:35'),
                ],
                'season_pattern': 'spring',
                'month_day_start': '04-28',
                'month_day_end': '05-31'
            },
            # 稚内→香深 夏季 (6/1-9/30)
            {
                'route': 'wakkanai_kafuka',
                'sailings': [
                    ('06:30', '10:00'),
                    ('08:55', '12:25'),
                    ('10:30', '14:00'),
                    ('14:20', '17:50'),
                    ('14:50', '18:20'),
                    ('17:10', '20:40'),
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 稚内→香深 秋 (10/1-10/31)
            {
                'route': 'wakkanai_kafuka',
                'sailings': [
                    ('06:30', '10:00'),
                    ('08:55', '12:25'),
                    ('10:10', '13:40'),
                    ('14:45', '18:15'),
                    ('17:05', '20:35'),
                ],
                'season_pattern': 'autumn',
                'month_day_start': '10-01',
                'month_day_end': '10-31'
            },
            # 稚内→香深 晩秋 (11/1-12/31)
            {
                'route': 'wakkanai_kafuka',
                'sailings': [
                    ('06:35', '10:05'),
                    ('09:00', '12:30'),
                    ('14:10', '17:40'),
                    ('17:05', '20:35'),
                ],
                'season_pattern': 'late_autumn',
                'month_day_start': '11-01',
                'month_day_end': '12-31'
            },

            # 鴛泊→香深（利尻→礼文）冬季・早春 (1/1-4/27)
            {
                'route': 'oshidomari_kafuka',
                'sailings': [
                    ('16:00', '16:45'),
                ],
                'season_pattern': 'winter',
                'month_day_start': '01-01',
                'month_day_end': '04-27'
            },
            # 鴛泊→香深 春・秋 (4/28-5/31, 10/1-10/31)
            {
                'route': 'oshidomari_kafuka',
                'sailings': [
                    ('12:15', '13:00'),
                ],
                'season_pattern': 'spring',
                'month_day_start': '04-28',
                'month_day_end': '05-31'
            },
            {
                'route': 'oshidomari_kafuka',
                'sailings': [
                    ('12:15', '13:00'),
                ],
                'season_pattern': 'autumn',
                'month_day_start': '10-01',
                'month_day_end': '10-31'
            },
            # 鴛泊→香深 夏季 (6/1-9/30)
            {
                'route': 'oshidomari_kafuka',
                'sailings': [
                    ('09:30', '10:15'),
                    ('13:15', '14:00'),
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 鴛泊→香深 晩秋 (11/1-12/31)
            {
                'route': 'oshidomari_kafuka',
                'sailings': [
                    ('16:00', '16:45'),
                ],
                'season_pattern': 'late_autumn',
                'month_day_start': '11-01',
                'month_day_end': '12-31'
            },

            # 香深→鴛泊（礼文→利尻）冬季・早春 (1/1-4/27)
            {
                'route': 'kafuka_oshidomari',
                'sailings': [
                    ('16:25', '17:10'),
                ],
                'season_pattern': 'winter',
                'month_day_start': '01-01',
                'month_day_end': '04-27'
            },
            # 香深→鴛泊 春・秋 (4/28-5/31, 10/1-10/31)
            {
                'route': 'kafuka_oshidomari',
                'sailings': [
                    ('13:25', '14:10'),
                ],
                'season_pattern': 'spring',
                'month_day_start': '04-28',
                'month_day_end': '05-31'
            },
            {
                'route': 'kafuka_oshidomari',
                'sailings': [
                    ('13:25', '14:10'),
                ],
                'season_pattern': 'autumn',
                'month_day_start': '10-01',
                'month_day_end': '10-31'
            },
            # 香深→鴛泊 夏季 (6/1-9/30)
            {
                'route': 'kafuka_oshidomari',
                'sailings': [
                    ('10:40', '11:25'),
                    ('15:30', '16:15'),
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 香深→鴛泊 晩秋 (11/1-12/31)
            {
                'route': 'kafuka_oshidomari',
                'sailings': [
                    ('16:25', '17:10'),
                ],
                'season_pattern': 'late_autumn',
                'month_day_start': '11-01',
                'month_day_end': '12-31'
            },

            # 鴛泊→稚内（利尻島→稚内）冬季・早春 (1/1-4/27)
            {
                'route': 'oshidomari_wakkanai',
                'sailings': [
                    ('09:05', '10:45'),
                    ('14:00', '15:40'),
                    ('17:30', '19:10'),
                ],
                'season_pattern': 'winter',
                'month_day_start': '01-01',
                'month_day_end': '04-27'
            },
            # 鴛泊→稚内 春・秋 (4/28-5/31, 10/1-10/31)
            {
                'route': 'oshidomari_wakkanai',
                'sailings': [
                    ('08:55', '10:35'),
                    ('14:30', '16:10'),
                    ('16:40', '18:20'),
                ],
                'season_pattern': 'spring',
                'month_day_start': '04-28',
                'month_day_end': '05-31'
            },
            {
                'route': 'oshidomari_wakkanai',
                'sailings': [
                    ('08:55', '10:35'),
                    ('14:30', '16:10'),
                    ('16:40', '18:20'),
                ],
                'season_pattern': 'autumn',
                'month_day_start': '10-01',
                'month_day_end': '10-31'
            },
            # 鴛泊→稚内 夏季 (6/1-9/30)
            {
                'route': 'oshidomari_wakkanai',
                'sailings': [
                    ('08:25', '10:05'),
                    ('12:05', '13:45'),
                    ('16:40', '18:20'),
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 鴛泊→稚内 晩秋 (11/1-12/31)
            {
                'route': 'oshidomari_wakkanai',
                'sailings': [
                    ('09:05', '10:45'),
                    ('14:00', '15:40'),
                    ('17:30', '19:10'),
                ],
                'season_pattern': 'late_autumn',
                'month_day_start': '11-01',
                'month_day_end': '12-31'
            },

            # 沓形→香深（利尻沓形→礼文）夏季限定 (6/1-9/30)
            {
                'route': 'kutsugata_kafuka',
                'sailings': [
                    ('14:25', '15:05'),  # 約40分
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 香深→沓形（礼文→利尻沓形）夏季限定 (6/1-9/30)
            {
                'route': 'kafuka_kutsugata',
                'sailings': [
                    ('12:50', '13:30'),  # 約40分
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },

            # 香深→稚内（礼文島→稚内）冬季・早春 (1/1-4/27)
            {
                'route': 'kafuka_wakkanai',
                'sailings': [
                    ('09:00', '10:55'),  # 直行便
                    ('14:10', '16:05'),  # 直行便
                    ('17:05', '19:00'),  # 直行便
                ],
                'season_pattern': 'winter',
                'month_day_start': '01-01',
                'month_day_end': '04-27'
            },
            # 香深→稚内 春 (4/28-5/31)
            {
                'route': 'kafuka_wakkanai',
                'sailings': [
                    ('08:55', '10:50'),  # 直行便
                    ('10:10', '13:00'),  # 利尻経由
                    ('13:25', '16:15'),  # 利尻経由
                    ('14:45', '16:40'),  # 直行便
                    ('17:05', '19:00'),  # 直行便
                ],
                'season_pattern': 'spring',
                'month_day_start': '04-28',
                'month_day_end': '05-31'
            },
            # 香深→稚内 夏季 (6/1-9/30)
            {
                'route': 'kafuka_wakkanai',
                'sailings': [
                    ('08:55', '10:50'),
                    ('14:20', '16:15'),
                    ('14:50', '16:45'),
                    ('17:10', '19:05'),
                ],
                'season_pattern': 'summer',
                'month_day_start': '06-01',
                'month_day_end': '09-30'
            },
            # 香深→稚内 秋 (10/1-10/31)
            {
                'route': 'kafuka_wakkanai',
                'sailings': [
                    ('08:55', '10:50'),
                    ('10:10', '13:00'),  # 利尻経由
                    ('13:25', '16:15'),  # 利尻経由
                    ('14:45', '16:40'),
                    ('17:05', '19:00'),
                ],
                'season_pattern': 'autumn',
                'month_day_start': '10-01',
                'month_day_end': '10-31'
            },
            # 香深→稚内 晩秋 (11/1-12/31)
            {
                'route': 'kafuka_wakkanai',
                'sailings': [
                    ('09:00', '10:55'),
                    ('14:10', '16:05'),
                    ('17:05', '19:00'),
                ],
                'season_pattern': 'late_autumn',
                'month_day_start': '11-01',
                'month_day_end': '12-31'
            },
        ]

        # 年度ごとにデータを生成
        timetable_data = []
        for year in range(start_year, end_year + 1):
            for schedule in base_schedules:
                route = schedule['route']
                season = f"{schedule['season_pattern']}_{year}"
                start_date = f"{year}-{schedule['month_day_start']}"
                end_date = f"{year}-{schedule['month_day_end']}"

                for dept, arr in schedule['sailings']:
                    timetable_data.append((route, dept, arr, season, start_date, end_date))

        inserted = 0
        for route, dept, arr, season, start, end in timetable_data:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO ferry_timetable
                    (route, departure_time, arrival_time, season, season_start, season_end)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (route, dept, arr, season, start, end))
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.IntegrityError:
                continue

        conn.commit()
        conn.close()

        print(f"[OK] Inserted {inserted} timetable entries")
        return inserted

    def get_sailings_for_date(self, target_date: str, route: Optional[str] = None) -> List[Dict]:
        """Get all scheduled sailings for a specific date"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        query = '''
            SELECT route, departure_time, arrival_time, season
            FROM ferry_timetable
            WHERE active = 1
            AND date(?) BETWEEN season_start AND season_end
        '''
        params = [target_date]

        if route:
            query += ' AND route = ?'
            params.append(route)

        query += ' ORDER BY departure_time'

        cursor.execute(query, params)
        sailings = []

        for row in cursor.fetchall():
            sailings.append({
                'route': row[0],
                'departure_time': row[1],
                'arrival_time': row[2],
                'season': row[3]
            })

        conn.close()
        return sailings

    def calculate_sailing_risk(self, forecast_date: str, departure_hour: int) -> Tuple[str, float, Dict]:
        """
        Calculate risk for a specific sailing time

        Returns: (risk_level, risk_score, weather_data)
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get weather forecast around departure time (±2 hours)
        cursor.execute('''
            SELECT
                AVG(COALESCE(wind_speed_max, wind_speed_numeric)) as wind_speed,
                AVG(wave_height_max) as wave_height,
                AVG(visibility) as visibility,
                AVG(temperature) as temperature
            FROM weather_forecast
            WHERE forecast_date = ?
            AND CAST(strftime('%H', forecast_hour) AS INTEGER) BETWEEN ? AND ?
            HAVING wind_speed IS NOT NULL OR wave_height IS NOT NULL
        ''', (forecast_date, max(0, departure_hour - 2), min(23, departure_hour + 2)))

        result = cursor.fetchone()
        conn.close()

        if not result or (result[0] is None and result[1] is None):
            # No data available
            return 'UNKNOWN', 0, {}

        wind_speed, wave_height, visibility, temperature = result
        wind_speed = wind_speed if wind_speed else 10.0
        wave_height = wave_height if wave_height else 1.5

        # Calculate risk score (same logic as daily forecast)
        risk_score = 0
        risk_factors = []

        # Wind risk
        if wind_speed >= 35:
            risk_score += 70
            risk_factors.append(f"極めて強風 ({wind_speed:.1f}m/s)")
        elif wind_speed >= 30:
            risk_score += 60
            risk_factors.append(f"非常に強風 ({wind_speed:.1f}m/s)")
        elif wind_speed >= 25:
            risk_score += 50
            risk_factors.append(f"強風 ({wind_speed:.1f}m/s)")
        elif wind_speed >= 20:
            risk_score += 35
            risk_factors.append(f"やや強風 ({wind_speed:.1f}m/s)")
        elif wind_speed >= 15:
            risk_score += 20
        elif wind_speed >= 10:
            risk_score += 10

        # Wave risk
        if wave_height >= 4.0:
            risk_score += 40
            risk_factors.append(f"非常に高波 ({wave_height:.1f}m)")
        elif wave_height >= 3.0:
            risk_score += 30
            risk_factors.append(f"高波 ({wave_height:.1f}m)")
        elif wave_height >= 2.0:
            risk_score += 15

        # Visibility risk
        if visibility and visibility < 1.0:
            risk_score += 20
            risk_factors.append(f"視界不良 ({visibility:.1f}km)")
        elif visibility and visibility < 3.0:
            risk_score += 10

        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        elif risk_score >= 20:
            risk_level = "LOW"
        else:
            risk_level = "MINIMAL"

        weather_data = {
            'wind_speed': wind_speed,
            'wave_height': wave_height,
            'visibility': visibility,
            'temperature': temperature,
            'risk_factors': ' / '.join(risk_factors) if risk_factors else ''
        }

        return risk_level, risk_score, weather_data

    def generate_sailing_forecasts(self, days_ahead: int = 7):
        """Generate sailing-by-sailing forecasts for the next N days"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Clear old forecasts
        cursor.execute('DELETE FROM sailing_forecast WHERE forecast_date < date("now")')

        generated = 0
        today = datetime.now().date()

        for day_offset in range(days_ahead):
            forecast_date = (today + timedelta(days=day_offset)).isoformat()

            # Get all scheduled sailings for this date
            sailings = self.get_sailings_for_date(forecast_date)

            for sailing in sailings:
                # Parse departure hour
                departure_hour = int(sailing['departure_time'].split(':')[0])

                # Calculate risk
                risk_level, risk_score, weather_data = self.calculate_sailing_risk(
                    forecast_date, departure_hour
                )

                if risk_level == 'UNKNOWN':
                    continue

                # Recommended action
                if risk_level == 'HIGH':
                    action = "❌ 欠航の可能性が高い - 代替日を検討"
                elif risk_level == 'MEDIUM':
                    action = "⚠️ 欠航リスクあり - 天気予報を注視"
                elif risk_level == 'LOW':
                    action = "✅ 低リスク - 通常通り運航予想"
                else:
                    action = "✅ 良好 - 安定運航予想"

                # Insert forecast
                cursor.execute('''
                    INSERT OR REPLACE INTO sailing_forecast
                    (forecast_date, route, departure_time, arrival_time, risk_level, risk_score,
                     wind_forecast, wave_forecast, visibility_forecast, temperature_forecast,
                     risk_factors, recommended_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    forecast_date,
                    sailing['route'],
                    sailing['departure_time'],
                    sailing['arrival_time'],
                    risk_level,
                    risk_score,
                    weather_data.get('wind_speed'),
                    weather_data.get('wave_height'),
                    weather_data.get('visibility'),
                    weather_data.get('temperature'),
                    weather_data.get('risk_factors', ''),
                    action
                ))

                generated += 1

        conn.commit()
        conn.close()

        print(f"[OK] Generated {generated} sailing forecasts for {days_ahead} days")
        return generated

    def check_timetable_coverage(self, days_ahead: int = 14) -> Dict:
        """
        Check if timetable data covers the required forecast period

        Returns: {
            'has_coverage': bool,
            'covered_until': str,
            'missing_dates': List[str],
            'needs_update': bool
        }
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        today = datetime.now().date()
        end_date = (today + timedelta(days=days_ahead)).isoformat()

        # Get max coverage date
        cursor.execute('SELECT MAX(season_end) FROM ferry_timetable WHERE active = 1')
        max_coverage = cursor.fetchone()[0]

        # Check for gaps
        missing_dates = []
        for day_offset in range(days_ahead):
            check_date = (today + timedelta(days=day_offset)).isoformat()
            cursor.execute('''
                SELECT COUNT(*) FROM ferry_timetable
                WHERE active = 1
                AND date(?) BETWEEN season_start AND season_end
            ''', (check_date,))

            if cursor.fetchone()[0] == 0:
                missing_dates.append(check_date)

        conn.close()

        return {
            'has_coverage': len(missing_dates) == 0,
            'covered_until': max_coverage,
            'missing_dates': missing_dates,
            'needs_update': max_coverage < end_date if max_coverage else True
        }

    def deprecate_old_schedules(self, cutoff_date: Optional[str] = None):
        """
        Mark old timetable entries as inactive (for schedule changes)

        Args:
            cutoff_date: Date before which schedules should be deprecated (default: yesterday)
        """
        if cutoff_date is None:
            cutoff_date = (datetime.now().date() - timedelta(days=1)).isoformat()

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE ferry_timetable
            SET active = 0
            WHERE season_end < ?
        ''', (cutoff_date,))

        deprecated_count = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"[OK] Deprecated {deprecated_count} old timetable entries")
        return deprecated_count

def main():
    """Initialize and populate sailing forecast system"""
    print("=" * 80)
    print("SAILING FORECAST SYSTEM INITIALIZATION")
    print("=" * 80)

    system = SailingForecastSystem()

    # Check coverage
    print("\n[INFO] Checking timetable coverage...")
    coverage = system.check_timetable_coverage(days_ahead=14)

    if coverage['needs_update']:
        print(f"[WARN] Timetable coverage insufficient")
        print(f"       Covered until: {coverage['covered_until']}")
        print(f"       Missing dates: {len(coverage['missing_dates'])} days")

        # Auto-populate for current and next year
        print("\n[INFO] Auto-populating timetable for current and next year...")
        current_year = datetime.now().year
        system.populate_timetable(start_year=current_year, end_year=current_year + 1)
    else:
        print(f"[OK] Timetable coverage is sufficient until {coverage['covered_until']}")

    # Deprecate old schedules
    print("\n[INFO] Cleaning up old timetable entries...")
    system.deprecate_old_schedules()

    # Generate forecasts
    print("\n[INFO] Generating sailing forecasts...")
    system.generate_sailing_forecasts(days_ahead=7)

    print("\n" + "=" * 80)
    print("[SUCCESS] Sailing forecast system initialized")
    print("=" * 80)

if __name__ == '__main__':
    exit(main())
