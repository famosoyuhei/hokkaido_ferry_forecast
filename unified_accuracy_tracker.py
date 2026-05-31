#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Accuracy Tracker
Calculates hindcast accuracy per sailing:
  - For each actual sailing, fetch weather from its departure port at departure hour
  - Compute hindcast risk from actual weather
  - Compare to actual operated/cancelled outcome
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pytz

def _safe_max(a, b):
    if a is None: return b
    if b is None: return a
    return max(a, b)

def _safe_min(a, b):
    if a is None: return b
    if b is None: return a
    return min(a, b)


class UnifiedAccuracyTracker:

    # Maps route name → departure port (matches actual_weather location keys)
    # wakkanai_kutsugata / kutsugata_wakkanai は存在しない航路。使用禁止。
    # 沓形関連は kutsugata_kafuka（沓形→香深）/ kafuka_kutsugata（香深→沓形）のみ。
    ROUTE_DEPARTURE_PORT = {
        'wakkanai_oshidomari': 'wakkanai',
        'oshidomari_wakkanai': 'oshidomari',
        'wakkanai_kafuka':     'wakkanai',
        'kafuka_wakkanai':     'kafuka',
        'kutsugata_kafuka':    'kutsugata',   # 夏季のみ（6/1〜9/30）
        'kafuka_kutsugata':    'kafuka',      # 夏季のみ（6/1〜9/30）
        'oshidomari_kafuka':   'oshidomari',
        'kafuka_oshidomari':   'kafuka',
    }

    # Maps route name → destination port (for routes where both ends matter)
    ROUTE_DESTINATION_PORT = {
        'wakkanai_kafuka':   'kafuka',
        'kafuka_wakkanai':   'wakkanai',
        'kutsugata_kafuka':  'kafuka',    # 夏季のみ（6/1〜9/30）
        'kafuka_kutsugata':  'kutsugata', # 夏季のみ（6/1〜9/30）
        'oshidomari_kafuka': 'kafuka',
        'kafuka_oshidomari': 'oshidomari',
    }

    # Annual dock maintenance window (month-day range, inclusive)
    # Heartland Ferry typically does spring maintenance in early-mid April
    MAINTENANCE_WINDOW = (4, 5, 4, 15)   # (start_month, start_day, end_month, end_day)

    def __init__(self):
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.forecast_db  = os.path.join(data_dir, 'ferry_weather_forecast.db')
        self.real_data_db = os.path.join(data_dir, 'heartland_ferry_real_data.db')
        self.jst = pytz.timezone('Asia/Tokyo')
        self.init_accuracy_tables()
        print(f"Initialized UnifiedAccuracyTracker")
        print(f"  Forecast DB:  {self.forecast_db}")
        print(f"  Real Data DB: {self.real_data_db}")

    def init_accuracy_tables(self):
        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_operation_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_date TEXT NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT,

                predicted_risk TEXT,
                predicted_score REAL,
                predicted_wind REAL,
                predicted_wave REAL,
                predicted_visibility REAL,

                actual_status TEXT,
                actual_wind REAL,
                actual_wave REAL,
                actual_visibility REAL,

                is_correct BOOLEAN,
                false_positive BOOLEAN,
                false_negative BOOLEAN,
                prediction_error REAL,

                is_likely_maintenance BOOLEAN DEFAULT 0,

                calculated_at TEXT,
                data_source TEXT,

                UNIQUE(operation_date, route, departure_time)
            )
        ''')
        # Add is_likely_maintenance column if upgrading from old schema
        try:
            cursor.execute('ALTER TABLE unified_operation_accuracy ADD COLUMN is_likely_maintenance BOOLEAN DEFAULT 0')
            conn.commit()
        except Exception:
            pass  # column already exists

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date TEXT NOT NULL UNIQUE,

                total_predictions INTEGER,
                correct_predictions INTEGER,
                accuracy_rate REAL,

                true_positives INTEGER,
                true_negatives INTEGER,
                false_positives INTEGER,
                false_negatives INTEGER,

                precision_score REAL,
                recall_score REAL,
                f1_score REAL,

                avg_wind_error REAL,
                avg_wave_error REAL,
                avg_visibility_error REAL,

                calculated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_level_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_date TEXT NOT NULL,
                risk_level TEXT NOT NULL,

                predictions_count INTEGER,
                correct_count INTEGER,
                accuracy_rate REAL,

                avg_score REAL,
                avg_actual_wind REAL,
                avg_actual_wave REAL,

                calculated_at TEXT,

                UNIQUE(analysis_date, risk_level)
            )
        ''')

        conn.commit()
        conn.close()
        print("Accuracy tables initialized")

    # ------------------------------------------------------------------
    def _calc_risk(self, wind: float, wave: Optional[float], vis: Optional[float]):
        """Risk calculation (mirrors weather_forecast_collector logic)."""
        score = 0
        if wind >= 35:   score += 70
        elif wind >= 30: score += 60
        elif wind >= 25: score += 50
        elif wind >= 20: score += 35
        elif wind >= 15: score += 20
        elif wind >= 10: score += 10

        if wave is not None:
            if wave >= 4.0:   score += 40
            elif wave >= 3.0: score += 30
            elif wave >= 2.0: score += 15

        if vis is not None:
            if vis < 1.0:   score += 20
            elif vis < 3.0: score += 10

        if score >= 70:   risk = 'HIGH'
        elif score >= 40: risk = 'MEDIUM'
        elif score >= 20: risk = 'LOW'
        else:             risk = 'MINIMAL'
        return risk, score

    def _get_sailing_weather(self, cursor, date: str, port: str, dep_hour: int):
        """
        Fetch actual weather for a port at departure hour.
        Falls back to dep_hour±1 if exact hour has no data.
        Handles both old schema (no location column) and new schema.
        """
        for h in [dep_hour, dep_hour - 1, dep_hour + 1]:
            if not (0 <= h <= 23):
                continue
            try:
                cursor.execute('''
                    SELECT wind_speed, wave_height, visibility
                    FROM actual_weather
                    WHERE date = ? AND location = ? AND hour = ?
                ''', (date, port, h))
            except Exception:
                # location column not yet present — fall back to old schema (wakkanai only)
                cursor.execute('''
                    SELECT wind_speed, wave_height, visibility
                    FROM actual_weather
                    WHERE date = ? AND hour = ?
                ''', (date, h))
            row = cursor.fetchone()
            if row and row[0] is not None:
                return row[0], row[1], row[2]
        return None, None, None

    def _get_route_weather(self, cursor, date: str, route: str, dep_hour: int):
        """
        Return worst-case weather for a route:
        - For Rebun (kafuka) routes: MAX of departure port and kafuka weather,
          because Rebun Island has no orographic shelter and is consistently
          windier/rougher than conditions at the departure port.
        - For all other routes: departure port only.
        """
        dep_port  = self.ROUTE_DEPARTURE_PORT.get(route)
        dest_port = self.ROUTE_DESTINATION_PORT.get(route)

        wind1, wave1, vis1 = self._get_sailing_weather(cursor, date, dep_port, dep_hour)

        if dest_port is None or dest_port == dep_port:
            return wind1, wave1, vis1

        wind2, wave2, vis2 = self._get_sailing_weather(cursor, date, dest_port, dep_hour)

        # Take worst-case (max wind/wave, min visibility) across both ports
        wind = _safe_max(wind1, wind2)
        wave = _safe_max(wave1, wave2)
        vis  = _safe_min(vis1, vis2)
        return wind, wave, vis

    def _is_maintenance_window(self, date_str: str) -> bool:
        """Return True if date falls within the annual dock maintenance window."""
        try:
            from datetime import date as date_cls
            d = date_cls.fromisoformat(date_str)
            sm, sd, em, ed = self.MAINTENANCE_WINDOW
            start = date_cls(d.year, sm, sd)
            end   = date_cls(d.year, em, ed)
            return start <= d <= end
        except Exception:
            return False

    def _detect_maintenance_day(self, sailings, wind_values: List) -> bool:
        """
        Heuristic: likely dock maintenance if:
        - ALL sailings are cancelled, AND
        - median actual wind speed < 15 m/s (weather is calm), AND
        - date falls within the annual maintenance window (Apr 5-15).
        This is used to flag — not filter — the day.
        """
        if not sailings:
            return False
        if not self._is_maintenance_window(sailings[0][3]):
            return False
        all_cancelled = all(bool(s[2]) for s in sailings)
        valid_winds = [w for w in wind_values if w is not None]
        calm_weather = len(valid_winds) > 0 and (sum(valid_winds) / len(valid_winds)) < 15.0
        return all_cancelled and calm_weather

    # ------------------------------------------------------------------
    def calculate_daily_accuracy(self, target_date: Optional[str] = None) -> Dict:
        """Calculate per-sailing hindcast accuracy for target_date."""

        if target_date is None:
            yesterday = datetime.now(self.jst) - timedelta(days=1)
            target_date = yesterday.strftime('%Y-%m-%d')

        print(f"\nCalculating accuracy for {target_date}...")

        # --- Actual sailings (include target_date in tuple for maintenance detection) ---
        real_conn = sqlite3.connect(self.real_data_db)
        real_cursor = real_conn.cursor()
        real_cursor.execute('''
            SELECT route, departure_time, is_cancelled
            FROM ferry_status_enhanced
            WHERE scrape_date = ?
            ORDER BY route, departure_time
        ''', (target_date,))
        sailings_raw = real_cursor.fetchall()
        real_conn.close()

        # Attach target_date to each sailing for maintenance detection helper
        sailings = [(r, dt, ic, target_date) for r, dt, ic in sailings_raw]

        if not sailings:
            print(f"  No actual sailing data for {target_date}")
            return {}

        routes_with_data = len(set(s[0] for s in sailings))
        print(f"  Found {len(sailings)} sailings across {routes_with_data} routes")

        # --- Forecasts (one per route, latest forecast_hour) ---
        forecast_conn = sqlite3.connect(self.forecast_db)
        forecast_cursor = forecast_conn.cursor()
        forecast_cursor.execute('''
            SELECT
                cf.route,
                cf.risk_level,
                cf.risk_score,
                cf.wind_forecast,
                cf.wave_forecast,
                cf.visibility_forecast
            FROM cancellation_forecast cf
            INNER JOIN (
                SELECT forecast_for_date, route, MAX(forecast_hour) as max_hour
                FROM cancellation_forecast
                WHERE forecast_for_date = ?
                GROUP BY forecast_for_date, route
            ) latest
            ON cf.forecast_for_date = latest.forecast_for_date
            AND cf.route = latest.route
            AND cf.forecast_hour = latest.max_hour
        ''', (target_date,))
        forecast_by_route = {row[0]: row[1:] for row in forecast_cursor.fetchall()}
        print(f"  Found {len(forecast_by_route)} route forecasts")

        # --- First pass: collect weather for each sailing ---
        sailing_data = []   # (route, dep_time, is_cancelled, wind, wave, vis, use_hindcast)
        for route, dep_time, is_cancelled, _ in sailings:
            m = re.search(r'(\d{1,2}):', dep_time or '')
            dep_hour = int(m.group(1)) if m else 6

            # Worst-case weather: for Rebun routes uses MAX(departure, kafuka) weather
            wind, wave, vis = self._get_route_weather(
                forecast_cursor, target_date, route, dep_hour
            )

            use_hindcast = (wind is not None and self.ROUTE_DEPARTURE_PORT.get(route) is not None)

            if not use_hindcast:
                if route not in forecast_by_route:
                    continue
                wind = forecast_by_route[route][2]
                wave = forecast_by_route[route][3]
                vis  = forecast_by_route[route][4]

            sailing_data.append((route, dep_time, is_cancelled, wind, wave, vis, use_hindcast))

        # --- Detect maintenance day before writing records ---
        wind_values = [sd[3] for sd in sailing_data]
        is_maint_day = self._detect_maintenance_day(sailings, wind_values)
        if is_maint_day:
            print(f"  *** Likely dock maintenance day detected — flagging all sailings ***")

        # --- Per-sailing evaluation ---
        matched = correct = tp = tn = fp = fn = 0
        hindcast_used = 0
        # Separate counters that exclude maintenance days
        matched_ex = correct_ex = tp_ex = tn_ex = fp_ex = fn_ex = 0

        unified_conn = sqlite3.connect(self.forecast_db)
        unified_cursor = unified_conn.cursor()

        for route, dep_time, is_cancelled, wind, wave, vis, use_hindcast in sailing_data:
            if use_hindcast:
                eval_risk, eval_score = self._calc_risk(wind, wave, vis)
                hindcast_used += 1
            else:
                eval_risk  = forecast_by_route[route][0]
                eval_score = forecast_by_route[route][1]

            actual_cancelled = bool(is_cancelled)
            predicted_high   = eval_risk in ['HIGH', 'MEDIUM']
            is_correct = (predicted_high == actual_cancelled)

            if   predicted_high and     actual_cancelled: tp += 1
            elif predicted_high and not actual_cancelled: fp += 1
            elif not predicted_high and actual_cancelled: fn += 1
            else:                                         tn += 1

            if is_correct:
                correct += 1
            matched += 1

            # Exclude maintenance-flagged days from clean metrics
            if not is_maint_day:
                if   predicted_high and     actual_cancelled: tp_ex += 1
                elif predicted_high and not actual_cancelled: fp_ex += 1
                elif not predicted_high and actual_cancelled: fn_ex += 1
                else:                                         tn_ex += 1
                if is_correct: correct_ex += 1
                matched_ex += 1

            unified_cursor.execute('''
                INSERT OR REPLACE INTO unified_operation_accuracy
                (operation_date, route, departure_time,
                 predicted_risk, predicted_score, predicted_wind, predicted_wave, predicted_visibility,
                 actual_status, actual_wind, actual_wave, actual_visibility,
                 is_correct, false_positive, false_negative,
                 is_likely_maintenance,
                 calculated_at, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                target_date, route, dep_time,
                eval_risk, eval_score, wind, wave, vis,
                'CANCELLED' if actual_cancelled else 'OPERATED',
                wind, wave, vis,
                is_correct,
                predicted_high and not actual_cancelled,
                not predicted_high and actual_cancelled,
                1 if is_maint_day else 0,
                datetime.now(self.jst).isoformat(),
                'hindcast' if use_hindcast else 'forecast',
            ))

        unified_conn.commit()

        # --- Aggregate metrics (use maintenance-excluded counts for precision/recall) ---
        accuracy_rate = (correct / matched * 100) if matched > 0 else 0
        # Use clean (non-maintenance) counts for precision/recall/F1
        precision = tp_ex / (tp_ex + fp_ex) if (tp_ex + fp_ex) > 0 else 0
        recall    = tp_ex / (tp_ex + fn_ex) if (tp_ex + fn_ex) > 0 else 0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        unified_cursor.execute('''
            INSERT OR REPLACE INTO unified_daily_summary
            (summary_date, total_predictions, correct_predictions, accuracy_rate,
             true_positives, true_negatives, false_positives, false_negatives,
             precision_score, recall_score, f1_score, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            target_date, matched, correct, accuracy_rate,
            tp_ex, tn_ex, fp_ex, fn_ex,
            precision, recall, f1,
            datetime.now(self.jst).isoformat()
        ))

        unified_conn.commit()
        unified_conn.close()
        forecast_conn.close()

        maint_note = ' [MAINTENANCE DAY — excluded from P/R/F1]' if is_maint_day else ''
        print(f"  Hindcast used for {hindcast_used}/{matched} sailings{maint_note}")
        print(f"  Accuracy: {accuracy_rate:.1f}%  "
              f"Precision: {precision:.3f}  Recall: {recall:.3f}  F1: {f1:.3f}")
        print(f"  TP={tp_ex} TN={tn_ex} FP={fp_ex} FN={fn_ex} (excl. maintenance)")

        return {
            'date':                  target_date,
            'matched':               matched,
            'correct':               correct,
            'accuracy_rate':         accuracy_rate,
            'true_positives':        tp_ex,
            'true_negatives':        tn_ex,
            'false_positives':       fp_ex,
            'false_negatives':       fn_ex,
            'precision':             precision,
            'recall':                recall,
            'f1_score':              f1,
            'is_likely_maintenance': is_maint_day,
        }

    # ------------------------------------------------------------------
    def calculate_weekly_summary(self) -> Dict:
        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        end_date   = datetime.now(self.jst)
        start_date = end_date - timedelta(days=7)

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN false_positive = 1 THEN 1 ELSE 0 END) as fp,
                SUM(CASE WHEN false_negative = 1 THEN 1 ELSE 0 END) as fn
            FROM unified_operation_accuracy
            WHERE operation_date >= ?
              AND operation_date <  ?
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            total, correct, fp, fn = row
            accuracy = (correct / total * 100) if total > 0 else 0
            return {
                'period':          f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'total':           total,
                'correct':         correct,
                'accuracy_rate':   accuracy,
                'false_positives': fp,
                'false_negatives': fn,
            }
        return {}

    def generate_report(self) -> str:
        report = []
        report.append("=" * 80)
        report.append("UNIFIED ACCURACY TRACKER REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now(self.jst).strftime('%Y-%m-%d %H:%M:%S JST')}")
        report.append("")

        yesterday = (datetime.now(self.jst) - timedelta(days=1)).strftime('%Y-%m-%d')
        daily_result = self.calculate_daily_accuracy(yesterday)

        if daily_result:
            report.append(f"Daily Accuracy ({yesterday}):")
            report.append(f"  Sailings matched: {daily_result['matched']}")
            report.append(f"  Accuracy: {daily_result['accuracy_rate']:.1f}%")
            report.append(f"  Precision: {daily_result['precision']:.3f}")
            report.append(f"  Recall:    {daily_result['recall']:.3f}")
            report.append(f"  F1 Score:  {daily_result['f1_score']:.3f}")
            report.append("")

        weekly = self.calculate_weekly_summary()
        if weekly:
            report.append("Weekly Summary (Last 7 days):")
            report.append(f"  Period: {weekly['period']}")
            report.append(f"  Total sailings: {weekly['total']}")
            report.append(f"  Accuracy: {weekly['accuracy_rate']:.1f}%")
            report.append(f"  False Positives: {weekly['false_positives']}")
            report.append(f"  False Negatives: {weekly['false_negatives']}")
            report.append("")

        report.append("=" * 80)
        return "\n".join(report)


