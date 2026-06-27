#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit that permanent accuracy DB exports and Google Sheets are filled daily."""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytz


JST = pytz.timezone('Asia/Tokyo')
DEFAULT_SHEETS_ID = '1C2kvlDZxo0XBagaZfZw3muShhm2Z3XGu9wMIK90kmUM'
SHEET_RANGES = {
    'daily_metrics': ('Daily Metrics', 'A1:N1001'),
    'ferry_details': ('Ferry Details', 'A1:W2000'),
    'flight_details': ('Flight Details', 'A1:AC1001'),
    'alerts': ('Alerts', 'A1:G1001'),
}


def _yesterday_jst() -> str:
    return (datetime.now(JST) - timedelta(days=1)).date().isoformat()


def _load_json(path: Optional[str], url: Optional[str], admin_token: Optional[str]) -> Dict:
    if path:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    if not url:
        raise ValueError('Either --input or --accuracy-url is required')
    headers = {}
    if admin_token:
        headers['X-Admin-Token'] = admin_token
    request = Request(url, headers=headers)
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode('utf-8'))


def _fetch_sheet_range(spreadsheet_id: str, sheet_name: str, cell_range: str) -> List[List]:
    api_key = os.environ.get('GOOGLE_SHEETS_API_KEY')
    bearer = os.environ.get('GOOGLE_SHEETS_BEARER_TOKEN')
    if not api_key and not bearer:
        raise ValueError('Google Sheets auth is not configured. Set GOOGLE_SHEETS_API_KEY or GOOGLE_SHEETS_BEARER_TOKEN.')

    encoded_range = quote(f"'{sheet_name}'!{cell_range}", safe='')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}'
    if api_key:
        url += f'?key={quote(api_key)}'
    headers = {}
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    request = Request(url, headers=headers)
    with urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode('utf-8'))
    return data.get('values', [])


def fetch_sheets(spreadsheet_id: str) -> Dict[str, List[Dict]]:
    sheets = {}
    for dataset, (sheet_name, cell_range) in SHEET_RANGES.items():
        values = _fetch_sheet_range(spreadsheet_id, sheet_name, cell_range)
        sheets[dataset] = _rows_from_values(values)
    return sheets


def _rows_from_values(values: List[List]) -> List[Dict]:
    if not values:
        return []
    headers = [str(value).strip() for value in values[0]]
    rows = []
    for raw in values[1:]:
        if not raw or not any(str(value).strip() for value in raw):
            continue
        row = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            row[header] = raw[idx] if idx < len(raw) else ''
        rows.append(row)
    return rows


def _latest_date(rows: Iterable[Dict]) -> Optional[str]:
    dates = [str(row.get('date') or row.get('operation_date') or '') for row in rows]
    dates = [date for date in dates if date]
    return max(dates) if dates else None


def _rows_for_date(rows: Iterable[Dict], date_str: str) -> List[Dict]:
    return [row for row in rows if str(row.get('date') or row.get('operation_date') or '') == date_str]


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}


def _blank(value) -> bool:
    return value is None or str(value).strip() == ''


def _add_issue(issues: List[Dict], severity: str, code: str, message: str, **extra) -> None:
    issues.append({'severity': severity, 'code': code, 'message': message, **extra})


def _group_daily(rows: Iterable[Dict]) -> Dict[str, Dict[str, Dict]]:
    grouped: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for row in rows:
        transport = str(row.get('transport') or '')
        date_str = str(row.get('date') or '')
        if transport and date_str:
            grouped[transport][date_str] = row
    return grouped


