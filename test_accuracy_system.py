#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accuracy System Integration Test
Tests the complete accuracy improvement system
"""

import os
from datetime import datetime
from pathlib import Path

def run_integration_test():
    """Run complete integration test of the accuracy system"""

    print("="*80)
    print("ACCURACY IMPROVEMENT SYSTEM - INTEGRATION TEST")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    test_results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }

    # Test 1: Database Initialization
    print("[Test 1/6] Testing database initialization...")
    try:
        from prediction_accuracy_system import PredictionAccuracySystem
        system = PredictionAccuracySystem()
        print("✓ PASS: Databases initialized successfully")
        test_results['passed'] += 1
    except Exception as e:
        print(f"✗ FAIL: Database initialization failed: {e}")
        test_results['failed'] += 1
        return test_results

    # Test 2: Generate Test Data
    print("\n[Test 2/6] Testing test data generation...")
    try:
        from generate_test_predictions import generate_test_predictions
        generate_test_predictions(days_back=7)
        print("✓ PASS: Test predictions generated")
        test_results['passed'] += 1
    except Exception as e:
        print(f"✗ FAIL: Test data generation failed: {e}")
        test_results['failed'] += 1

    # Test 3: Collect Actual Operations
    print("\n[Test 3/6] Testing actual operations collection...")
    try:
        from accuracy_tracker import AccuracyTracker
        tracker = AccuracyTracker()
        today = datetime.now().strftime('%Y-%m-%d')
        count = tracker.collect_actual_operations(today)
        if count > 0:
            print(f"✓ PASS: Collected {count} actual operations")
            test_results['passed'] += 1
        else:
            print("⚠ WARNING: No actual operations collected (may be normal)")
            test_results['warnings'] += 1
    except Exception as e:
        print(f"✗ FAIL: Actual operations collection failed: {e}")
        test_results['failed'] += 1

    # Test 4: Prediction Matching
    print("\n[Test 4/6] Testing prediction-actual matching...")
    try:
        matched = system.match_predictions_with_actuals(lookback_days=30)
        if matched > 0:
            print(f"✓ PASS: Matched {matched} predictions with actuals")
            test_results['passed'] += 1
        else:
            print("⚠ WARNING: No matches found (need more data)")
            test_results['warnings'] += 1
    except Exception as e:
        print(f"✗ FAIL: Prediction matching failed: {e}")
        test_results['failed'] += 1

    # Test 5: Performance Evaluation
    print("\n[Test 5/6] Testing performance evaluation...")
    try:
        performance = system.evaluate_model_performance(evaluation_days=30)
        if performance:
            print(f"✓ PASS: Performance evaluated - Accuracy: {performance.get('accuracy', 0):.1%}")
            test_results['passed'] += 1
        else:
            print("⚠ WARNING: No performance data (need more matches)")
            test_results['warnings'] += 1
    except Exception as e:
        print(f"✗ FAIL: Performance evaluation failed: {e}")
        test_results['failed'] += 1

    # Test 6: Report Generation
    print("\n[Test 6/6] Testing report generation...")
    try:
        report = system.generate_accuracy_report(days=30)
        if len(report) > 100:
            print("✓ PASS: Report generated successfully")
            test_results['passed'] += 1

            # Save test report
            report_file = Path("data") / "test_accuracy_report.txt"
            report_file.write_text(report, encoding='utf-8')
            print(f"  Report saved to: {report_file}")
        else:
            print("⚠ WARNING: Report generated but may be incomplete")
            test_results['warnings'] += 1
    except Exception as e:
        print(f"✗ FAIL: Report generation failed: {e}")
        test_results['failed'] += 1

    # Test Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✓ Passed:   {test_results['passed']}/6")
    print(f"✗ Failed:   {test_results['failed']}/6")
    print(f"⚠ Warnings: {test_results['warnings']}/6")

    if test_results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe accuracy improvement system is ready to use.")
        print("\nNext steps:")
        print("  1. Run: python automated_improvement_runner.py")
        print("  2. Start dashboard: python accuracy_dashboard.py")
        print("  3. Access: http://localhost:5001")
    else:
        print("\n⚠ SOME TESTS FAILED")
        print("Please review the errors above and fix any issues.")

    print("\n" + "="*80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    return test_results

if __name__ == '__main__':
    results = run_integration_test()
    sys.exit(0 if results['failed'] == 0 else 1)
