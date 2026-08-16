#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full spreadsheet audit per docs/ai_employees/spreadsheet_auditor_employee.md.

Recomputes accuracy datasets from detail rows and checks the 12 rules in that
spec (key uniqueness, predicted/actual leakage, confusion-matrix consistency,
timetable membership, zero-filled missing values, daily recalculation,
day-over-day volume swings). Runs against the permanent-DB export JSON, and
optionally against the same tabs in Google Sheets, using the same rule set
for both so DB-vs-Sheets drift shows up as a normal finding rather than a
separate code path.
"""

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

import pytz

from accuracy_fill_auditor import DEFAULT_SHEETS_ID, SHEETS_SYNC_LAG_DAYS, _shift_date, fetch_sheets
from flight_timetable_utils import get_active_flights_on
from jst_utils import get_timetable_sailings

JST = pytz.timezone('Asia/Tokyo')


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}


def _blank(value) -> bool:
    return value is None or str(value).strip() == ''


def _parse_time_to_minutes(value) -> Optional[int]:
    """Normalize a time-of-day value to minutes since midnight.

    Google Sheets sometimes reformats a plain "HH:MM" string it auto-detects
    as a time cell (e.g. into "6:55:00 AM" or a day-fraction serial number).
    Comparing raw strings against the timetable would then false-positive on
    every row, so both sides of the timetable-membership check go through
    this normalizer instead of exact string equality.
    """
    if _blank(value):
        return None
    text = str(value).strip()
    try:
        as_float = float(text)
        if 0 <= as_float < 1:
            return round(as_float * 24 * 60) % 1440
    except ValueError:
        pass
    am_pm = None
    upper = text.upper()
    if upper.endswith('AM') or upper.endswith('PM'):
        am_pm = upper[-2:]
        text = text[:-2].strip()
    parts = text.split(':')
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if am_pm == 'PM' and hour < 12:
        hour += 12
    elif am_pm == 'AM' and hour == 12:
        hour = 0
    return (hour * 60 + minute) % 1440


def _as_float(value) -> Optional[float]:
    if _blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_json(path: Optional[str], url: Optional[str], admin_token: Optional[str], days: int) -> Dict:
    if path:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    if not url:
        raise ValueError('Either --input or --export-url is required')
    full_url = url if '?' in url else f'{url}?days={days}'
    headers = {}
    if admin_token:
        headers['X-Admin-Token'] = admin_token
    request = Request(full_url, headers=headers)
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode('utf-8'))


def _add_issue(issues: List[Dict], severity: str, code: str, message: str, **extra) -> None:
    issues.append({'severity': severity, 'code': code, 'message': message, **extra})


# ---------------------------------------------------------------------------
# Rule 1: row key uniqueness
# ---------------------------------------------------------------------------

def _rule_duplicate_keys(source: str, dataset: str, rows: List[Dict], issues: List[Dict]) -> None:
    counts = Counter(row.get('key') for row in rows if row.get('key'))
    dupes = sorted(key for key, count in counts.items() if count > 1)
    if dupes:
        _add_issue(
            issues, 'HIGH', 'DUPLICATE_ROW_KEY',
            f'[{source}] {dataset} に重複キーが{len(dupes)}件あります。',
            source=source, dataset=dataset, sample_keys=dupes[:10],
        )


# ---------------------------------------------------------------------------
# Rule 3: forecast/actual leakage (ferry wind/wave/visibility)
# ---------------------------------------------------------------------------

def _rule_leakage(source: str, rows: List[Dict], issues: List[Dict]) -> None:
    included = [row for row in rows if _truthy(row.get('included_in_accuracy'))]
    if not included:
        return
    candidates = []
    for row in included:
        pw, aw = _as_float(row.get('predicted_wind')), _as_float(row.get('actual_wind'))
        pv, av = _as_float(row.get('predicted_wave')), _as_float(row.get('actual_wave'))
        if pw is None or aw is None or pv is None or av is None:
            continue
        if pw == aw and pv == av:
            candidates.append(row.get('key'))
    if len(candidates) >= max(3, len(included) // 2):
        _add_issue(
            issues, 'HIGH', 'FORECAST_ACTUAL_LEAKAGE',
            f'[{source}] ferry_details で予報値と実測値(風速・波高)が完全一致する行が{len(candidates)}件あります。',
            source=source, dataset='ferry_details', sample_keys=candidates[:10],
        )


# ---------------------------------------------------------------------------
# Rule 4: predicted_disruption <-> predicted_risk consistency
# ---------------------------------------------------------------------------

def _rule_predicted_consistency(source: str, dataset: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = []
    for row in rows:
        risk = str(row.get('predicted_risk') or '').upper()
        if not risk:
            continue
        expected = risk in ('HIGH', 'MEDIUM')
        if 'predicted_disruption' in row and _truthy(row.get('predicted_disruption')) != expected:
            bad.append(row.get('key'))
    if bad:
        _add_issue(
            issues, 'HIGH', 'PREDICTED_DISRUPTION_MISMATCH',
            f'[{source}] {dataset} で predicted_disruption と predicted_risk が矛盾する行が{len(bad)}件あります。',
            source=source, dataset=dataset, sample_keys=bad[:10],
        )


# ---------------------------------------------------------------------------
# Rule 5: actual_disruption <-> actual_status / cancellation flags
# ---------------------------------------------------------------------------

def _rule_actual_consistency_ferry(source: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = []
    for row in rows:
        if 'actual_disruption' not in row or _blank(row.get('actual_disruption')):
            continue
        status = str(row.get('actual_status') or '').upper()
        if not status:
            continue
        expected = status == 'CANCELLED'
        if _truthy(row.get('actual_disruption')) != expected:
            bad.append(row.get('key'))
    if bad:
        _add_issue(
            issues, 'HIGH', 'ACTUAL_DISRUPTION_MISMATCH',
            f'[{source}] ferry_details で actual_disruption と actual_status が矛盾する行が{len(bad)}件あります。',
            source=source, dataset='ferry_details', sample_keys=bad[:10],
        )


def _rule_actual_consistency_flight(source: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = []
    for row in rows:
        if 'actual_disruption' not in row:
            continue
        expected = _truthy(row.get('is_cancelled')) or _truthy(row.get('is_diverted'))
        if _truthy(row.get('actual_disruption')) != expected:
            bad.append(row.get('key'))
    if bad:
        _add_issue(
            issues, 'HIGH', 'ACTUAL_DISRUPTION_MISMATCH',
            f'[{source}] flight_details で actual_disruption と欠航/引き返しフラグが矛盾する行が{len(bad)}件あります。',
            source=source, dataset='flight_details', sample_keys=bad[:10],
        )


# ---------------------------------------------------------------------------
# Rule 6: is_correct / false_positive / false_negative vs confusion matrix
# ---------------------------------------------------------------------------

def _rule_confusion_matrix(source: str, dataset: str, rows: List[Dict], issues: List[Dict]) -> None:
    mismatched = []
    both_true = []
    for row in rows:
        if not _truthy(row.get('included_in_accuracy')):
            continue
        predicted = _truthy(row.get('predicted_disruption'))
        actual = _truthy(row.get('actual_disruption'))
        fp = _truthy(row.get('false_positive'))
        fn = _truthy(row.get('false_negative'))
        if fp and fn:
            both_true.append(row.get('key'))
        if not _blank(row.get('is_correct')) and _truthy(row.get('is_correct')) != (predicted == actual):
            mismatched.append(row.get('key'))
        if fp != (predicted and not actual) or fn != ((not predicted) and actual):
            mismatched.append(row.get('key'))
    if mismatched:
        _add_issue(
            issues, 'HIGH', 'CONFUSION_MATRIX_CONFLICT',
            f'[{source}] {dataset} で is_correct/false_positive/false_negative が混同行列の定義と一致しない行が{len(set(mismatched))}件あります。',
            source=source, dataset=dataset, sample_keys=sorted(set(mismatched))[:10],
        )
    if both_true:
        _add_issue(
            issues, 'HIGH', 'CONFUSION_MATRIX_CONFLICT',
            f'[{source}] {dataset} で false_positive と false_negative が同時にtrueの行が{len(both_true)}件あります。',
            source=source, dataset=dataset, sample_keys=both_true[:10],
        )


# ---------------------------------------------------------------------------
# Rule 7: excluded rows must carry an exclusion_reason
# ---------------------------------------------------------------------------

def _rule_exclusion_reason(source: str, dataset: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = [
        row.get('key') for row in rows
        if not _truthy(row.get('included_in_accuracy')) and _blank(row.get('exclusion_reason'))
    ]
    if bad:
        _add_issue(
            issues, 'HIGH', 'MISSING_EXCLUSION_REASON',
            f'[{source}] {dataset} で included_in_accuracy=false なのに exclusion_reason が空の行が{len(bad)}件あります。',
            source=source, dataset=dataset, sample_keys=bad[:10],
        )


# ---------------------------------------------------------------------------
# Rule 8 / 9: evaluated rows must exist in the official timetable
# ---------------------------------------------------------------------------

def _rule_ferry_timetable(source: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = []
    cache: Dict[tuple, Optional[set]] = {}
    for row in rows:
        if not _truthy(row.get('included_in_accuracy')):
            continue
        date, route, dep = row.get('date'), row.get('route'), row.get('service_no')
        if _blank(date) or _blank(route) or _blank(dep):
            continue
        cache_key = (route, date)
        if cache_key not in cache:
            try:
                cache[cache_key] = {
                    _parse_time_to_minutes(d) for d, _a in get_timetable_sailings(route, date)
                }
            except Exception:
                cache[cache_key] = None
        sailings = cache[cache_key]
        dep_minutes = _parse_time_to_minutes(dep)
        if sailings and dep_minutes is not None and dep_minutes not in sailings:
            bad.append(row.get('key'))
    if bad:
        _add_issue(
            issues, 'HIGH', 'OFF_TIMETABLE_FERRY_ROW',
            f'[{source}] ferry_details に公式時刻表にない便が{len(bad)}件含まれています。',
            source=source, dataset='ferry_details', sample_keys=bad[:10],
        )


def _rule_flight_timetable(source: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = []
    cache: Dict[str, Optional[set]] = {}
    for row in rows:
        if not _truthy(row.get('included_in_accuracy')):
            continue
        date, flight_no, role = row.get('date'), row.get('service_no'), row.get('role')
        if _blank(date) or _blank(flight_no) or _blank(role):
            continue
        if date not in cache:
            try:
                flights = get_active_flights_on(date)
                cache[date] = {(f['flight_no'], f['rishiri_role']) for f in flights}
            except Exception:
                cache[date] = None
        active = cache[date]
        if active is not None and (flight_no, role) not in active:
            bad.append(row.get('key'))
    if bad:
        _add_issue(
            issues, 'HIGH', 'OFF_TIMETABLE_FLIGHT_ROW',
            f'[{source}] flight_details に日付ごとの就航便に含まれない行が{len(bad)}件あります（HAC/ANA季節混同の可能性）。',
            source=source, dataset='flight_details', sample_keys=bad[:10],
        )


# ---------------------------------------------------------------------------
# Rule 10: missing values must be blank/NULL, not zero-filled
# ---------------------------------------------------------------------------

ZERO_CHECK_FIELDS = ('predicted_wind', 'predicted_wave', 'actual_wind', 'actual_wave')


def _rule_zero_filled(source: str, dataset: str, rows: List[Dict], issues: List[Dict]) -> None:
    bad = []
    for row in rows:
        for field in ZERO_CHECK_FIELDS:
            if field not in row or _blank(row.get(field)):
                continue
            value = _as_float(row.get(field))
            if value == 0.0:
                bad.append(f"{row.get('key')}:{field}")
    if len(bad) >= 5:
        _add_issue(
            issues, 'MEDIUM', 'ZERO_FILLED_MISSING_VALUE',
            f'[{source}] {dataset} で欠損値が0埋めされている疑いのある値が{len(bad)}件あります。',
            source=source, dataset=dataset, sample_keys=bad[:10],
        )


# ---------------------------------------------------------------------------
# Rule 11: daily aggregates must match a recalculation from detail rows
# ---------------------------------------------------------------------------

def _recompute_daily(detail_rows: List[Dict]) -> Dict[tuple, Dict]:
    grouped: Dict[tuple, List[Dict]] = defaultdict(list)
    for row in detail_rows:
        transport, date = row.get('transport'), row.get('date')
        if transport and date:
            grouped[(transport, date)].append(row)

    result = {}
    for key, rows in grouped.items():
        included = [row for row in rows if _truthy(row.get('included_in_accuracy'))]
        tp = sum(1 for r in included if _truthy(r.get('predicted_disruption')) and _truthy(r.get('actual_disruption')))
        tn = sum(1 for r in included if not _truthy(r.get('predicted_disruption')) and not _truthy(r.get('actual_disruption')))
        fp = sum(1 for r in included if _truthy(r.get('predicted_disruption')) and not _truthy(r.get('actual_disruption')))
        fn = sum(1 for r in included if not _truthy(r.get('predicted_disruption')) and _truthy(r.get('actual_disruption')))
        total = tp + tn + fp + fn
        precision = round(tp / (tp + fp), 6) if (tp + fp) else None
        recall = round(tp / (tp + fn), 6) if (tp + fn) else None
        f1 = round(2 * precision * recall / (precision + recall), 6) if precision and recall and (precision + recall) else None
        result[key] = {
            'total': total,
            'accuracy': round((tp + tn) / total, 6) if total else None,
            'precision': precision,
            'recall': recall,
            'f1': f1,
        }
    return result


def _rule_daily_recalc(source: str, daily_rows: List[Dict], detail_rows: List[Dict], issues: List[Dict]) -> None:
    recomputed = _recompute_daily(detail_rows)
    bad = []
    for row in daily_rows:
        key = (row.get('transport'), row.get('date'))
        expected = recomputed.get(key)
        if expected is None:
            continue
        for field in ('total', 'accuracy', 'precision', 'recall', 'f1'):
            actual_val = _as_float(row.get(field)) if field != 'total' else row.get('total')
            expected_val = expected.get(field)
            if expected_val is None and (actual_val is None or actual_val == 0):
                continue
            if expected_val is None or actual_val is None:
                if expected_val != actual_val:
                    bad.append(f"{row.get('key')}:{field}")
                continue
            if abs(float(actual_val) - float(expected_val)) > 0.01:
                bad.append(f"{row.get('key')}:{field}")
    if bad:
        _add_issue(
            issues, 'HIGH', 'DAILY_RECALC_MISMATCH',
            f'[{source}] daily_metrics が明細行からの再計算と一致しない項目が{len(bad)}件あります。',
            source=source, dataset='daily_metrics', sample_keys=sorted(set(bad))[:10],
        )


# ---------------------------------------------------------------------------
# Rule 12: sudden day-over-day volume swings
# ---------------------------------------------------------------------------

def _rule_sudden_change(source: str, daily_rows: List[Dict], issues: List[Dict]) -> None:
    by_transport: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for row in daily_rows:
        transport, date = row.get('transport'), row.get('date')
        if transport and date:
            by_transport[transport][date] = row

    for transport, by_date in by_transport.items():
        dates = sorted(by_date.keys())
        for prev_date, cur_date in zip(dates, dates[1:]):
            prev_total = _as_float(by_date[prev_date].get('total')) or 0
            cur_total = _as_float(by_date[cur_date].get('total')) or 0
            if prev_total >= 5 and abs(cur_total - prev_total) / prev_total > 0.5:
                _add_issue(
                    issues, 'MEDIUM', 'SUDDEN_VOLUME_CHANGE',
                    f'[{source}] {transport} {cur_date} の評価対象件数が前日比で急変しています'
                    f'（{int(prev_total)}→{int(cur_total)}）。時刻表切り替えまたは収集失敗の可能性があります。',
                    source=source, transport=transport, date=cur_date,
                    previous=prev_total, current=cur_total,
                )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _audit_source(source: str, datasets: Dict[str, List[Dict]], issues: List[Dict]) -> None:
    daily_rows = datasets.get('daily_metrics') or []
    ferry_rows = datasets.get('ferry_details') or []
    flight_rows = datasets.get('flight_details') or []

    _rule_duplicate_keys(source, 'ferry_details', ferry_rows, issues)
    _rule_duplicate_keys(source, 'flight_details', flight_rows, issues)

    _rule_leakage(source, ferry_rows, issues)

    _rule_predicted_consistency(source, 'ferry_details', ferry_rows, issues)
    _rule_predicted_consistency(source, 'flight_details', flight_rows, issues)

    _rule_actual_consistency_ferry(source, ferry_rows, issues)
    _rule_actual_consistency_flight(source, flight_rows, issues)

    _rule_confusion_matrix(source, 'ferry_details', ferry_rows, issues)
    _rule_confusion_matrix(source, 'flight_details', flight_rows, issues)

    _rule_exclusion_reason(source, 'ferry_details', ferry_rows, issues)
    _rule_exclusion_reason(source, 'flight_details', flight_rows, issues)

    _rule_ferry_timetable(source, ferry_rows, issues)
    _rule_flight_timetable(source, flight_rows, issues)

    _rule_zero_filled(source, 'ferry_details', ferry_rows, issues)

    _rule_daily_recalc(source, daily_rows, ferry_rows + flight_rows, issues)
    _rule_sudden_change(source, daily_rows, issues)


def _filter_datasets_by_period(datasets: Dict[str, List[Dict]], start: str, end: str) -> Dict[str, List[Dict]]:
    """Restrict each dataset to rows dated within [start, end].

    Google Sheets tabs accumulate the full history since the project began,
    while the DB export is a rolling window (e.g. the last 14 days). Auditing
    the full Sheets history against the same rules every day would make any
    old, already-understood anomaly (e.g. the documented April schedule
    changeover) fail the job forever. Rows without a usable date pass through
    unfiltered rather than being silently dropped.
    """
    filtered = {}
    for name, rows in datasets.items():
        kept = []
        for row in rows:
            date = row.get('date')
            if _blank(date) or (start <= str(date) <= end):
                kept.append(row)
        filtered[name] = kept
    return filtered


def audit_payload(payload: Dict, sheets: Optional[Dict[str, List[Dict]]] = None) -> Dict:
    datasets = payload.get('datasets') or {}
    issues: List[Dict] = []

    _audit_source('db_export', datasets, issues)
    if sheets is not None:
        period = payload.get('period') or {}
        start, end = period.get('start'), period.get('end')
        if start and end:
            # n8n syncs Sheets from the DB once daily and can lag a day behind
            # on the most recent date, so exclude that tail from the sheets
            # side of the audit rather than flagging a transient sync gap.
            sheets_end = _shift_date(end, -SHEETS_SYNC_LAG_DAYS)
            windowed_sheets = _filter_datasets_by_period(sheets, start, sheets_end)
        else:
            windowed_sheets = sheets
        _audit_source('sheets', windowed_sheets, issues)

    high_count = sum(1 for issue in issues if issue['severity'] == 'HIGH')
    medium_count = sum(1 for issue in issues if issue['severity'] == 'MEDIUM')

    return {
        'status': 'fail' if high_count else 'success',
        'generated_at': datetime.now(JST).isoformat(),
        'period': payload.get('period'),
        'sources_checked': ['db_export'] + (['sheets'] if sheets is not None else []),
        'counts': {
            'db_ferry_details': len(datasets.get('ferry_details') or []),
            'db_flight_details': len(datasets.get('flight_details') or []),
            'db_daily_metrics': len(datasets.get('daily_metrics') or []),
            'sheet_ferry_details': len((sheets or {}).get('ferry_details') or []),
            'sheet_flight_details': len((sheets or {}).get('flight_details') or []),
            'sheet_daily_metrics': len((sheets or {}).get('daily_metrics') or []),
            'issues': len(issues),
            'high_issues': high_count,
            'medium_issues': medium_count,
        },
        'issues': issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Full spreadsheet audit (12-rule check) for accuracy datasets.')
    parser.add_argument('--input', help='Local accuracy-export.json file (from accuracy_sheet_exporter.py)')
    parser.add_argument('--export-url', help='Admin export URL, e.g. https://.../admin/export-accuracy-data')
    parser.add_argument('--admin-token', default=os.environ.get('ADMIN_TOKEN'))
    parser.add_argument('--days', type=int, default=14, help='Lookback window when fetching from --export-url')
    parser.add_argument('--sheets-id', default=os.environ.get('GOOGLE_SHEETS_ID') or DEFAULT_SHEETS_ID)
    parser.add_argument('--skip-sheets', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()

    try:
        payload = _load_json(args.input, args.export_url, args.admin_token, args.days)
        sheets = None if args.skip_sheets else fetch_sheets(args.sheets_id)
        report = audit_payload(payload, sheets)
    except Exception as exc:
        report = {
            'status': 'fail',
            'generated_at': datetime.now(JST).isoformat(),
            'counts': {'issues': 1, 'high_issues': 1, 'medium_issues': 0},
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