def audit_payload(payload: Dict, expected_date: str, sheets: Optional[Dict[str, List[Dict]]] = None) -> Dict:
    datasets = payload.get('datasets') or {}
    issues: List[Dict] = []

    period_end = str((payload.get('period') or {}).get('end') or '')
    if period_end and period_end < expected_date:
        _add_issue(
            issues, 'HIGH', 'DB_EXPORT_STALE',
            f'Permanent DB export ends at {period_end}, expected at least {expected_date}.',
            latest_date=period_end, expected_date=expected_date,
        )

    daily_rows = datasets.get('daily_metrics') or []
    ferry_rows = datasets.get('ferry_details') or []
    flight_rows = datasets.get('flight_details') or []
    daily_by_transport = _group_daily(daily_rows)

    for transport, detail_rows in (('ferry', ferry_rows), ('flight', flight_rows)):
        latest = _latest_date(detail_rows)
        if latest != expected_date:
            _add_issue(
                issues, 'HIGH', 'DB_DETAIL_DATE_MISMATCH',
                f'{transport} DB detail latest date is {latest or "none"}, expected {expected_date}.',
                transport=transport, latest_date=latest, expected_date=expected_date,
            )
        latest_details = _rows_for_date(detail_rows, expected_date)
        if not latest_details:
            _add_issue(
                issues, 'HIGH', 'DB_DETAIL_MISSING',
                f'{transport} DB detail rows are missing for {expected_date}.',
                transport=transport, expected_date=expected_date,
            )
        if expected_date not in daily_by_transport.get(transport, {}):
            _add_issue(
                issues, 'HIGH', 'DB_DAILY_MISSING',
                f'{transport} daily metrics row is missing for {expected_date}.',
                transport=transport, expected_date=expected_date,
            )

    ferry_latest = _rows_for_date(ferry_rows, expected_date)
    included_ferry = [row for row in ferry_latest if row.get('included_in_accuracy') is not False]
    missing_actual_wind_wave = [
        row.get('key') for row in included_ferry
        if _blank(row.get('actual_wind')) or _blank(row.get('actual_wave'))
    ]
    if missing_actual_wind_wave:
        _add_issue(
            issues, 'HIGH', 'DB_ACTUAL_WEATHER_MISSING',
            f'{len(missing_actual_wind_wave)} ferry rows for {expected_date} lack actual wind or wave values.',
            transport='ferry', expected_date=expected_date, sample_keys=missing_actual_wind_wave[:10],
        )

    leakage_candidates = [
        row.get('key') for row in included_ferry
        if not _blank(row.get('predicted_wind')) and not _blank(row.get('actual_wind'))
        and str(row.get('predicted_wind')) == str(row.get('actual_wind'))
        and not _blank(row.get('predicted_wave')) and not _blank(row.get('actual_wave'))
        and str(row.get('predicted_wave')) == str(row.get('actual_wave'))
    ]
    if len(leakage_candidates) >= max(3, len(included_ferry) // 2):
        _add_issue(
            issues, 'HIGH', 'FORECAST_ACTUAL_LEAKAGE_SUSPECTED',
            f'{len(leakage_candidates)} ferry rows have identical predicted/actual wind and wave values.',
            transport='ferry', expected_date=expected_date, sample_keys=leakage_candidates[:10],
        )

    if sheets is not None:
        _audit_sheets(sheets, datasets, expected_date, issues)

    high_count = sum(1 for issue in issues if issue['severity'] == 'HIGH')
    return {
        'status': 'fail' if high_count else 'success',
        'generated_at': datetime.now(JST).isoformat(),
        'expected_date': expected_date,
        'counts': {
            'db_daily_metrics': len(daily_rows),
            'db_ferry_details': len(ferry_rows),
            'db_flight_details': len(flight_rows),
            'sheet_daily_metrics': len((sheets or {}).get('daily_metrics', [])),
            'sheet_ferry_details': len((sheets or {}).get('ferry_details', [])),
            'sheet_flight_details': len((sheets or {}).get('flight_details', [])),
            'issues': len(issues),
            'high_issues': high_count,
        },
        'issues': issues,
    }


def _audit_sheets(sheets: Dict[str, List[Dict]], datasets: Dict, expected_date: str, issues: List[Dict]) -> None:
    for dataset in ('daily_metrics', 'ferry_details', 'flight_details'):
        db_rows = datasets.get(dataset) or []
        sheet_rows = sheets.get(dataset) or []
        latest = _latest_date(sheet_rows)
        if latest != expected_date:
            _add_issue(
                issues, 'HIGH', 'SHEET_DATE_MISMATCH',
                f'{dataset} sheet latest date is {latest or "none"}, expected {expected_date}.',
                dataset=dataset, latest_date=latest, expected_date=expected_date,
            )

        db_keys = {str(row.get('key')) for row in _rows_for_date(db_rows, expected_date) if row.get('key')}
        sheet_keys = {str(row.get('key')) for row in _rows_for_date(sheet_rows, expected_date) if row.get('key')}
        missing = sorted(db_keys - sheet_keys)
        if missing:
            _add_issue(
                issues, 'HIGH', 'SHEET_KEYS_MISSING',
                f'{dataset} sheet is missing {len(missing)} keys for {expected_date}.',
                dataset=dataset, expected_date=expected_date, sample_keys=missing[:10],
            )

    ferry_sheet_latest = _rows_for_date(sheets.get('ferry_details') or [], expected_date)
    included = [row for row in ferry_sheet_latest if _truthy(row.get('included_in_accuracy'))]
    missing_actual = [
        row.get('key') for row in included
        if _blank(row.get('actual_wind')) or _blank(row.get('actual_wave'))
    ]
    if missing_actual:
        _add_issue(
            issues, 'HIGH', 'SHEET_ACTUAL_WEATHER_MISSING',
            f'{len(missing_actual)} ferry sheet rows for {expected_date} lack actual wind or wave values.',
            dataset='ferry_details', expected_date=expected_date, sample_keys=missing_actual[:10],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit DB and Sheets daily accuracy fill completeness.')
    parser.add_argument('--input', help='Local accuracy-export.json file')
    parser.add_argument('--accuracy-url', help='Admin export URL')
    parser.add_argument('--admin-token', default=os.environ.get('ADMIN_TOKEN'))
    parser.add_argument('--expected-date', default=_yesterday_jst())
    parser.add_argument('--sheets-id', default=os.environ.get('GOOGLE_SHEETS_ID') or DEFAULT_SHEETS_ID)
    parser.add_argument('--skip-sheets', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()

    try:
        payload = _load_json(args.input, args.accuracy_url, args.admin_token)
        sheets = None if args.skip_sheets else fetch_sheets(args.sheets_id)
        report = audit_payload(payload, args.expected_date, sheets)
    except Exception as exc:
        report = {
            'status': 'fail',
            'generated_at': datetime.now(JST).isoformat(),
            'expected_date': args.expected_date,
            'counts': {'issues': 1, 'high_issues': 1},
            'issues': [{'severity': 'HIGH', 'code': 'AUDITOR_RUNTIME_ERROR', 'message': str(exc)}],
        }

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(rendered + '\n')
    print(rendered)
    return 0 if report.get('status') == 'success' else 2


if __name__ == '__main__':
    raise SystemExit(main())
