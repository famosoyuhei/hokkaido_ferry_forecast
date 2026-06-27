#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only accuracy export for n8n and spreadsheet analytics.

This module never creates or updates application tables.  It reads the ferry
hindcast audit and matches the latest flight forecast to FlightAware results,
then returns JSON-friendly rows suitable for Google Sheets upserts.
"""

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import pytz


JST = pytz.timezone('Asia/Tokyo')
MIN_ACCURACY_DATE = '2026-04-05'
PREDICTED_DISRUPTION_LEVELS = {'HIGH', 'MEDIUM'}
NON_WEATHER_REASON_WORDS = (
    'maintenance', 'mechanical', 'crew', 'aircraft change', 'schedule change',
    '整備', '機材', '乗員', 'ダイヤ', '季節運休',
)
LEGACY_FERRY_DATA_SOURCES = {'hindcast'}


def _date_range(days: int, start_date: Optional[str], end_date: Optional[str]) -> Tuple[str, str]:
    """Return a validated, inclusive JST date range."""
    end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else (
        datetime.now(JST) - timedelta(days=1)
    ).date()
    start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else (
        end - timedelta(days=max(1, days) - 1)
    )
    floor = datetime.strptime(MIN_ACCURACY_DATE, '%Y-%m-%d').date()
    start = max(start, floor)
    if start > end:
        raise ValueError('start_date must be on or before end_date')
    return start.isoformat(), end.isoformat()


def _readonly_connection(path: Path) -> Optional[sqlite3.Connection]:
    """Open an existing SQLite database without creating or changing it."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    uri = f"file:{quote(str(path.resolve()).replace(os.sep, '/'), safe='/:')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA query_only = ON')
    return conn


def _table_exists(conn: Optional[sqlite3.Connection], table: str) -> bool:
    if conn is None:
        return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 6) if denominator else None


def _metrics(rows: Iterable[Dict]) -> Dict:
    included = [row for row in rows if row.get('included_in_accuracy')]
    tp = sum(1 for row in included if row['predicted_disruption'] and row['actual_disruption'])
    tn = sum(1 for row in included if not row['predicted_disruption'] and not row['actual_disruption'])
    fp = sum(1 for row in included if row['predicted_disruption'] and not row['actual_disruption'])
    fn = sum(1 for row in included if not row['predicted_disruption'] and row['actual_disruption'])
    total = tp + tn + fp + fn
    correct = tp + tn
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = round(2 * precision * recall / (precision + recall), 6)
    return {
        'total': total,
        'correct': correct,
        'accuracy': _ratio(correct, total),
        'true_positives': tp,
        'true_negatives': tn,
        'false_positives': fp,
        'false_negatives': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }


def _daily_rows(transport: str, details: List[Dict]) -> List[Dict]:
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for row in details:
        grouped[row['date']].append(row)
    result = []
    for date_str in sorted(grouped):
        metrics = _metrics(grouped[date_str])
        result.append({
            'key': f'{transport}:{date_str}',
            'transport': transport,
            'date': date_str,
            **metrics,
            'excluded': sum(1 for row in grouped[date_str] if not row['included_in_accuracy']),
        })
    return result


def _ferry_details(conn: Optional[sqlite3.Connection], start: str, end: str) -> List[Dict]:
    if not _table_exists(conn, 'unified_operation_accuracy'):
        return []
    rows = conn.execute('''
        SELECT operation_date, route, departure_time, predicted_risk,
               predicted_score, predicted_wind, predicted_wave,
               predicted_visibility, actual_status, actual_wind, actual_wave,
               actual_visibility, is_correct, false_positive, false_negative,
               COALESCE(is_likely_maintenance, 0) AS is_likely_maintenance,
               calculated_at, data_source
        FROM unified_operation_accuracy
        WHERE operation_date BETWEEN ? AND ?
        ORDER BY operation_date, route, departure_time
    ''', (start, end)).fetchall()
    details = []
    for row in rows:
        maintenance = bool(row['is_likely_maintenance'])
        legacy_source = (row['data_source'] or '').lower() in LEGACY_FERRY_DATA_SOURCES
        predicted = (row['predicted_risk'] or '').upper() in PREDICTED_DISRUPTION_LEVELS
        actual = (row['actual_status'] or '').upper() == 'CANCELLED'
        exclusion_reason = ''
        if maintenance:
            exclusion_reason = 'likely_maintenance'
        elif legacy_source:
            exclusion_reason = 'legacy_hindcast_requires_recalc'
        details.append({
            'key': f"ferry:{row['operation_date']}:{row['route']}:{row['departure_time'] or ''}",
            'transport': 'ferry',
            'date': row['operation_date'],
            'route': row['route'],
            'service_no': row['departure_time'] or '',
            'predicted_risk': row['predicted_risk'],
            'predicted_score': row['predicted_score'],
            'predicted_wind': row['predicted_wind'],
            'predicted_wave': row['predicted_wave'],
            'predicted_visibility': row['predicted_visibility'],
            'actual_status': row['actual_status'],
            'actual_wind': row['actual_wind'],
            'actual_wave': row['actual_wave'],
            'actual_visibility': row['actual_visibility'],
            'predicted_disruption': predicted,
            'actual_disruption': actual,
            'is_correct': bool(row['is_correct']) if row['is_correct'] is not None else None,
            'false_positive': bool(row['false_positive']),
            'false_negative': bool(row['false_negative']),
            'included_in_accuracy': not exclusion_reason,
            'exclusion_reason': exclusion_reason,
            'data_source': row['data_source'],
            'calculated_at': row['calculated_at'],
        })
    return details


