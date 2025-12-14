#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prediction Accuracy Improvement System
Links predictions with actual operations to continuously improve forecast accuracy
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class PredictionAccuracySystem:
    """System to match predictions with actual results and improve accuracy"""

    def __init__(self):
        # Database paths
        import os
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.actual_db = os.path.join(data_dir, "ferry_actual_operations.db")
        self.accuracy_db = os.path.join(data_dir, "prediction_accuracy.db")

        # Initialize databases
        self.init_accuracy_database()

        # Route mappings for consistency
        self.route_mappings = {
            "wakkanai_oshidomari": "稚内⇔鴛泊",
            "oshidomari_wakkanai": "鴛泊⇔稚内",
            "wakkanai_kafuka": "稚内⇔香深",
            "kafuka_wakkanai": "香深⇔稚内",
            "oshidomari_kafuka": "鴛泊⇔香深",
            "kafuka_oshidomari": "香深⇔鴛泊"
        }

        # Risk thresholds (will be adapted over time)
        self.risk_thresholds = {
            'wind_speed': 15.0,      # m/s
            'wave_height': 3.0,      # m
            'visibility': 1.0,       # km
            'temperature': -10.0     # °C (lower bound)
        }

        # Model weights (will be adjusted based on accuracy)
        self.model_weights = {
            'wind_speed': 0.40,
            'wave_height': 0.35,
            'visibility': 0.15,
            'temperature': 0.10
        }

    def init_accuracy_database(self):
        """Initialize the accuracy improvement database"""

        conn = sqlite3.connect(self.accuracy_db)
        cursor = conn.cursor()

        # Matched predictions vs actuals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prediction_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_date DATE NOT NULL,
                route TEXT NOT NULL,

                -- Prediction data
                predicted_risk_level TEXT,
                predicted_risk_score REAL,
                predicted_cancellation BOOLEAN,
                prediction_confidence REAL,

                -- Weather conditions at prediction time
                pred_wind_speed REAL,
                pred_wave_height REAL,
                pred_visibility REAL,
                pred_temperature REAL,

                -- Actual outcome
                actual_status TEXT,  -- OPERATING, CANCELLED, DELAYED
                actual_cancellation BOOLEAN,

                -- Accuracy metrics
                prediction_correct BOOLEAN,
                false_positive BOOLEAN,
                false_negative BOOLEAN,
                prediction_error REAL,

                -- Metadata
                matched_at TEXT NOT NULL,

                UNIQUE(match_date, route)
            )
        ''')

        # Model performance over time
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_date DATE NOT NULL UNIQUE,

                -- Overall metrics
                total_predictions INTEGER,
                correct_predictions INTEGER,
                accuracy_rate REAL,

                -- Classification metrics
                true_positives INTEGER,
                true_negatives INTEGER,
                false_positives INTEGER,
                false_negatives INTEGER,
                precision_score REAL,
                recall_score REAL,
                f1_score REAL,

                -- Error metrics
                mean_absolute_error REAL,
                root_mean_squared_error REAL,

                -- Calibration
                calibration_score REAL,

                calculated_at TEXT NOT NULL
            )
        ''')

        # Threshold adjustments history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threshold_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_date DATE NOT NULL,
                parameter_name TEXT NOT NULL,
                old_value REAL,
                new_value REAL,
                reason TEXT,
                impact_estimate REAL,
                created_at TEXT NOT NULL
            )
        ''')

        # Model weight adjustments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weight_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_date DATE NOT NULL,
                weights_json TEXT NOT NULL,
                accuracy_before REAL,
                accuracy_after REAL,
                created_at TEXT NOT NULL
            )
        ''')

        # Accuracy improvement log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS improvement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date DATE NOT NULL,
                improvement_type TEXT NOT NULL,
                description TEXT,
                metric_name TEXT,
                value_before REAL,
                value_after REAL,
                improvement_percentage REAL,
                created_at TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()
        print("[OK] Accuracy improvement database initialized")

    def match_predictions_with_actuals(self, lookback_days: int = 7) -> int:
        """Match predictions with actual operations for the last N days"""

        print(f"\n{'='*80}")
        print(f"MATCHING PREDICTIONS WITH ACTUAL OPERATIONS")
        print(f"{'='*80}")

        matched_count = 0

        # Get date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)

        print(f"Period: {start_date} to {end_date}")

        # Get predictions
        predictions = self._get_predictions(start_date, end_date)
        print(f"Found {len(predictions)} predictions")

        # Get actual operations
        actuals = self._get_actual_operations(start_date, end_date)
        print(f"Found {len(actuals)} actual operation records")

        if not predictions or not actuals:
            print("[WARNING] Insufficient data for matching")
            return 0

        # Match by date and route
        conn = sqlite3.connect(self.accuracy_db)
        cursor = conn.cursor()

        for (date, route), pred in predictions.items():
            actual = actuals.get((date, route))

            if actual is None:
                continue

            # Determine if prediction was correct
            predicted_cancellation = pred['risk_level'] in ['HIGH', 'MEDIUM']
            actual_cancellation = actual['status'] in ['CANCELLED', 'DELAYED']

            correct = (predicted_cancellation and actual_cancellation) or \
                     (not predicted_cancellation and not actual_cancellation)

            false_positive = predicted_cancellation and not actual_cancellation
            false_negative = not predicted_cancellation and actual_cancellation

            # Calculate prediction error
            actual_score = 100 if actual['status'] == 'CANCELLED' else \
                          50 if actual['status'] == 'DELAYED' else 0
            error = abs(pred['risk_score'] - actual_score)

            # Insert or update match
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO prediction_matches (
                        match_date, route,
                        predicted_risk_level, predicted_risk_score,
                        predicted_cancellation, prediction_confidence,
                        pred_wind_speed, pred_wave_height,
                        pred_visibility, pred_temperature,
                        actual_status, actual_cancellation,
                        prediction_correct, false_positive, false_negative,
                        prediction_error, matched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    date, route,
                    pred['risk_level'], pred['risk_score'],
                    predicted_cancellation, pred.get('confidence', 0.8),
                    pred.get('wind_speed', 0), pred.get('wave_height', 0),
                    pred.get('visibility', 10), pred.get('temperature', 10),
                    actual['status'], actual_cancellation,
                    correct, false_positive, false_negative,
                    error, datetime.now().isoformat()
                ))
                matched_count += 1
            except Exception as e:
                print(f"[WARNING] Failed to match {date} {route}: {e}")

        conn.commit()
        conn.close()

        print(f"[OK] Successfully matched {matched_count} predictions with actuals")
        return matched_count

    def _get_predictions(self, start_date, end_date) -> Dict:
        """Get predictions from forecast database"""

        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                forecast_for_date, route,
                risk_level, risk_score, confidence,
                wind_forecast, wave_forecast,
                visibility_forecast, temperature_forecast
            FROM cancellation_forecast
            WHERE forecast_for_date BETWEEN ? AND ?
            GROUP BY forecast_for_date, route
        ''', (str(start_date), str(end_date)))

        predictions = {}
        for row in cursor.fetchall():
            date = datetime.strptime(row[0], '%Y-%m-%d').date() if isinstance(row[0], str) else row[0]
            route = row[1]

            predictions[(date, route)] = {
                'risk_level': row[2],
                'risk_score': row[3],
                'confidence': row[4] if row[4] else 0.8,
                'wind_speed': row[5],
                'wave_height': row[6],
                'visibility': row[7],
                'temperature': row[8]
            }

        conn.close()
        return predictions

    def _get_actual_operations(self, start_date, end_date) -> Dict:
        """Get actual operations from operations database"""

        conn = sqlite3.connect(self.actual_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT operation_date, route, status
            FROM actual_operations
            WHERE operation_date BETWEEN ? AND ?
        ''', (str(start_date), str(end_date)))

        actuals = {}
        for row in cursor.fetchall():
            date = datetime.strptime(row[0], '%Y-%m-%d').date() if isinstance(row[0], str) else row[0]
            route = row[1]

            actuals[(date, route)] = {
                'status': row[2]
            }

        conn.close()
        return actuals

    def evaluate_model_performance(self, evaluation_days: int = 30) -> Dict:
        """Evaluate model performance over recent period"""

        print(f"\n{'='*80}")
        print(f"EVALUATING MODEL PERFORMANCE")
        print(f"{'='*80}")

        conn = sqlite3.connect(self.accuracy_db)

        # Calculate metrics from matched data
        query = f'''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN actual_cancellation = 1 AND predicted_cancellation = 1 THEN 1 ELSE 0 END) as tp,
                SUM(CASE WHEN actual_cancellation = 0 AND predicted_cancellation = 0 THEN 1 ELSE 0 END) as tn,
                SUM(CASE WHEN false_positive = 1 THEN 1 ELSE 0 END) as fp,
                SUM(CASE WHEN false_negative = 1 THEN 1 ELSE 0 END) as fn,
                AVG(prediction_error) as mae,
                AVG(prediction_error * prediction_error) as mse
            FROM prediction_matches
            WHERE match_date >= date('now', '-{evaluation_days} days')
        '''

        df = pd.read_sql_query(query, conn)

        if df.empty or df['total'].iloc[0] == 0:
            print("[WARNING] No matched data available for evaluation")
            conn.close()
            return {}

        row = df.iloc[0]
        total = row['total']
        correct = row['correct']
        tp = row['tp']
        tn = row['tn']
        fp = row['fp']
        fn = row['fn']
        mae = row['mae']
        rmse = np.sqrt(row['mse']) if row['mse'] else 0

        # Calculate metrics
        accuracy = correct / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Calculate calibration
        calibration = self._calculate_calibration(conn)

        # Save performance metrics
        cursor = conn.cursor()
        today = datetime.now().date()

        cursor.execute('''
            INSERT OR REPLACE INTO model_performance (
                evaluation_date, total_predictions, correct_predictions, accuracy_rate,
                true_positives, true_negatives, false_positives, false_negatives,
                precision_score, recall_score, f1_score,
                mean_absolute_error, root_mean_squared_error, calibration_score,
                calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            today, int(total), int(correct), accuracy,
            int(tp), int(tn), int(fp), int(fn),
            precision, recall, f1,
            mae, rmse, calibration,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        # Print metrics
        print(f"\nPerformance Metrics (Last {evaluation_days} days):")
        print(f"  Total Predictions: {int(total)}")
        print(f"  Accuracy: {accuracy:.1%}")
        print(f"  Precision: {precision:.1%}")
        print(f"  Recall: {recall:.1%}")
        print(f"  F1-Score: {f1:.3f}")
        print(f"  MAE: {mae:.2f}")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  Calibration: {calibration:.1%}")

        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'mae': mae,
            'rmse': rmse,
            'calibration': calibration
        }

    def _calculate_calibration(self, conn) -> float:
        """Calculate prediction calibration score"""

        query = '''
            SELECT predicted_risk_score, actual_cancellation
            FROM prediction_matches
            WHERE match_date >= date('now', '-30 days')
        '''

        df = pd.read_sql_query(query, conn)

        if len(df) < 10:
            return 0.0

        # Bin predictions and calculate calibration
        bins = np.linspace(0, 100, 11)
        calibration_error = 0.0

        for i in range(len(bins) - 1):
            in_bin = (df['predicted_risk_score'] >= bins[i]) & (df['predicted_risk_score'] < bins[i+1])

            if in_bin.sum() > 0:
                avg_predicted = df.loc[in_bin, 'predicted_risk_score'].mean() / 100
                actual_rate = df.loc[in_bin, 'actual_cancellation'].mean()
                calibration_error += abs(avg_predicted - actual_rate) * (in_bin.sum() / len(df))

        return 1.0 - calibration_error

    def adjust_thresholds(self) -> Dict:
        """Automatically adjust risk thresholds based on accuracy data"""

        print(f"\n{'='*80}")
        print(f"ADJUSTING RISK THRESHOLDS")
        print(f"{'='*80}")

        conn = sqlite3.connect(self.accuracy_db)

        # Analyze false positives and false negatives
        query = '''
            SELECT
                AVG(pred_wind_speed) as avg_wind_fp,
                AVG(pred_wave_height) as avg_wave_fp,
                AVG(pred_visibility) as avg_vis_fp
            FROM prediction_matches
            WHERE false_positive = 1
        '''
        fp_data = pd.read_sql_query(query, conn).iloc[0]

        query = '''
            SELECT
                AVG(pred_wind_speed) as avg_wind_fn,
                AVG(pred_wave_height) as avg_wave_fn,
                AVG(pred_visibility) as avg_vis_fn
            FROM prediction_matches
            WHERE false_negative = 1
        '''
        fn_data = pd.read_sql_query(query, conn).iloc[0]

        adjustments = {}
        cursor = conn.cursor()

        # Adjust wind speed threshold
        if not pd.isna(fp_data['avg_wind_fp']) and not pd.isna(fn_data['avg_wind_fn']):
            # If we're getting false positives at lower wind speeds, increase threshold
            # If we're missing cancellations at higher wind speeds, decrease threshold
            optimal_wind = (fp_data['avg_wind_fp'] + fn_data['avg_wind_fn']) / 2

            if abs(optimal_wind - self.risk_thresholds['wind_speed']) > 1.0:
                old_value = self.risk_thresholds['wind_speed']
                new_value = optimal_wind

                cursor.execute('''
                    INSERT INTO threshold_adjustments (
                        adjustment_date, parameter_name, old_value, new_value,
                        reason, impact_estimate, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().date(), 'wind_speed', old_value, new_value,
                    'Optimizing based on false positive/negative analysis',
                    abs(new_value - old_value) / old_value,
                    datetime.now().isoformat()
                ))

                self.risk_thresholds['wind_speed'] = new_value
                adjustments['wind_speed'] = {'old': old_value, 'new': new_value}
                print(f"  Wind Speed: {old_value:.1f} → {new_value:.1f} m/s")

        # Similar for wave height
        if not pd.isna(fp_data['avg_wave_fp']) and not pd.isna(fn_data['avg_wave_fn']):
            optimal_wave = (fp_data['avg_wave_fp'] + fn_data['avg_wave_fn']) / 2

            if abs(optimal_wave - self.risk_thresholds['wave_height']) > 0.3:
                old_value = self.risk_thresholds['wave_height']
                new_value = optimal_wave

                cursor.execute('''
                    INSERT INTO threshold_adjustments (
                        adjustment_date, parameter_name, old_value, new_value,
                        reason, impact_estimate, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().date(), 'wave_height', old_value, new_value,
                    'Optimizing based on false positive/negative analysis',
                    abs(new_value - old_value) / old_value,
                    datetime.now().isoformat()
                ))

                self.risk_thresholds['wave_height'] = new_value
                adjustments['wave_height'] = {'old': old_value, 'new': new_value}
                print(f"  Wave Height: {old_value:.1f} → {new_value:.1f} m")

        conn.commit()
        conn.close()

        if adjustments:
            print(f"[OK] Adjusted {len(adjustments)} thresholds")
        else:
            print("[INFO] No threshold adjustments needed")

        return adjustments

    def generate_accuracy_report(self, days: int = 30) -> str:
        """Generate comprehensive accuracy report"""

        print(f"\n{'='*80}")
        print(f"GENERATING ACCURACY REPORT")
        print(f"{'='*80}")

        conn = sqlite3.connect(self.accuracy_db)

        # Get overall statistics
        total_matches = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM prediction_matches", conn
        ).iloc[0]['count']

        if total_matches == 0:
            conn.close()
            return "No prediction-actual matches available yet. Please run data collection."

        # Get recent performance
        recent_perf = pd.read_sql_query('''
            SELECT * FROM model_performance
            ORDER BY evaluation_date DESC LIMIT 1
        ''', conn)

        # Get accuracy trend
        trend = pd.read_sql_query(f'''
            SELECT evaluation_date, accuracy_rate
            FROM model_performance
            ORDER BY evaluation_date DESC LIMIT 7
        ''', conn)

        # Get recent adjustments
        adjustments = pd.read_sql_query('''
            SELECT parameter_name, old_value, new_value, adjustment_date
            FROM threshold_adjustments
            ORDER BY adjustment_date DESC LIMIT 5
        ''', conn)

        conn.close()

        # Build report
        report = f"""
{'='*80}
PREDICTION ACCURACY IMPROVEMENT REPORT
{'='*80}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATUS
{'='*80}
Total Prediction-Actual Matches: {int(total_matches)}
Data Collection Period: {days} days
"""

        if not recent_perf.empty:
            perf = recent_perf.iloc[0]
            report += f"""
CURRENT PERFORMANCE METRICS
{'='*80}
Accuracy:  {perf['accuracy_rate']:.1%}
Precision: {perf['precision_score']:.1%}
Recall:    {perf['recall_score']:.1%}
F1-Score:  {perf['f1_score']:.3f}

Prediction Errors:
  Mean Absolute Error: {perf['mean_absolute_error']:.2f}
  Root Mean Squared Error: {perf['root_mean_squared_error']:.2f}

Calibration Score: {perf['calibration_score']:.1%}
"""

        if len(trend) > 1:
            first_acc = trend.iloc[-1]['accuracy_rate']
            latest_acc = trend.iloc[0]['accuracy_rate']
            improvement = latest_acc - first_acc

            report += f"""
ACCURACY TREND
{'='*80}
First Measurement: {first_acc:.1%}
Latest: {latest_acc:.1%}
Improvement: {improvement:+.1%} {'📈' if improvement > 0 else '📉' if improvement < 0 else '➡️'}
"""

        if not adjustments.empty:
            report += f"""
RECENT THRESHOLD ADJUSTMENTS
{'='*80}
"""
            for _, adj in adjustments.iterrows():
                report += f"{adj['adjustment_date']}: {adj['parameter_name']}: {adj['old_value']:.2f} → {adj['new_value']:.2f}\n"

        report += f"""
CURRENT RISK THRESHOLDS
{'='*80}
Wind Speed:  {self.risk_thresholds['wind_speed']:.1f} m/s
Wave Height: {self.risk_thresholds['wave_height']:.1f} m
Visibility:  {self.risk_thresholds['visibility']:.1f} km
Temperature: {self.risk_thresholds['temperature']:.1f} °C

{'='*80}
"""

        return report

def main():
    """Main execution"""

    print("="*80)
    print("PREDICTION ACCURACY IMPROVEMENT SYSTEM")
    print("="*80)

    system = PredictionAccuracySystem()

    # Step 1: Match predictions with actuals
    matched = system.match_predictions_with_actuals(lookback_days=30)

    if matched == 0:
        print("\n[WARNING] No matches found. Need more actual operation data.")
        print("Please ensure accuracy_tracker.py is running regularly to collect actual operations.")
        return

    # Step 2: Evaluate current performance
    performance = system.evaluate_model_performance(evaluation_days=30)

    # Step 3: Adjust thresholds if needed
    adjustments = system.adjust_thresholds()

    # Step 4: Generate report
    report = system.generate_accuracy_report(days=30)
    print(report)

    # Save report to file
    report_file = Path("data") / "accuracy_report.txt"
    report_file.write_text(report, encoding='utf-8')
    print(f"[OK] Report saved to {report_file}")

    print("\n" + "="*80)
    print("✅ ACCURACY IMPROVEMENT CYCLE COMPLETED")
    print("="*80)

if __name__ == '__main__':
    main()
