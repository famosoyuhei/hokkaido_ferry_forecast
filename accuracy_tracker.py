#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferry Forecast Accuracy Tracker
Compares predictions with actual ferry operations to measure accuracy
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class AccuracyTracker:
    """Track and analyze forecast accuracy"""

    def __init__(self):
        # Database files
        import os
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.actual_db = os.path.join(data_dir, "ferry_actual_operations.db")

        # Initialize databases
        self.init_databases()

        # Heartland Ferry status URL
        self.status_url = "https://heartlandferry.jp/status/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Route mappings
        self.routes = [
            'wakkanai_oshidomari',
            'wakkanai_kafuka',
            'oshidomari_wakkanai',
            'kafuka_wakkanai',
            'oshidomari_kafuka',
            'kafuka_oshidomari'
        ]

    def init_databases(self):
        """Initialize actual operations database"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        # Actual ferry operations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actual_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_date DATE NOT NULL,
                route TEXT NOT NULL,

                status TEXT NOT NULL,  -- OPERATING, CANCELLED, DELAYED
                cancellation_reason TEXT,

                actual_wind_speed REAL,
                actual_wave_height REAL,
                actual_visibility REAL,
                actual_weather TEXT,

                collected_at TEXT NOT NULL,
                data_source TEXT,

                UNIQUE(operation_date, route, collected_at)
            )
        ''')

        # Accuracy metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accuracy_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                route TEXT NOT NULL,

                predicted_risk_level TEXT,
                predicted_risk_score REAL,
                actual_status TEXT,

                correct_prediction BOOLEAN,
                false_positive BOOLEAN,  -- Predicted cancellation but operated
                false_negative BOOLEAN,  -- Predicted safe but cancelled

                prediction_error REAL,  -- Difference between risk score and actual outcome

                calculated_at TEXT NOT NULL,

                UNIQUE(date, route)
            )
        ''')

        # Daily accuracy summary
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accuracy_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,

                total_predictions INTEGER,
                correct_predictions INTEGER,
                false_positives INTEGER,
                false_negatives INTEGER,

                accuracy_rate REAL,
                precision REAL,  -- TP / (TP + FP)
                recall REAL,     -- TP / (TP + FN)
                f1_score REAL,

                calculated_at TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()
        print("[OK] Accuracy tracking database initialized")

    def collect_actual_operations(self, date: str = None) -> int:
        """Collect actual ferry operation status for a specific date"""

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n[INFO] Collecting actual operations for {date}")

        try:
            # Scrape Heartland Ferry status page
            response = requests.get(self.status_url, headers=self.headers, timeout=30, verify=False)

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            # Parse status
            status = self._parse_ferry_status(response.text, date)

            # Save to database
            saved = self._save_actual_operations(status, date)

            print(f"[OK] Saved {saved} actual operation records")
            return saved

        except Exception as e:
            print(f"[ERROR] Failed to collect actual operations: {e}")
            return 0

    def _parse_ferry_status(self, html_text: str, date: str) -> Dict[str, str]:
        """Parse ferry status from HTML"""

        status = {}

        # Simple heuristic: check for cancellation keywords
        if "欠航" in html_text:
            # Assume all routes cancelled if general cancellation notice
            for route in self.routes:
                status[route] = "CANCELLED"
        elif "遅延" in html_text:
            for route in self.routes:
                status[route] = "DELAYED"
        else:
            # Assume operating if no cancellation notice
            for route in self.routes:
                status[route] = "OPERATING"

        return status

    def _save_actual_operations(self, status: Dict[str, str], date: str) -> int:
        """Save actual operations to database"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        saved = 0
        collected_at = datetime.now().isoformat()

        for route, operation_status in status.items():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO actual_operations (
                        operation_date, route, status,
                        collected_at, data_source
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (date, route, operation_status, collected_at, 'heartland_ferry'))

                saved += 1
            except Exception as e:
                print(f"[WARNING] Failed to save {route}: {e}")

        conn.commit()
        conn.close()

        return saved

    def calculate_accuracy(self, date: str = None) -> Dict:
        """Calculate accuracy for a specific date"""

        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"\n[INFO] Calculating accuracy for {date}")

        # Get predictions
        predictions = self._get_predictions(date)

        # Get actual operations
        actuals = self._get_actual_operations(date)

        if not predictions or not actuals:
            print(f"[WARNING] Insufficient data for {date}")
            return {}

        # Compare and calculate metrics
        metrics = self._compare_predictions(predictions, actuals, date)

        # Save metrics
        self._save_accuracy_metrics(metrics, date)

        # Calculate daily summary
        summary = self._calculate_daily_summary(date)

        print(f"[OK] Accuracy: {summary.get('accuracy_rate', 0):.1%}")

        return summary

    def _get_predictions(self, date: str) -> Dict:
        """Get predictions for a date"""

        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT route, risk_level, risk_score
            FROM cancellation_forecast
            WHERE forecast_for_date = ?
            GROUP BY route
        ''', (date,))

        predictions = {}
        for row in cursor.fetchall():
            route, risk_level, risk_score = row
            predictions[route] = {
                'risk_level': risk_level,
                'risk_score': risk_score
            }

        conn.close()
        return predictions

    def _get_actual_operations(self, date: str) -> Dict:
        """Get actual operations for a date"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT route, status
            FROM actual_operations
            WHERE operation_date = ?
        ''', (date,))

        actuals = {}
        for row in cursor.fetchall():
            route, status = row
            actuals[route] = status

        conn.close()
        return actuals

    def _compare_predictions(self, predictions: Dict, actuals: Dict, date: str) -> List[Dict]:
        """Compare predictions with actuals"""

        metrics = []

        for route in self.routes:
            if route not in predictions or route not in actuals:
                continue

            pred = predictions[route]
            actual = actuals[route]

            # Determine if prediction was correct
            predicted_cancellation = pred['risk_level'] in ['HIGH', 'MEDIUM']
            actual_cancellation = actual in ['CANCELLED', 'DELAYED']

            correct = (predicted_cancellation and actual_cancellation) or \
                     (not predicted_cancellation and not actual_cancellation)

            false_positive = predicted_cancellation and not actual_cancellation
            false_negative = not predicted_cancellation and actual_cancellation

            # Calculate prediction error
            # Map actual status to score: CANCELLED=100, DELAYED=50, OPERATING=0
            actual_score = 100 if actual == 'CANCELLED' else (50 if actual == 'DELAYED' else 0)
            error = abs(pred['risk_score'] - actual_score)

            metrics.append({
                'route': route,
                'predicted_risk_level': pred['risk_level'],
                'predicted_risk_score': pred['risk_score'],
                'actual_status': actual,
                'correct': correct,
                'false_positive': false_positive,
                'false_negative': false_negative,
                'error': error
            })

        return metrics

    def _save_accuracy_metrics(self, metrics: List[Dict], date: str):
        """Save accuracy metrics to database"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        calculated_at = datetime.now().isoformat()

        for metric in metrics:
            cursor.execute('''
                INSERT OR REPLACE INTO accuracy_metrics (
                    date, route,
                    predicted_risk_level, predicted_risk_score, actual_status,
                    correct_prediction, false_positive, false_negative,
                    prediction_error, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, metric['route'],
                metric['predicted_risk_level'], metric['predicted_risk_score'], metric['actual_status'],
                metric['correct'], metric['false_positive'], metric['false_negative'],
                metric['error'], calculated_at
            ))

        conn.commit()
        conn.close()

    def _calculate_daily_summary(self, date: str) -> Dict:
        """Calculate daily accuracy summary"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN correct_prediction = 1 THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN false_positive = 1 THEN 1 ELSE 0 END) as fp,
                SUM(CASE WHEN false_negative = 1 THEN 1 ELSE 0 END) as fn
            FROM accuracy_metrics
            WHERE date = ?
        ''', (date,))

        row = cursor.fetchone()
        total, correct, fp, fn = row

        if total == 0:
            return {}

        tp = correct - (total - fp - fn)  # True positives

        accuracy = correct / total
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Save summary
        calculated_at = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO accuracy_summary (
                date, total_predictions, correct_predictions,
                false_positives, false_negatives,
                accuracy_rate, precision, recall, f1_score,
                calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, total, correct, fp, fn, accuracy, precision, recall, f1, calculated_at))

        conn.commit()
        conn.close()

        return {
            'date': date,
            'total_predictions': total,
            'correct_predictions': correct,
            'false_positives': fp,
            'false_negatives': fn,
            'accuracy_rate': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1
        }

    def get_overall_accuracy(self, days: int = 30) -> Dict:
        """Get overall accuracy metrics for the last N days"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT
                COUNT(*) as days,
                AVG(accuracy_rate) as avg_accuracy,
                AVG(precision) as avg_precision,
                AVG(recall) as avg_recall,
                AVG(f1_score) as avg_f1,
                SUM(total_predictions) as total_pred,
                SUM(correct_predictions) as total_correct
            FROM accuracy_summary
            WHERE date >= ?
        ''', (start_date,))

        row = cursor.fetchone()
        conn.close()

        if not row or row[0] == 0:
            return {
                'days_tracked': 0,
                'message': 'No accuracy data available yet'
            }

        return {
            'days_tracked': row[0],
            'average_accuracy': row[1],
            'average_precision': row[2],
            'average_recall': row[3],
            'average_f1_score': row[4],
            'total_predictions': row[5],
            'total_correct': row[6]
        }