def _likely_non_weather(reason: str) -> bool:
    lowered = (reason or '').lower()
    return any(word in lowered for word in NON_WEATHER_REASON_WORDS)


def _flight_details(
    forecast_conn: Optional[sqlite3.Connection],
    actual_conn: Optional[sqlite3.Connection],
    start: str,
    end: str,
) -> List[Dict]:
    if not _table_exists(forecast_conn, 'flight_cancellation_forecast'):
        return []
    if not _table_exists(actual_conn, 'flight_status_rishiri'):
        return []

    forecast_rows = forecast_conn.execute('''
        SELECT f.forecast_for_date, f.route_key, f.flight_no, f.airline,
               f.aircraft, f.rishiri_time, f.rishiri_role, f.risk_level,
               f.risk_score, f.wind_speed, f.wind_direction,
               f.crosswind_component, f.visibility, f.generated_at
        FROM flight_cancellation_forecast f
        INNER JOIN (
            SELECT forecast_for_date, flight_no, rishiri_role, MAX(id) AS max_id
            FROM flight_cancellation_forecast
            WHERE forecast_for_date BETWEEN ? AND ?
              AND generated_at <= (
                  forecast_for_date || 'T' || SUBSTR(rishiri_time, 1, 5) || ':00+09:00'
              )
            GROUP BY forecast_for_date, flight_no, rishiri_role
        ) latest ON f.id = latest.max_id
        ORDER BY f.forecast_for_date, f.rishiri_time, f.flight_no
    ''', (start, end)).fetchall()
    forecasts = {
        (str(row['forecast_for_date']), row['flight_no'], row['rishiri_role']): row
        for row in forecast_rows
    }
    actual_rows = actual_conn.execute('''
        SELECT scrape_date, flight_no, airline, aircraft, route_key,
               rishiri_role, scheduled_time, actual_time, status,
               is_cancelled, is_diverted, cancellation_reason, collected_at
        FROM flight_status_rishiri
        WHERE scrape_date BETWEEN ? AND ?
        ORDER BY scrape_date, scheduled_time, flight_no
    ''', (start, end)).fetchall()

    details = []
    for actual_row in actual_rows:
        key_tuple = (actual_row['scrape_date'], actual_row['flight_no'], actual_row['rishiri_role'])
        forecast = forecasts.get(key_tuple)
        status = (actual_row['status'] or '').strip().lower()
        reason = actual_row['cancellation_reason'] or ''
        exclusion_reason = ''
        if forecast is None:
            exclusion_reason = 'missing_forecast'
        elif _likely_non_weather(reason):
            exclusion_reason = 'likely_non_weather'
        inferred_operated = False
        if forecast is not None and (not status or status == 'unknown'):
            if not actual_row['is_cancelled'] and not actual_row['is_diverted'] and not reason:
                status = 'operated_inferred'
                inferred_operated = True
            else:
                exclusion_reason = 'unknown_actual_status'
        risk = forecast['risk_level'] if forecast else None
        predicted = (risk or '').upper() in PREDICTED_DISRUPTION_LEVELS
        actual_disruption = bool(actual_row['is_cancelled'] or actual_row['is_diverted'])
        included = not exclusion_reason
        details.append({
            'key': f"flight:{actual_row['scrape_date']}:{actual_row['flight_no']}:{actual_row['rishiri_role']}",
            'transport': 'flight',
            'date': actual_row['scrape_date'],
            'route': actual_row['route_key'],
            'service_no': actual_row['flight_no'],
            'role': actual_row['rishiri_role'],
            'airline': actual_row['airline'],
            'aircraft': actual_row['aircraft'],
            'scheduled_time': actual_row['scheduled_time'],
            'actual_time': actual_row['actual_time'],
            'predicted_risk': risk,
            'predicted_score': forecast['risk_score'] if forecast else None,
            'wind_speed': forecast['wind_speed'] if forecast else None,
            'wind_direction': forecast['wind_direction'] if forecast else None,
            'crosswind_component': forecast['crosswind_component'] if forecast else None,
            'visibility': forecast['visibility'] if forecast else None,
            'actual_status': status or actual_row['status'],
            'is_cancelled': bool(actual_row['is_cancelled']),
            'is_diverted': bool(actual_row['is_diverted']),
            'cancellation_reason': reason,
            'predicted_disruption': predicted,
            'actual_disruption': actual_disruption,
            'is_correct': (predicted == actual_disruption) if included else None,
            'false_positive': (predicted and not actual_disruption) if included else False,
            'false_negative': (not predicted and actual_disruption) if included else False,
            'included_in_accuracy': included,
            'exclusion_reason': exclusion_reason,
            'actual_status_inferred': inferred_operated,
            'forecast_generated_at': forecast['generated_at'] if forecast else None,
            'collected_at': actual_row['collected_at'],
        })
    return details


