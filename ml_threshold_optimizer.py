#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML-Based Risk Threshold Optimizer
Automatically adjusts risk calculation thresholds based on historical accuracy data
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np
import os

class MLThresholdOptimizer:
    """Machine learning-based threshold optimizer for risk calculation"""

    def __init__(self):
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
        self.forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.actual_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

        # Current thresholds (from sailing_forecast_system.py)
        self.current_thresholds = {
            'HIGH': 70,
            'MEDIUM': 40,
            'LOW': 20,
            'MINIMAL': 0
        }

        # Optimization targets
        self.optimization_goal = 'f1_score'  # or 'accuracy', 'minimize_fn', 'minimize_fp'

    def collect_historical_data(self, days_back: int = 30) -> Dict:
        """
        Collect historical prediction vs actual operation data

        Returns:
            Dictionary with:
            - cancellations: List of (risk_score, wind, wave, vis) when actually cancelled
            - operations: List of (risk_score, wind, wave, vis) when actually operated
        """
        if not os.path.exists(self.actual_db):
            print("[WARNING] No actual operations database found")
            return {'cancellations': [], 'operations': []}

        forecast_conn = sqlite3.connect(self.forecast_db)
        actual_conn = sqlite3.connect(self.actual_db)

        forecast_cursor = forecast_conn.cursor()
        actual_cursor = actual_conn.cursor()

        # Get date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)

        cancellations = []
        operations = []

        # Iterate through each day
        for day_offset in range(days_back):
            check_date = (start_date + timedelta(days=day_offset)).isoformat()

            # Get predictions
            forecast_cursor.execute('''
                SELECT route, departure_time, risk_score,
                       wind_forecast, wave_forecast, visibility_forecast
                FROM sailing_forecast
                WHERE forecast_date = ?
            ''', (check_date,))

            predictions = {f"{row[0]}_{row[1]}": row[2:] for row in forecast_cursor.fetchall()}

            # Get actuals
            actual_cursor.execute('''
                SELECT route, departure_time, is_cancelled
                FROM ferry_status
                WHERE scrape_date = ?
            ''', (check_date,))

            actuals = {f"{row[0]}_{row[1]}": row[2] for row in actual_cursor.fetchall()}

            # Combine
            for key, pred_data in predictions.items():
                if key not in actuals:
                    continue

                risk_score, wind, wave, vis = pred_data
                was_cancelled = bool(actuals[key])

                data_point = (risk_score, wind or 0, wave or 0, vis or 999)

                if was_cancelled:
                    cancellations.append(data_point)
                else:
                    operations.append(data_point)

        forecast_conn.close()
        actual_conn.close()

        print(f"[OK] Collected {len(cancellations)} cancellations and {len(operations)} operations")

        return {
            'cancellations': cancellations,
            'operations': operations
        }

    def analyze_current_performance(self, data: Dict) -> Dict:
        """
        Analyze current threshold performance

        Returns confusion matrix and metrics for current thresholds
        """
        cancellations = data['cancellations']
        operations = data['operations']

        if not cancellations and not operations:
            return {'error': 'No data available'}

        # Apply current threshold (HIGH/MEDIUM = predict cancel)
        cancel_threshold = self.current_thresholds['MEDIUM']  # 40

        tp = sum(1 for score, _, _, _ in cancellations if score >= cancel_threshold)
        fn = sum(1 for score, _, _, _ in cancellations if score < cancel_threshold)

        tn = sum(1 for score, _, _, _ in operations if score < cancel_threshold)
        fp = sum(1 for score, _, _, _ in operations if score >= cancel_threshold)

        total = tp + tn + fp + fn
        accuracy = (tp + tn) / total * 100 if total > 0 else 0
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'threshold': cancel_threshold,
            'tp': tp,
            'tn': tn,
            'fp': fp,
            'fn': fn,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1
        }

    def find_optimal_threshold(self, data: Dict, metric: str = 'f1_score') -> Tuple[float, Dict]:
        """
        Find optimal threshold that maximizes the given metric

        Args:
            data: Historical data
            metric: 'f1_score', 'accuracy', 'precision', 'recall'

        Returns:
            (optimal_threshold, performance_metrics)
        """
        cancellations = data['cancellations']
        operations = data['operations']

        if not cancellations or not operations:
            return self.current_thresholds['MEDIUM'], {'error': 'Insufficient data'}

        # Test thresholds from 10 to 90 in steps of 5
        best_threshold = None
        best_score = 0
        best_metrics = {}

        for threshold in range(10, 95, 5):
            # Calculate confusion matrix
            tp = sum(1 for score, _, _, _ in cancellations if score >= threshold)
            fn = sum(1 for score, _, _, _ in cancellations if score < threshold)
            tn = sum(1 for score, _, _, _ in operations if score < threshold)
            fp = sum(1 for score, _, _, _ in operations if score >= threshold)

            total = tp + tn + fp + fn
            if total == 0:
                continue

            accuracy = (tp + tn) / total * 100
            precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            # Select score based on metric
            if metric == 'f1_score':
                score = f1
            elif metric == 'accuracy':
                score = accuracy
            elif metric == 'precision':
                score = precision
            elif metric == 'recall':
                score = recall
            else:
                score = f1

            if score > best_score:
                best_score = score
                best_threshold = threshold
                best_metrics = {
                    'threshold': threshold,
                    'tp': tp,
                    'tn': tn,
                    'fp': fp,
                    'fn': fn,
                    'accuracy': accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1_score': f1
                }

        return best_threshold, best_metrics

    def build_wind_wave_correlation(self, data: Dict) -> Dict:
        """
        Build correlation model between wind speed and wave height from cancellation data

        Returns:
            Correlation coefficient and regression parameters
        """
        cancellations = data['cancellations']

        if len(cancellations) < 5:
            return {'error': 'Insufficient cancellation data for correlation'}

        # Extract wind and wave data
        wind_speeds = [wind for _, wind, _, _ in cancellations if wind > 0]
        wave_heights = [wave for _, _, wave, _ in cancellations if wave > 0]

        if len(wind_speeds) < 5 or len(wave_heights) < 5:
            return {'error': 'Insufficient wind/wave data'}

        # Simple correlation (Pearson)
        wind_array = np.array(wind_speeds)
        wave_array = np.array(wave_heights)

        if len(wind_array) != len(wave_array):
            # Use minimum length
            min_len = min(len(wind_array), len(wave_array))
            wind_array = wind_array[:min_len]
            wave_array = wave_array[:min_len]

        correlation = np.corrcoef(wind_array, wave_array)[0, 1] if len(wind_array) > 1 else 0

        # Simple linear regression: wave = a * wind + b
        if len(wind_array) > 1:
            a, b = np.polyfit(wind_array, wave_array, 1)
        else:
            a, b = 0, 0

        return {
            'correlation': correlation,
            'regression_slope': a,
            'regression_intercept': b,
            'sample_size': len(wind_array),
            'mean_wind': np.mean(wind_array),
            'mean_wave': np.mean(wave_array)
        }

    def generate_recommendations(self, current_perf: Dict, optimal_perf: Dict, correlation: Dict) -> str:
        """
        Generate human-readable recommendations for system improvement
        """
        recommendations = []

        recommendations.append("=" * 80)
        recommendations.append("ML-BASED THRESHOLD OPTIMIZATION RECOMMENDATIONS")
        recommendations.append("=" * 80)

        # Current performance
        recommendations.append(f"\n📊 CURRENT PERFORMANCE (Threshold: {current_perf.get('threshold', 'N/A')})")
        recommendations.append(f"   Accuracy: {current_perf.get('accuracy', 0):.1f}%")
        recommendations.append(f"   F1-Score: {current_perf.get('f1_score', 0):.1f}")
        recommendations.append(f"   TP: {current_perf.get('tp', 0)}, TN: {current_perf.get('tn', 0)}, " +
                             f"FP: {current_perf.get('fp', 0)}, FN: {current_perf.get('fn', 0)}")

        # Optimal performance
        if 'error' not in optimal_perf:
            recommendations.append(f"\n🎯 OPTIMAL PERFORMANCE (Threshold: {optimal_perf.get('threshold', 'N/A')})")
            recommendations.append(f"   Accuracy: {optimal_perf.get('accuracy', 0):.1f}%")
            recommendations.append(f"   F1-Score: {optimal_perf.get('f1_score', 0):.1f}")
            recommendations.append(f"   TP: {optimal_perf.get('tp', 0)}, TN: {optimal_perf.get('tn', 0)}, " +
                                 f"FP: {optimal_perf.get('fp', 0)}, FN: {optimal_perf.get('fn', 0)}")

            improvement = optimal_perf.get('f1_score', 0) - current_perf.get('f1_score', 0)
            if improvement > 1:
                recommendations.append(f"\n✅ RECOMMENDATION: Adjust threshold from {current_perf.get('threshold')} " +
                                     f"to {optimal_perf.get('threshold')} for {improvement:.1f}% F1 improvement")

        # Wind-wave correlation
        if 'error' not in correlation:
            recommendations.append(f"\n🌊 WIND-WAVE CORRELATION")
            recommendations.append(f"   Correlation: {correlation.get('correlation', 0):.3f}")
            recommendations.append(f"   Regression: wave = {correlation.get('regression_slope', 0):.3f} * wind + " +
                                 f"{correlation.get('regression_intercept', 0):.3f}")
            recommendations.append(f"   Sample size: {correlation.get('sample_size', 0)} cancellations")

        recommendations.append("\n" + "=" * 80)

        return "\n".join(recommendations)

if __name__ == "__main__":
    print("=" * 80)
    print("ML THRESHOLD OPTIMIZER")
    print("=" * 80)

    optimizer = MLThresholdOptimizer()

    print("\n[INFO] Collecting historical data (last 30 days)...")
    data = optimizer.collect_historical_data(days_back=30)

    print("\n[INFO] Analyzing current threshold performance...")
    current_perf = optimizer.analyze_current_performance(data)

    print("\n[INFO] Finding optimal threshold...")
    optimal_threshold, optimal_perf = optimizer.find_optimal_threshold(data, metric='f1_score')

    print("\n[INFO] Building wind-wave correlation model...")
    correlation = optimizer.build_wind_wave_correlation(data)

    print("\n[INFO] Generating recommendations...")
    recommendations = optimizer.generate_recommendations(current_perf, optimal_perf, correlation)

    print("\n" + recommendations)

    print("\n[SUCCESS] ML optimization analysis completed")
