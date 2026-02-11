#!/usr/bin/env python3
"""
Accuracy Analysis Script for Hokkaido Ferry Forecast System

This script analyzes the prediction accuracy data collected by unified_accuracy_tracker.py
and generates a comprehensive report.

Usage:
    python analyze_accuracy.py
"""

import sqlite3
import sys
from datetime import datetime, timedelta
import json

def connect_to_database():
    """Connect to the ferry weather forecast database"""
    try:
        # Try production path first
        db_path = '/data/ferry_weather_forecast.db'
        conn = sqlite3.connect(db_path)
        return conn, db_path
    except:
        # Fall back to local path
        db_path = 'ferry_weather_forecast.db'
        conn = sqlite3.connect(db_path)
        return conn, db_path

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def analyze_overall_accuracy(cursor):
    """Analyze overall prediction accuracy"""
    print("\n" + "="*70)
    print("OVERALL ACCURACY ANALYSIS")
    print("="*70)

    # Daily summaries
    query = """
    SELECT
        summary_date,
        total_predictions,
        correct_predictions,
        accuracy_rate,
        precision_score,
        recall_score,
        f1_score
    FROM unified_daily_summary
    ORDER BY summary_date DESC
    LIMIT 10
    """

    cursor.execute(query)
    summaries = cursor.fetchall()

    if not summaries:
        print("  No daily summary data found yet.")
        print("    Data collection may still be in progress.")
        return None

    print(f"\n{'Date':<12} {'Predictions':<12} {'Correct':<10} {'Accuracy':<10} {'F1 Score':<10}")
    print("-" * 70)

    total_predictions = 0
    total_correct = 0

    for row in summaries:
        date, predictions, correct, accuracy, precision, recall, f1 = row
        # accuracy_rate is already stored as percentage (0-100) in the database
        accuracy_pct = accuracy if accuracy else 0
        print(f"{date:<12} {predictions:<12} {correct:<10} {accuracy_pct:>8.1f}% {f1 or 0:>8.3f}")
        total_predictions += predictions
        total_correct += correct

    overall_accuracy = (total_correct / total_predictions * 100) if total_predictions > 0 else 0

    print("-" * 70)
    print(f"{'TOTAL':<12} {total_predictions:<12} {total_correct:<10} {overall_accuracy:>8.1f}%")

    return {
        'total_predictions': total_predictions,
        'total_correct': total_correct,
        'overall_accuracy': overall_accuracy,
        'days_analyzed': len(summaries)
    }

def analyze_risk_level_accuracy(cursor):
    """Analyze accuracy by risk level"""
    print("\n" + "="*70)
    print(" RISK LEVEL ACCURACY")
    print("="*70)

    query = """
    SELECT
        risk_level,
        predictions_count,
        correct_count,
        accuracy_rate
    FROM risk_level_accuracy
    WHERE analysis_date = (SELECT MAX(analysis_date) FROM risk_level_accuracy)
    ORDER BY
        CASE risk_level
            WHEN 'HIGH' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'LOW' THEN 3
            WHEN 'MINIMAL' THEN 4
        END
    """

    cursor.execute(query)
    results = cursor.fetchall()

    if not results:
        print("  No risk level accuracy data found yet.")
        return None

    print(f"\n{'Risk Level':<12} {'Predictions':<12} {'Correct':<10} {'Accuracy':<10}")
    print("-" * 70)

    for row in results:
        level, predictions, correct, accuracy = row
        accuracy_pct = accuracy * 100 if accuracy else 0
        print(f"{level:<12} {predictions:<12} {correct:<10} {accuracy_pct:>8.1f}%")

    return results

def analyze_operation_accuracy(cursor):
    """Analyze detailed operation-level accuracy"""
    print("\n" + "="*70)
    print(" OPERATION-LEVEL ACCURACY (Last 20 Records)")
    print("="*70)

    query = """
    SELECT
        operation_date,
        route,
        predicted_risk,
        actual_status,
        is_correct
    FROM unified_operation_accuracy
    ORDER BY operation_date DESC, route
    LIMIT 20
    """

    cursor.execute(query)
    operations = cursor.fetchall()

    if not operations:
        print("  No operation-level accuracy data found yet.")
        return None

    print(f"\n{'Date':<12} {'Route':<20} {'Predicted':<12} {'Actual':<12} {'Correct':<8}")
    print("-" * 70)

    for row in operations:
        date, route, predicted, actual, correct = row
        correct_icon = "" if correct == 1 else ""
        print(f"{date:<12} {route:<20} {predicted:<12} {actual:<12} {correct_icon:<8}")

    return operations

def generate_recommendations(overall_stats, risk_results):
    """Generate recommendations based on analysis"""
    print("\n" + "="*70)
    print(" RECOMMENDATIONS")
    print("="*70)

    if not overall_stats:
        print("\n Insufficient data for recommendations.")
        print("   Continue collecting data for at least 7 days.")
        return

    accuracy = overall_stats['overall_accuracy']
    days = overall_stats['days_analyzed']

    print(f"\n Current Status:")
    print(f"    {days} days of data collected")
    print(f"    {overall_stats['total_predictions']} predictions analyzed")
    print(f"    {accuracy:.1f}% overall accuracy")

    print(f"\n Next Steps:")

    if days < 7:
        print(f"   1. Continue data collection (need {7-days} more days)")
        print(f"   2. Monitor daily for any anomalies")
        print(f"   3. Return for full analysis after 7 days")
    elif accuracy >= 85:
        print(f"   1.  Accuracy is good ({accuracy:.1f}% >= 85%)")
        print(f"   2. Continue monitoring with current settings")
        print(f"   3. Consider Phase 3 (ML) for further optimization")
    elif accuracy >= 70:
        print(f"   1.   Accuracy is acceptable ({accuracy:.1f}%)")
        print(f"   2. Implement Phase 3 (ML threshold optimization)")
        print(f"   3. Add additional weather data sources")
    else:
        print(f"   1.  Accuracy needs improvement ({accuracy:.1f}% < 70%)")
        print(f"   2. URGENT: Review risk calculation algorithm")
        print(f"   3. Implement Phase 3 immediately")
        print(f"   4. Consider adding real-time weather measurements")

    if risk_results:
        print(f"\n Focus Areas:")
        for row in risk_results:
            level, predictions, correct, accuracy = row
            accuracy_pct = accuracy * 100 if accuracy else 0
            if accuracy_pct < 70:
                print(f"    {level}: Low accuracy ({accuracy_pct:.1f}%) - needs improvement")

def main():
    """Main analysis function"""
    print("\n" + "="*70)
    print(" HOKKAIDO FERRY FORECAST - ACCURACY ANALYSIS")
    print("="*70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        conn, db_path = connect_to_database()
        print(f"Database: {db_path}")
        cursor = conn.cursor()

        # Check if accuracy tables exist
        tables = ['unified_operation_accuracy', 'unified_daily_summary', 'risk_level_accuracy']
        missing_tables = []

        for table in tables:
            if not check_table_exists(cursor, table):
                missing_tables.append(table)

        if missing_tables:
            print(f"\n  Missing tables: {', '.join(missing_tables)}")
            print("   Please ensure unified_accuracy_tracker.py has been run.")
            sys.exit(1)

        # Run analyses
        overall_stats = analyze_overall_accuracy(cursor)
        risk_results = analyze_risk_level_accuracy(cursor)
        analyze_operation_accuracy(cursor)
        generate_recommendations(overall_stats, risk_results)

        print("\n" + "="*70)
        print(" Analysis Complete")
        print("="*70 + "\n")

        conn.close()

    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
