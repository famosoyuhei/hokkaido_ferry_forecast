#!/usr/bin/env python3
"""
Analyze prediction accuracy by weather conditions
to identify optimal thresholds
"""
import sqlite3
import os
from collections import defaultdict

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
real_data_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

print("THRESHOLD ACCURACY ANALYSIS")
print("=" * 100)

# Get all predictions with actual outcomes
conn1 = sqlite3.connect(forecast_db)
cursor1 = conn1.cursor()

cursor1.execute('''
    SELECT
        operation_date,
        route,
        predicted_risk,
        predicted_score,
        predicted_wind,
        predicted_wave,
        actual_status,
        is_correct
    FROM unified_operation_accuracy
    WHERE operation_date >= date('now', '-14 days')
    ORDER BY operation_date DESC
''')

records = cursor1.fetchall()
conn1.close()

if not records:
    print("No accuracy records found yet.")
    exit(0)

print(f"\nAnalyzing {len(records)} predictions from last 14 days\n")

# Group by wind speed ranges
wind_ranges = {
    '0-8': (0, 8),
    '8-12': (8, 12),
    '12-15': (12, 15),
    '15-20': (15, 20),
    '20-25': (20, 25),
    '25-30': (25, 30),
    '30+': (30, 999)
}

wind_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'cancelled': 0, 'operated': 0})

for record in records:
    date, route, pred_risk, pred_score, pred_wind, pred_wave, actual, is_correct = record

    # Find wind range
    for range_name, (min_w, max_w) in wind_ranges.items():
        if min_w <= pred_wind < max_w:
            wind_stats[range_name]['total'] += 1
            if is_correct:
                wind_stats[range_name]['correct'] += 1
            if 'CANCELLED' in actual:
                wind_stats[range_name]['cancelled'] += 1
            else:
                wind_stats[range_name]['operated'] += 1
            break

print("ACCURACY BY WIND SPEED RANGE:")
print(f"{'Wind (m/s)':<12} {'Total':<8} {'Correct':<10} {'Accuracy':<10} {'Cancelled':<12} {'Cancel %':<10}")
print("-" * 100)

for range_name in ['0-8', '8-12', '12-15', '15-20', '20-25', '25-30', '30+']:
    stats = wind_stats[range_name]
    if stats['total'] > 0:
        accuracy = (stats['correct'] / stats['total'] * 100)
        cancel_pct = (stats['cancelled'] / stats['total'] * 100)
        print(f"{range_name:<12} {stats['total']:<8} {stats['correct']:<10} {accuracy:>8.1f}% {stats['cancelled']:<12} {cancel_pct:>8.1f}%")

# Find problematic cases (predicted LOW/MINIMAL but actually CANCELLED)
print("\n" + "=" * 100)
print("PROBLEMATIC PREDICTIONS (False Negatives):")
print("=" * 100)
print(f"{'Date':<12} {'Route':<25} {'Pred Risk':<12} {'Score':<8} {'Wind':<8} {'Wave':<8} {'Actual':<20}")
print("-" * 100)

false_negatives = []
for record in records:
    date, route, pred_risk, pred_score, pred_wind, pred_wave, actual, is_correct = record
    if not is_correct and pred_risk in ['LOW', 'MINIMAL'] and 'CANCELLED' in actual:
        false_negatives.append(record)
        print(f"{date:<12} {route:<25} {pred_risk:<12} {pred_score:<8.1f} {pred_wind:<8.1f} {pred_wave:<8.1f} {actual:<20}")

if false_negatives:
    # Calculate average conditions for false negatives
    avg_wind = sum(r[4] for r in false_negatives) / len(false_negatives)
    avg_wave = sum(r[5] for r in false_negatives) / len(false_negatives)
    print(f"\n  Average conditions when we UNDER-predicted:")
    print(f"    Wind: {avg_wind:.1f} m/s")
    print(f"    Wave: {avg_wave:.1f} m")
    print(f"  >> These should trigger at least MEDIUM risk")

# Find conservative cases (predicted HIGH/MEDIUM but actually OPERATED)
print("\n" + "=" * 100)
print("CONSERVATIVE PREDICTIONS (False Positives):")
print("=" * 100)
print(f"{'Date':<12} {'Route':<25} {'Pred Risk':<12} {'Score':<8} {'Wind':<8} {'Wave':<8} {'Actual':<20}")
print("-" * 100)

false_positives = []
for record in records:
    date, route, pred_risk, pred_score, pred_wind, pred_wave, actual, is_correct = record
    if not is_correct and pred_risk in ['HIGH', 'MEDIUM'] and 'OPERATED' in actual:
        false_positives.append(record)
        print(f"{date:<12} {route:<25} {pred_risk:<12} {pred_score:<8.1f} {pred_wind:<8.1f} {pred_wave:<8.1f} {actual:<20}")

if false_positives:
    avg_wind = sum(r[4] for r in false_positives) / len(false_positives)
    avg_wave = sum(r[5] for r in false_positives) / len(false_positives)
    print(f"\n  Average conditions when we OVER-predicted:")
    print(f"    Wind: {avg_wind:.1f} m/s")
    print(f"    Wave: {avg_wave:.1f} m")
    print(f"  >> These conditions actually allow operation")

print("\n" + "=" * 100)
print("RECOMMENDATIONS:")
print("=" * 100)

if false_negatives:
    fn_wind = sum(r[4] for r in false_negatives) / len(false_negatives)
    print(f"1. Lower MEDIUM threshold: Current wind threshold should catch {fn_wind:.1f}m/s")
    print(f"   Suggested: Wind >={fn_wind - 2:.0f}m/s should be MEDIUM in winter")

if false_positives:
    fp_wind = sum(r[4] for r in false_positives) / len(false_positives)
    print(f"\n2. Raise HIGH threshold: Wind {fp_wind:.1f}m/s sometimes allows operation")
    print(f"   Suggested: Increase HIGH threshold slightly")

print(f"\nTotal False Negatives: {len(false_negatives)} (under-predicted)")
print(f"Total False Positives: {len(false_positives)} (over-predicted)")
print(f"Better to have False Positives than False Negatives (safety first)")
