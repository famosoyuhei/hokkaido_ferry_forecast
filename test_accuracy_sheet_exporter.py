import sqlite3
import unittest
from pathlib import Path

from accuracy_sheet_exporter import build_accuracy_payload


class AccuracySheetExporterTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / '.test_accuracy_sheet_exporter'
        self.root.mkdir(exist_ok=True)
        for name in ('ferry_weather_forecast.db', 'heartland_ferry_real_data.db'):
            path = self.root / name
            if path.exists():
                path.unlink()
        root = self.root
        forecast = sqlite3.connect(root / 'ferry_weather_forecast.db')
        forecast.executescript('''
            CREATE TABLE unified_operation_accuracy (
                operation_date TEXT, route TEXT, departure_time TEXT,
                predicted_risk TEXT, predicted_score REAL, predicted_wind REAL,
                predicted_wave REAL, predicted_visibility REAL, actual_status TEXT,
                actual_wind REAL, actual_wave REAL, actual_visibility REAL,
                is_correct INTEGER, false_positive INTEGER, false_negative INTEGER,
                is_likely_maintenance INTEGER, calculated_at TEXT, data_source TEXT
            );
            CREATE TABLE flight_cancellation_forecast (
                id INTEGER PRIMARY KEY, forecast_for_date TEXT, route_key TEXT,
                flight_no TEXT, airline TEXT, aircraft TEXT, rishiri_time TEXT,
                rishiri_role TEXT, risk_level TEXT, risk_score REAL,
                wind_speed REAL, wind_direction REAL, crosswind_component REAL,
                visibility REAL, generated_at TEXT
            );
        ''')
        forecast.execute(
            "INSERT INTO unified_operation_accuracy VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('2026-06-20', 'wakkanai_oshidomari', '06:30', 'MINIMAL', 0, 5, 1, 10,
             'OPERATED', 5, 1, 10, 1, 0, 0, 0, '2026-06-21T07:00:00+09:00', 'hindcast'),
        )
        forecast.execute(
            "INSERT INTO flight_cancellation_forecast VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, '2026-06-20', 'ris_okd', 'JAL2880', 'HAC', 'ATR42-600', '09:00',
             'departure', 'HIGH', 80, 12, 360, 11.2, 10, '2026-06-19T23:00:00+09:00'),
        )
        # A post-departure forecast must not leak into the accuracy evaluation.
        forecast.execute(
            "INSERT INTO flight_cancellation_forecast VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (2, '2026-06-20', 'ris_okd', 'JAL2880', 'HAC', 'ATR42-600', '09:00',
             'departure', 'MINIMAL', 0, 2, 90, 0.7, 20, '2026-06-20T12:00:00+09:00'),
        )
        forecast.commit()
        forecast.close()

        actual = sqlite3.connect(root / 'heartland_ferry_real_data.db')
        actual.executescript('''
            CREATE TABLE flight_status_rishiri (
                scrape_date TEXT, flight_no TEXT, airline TEXT, aircraft TEXT,
                route_key TEXT, rishiri_role TEXT, scheduled_time TEXT,
                actual_time TEXT, status TEXT, is_cancelled INTEGER,
                is_diverted INTEGER, cancellation_reason TEXT, collected_at TEXT
            );
        ''')
        actual.execute(
            "INSERT INTO flight_status_rishiri VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('2026-06-20', 'JAL2880', 'HAC', 'ATR42-600', 'ris_okd', 'departure',
             '09:00', '', 'cancelled', 1, 0, 'weather', '2026-06-21T05:00:00+09:00'),
        )
        actual.commit()
        actual.close()

    def tearDown(self):
        for name in ('ferry_weather_forecast.db', 'heartland_ferry_real_data.db'):
            path = self.root / name
            if path.exists():
                path.unlink()
        self.root.rmdir()

    def test_builds_ferry_and_flight_metrics(self):
        payload = build_accuracy_payload(
            start_date='2026-06-20', end_date='2026-06-20', data_dir=str(self.root)
        )
        daily = {row['transport']: row for row in payload['datasets']['daily_metrics']}
        self.assertEqual(daily['ferry']['accuracy'], 1.0)
        self.assertEqual(daily['flight']['true_positives'], 1)
        self.assertEqual(daily['flight']['recall'], 1.0)

    def test_missing_databases_are_reported_without_creation(self):
        empty = Path(__file__).parent / '.test_accuracy_sheet_exporter_empty'
        empty.mkdir(exist_ok=True)
        try:
            payload = build_accuracy_payload(
                start_date='2026-06-20', end_date='2026-06-20', data_dir=str(empty)
            )
            self.assertEqual(payload['counts']['daily_metrics'], 0)
            self.assertEqual(len(payload['datasets']['alerts']), 2)
            self.assertEqual(list(Path(empty).iterdir()), [])
        finally:
            empty.rmdir()


if __name__ == '__main__':
    unittest.main()
