import os
import shutil
import sqlite3
import unittest
from pathlib import Path

from unified_accuracy_tracker import UnifiedAccuracyTracker


class UnifiedAccuracyTrackerTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / '.test_unified_accuracy_tracker'
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir()
        self.old_data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
        os.environ['RAILWAY_VOLUME_MOUNT_PATH'] = str(self.root)

        forecast = sqlite3.connect(self.root / 'ferry_weather_forecast.db')
        forecast.executescript('''
            CREATE TABLE cancellation_forecast (
                id INTEGER PRIMARY KEY,
                forecast_for_date TEXT,
                forecast_hour INTEGER,
                route TEXT,
                risk_level TEXT,
                risk_score REAL,
                wind_forecast REAL,
                wave_forecast REAL,
                visibility_forecast REAL
            );
            CREATE TABLE actual_weather (
                date TEXT,
                hour INTEGER,
                location TEXT,
                wind_speed REAL,
                wave_height REAL,
                visibility REAL
            );
        ''')
        forecast.execute(
            '''INSERT INTO cancellation_forecast
               (forecast_for_date, forecast_hour, route, risk_level, risk_score,
                wind_forecast, wave_forecast, visibility_forecast)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            ('2026-06-20', 5, 'wakkanai_oshidomari', 'MEDIUM', 40, 12.0, 2.5, 8.0),
        )
        forecast.execute(
            '''INSERT INTO actual_weather
               (date, hour, location, wind_speed, wave_height, visibility)
               VALUES (?, ?, ?, ?, ?, ?)''',
            ('2026-06-20', 6, 'wakkanai', 4.0, 0.8, 20.0),
        )
        forecast.commit()
        forecast.close()

        real = sqlite3.connect(self.root / 'heartland_ferry_real_data.db')
        real.executescript('''
            CREATE TABLE ferry_status_enhanced (
                scrape_date TEXT,
                route TEXT,
                departure_time TEXT,
                is_cancelled INTEGER
            );
        ''')
        real.execute(
            '''INSERT INTO ferry_status_enhanced
               (scrape_date, route, departure_time, is_cancelled)
               VALUES (?, ?, ?, ?)''',
            ('2026-06-20', 'wakkanai_oshidomari', '06:30', 0),
        )
        real.commit()
        real.close()

    def tearDown(self):
        if self.old_data_dir is None:
            os.environ.pop('RAILWAY_VOLUME_MOUNT_PATH', None)
        else:
            os.environ['RAILWAY_VOLUME_MOUNT_PATH'] = self.old_data_dir
        shutil.rmtree(self.root)

    def test_forecast_and_actual_weather_are_stored_separately(self):
        tracker = UnifiedAccuracyTracker()
        result = tracker.calculate_daily_accuracy('2026-06-20')
        self.assertEqual(result['matched'], 1)

        conn = sqlite3.connect(self.root / 'ferry_weather_forecast.db')
        row = conn.execute('''
            SELECT predicted_risk, predicted_wind, predicted_wave, predicted_visibility,
                   actual_wind, actual_wave, actual_visibility,
                   is_correct, false_positive, data_source
            FROM unified_operation_accuracy
            WHERE operation_date = '2026-06-20'
        ''').fetchone()
        summary = conn.execute('''
            SELECT avg_wind_error, avg_wave_error, avg_visibility_error
            FROM unified_daily_summary
            WHERE summary_date = '2026-06-20'
        ''').fetchone()
        conn.close()

        self.assertEqual(row[0], 'MEDIUM')
        self.assertEqual(row[1:4], (12.0, 2.5, 8.0))
        self.assertEqual(row[4:7], (4.0, 0.8, 20.0))
        self.assertEqual(row[7], 0)
        self.assertEqual(row[8], 1)
        self.assertEqual(row[9], 'forecast')
        self.assertEqual(summary, (8.0, 1.7, 12.0))


if __name__ == '__main__':
    unittest.main()
