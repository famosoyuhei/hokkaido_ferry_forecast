#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Accuracy Improvement Runner
Runs daily to continuously improve prediction accuracy
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
from datetime import datetime
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def run_accuracy_improvement_cycle():
    """Run complete accuracy improvement cycle"""

    print("="*80)
    print(f"AUTOMATED ACCURACY IMPROVEMENT CYCLE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Step 1: Collect actual operations
    print("\n[1/4] Collecting actual ferry operations...")
    try:
        from accuracy_tracker import AccuracyTracker
        tracker = AccuracyTracker()
        today = datetime.now().strftime('%Y-%m-%d')
        tracker.collect_actual_operations(today)
        print("✓ Actual operations collected")
    except Exception as e:
        print(f"✗ Error collecting actual operations: {e}")

    # Step 2: Match predictions with actuals
    print("\n[2/4] Matching predictions with actual results...")
    try:
        from prediction_accuracy_system import PredictionAccuracySystem
        system = PredictionAccuracySystem()
        matched = system.match_predictions_with_actuals(lookback_days=30)
        print(f"✓ Matched {matched} predictions")
    except Exception as e:
        print(f"✗ Error matching predictions: {e}")
        return

    # Step 3: Evaluate and adjust model
    print("\n[3/4] Evaluating model performance...")
    try:
        performance = system.evaluate_model_performance(evaluation_days=30)

        if performance:
            print(f"✓ Current accuracy: {performance.get('accuracy', 0):.1%}")

            # Adjust thresholds if accuracy is below target
            if performance.get('accuracy', 0) < 0.75:
                print("\n[3.1] Adjusting risk thresholds...")
                adjustments = system.adjust_thresholds()
                if adjustments:
                    print(f"✓ Adjusted {len(adjustments)} thresholds")
                else:
                    print("✓ No adjustments needed")
    except Exception as e:
        print(f"✗ Error evaluating performance: {e}")

    # Step 4: Generate and save report
    print("\n[4/4] Generating accuracy report...")
    try:
        report = system.generate_accuracy_report(days=30)

        # Save report
        report_dir = Path("data") / "accuracy_reports"
        report_dir.mkdir(exist_ok=True)

        report_file = report_dir / f"accuracy_report_{datetime.now().strftime('%Y%m%d')}.txt"
        report_file.write_text(report, encoding='utf-8')

        print(f"✓ Report saved to {report_file}")

        # Also save as latest
        latest_file = Path("data") / "accuracy_report.txt"
        latest_file.write_text(report, encoding='utf-8')

    except Exception as e:
        print(f"✗ Error generating report: {e}")

    print("\n" + "="*80)
    print(f"ACCURACY IMPROVEMENT CYCLE COMPLETED")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == '__main__':
    run_accuracy_improvement_cycle()
