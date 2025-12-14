#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick test of accuracy system"""

print("="*80)
print("QUICK ACCURACY SYSTEM TEST")
print("="*80)

# Test 1: Database
print("\n[1/3] Database initialization...")
try:
    from prediction_accuracy_system import PredictionAccuracySystem
    system = PredictionAccuracySystem()
    print("OK - Database ready")
except Exception as e:
    print(f"FAIL - {e}")
    exit(1)

# Test 2: Run accuracy cycle
print("\n[2/3] Running accuracy improvement cycle...")
try:
    matched = system.match_predictions_with_actuals(lookback_days=30)
    print(f"OK - Matched {matched} predictions")

    if matched > 0:
        perf = system.evaluate_model_performance(evaluation_days=30)
        print(f"OK - Accuracy: {perf.get('accuracy', 0):.1%}")
except Exception as e:
    print(f"FAIL - {e}")

# Test 3: Generate report
print("\n[3/3] Generating report...")
try:
    report = system.generate_accuracy_report(days=30)
    print("OK - Report generated")
    print("\nReport preview:")
    print(report[:500])
except Exception as e:
    print(f"FAIL - {e}")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
print("\nTo view full dashboard:")
print("  python accuracy_dashboard.py")
print("  Then open: http://localhost:5001")
print("="*80)
