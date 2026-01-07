#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatic Threshold Adjuster
Applies ML-optimized thresholds to the risk calculation system
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import os
from datetime import datetime
from ml_threshold_optimizer import MLThresholdOptimizer

class AutoThresholdAdjuster:
    """Automatically adjust risk thresholds based on ML optimization"""

    def __init__(self):
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
        self.db_file = os.path.join(data_dir, "ferry_weather_forecast.db")

        # Minimum improvement required to adjust (in F1-score points)
        self.min_improvement = 2.0

        # Minimum data points required
        self.min_data_points = 20

    def init_threshold_history_table(self):
        """Initialize table to track threshold adjustments over time"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threshold_adjustment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjusted_at TEXT NOT NULL,

                -- Old thresholds
                old_high_threshold REAL,
                old_medium_threshold REAL,
                old_low_threshold REAL,

                -- New thresholds
                new_high_threshold REAL,
                new_medium_threshold REAL,
                new_low_threshold REAL,

                -- Performance before
                old_accuracy REAL,
                old_f1_score REAL,
                old_precision REAL,
                old_recall REAL,

                -- Expected performance after
                expected_accuracy REAL,
                expected_f1_score REAL,
                expected_precision REAL,
                expected_recall REAL,

                -- Metadata
                data_points_analyzed INTEGER,
                reason TEXT,
                auto_applied BOOLEAN DEFAULT 0
            )
        ''')

        conn.commit()
        conn.close()

        print("[OK] Threshold adjustment history table initialized")

    def should_adjust_threshold(self, current_perf: dict, optimal_perf: dict, data: dict) -> bool:
        """
        Determine if threshold should be adjusted based on improvement and data quality

        Returns:
            True if adjustment is recommended
        """
        # Check for errors
        if 'error' in current_perf or 'error' in optimal_perf:
            print("[INFO] Insufficient data for threshold adjustment")
            return False

        # Check data points
        total_data = len(data.get('cancellations', [])) + len(data.get('operations', []))
        if total_data < self.min_data_points:
            print(f"[INFO] Insufficient data points: {total_data} < {self.min_data_points}")
            return False

        # Check improvement
        current_f1 = current_perf.get('f1_score', 0)
        optimal_f1 = optimal_perf.get('f1_score', 0)
        improvement = optimal_f1 - current_f1

        if improvement < self.min_improvement:
            print(f"[INFO] Improvement too small: {improvement:.1f} < {self.min_improvement}")
            return False

        print(f"[OK] Adjustment recommended: F1 improvement = {improvement:.1f}")
        return True

    def apply_threshold_adjustment(self, current_perf: dict, optimal_perf: dict, data: dict, auto_apply: bool = False):
        """
        Record threshold adjustment (and optionally auto-apply)

        Args:
            current_perf: Current performance metrics
            optimal_perf: Optimal performance metrics
            data: Historical data used for optimization
            auto_apply: If True, automatically update sailing_forecast_system.py (NOT IMPLEMENTED YET)
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Current threshold (MEDIUM = 40 is the cancel/operate boundary)
        old_medium = 40
        new_medium = optimal_perf.get('threshold', 40)

        # For now, we only adjust the MEDIUM threshold
        # HIGH and LOW are calculated relative to MEDIUM
        old_high = 70
        old_low = 20

        # Adjust proportionally
        ratio = new_medium / old_medium
        new_high = int(old_high * ratio)
        new_low = int(old_low * ratio)

        total_data = len(data.get('cancellations', [])) + len(data.get('operations', []))

        cursor.execute('''
            INSERT INTO threshold_adjustment_history
            (adjusted_at,
             old_high_threshold, old_medium_threshold, old_low_threshold,
             new_high_threshold, new_medium_threshold, new_low_threshold,
             old_accuracy, old_f1_score, old_precision, old_recall,
             expected_accuracy, expected_f1_score, expected_precision, expected_recall,
             data_points_analyzed, reason, auto_applied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            old_high, old_medium, old_low,
            new_high, new_medium, new_low,
            current_perf.get('accuracy'), current_perf.get('f1_score'),
            current_perf.get('precision'), current_perf.get('recall'),
            optimal_perf.get('accuracy'), optimal_perf.get('f1_score'),
            optimal_perf.get('precision'), optimal_perf.get('recall'),
            total_data,
            f"ML optimization: F1 improvement {optimal_perf.get('f1_score', 0) - current_perf.get('f1_score', 0):.1f}",
            auto_apply
        ))

        conn.commit()
        conn.close()

        print(f"[OK] Threshold adjustment recorded:")
        print(f"     OLD: HIGH={old_high}, MEDIUM={old_medium}, LOW={old_low}")
        print(f"     NEW: HIGH={new_high}, MEDIUM={new_medium}, LOW={new_low}")

        if auto_apply:
            print("[INFO] Auto-apply not yet implemented - manual code update required")
            print(f"     Update sailing_forecast_system.py lines 600-607:")
            print(f"     if risk_score >= {new_high}:")
            print(f"         risk_level = \"HIGH\"")
            print(f"     elif risk_score >= {new_medium}:")
            print(f"         risk_level = \"MEDIUM\"")
            print(f"     elif risk_score >= {new_low}:")
            print(f"         risk_level = \"LOW\"")

if __name__ == "__main__":
    print("=" * 80)
    print("AUTOMATIC THRESHOLD ADJUSTER")
    print("=" * 80)

    adjuster = AutoThresholdAdjuster()
    adjuster.init_threshold_history_table()

    # Run ML optimization
    optimizer = MLThresholdOptimizer()

    print("\n[INFO] Collecting historical data...")
    data = optimizer.collect_historical_data(days_back=30)

    print("\n[INFO] Analyzing current performance...")
    current_perf = optimizer.analyze_current_performance(data)

    print("\n[INFO] Finding optimal threshold...")
    optimal_threshold, optimal_perf = optimizer.find_optimal_threshold(data)

    # Check if adjustment is needed
    if adjuster.should_adjust_threshold(current_perf, optimal_perf, data):
        print("\n[INFO] Applying threshold adjustment...")
        adjuster.apply_threshold_adjustment(current_perf, optimal_perf, data, auto_apply=False)
    else:
        print("\n[INFO] No threshold adjustment needed at this time")

    print("\n[SUCCESS] Automatic threshold adjustment completed")