# ------------------------------------------------------------------
def main():
    """
    Usage:
        python unified_accuracy_tracker.py                        # yesterday only
        python unified_accuracy_tracker.py 2026-04-05            # single date
        python unified_accuracy_tracker.py 2026-04-05 2026-04-18 # date range
    """
    from datetime import date as date_cls

    print("Starting Unified Accuracy Tracker...")
    print("=" * 80)

    jst = pytz.timezone('Asia/Tokyo')
    yesterday_str = (datetime.now(jst) - timedelta(days=1)).strftime('%Y-%m-%d')

    args = sys.argv[1:]
    if len(args) >= 2:
        start_str, end_str = args[0], args[1]
    elif len(args) == 1:
        start_str = end_str = args[0]
    else:
        start_str = end_str = yesterday_str

    tracker = UnifiedAccuracyTracker()

    current  = date_cls.fromisoformat(start_str)
    end_d    = date_cls.fromisoformat(end_str)
    days_done = 0
    while current <= end_d:
        tracker.calculate_daily_accuracy(current.strftime('%Y-%m-%d'))
        current   += timedelta(days=1)
        days_done += 1

    print(f"\nProcessed {days_done} day(s) from {start_str} to {end_str}")

    report = tracker.generate_report()
    print("\n")
    print(report)

    report_dir  = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    report_file = os.path.join(report_dir, 'accuracy_report.txt')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {report_file}")
    print("\nUnified Accuracy Tracker completed successfully!")


if __name__ == '__main__':
    main()
