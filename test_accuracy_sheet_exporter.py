import sqlite3
import unittest
from datetime import datetime
from pathlib import Path

from accuracy_sheet_exporter import JST, build_accuracy_payload


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
             'OPERATED', 5, 1, 10, 1, 0, 0, 0, '2026-06-21T07:00:00+09:00', 'forecast'),
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

    def test_legacy_hindcast_ferry_rows_are_excluded_and_alerted(self):
        forecast = sqlite3.connect(self.root / 'ferry_weather_forecast.db')
        forecast.execute(
            "INSERT INTO unified_operation_accuracy VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('2026-06-21', 'wakkanai_kafuka', '06:30', 'MINIMAL', 0, 4, 0.5, None,
             'OPERATED', 4, 0.5, None, 1, 0, 0, 0, '2026-06-22T07:00:00+09:00', 'hindcast'),
        )
        forecast.commit()
        forecast.close()

        payload = build_accuracy_payload(
            start_date='2026-06-21', end_date='2026-06-21', data_dir=str(self.root)
        )
        ferry = payload['datasets']['ferry_details'][0]
        self.assertFalse(ferry['included_in_accuracy'])
        self.assertEqual(ferry['exclusion_reason'], 'legacy_hindcast_requires_recalc')
        self.assertTrue(any(a['type'] == 'LEGACY_HINDCAST_RECALC_REQUIRED' for a in payload['datasets']['alerts']))

    def test_unknown_flight_without_disruption_is_included_as_inferred_operated(self):
        actual = sqlite3.connect(self.root / 'heartland_ferry_real_data.db')
        actual.execute("DELETE FROM flight_status_rishiri WHERE scrape_date = ? AND flight_no = ? AND rishiri_role = ?",
                       ('2026-06-20', 'JAL2880', 'departure'))
        actual.execute(
            "INSERT INTO flight_status_rishiri VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('2026-06-20', 'JAL2880', 'HAC', 'ATR42-600', 'ris_okd', 'departure',
             '09:00', '', 'unknown', 0, 0, '', '2026-06-21T05:00:00+09:00'),
        )
        actual.commit()
        actual.close()

        payload = build_accuracy_payload(
            start_date='2026-06-20', end_date='2026-06-20', data_dir=str(self.root)
        )
        flight = payload['datasets']['flight_details'][0]
        self.assertTrue(flight['included_in_accuracy'])
        self.assertEqual(flight['actual_status'], 'operated_inferred')
        self.assertTrue(flight['actual_status_inferred'])

    def test_snapshot_datasets_include_forecasts_and_actuals(self):
        service_date = datetime.now(JST).date().isoformat()
        forecast = sqlite3.connect(self.root / 'ferry_weather_forecast.db')
        forecast.executescript('''
            CREATE TABLE cancellation_forecast (
                id INTEGER PRIMARY KEY, forecast_for_date TEXT, route TEXT,
                forecast_hour INTEGER, risk_level TEXT, risk_score REAL,
                risk_factors TEXT, wind_forecast REAL, wave_forecast REAL,
                visibility_forecast REAL, temperature_forecast REAL,
                confidence REAL, generated_at TEXT
            );
            CREATE TABLE sailing_weather_forecast (
                service_date TEXT, route TEXT, departure_time TEXT, arrival_time TEXT,
                port_role TEXT, port_key TEXT, port_name TEXT, forecast_hour INTEGER,
                scheduled_reference_time TEXT, window_start_time TEXT, window_end_time TEXT,
                minutes_from_departure INTEGER, via_oshidomari INTEGER,
                wind_speed REAL, wind_direction REAL, wind_gusts REAL,
                wave_height REAL, wave_direction REAL, wave_period REAL,
                wind_wave_height REAL, swell_wave_height REAL, visibility REAL,
                precipitation REAL, snowfall REAL, temperature REAL, pressure_msl REAL,
                weather_code TEXT, source TEXT, source_time TEXT, valid_time TEXT,
                assigned_at TEXT
            );
            CREATE TABLE actual_sailing_weather (
                service_date TEXT, route TEXT, departure_time TEXT, arrival_time TEXT,
                port_role TEXT, port_key TEXT, port_name TEXT, weather_hour INTEGER,
                scheduled_reference_time TEXT, window_start_time TEXT, window_end_time TEXT,
                minutes_from_departure INTEGER, via_oshidomari INTEGER,
                wind_speed REAL, wind_direction REAL, wind_gusts REAL,
                wave_height REAL, wave_direction REAL, wave_period REAL,
                wind_wave_height REAL, swell_wave_height REAL, visibility REAL,
                precipitation REAL, snowfall REAL, temperature REAL, pressure_msl REAL,
                weather_code TEXT, source TEXT, valid_time TEXT, assigned_at TEXT
            );
        ''')
        forecast.execute(
            "INSERT INTO cancellation_forecast VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, service_date, 'wakkanai_oshidomari', 6, 'HIGH', 75, 'wind',
             22, 3.2, 8, 12, 0.9, f'{service_date}T04:00:00+09:00'),
        )
        forecast.execute(
            "INSERT INTO sailing_weather_forecast VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (service_date, 'wakkanai_oshidomari', '06:30', '08:10',
             'departure', 'wakkanai', '稚内', 6, '06:30', '06:00', '07:00',
             0, 0, 22, 300, 28, 3.2, 300, 6, 2.4, 0.8, 8,
             0, 0, 12, 1010, 'cloudy', 'open-meteo',
             f'{service_date}T04:00:00+09:00', f'{service_date}T06:00:00+09:00',
             f'{service_date}T04:00:00+09:00'),
        )
        forecast.execute(
            "INSERT INTO actual_sailing_weather VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (service_date, 'wakkanai_oshidomari', '06:30', '08:10',
             'departure', 'wakkanai', '稚内', 6, '06:30', '06:00', '07:00',
             0, 0, 24, 310, 30, 3.5, 310, 7, 2.7, 0.9, 6,
             0, 0, 11, 1008, 'rain', 'open-meteo-archive',
             f'{service_date}T06:00:00+09:00', f'{service_date}T09:00:00+09:00'),
        )
        forecast.execute(
            "INSERT INTO flight_cancellation_forecast VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (3, service_date, 'ris_okd', 'JAL2880', 'HAC', 'ATR42-600', '09:00',
             'departure', 'MEDIUM', 45, 9, 270, 7.5, 5, f'{service_date}T04:00:00+09:00'),
        )
        forecast.commit()
        forecast.close()

        actual = sqlite3.connect(self.root / 'heartland_ferry_real_data.db')
        actual.executescript('''
            CREATE TABLE ferry_status_enhanced (
                scrape_date TEXT, route TEXT, departure_time TEXT,
                operational_status TEXT, is_cancelled INTEGER
            );
        ''')
        actual.execute(
            "INSERT INTO ferry_status_enhanced VALUES (?,?,?,?,?)",
            (service_date, 'wakkanai_oshidomari', '06:30', 'CANCELLED', 1),
        )
        actual.commit()
        actual.close()

        payload = build_accuracy_payload(start_date=service_date, end_date=service_date, data_dir=str(self.root))
        forecast_snapshots = payload['datasets']['forecast_snapshots']
        actual_snapshots = payload['datasets']['actual_snapshots']

        self.assertTrue(any(row['key'].startswith('ferry_forecast:') for row in forecast_snapshots))
        self.assertTrue(any(row['key'].startswith('flight_forecast:') for row in forecast_snapshots))
        ferry_actual = next(row for row in actual_snapshots if row['key'].startswith('ferry_actual:'))
        self.assertEqual(ferry_actual['actual_status'], 'CANCELLED')
        self.assertTrue(ferry_actual['actual_disruption'])


if __name__ == '__main__':
    unittest.main()
