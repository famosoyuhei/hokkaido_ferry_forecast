#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Accuracy Tracker
Integrates multiple databases to calculate comprehensive accuracy metrics
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pytz

class UnifiedAccuracyTracker:
    """Unified accuracy tracking across multiple databases"""

    def __init__(self):
        # Database paths
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.real_data_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

        # Initialize tables
        self.init_accuracy_tables()

        # JST timezone
        self.jst = pytz.timezone('Asia/Tokyo')

        print(f"Initialized UnifiedAccuracyTracker")
        print(f"  Forecast DB: {self.forecast_db}")
        print(f"  Real Data DB: {self.real_data_db}")

    def init_accuracy_tables(self):
        """Initialize accuracy tracking tables"""
        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        # Unified operation accuracy table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_operation_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_date TEXT NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT,

                -- Prediction
                predicted_risk TEXT,
                predicted_score REAL,
                predicted_wind REAL,
                predicted_wave REAL,
                predicted_visibility REAL,

                -- Actual
                actual_status TEXT,  -- OPERATED or CANCELLED
                actual_wind REAL,
                actual_wave REAL,
                actual_visibility REAL,

                -- Accuracy metrics
                is_correct BOOLEAN,
                false_positive BOOLEAN,  -- Predicted HIGH but operated
                false_negative BOOLEAN,  -- Predicted LOW but cancelled
                prediction_error REAL,

                -- Metadata
                calculated_at TEXT,
                data_source TEXT,

                UNIQUE(operation_date, route, departure_time)
            )
        ''')

        # Daily summary table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date TEXT NOT NULL UNIQUE,

                -- Overall metrics
                total_predictions INTEGER,
                correct_predictions INTEGER,
                accuracy_rate REAL,

                -- Confusion matrix
                true_positives INTEGER,   -- Predicted HIGH, actually cancelled
                true_negatives INTEGER,   -- Predicted LOW, actually operated
                false_positives INTEGER,  -- Predicted HIGH, actually operated
                false_negatives INTEGER,  -- Predicted LOW, actually cancelled

                -- Derived metrics
                precision_score REAL,  -- TP / (TP + FP)
                recall_score REAL,     -- TP / (TP + FN)
                f1_score REAL,         -- 2 * (precision * recall) / (precision + recall)

                -- Weather accuracy
                avg_wind_error REAL,
                avg_wave_error REAL,
                avg_visibility_error REAL,

                calculated_at TEXT
            )
        ''')

        # Risk level accuracy table
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

    def calculate_daily_accuracy(self, target_date: Optional[str] = None) -> Dict:
        """Calculate accuracy for a specific date"""

        if target_date is None:
            # Yesterday (data should be available)
            yesterday = datetime.now(self.jst) - timedelta(days=1)
            target_date = yesterday.strftime('%Y-%m-%d')

        print(f"\nCalculating accuracy for {target_date}...")

        # Get predictions from cancellation_forecast
        forecast_conn = sqlite3.connect(self.forecast_db)
        forecast_cursor = forecast_conn.cursor()

        forecast_cursor.execute('''
            SELECT DISTINCT
                forecast_for_date,
                route,
                risk_level,
                risk_score,
                wind_forecast,
                wave_forecast,
                visibility_forecast
            FROM cancellation_forecast
            WHERE forecast_for_date = ?
        ''', (target_date,))

        predictions = forecast_cursor.fetchall()
        print(f"  Found {len(predictions)} predictions from cancellation_forecast")

        if not predictions:
            print(f"  No predictions found for {target_date}")
            forecast_conn.close()
            return {}

        # Get actual operations from real data DB
        real_conn = sqlite3.connect(self.real_data_db)
        real_cursor = real_conn.cursor()

        real_cursor.execute('''
            SELECT
                scrape_date,
                route,
                departure_time,
                operational_status,
                is_cancelled
            FROM ferry_status_enhanced
            WHERE scrape_date = ?
        ''', (target_date,))

        # Group actual operations by route
        actual_ops_by_route = {}
        for row in real_cursor.fetchall():
            date, route, dep_time, status, is_cancelled = row
            if route not in actual_ops_by_route:
                actual_ops_by_route[route] = []
            actual_ops_by_route[route].append({
                'departure_time': dep_time,
                'status': 'CANCELLED' if is_cancelled else 'OPERATED',
                'is_cancelled': is_cancelled
            })

        real_conn.close()
        print(f"  Found {sum(len(ops) for ops in actual_ops_by_route.values())} actual operations across {len(actual_ops_by_route)} routes")

        # Match predictions with actual
        matched = 0
        correct = 0
        false_positives = 0
        false_negatives = 0
        true_positives = 0
        true_negatives = 0

        unified_conn = sqlite3.connect(self.forecast_db)
        unified_cursor = unified_conn.cursor()

        for pred in predictions:
            pred_date, route, risk, score, wind, wave, vis = pred

            if route in actual_ops_by_route:
                # Route-level matching (since cancellation_forecast is per route, not per sailing)
                route_ops = actual_ops_by_route[route]

                # Count how many sailings were cancelled vs operated
                cancelled_count = sum(1 for op in route_ops if op['is_cancelled'])
                operated_count = len(route_ops) - cancelled_count

                # Route is considered "cancelled" if majority of sailings were cancelled
                route_mostly_cancelled = cancelled_count > operated_count

                # Determine if prediction was correct
                predicted_high_risk = risk in ['HIGH', 'MEDIUM']

                is_correct = (predicted_high_risk and route_mostly_cancelled) or \
                             (not predicted_high_risk and not route_mostly_cancelled)

                # Confusion matrix
                if predicted_high_risk and route_mostly_cancelled:
                    true_positives += 1
                elif predicted_high_risk and not route_mostly_cancelled:
                    false_positives += 1
                elif not predicted_high_risk and route_mostly_cancelled:
                    false_negatives += 1
                else:
                    true_negatives += 1

                if is_correct:
                    correct += 1

                matched += 1

                # Store one record per route (not per sailing)
                unified_cursor.execute('''
                    INSERT OR REPLACE INTO unified_operation_accuracy
                    (operation_date, route, departure_time,
                     predicted_risk, predicted_score, predicted_wind, predicted_wave, predicted_visibility,
                     actual_status, is_correct, false_positive, false_negative,
                     calculated_at, data_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pred_date, route, f"{cancelled_count}/{len(route_ops)} cancelled",
                    risk, score, wind, wave, vis,
                    'MOSTLY_CANCELLED' if route_mostly_cancelled else 'MOSTLY_OPERATED',
                    is_correct,
                    predicted_high_risk and not route_mostly_cancelled,
                    not predicted_high_risk and route_mostly_cancelled,
                    datetime.now(self.jst).isoformat(),
                    'heartland_ferry'
                ))

        unified_conn.commit()

        # Calculate metrics
        accuracy_rate = (correct / matched * 100) if matched > 0 else 0
        precision = (true_positives / (true_positives + false_positives)) if (true_positives + false_positives) > 0 else 0
        recall = (true_positives / (true_positives + false_negatives)) if (true_positives + false_negatives) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

        # Store daily summary
        unified_cursor.execute('''
            INSERT OR REPLACE INTO unified_daily_summary
            (summary_date, total_predictions, correct_predictions, accuracy_rate,
             true_positives, true_negatives, false_positives, false_negatives,
             precision_score, recall_score, f1_score, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            target_date, matched, correct, accuracy_rate,
            true_positives, true_negatives, false_positives, false_negatives,
            precision, recall, f1,
            datetime.now(self.jst).isoformat()
        ))

        unified_conn.commit()
        unified_conn.close()
        forecast_conn.close()

        results = {
            'date': target_date,
            'matched': matched,
            'correct': correct,
            'accuracy_rate': accuracy_rate,
            'true_positives': true_positives,
            'true_negatives': true_negatives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'precision': precision,
            'recall': recall,
            'f1_score': f1
        }

        print(f"\n  Results:")
        print(f"    Matched: {matched}")
        print(f"    Correct: {correct}")
        print(f"    Accuracy: {accuracy_rate:.1f}%")
        print(f"    Precision: {precision:.3f}")
        print(f"    Recall: {recall:.3f}")
        print(f"    F1 Score: {f1:.3f}")

        return results

    def calculate_weekly_summary(self) -> Dict:
        """Calculate weekly summary"""
        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        # Last 7 days
        end_date = datetime.now(self.jst)
        start_date = end_date - timedelta(days=7)

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN false_positive = 1 THEN 1 ELSE 0 END) as fp,
                SUM(CASE WHEN false_negative = 1 THEN 1 ELSE 0 END) as fn
            FROM unified_operation_accuracy
            WHERE operation_date >= ?
            AND operation_date < ?
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            total, correct, fp, fn = row
            accuracy = (correct / total * 100) if total > 0 else 0

            return {
                'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'total': total,
                'correct': correct,
                'accuracy_rate': accuracy,
                'false_positives': fp,
                'false_negatives': fn
            }
        else:
            return {}

    def generate_report(self) -> str:
        """Generate accuracy report"""
        report = []
        report.append("=" * 80)
        report.append("UNIFIED ACCURACY TRACKER REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now(self.jst).strftime('%Y-%m-%d %H:%M:%S JST')}")
        report.append("")

        # Yesterday's accuracy
        yesterday = (datetime.now(self.jst) - timedelta(days=1)).strftime('%Y-%m-%d')
        daily_result = self.calculate_daily_accuracy(yesterday)

        if daily_result:
            report.append(f"Daily Accuracy ({yesterday}):")
            report.append(f"  Predictions matched: {daily_result['matched']}")
            report.append(f"  Accuracy: {daily_result['accuracy_rate']:.1f}%")
            report.append(f"  Precision: {daily_result['precision']:.3f}")
            report.append(f"  Recall: {daily_result['recall']:.3f}")
            report.append(f"  F1 Score: {daily_result['f1_score']:.3f}")
            report.append("")

        # Weekly summary
        weekly = self.calculate_weekly_summary()
        if weekly:
            report.append("Weekly Summary (Last 7 days):")
            report.append(f"  Period: {weekly['period']}")
            report.append(f"  Total predictions: {weekly['total']}")
            report.append(f"  Accuracy: {weekly['accuracy_rate']:.1f}%")
            report.append(f"  False Positives: {weekly['false_positives']}")
            report.append(f"  False Negatives: {weekly['false_negatives']}")
            report.append("")

        report.append("=" * 80)

        return "\n".join(report)


def main():
    """Main execution"""
    print("Starting Unified Accuracy Tracker...")
    print("=" * 80)

    tracker = UnifiedAccuracyTracker()

    # Calculate yesterday's accuracy
    yesterday = (datetime.now(pytz.timezone('Asia/Tokyo')) - timedelta(days=1)).strftime('%Y-%m-%d')
    tracker.calculate_daily_accuracy(yesterday)

    # Generate and print report
    report = tracker.generate_report()
    print("\n")
    print(report)

    # Save report to file
    report_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    report_file = os.path.join(report_dir, "accuracy_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nReport saved to: {report_file}")
    print("\nUnified Accuracy Tracker completed successfully!")


if __name__ == '__main__':
    main()