def main():
    """Main execution"""

    print("=" * 80)
    print("FERRY FORECAST ACCURACY TRACKER")
    print("=" * 80)

    tracker = AccuracyTracker()

    # Collect today's actual operations
    today = datetime.now().strftime('%Y-%m-%d')
    tracker.collect_actual_operations(today)

    # Calculate accuracy for yesterday (predictions should exist)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    tracker.calculate_accuracy(yesterday)

    # Show overall accuracy
    print("\n" + "=" * 80)
    print("OVERALL ACCURACY (Last 30 Days)")
    print("=" * 80)

    overall = tracker.get_overall_accuracy(30)

    if overall.get('days_tracked', 0) > 0:
        print(f"\n📊 Days tracked: {overall['days_tracked']}")
        print(f"📈 Average accuracy: {overall['average_accuracy']:.1%}")
        print(f"🎯 Average precision: {overall['average_precision']:.1%}")
        print(f"🔍 Average recall: {overall['average_recall']:.1%}")
        print(f"⚖️  Average F1 score: {overall['average_f1_score']:.3f}")
        print(f"✅ Total predictions: {overall['total_predictions']}")
        print(f"✔️  Total correct: {overall['total_correct']}")
    else:
        print(f"\n⏳ {overall.get('message', 'Starting accuracy tracking...')}")

    print("\n" + "=" * 80)
    print("✅ Accuracy tracking completed")
    print("=" * 80)

if __name__ == '__main__':
    main()