def _alerts(ferry_details: List[Dict], flight_details: List[Dict], end: str) -> List[Dict]:
    alerts = []
    for transport, rows in (('ferry', ferry_details), ('flight', flight_details)):
        latest = max((row['date'] for row in rows), default=None)
        if latest is None:
            alerts.append({
                'key': f'{transport}:no_data:{end}', 'severity': 'HIGH',
                'transport': transport, 'date': end, 'type': 'NO_ACCURACY_DATA',
                'message': '対象期間に精度評価可能なデータがありません。',
            })
        elif latest < end:
            alerts.append({
                'key': f'{transport}:stale:{end}', 'severity': 'MEDIUM',
                'transport': transport, 'date': end, 'type': 'STALE_DATA',
                'message': f'最新データは {latest} です。収集ジョブを確認してください。',
            })
        false_negatives = [row for row in rows if row.get('false_negative')]
        if false_negatives:
            alerts.append({
                'key': f'{transport}:fn:{end}', 'severity': 'HIGH',
                'transport': transport, 'date': end, 'type': 'FALSE_NEGATIVE',
                'message': f'対象期間に見逃しが {len(false_negatives)} 件あります。閾値変更前に元データを確認してください。',
            })
    legacy_hindcast = [
        row for row in ferry_details
        if row.get('exclusion_reason') == 'legacy_hindcast_requires_recalc'
    ]
    if legacy_hindcast:
        alerts.append({
            'key': f'ferry:legacy_hindcast:{end}', 'severity': 'HIGH',
            'transport': 'ferry', 'date': end, 'type': 'LEGACY_HINDCAST_RECALC_REQUIRED',
            'message': f'予報値と実測値が混在しうる旧hindcast明細が {len(legacy_hindcast)} 件あります。bulk accuracy再計算後にSheetsを再同期してください。',
        })
    inferred_flights = [
        row for row in flight_details
        if row.get('actual_status_inferred') and row.get('included_in_accuracy')
    ]
    if inferred_flights:
        alerts.append({
            'key': f'flight:inferred_operated:{end}', 'severity': 'MEDIUM',
            'transport': 'flight', 'date': end, 'type': 'INFERRED_FLIGHT_STATUS',
            'message': f'飛行機実績 {len(inferred_flights)} 件はFlightAware欠航情報なしのため運航推定として評価しています。',
        })
    return alerts


def build_accuracy_payload(
    days: int = 90,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Dict:
    """Build all spreadsheet datasets without mutating application state."""
    start, end = _date_range(days, start_date, end_date)
    root = Path(data_dir or os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.')
    forecast_conn = _readonly_connection(root / 'ferry_weather_forecast.db')
    actual_conn = _readonly_connection(root / 'heartland_ferry_real_data.db')
    try:
        ferry_details = _ferry_details(forecast_conn, start, end)
        flight_details = _flight_details(forecast_conn, actual_conn, start, end)
    finally:
        if forecast_conn is not None:
            forecast_conn.close()
        if actual_conn is not None:
            actual_conn.close()

    ferry_daily = _daily_rows('ferry', ferry_details)
    flight_daily = _daily_rows('flight', flight_details)
    return {
        'status': 'success',
        'generated_at': datetime.now(JST).isoformat(),
        'timezone': 'Asia/Tokyo',
        'period': {'start': start, 'end': end},
        'definitions': {
            'predicted_disruption': 'risk_level is HIGH or MEDIUM',
            'flight_actual_disruption': 'cancelled or diverted',
            'excluded': 'maintenance/non-weather/unknown/missing forecast records are not scored',
        },
        'datasets': {
            'daily_metrics': ferry_daily + flight_daily,
            'ferry_details': ferry_details,
            'flight_details': flight_details,
            'alerts': _alerts(ferry_details, flight_details, end),
        },
        'counts': {
            'daily_metrics': len(ferry_daily) + len(flight_daily),
            'ferry_details': len(ferry_details),
            'flight_details': len(flight_details),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Export read-only ferry/flight accuracy data as JSON.')
    parser.add_argument('--days', type=int, default=90)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--data-dir')
    parser.add_argument('--output')
    args = parser.parse_args()
    payload = build_accuracy_payload(args.days, args.start, args.end, args.data_dir)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    else:
        print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
