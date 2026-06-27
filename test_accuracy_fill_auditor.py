import unittest

from accuracy_fill_auditor import audit_payload


def _base_payload():
    return {
        'period': {'start': '2026-06-27', 'end': '2026-06-27'},
        'datasets': {
            'daily_metrics': [
                {'key': 'ferry:2026-06-27', 'transport': 'ferry', 'date': '2026-06-27'},
                {'key': 'flight:2026-06-27', 'transport': 'flight', 'date': '2026-06-27'},
            ],
            'ferry_details': [
                {
                    'key': 'ferry:2026-06-27:wakkanai_oshidomari:07:15',
                    'transport': 'ferry',
                    'date': '2026-06-27',
                    'included_in_accuracy': True,
                    'predicted_wind': 3.87,
                    'predicted_wave': 0.46,
                    'actual_wind': 3.9,
                    'actual_wave': 0.56,
                },
            ],
            'flight_details': [
                {
                    'key': 'flight:2026-06-27:JAL2783:arrival',
                    'transport': 'flight',
                    'date': '2026-06-27',
                    'included_in_accuracy': True,
                },
            ],
            'alerts': [],
        },
    }


class AccuracyFillAuditorTest(unittest.TestCase):
    def test_success_when_db_and_sheets_have_expected_date(self):
        payload = _base_payload()
        sheets = {
            'daily_metrics': list(payload['datasets']['daily_metrics']),
            'ferry_details': list(payload['datasets']['ferry_details']),
            'flight_details': list(payload['datasets']['flight_details']),
            'alerts': [],
        }

        report = audit_payload(payload, '2026-06-27', sheets)

        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['counts']['high_issues'], 0)

    def test_fails_when_sheet_is_stale(self):
        payload = _base_payload()
        sheets = {
            'daily_metrics': [
                {'key': 'ferry:2026-06-26', 'transport': 'ferry', 'date': '2026-06-26'},
            ],
            'ferry_details': [],
            'flight_details': [],
            'alerts': [],
        }

        report = audit_payload(payload, '2026-06-27', sheets)

        self.assertEqual(report['status'], 'fail')
        self.assertTrue(any(issue['code'] == 'SHEET_DATE_MISMATCH' for issue in report['issues']))
        self.assertTrue(any(issue['code'] == 'SHEET_KEYS_MISSING' for issue in report['issues']))

    def test_fails_when_latest_ferry_actual_weather_is_missing(self):
        payload = _base_payload()
        payload['datasets']['ferry_details'][0]['actual_wind'] = None

        report = audit_payload(payload, '2026-06-27', None)

        self.assertEqual(report['status'], 'fail')
        self.assertTrue(any(issue['code'] == 'DB_ACTUAL_WEATHER_MISSING' for issue in report['issues']))


if __name__ == '__main__':
    unittest.main()
