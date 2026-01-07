#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferry Operation Forecast Accuracy Calculator
Compares sailing risk predictions with actual ferry operations
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
from datetime import datetime, timedelta
from typing import Dict
import os

class OperationAccuracyCalculator:
    """Calculate ferry operation forecast accuracy"""

    def __init__(self):
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
        self.forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.actual_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

    def init_tables(self):
        """Initialize accuracy tracking tables if they don't exist"""

        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        # Operation Accuracy Table (individual sailing predictions)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_date DATE NOT NULL,
                route TEXT NOT NULL,
                departure_time TEXT NOT NULL,

                -- Predicted values
                predicted_risk_level TEXT,
                predicted_risk_score REAL,
                predicted_wind REAL,
                predicted_wave REAL,
                predicted_visibility REAL,

                -- Actual values
                actual_status TEXT,

                -- Accuracy
                correct_prediction BOOLEAN,
                prediction_type TEXT,

                -- Metadata
                forecast_generated_at TEXT,
                actual_collected_at TEXT,

                UNIQUE(operation_date, route, departure_time)
            )
        ''')

        # Daily Accuracy Summary Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_accuracy_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date DATE NOT NULL UNIQUE,

                total_predictions INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                accuracy_rate REAL DEFAULT 0,

                -- Detailed metrics
                precision REAL DEFAULT 0,
                recall REAL DEFAULT 0,
                f1_score REAL DEFAULT 0,

                -- Confusion matrix
                true_positives INTEGER DEFAULT 0,
                true_negatives INTEGER DEFAULT 0,
                false_positives INTEGER DEFAULT 0,
                false_negatives INTEGER DEFAULT 0,

                calculated_at TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

        print("[OK] Operation accuracy tables initialized")

    def calculate_daily_accuracy(self, date: str) -> Dict:
        """
        Calculate operation forecast accuracy for a specific date

        Args:
            date: Date to evaluate (YYYY-MM-DD)

        Returns:
            Dictionary with accuracy metrics
        """
        if not os.path.exists(self.actual_db):
            print(f"[WARNING] Actual operations database not found: {self.actual_db}")
            return {'date': date, 'error': 'No actual data available'}

        # Connect to databases
        forecast_conn = sqlite3.connect(self.forecast_db)
        forecast_cursor = forecast_conn.cursor()

        actual_conn = sqlite3.connect(self.actual_db)
        actual_cursor = actual_conn.cursor()

        # Get predictions from sailing_forecast
        forecast_cursor.execute('''
            SELECT route, departure_time, risk_level, risk_score,
                   wind_forecast, wave_forecast, visibility_forecast
            FROM sailing_forecast
            WHERE forecast_date = ?
        ''', (date,))

        predictions = {f"{row[0]}_{row[1]}": row for row in forecast_cursor.fetchall()}

        # Get actual operations from ferry_status table
        actual_cursor.execute('''
            SELECT route, departure_time, operational_status, is_cancelled
            FROM ferry_status
            WHERE scrape_date = ?
        ''', (date,))

        actual_operations = {}
        for row in actual_cursor.fetchall():
            route, dept_time, status, is_cancelled = row
            key = f"{route}_{dept_time}"
            actual_operations[key] = {
                'status': status,
                'cancelled': bool(is_cancelled)
            }

        # Confusion matrix
        tp = tn = fp = fn = 0
        evaluated = 0

        for key, pred in predictions.items():
            if key not in actual_operations:
                continue  # No actual data for this sailing

            route, dept_time, risk_level, risk_score, wind, wave, vis = pred
            actual = actual_operations[key]
            evaluated += 1

            # HIGH/MEDIUM = predict cancellation
            predicted_cancel = (risk_level in ['HIGH', 'MEDIUM'])
            actual_cancel = actual['cancelled']

            # Determine prediction type
            if predicted_cancel and actual_cancel:
                pred_type = 'TP'
                tp += 1
                correct = True
            elif not predicted_cancel and not actual_cancel:
                pred_type = 'TN'
                tn += 1
                correct = True
            elif predicted_cancel and not actual_cancel:
                pred_type = 'FP'
                fp += 1
                correct = False
            else:
                pred_type = 'FN'
                fn += 1
                correct = False

            # Store individual result
            forecast_cursor.execute('''
                INSERT OR REPLACE INTO operation_accuracy
                (operation_date, route, departure_time,
                 predicted_risk_level, predicted_risk_score,
                 predicted_wind, predicted_wave, predicted_visibility,
                 actual_status, correct_prediction, prediction_type,
                 forecast_generated_at, actual_collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (date, route, dept_time, risk_level, risk_score,
                  wind, wave, vis, actual['status'], correct, pred_type,
                  datetime.now().isoformat(), datetime.now().isoformat()))

        # Calculate metrics
        total = evaluated
        correct_total = tp + tn
        accuracy = (correct_total / total * 100) if total > 0 else 0
        precision = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0
        recall = (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

        # Store daily summary
        forecast_cursor.execute('''
            INSERT OR REPLACE INTO daily_accuracy_summary
            (summary_date, total_predictions, correct_predictions,
             accuracy_rate, precision, recall, f1_score,
             true_positives, true_negatives, false_positives, false_negatives,
             calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, total, correct_total, accuracy, precision, recall, f1,
              tp, tn, fp, fn, datetime.now().isoformat()))

        forecast_conn.commit()
        forecast_conn.close()
        actual_conn.close()

        results = {
            'date': date,
            'total_sailings': total,
            'evaluated': evaluated,
            'correct': correct_total,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'tp': tp,
            'tn': tn,
            'fp': fp,
            'fn': fn
        }

        if total > 0:
            print(f"[OK] Operation accuracy for {date}: {accuracy:.1f}% ({correct_total}/{total})")
            print(f"     Precision: {precision:.1f}%, Recall: {recall:.1f}%, F1: {f1:.1f}")
            print(f"     TP: {tp}, TN: {tn}, FP: {fp}, FN: {fn}")
        else:
            print(f"[INFO] No sailings evaluated for {date}")

        return results

if __name__ == "__main__":
    print("=" * 80)
    print("FERRY OPERATION FORECAST ACCURACY CALCULATOR")
    print("=" * 80)

    calculator = OperationAccuracyCalculator()

    # Initialize tables
    print("\n[INFO] Initializing accuracy tracking tables...")
    calculator.init_tables()

    # Calculate for yesterday
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

    print(f"\n[INFO] Calculating operation forecast accuracy for {yesterday}...")
    results = calculator.calculate_daily_accuracy(yesterday)

    print("\n[SUCCESS] Accuracy calculation completed")
