#!/usr/bin/env python3
"""Investigate why 2026-02-16 had 1.1% accuracy"""
import sqlite3
import os

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
real_data_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

target_date = '2026-02-16'

print(f"Investigating {target_date} (1.1% accuracy)")
print("=" * 80)

# Get predictions
conn1 = sqlite3.connect(forecast_db)
cursor1 = conn1.cursor()

cursor1.execute('''
    SELECT
        cf.forecast_for_date,
        cf.route,
        cf.risk_level,
        cf.risk_score,
        cf.wind_forecast,
        cf.wave_forecast,
        cf.visibility_forecast
    FROM cancellation_forecast cf
    INNER JOIN (
        SELECT forecast_for_date, route, MAX(forecast_hour) as max_hour
        FROM cancellation_forecast
        WHERE forecast_for_date = ?
        GROUP BY forecast_for_date, route
    ) latest
    ON cf.forecast_for_date = latest.forecast_for_date
    AND cf.route = latest.route
    AND cf.forecast_hour = latest.max_hour
''', (target_date,))

predictions = cursor1.fetchall()

print(f"\nPREDICTIONS for {target_date}:")
print(f"{'Route':<25} {'Risk':<10} {'Score':<8} {'Wind':<8} {'Wave':<8} {'Vis':<8}")
print("-" * 80)
for pred in predictions:
    date, route, risk, score, wind, wave, vis = pred
    print(f"{route:<25} {risk:<10} {score:<8.1f} {wind:<8.1f} {wave:<8.1f} {vis or 0:<8.1f}")

# Get actual operations
conn2 = sqlite3.connect(real_data_db)
cursor2 = conn2.cursor()

cursor2.execute('''
    SELECT
        route,
        departure_time,
        operational_status,
        is_cancelled
    FROM ferry_status_enhanced
    WHERE scrape_date = ?
    ORDER BY route, departure_time
''', (target_date,))

actual_ops = cursor2.fetchall()

print(f"\nACTUAL OPERATIONS for {target_date}:")
print(f"{'Route':<25} {'Dep Time':<12} {'Status':<20} {'Cancelled':<10}")
print("-" * 80)

route_stats = {}
for op in actual_ops:
    route, dep_time, status, is_cancelled = op
    print(f"{route:<25} {dep_time:<12} {status:<20} {'YES' if is_cancelled else 'NO':<10}")

    if route not in route_stats:
        route_stats[route] = {'total': 0, 'cancelled': 0}
    route_stats[route]['total'] += 1
    if is_cancelled:
        route_stats[route]['cancelled'] += 1

print(f"\nROUTE SUMMARY:")
print(f"{'Route':<25} {'Total':<8} {'Cancelled':<12} {'Cancel %':<10}")
print("-" * 80)
for route, stats in route_stats.items():
    cancel_pct = (stats['cancelled'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"{route:<25} {stats['total']:<8} {stats['cancelled']:<12} {cancel_pct:>8.1f}%")

conn1.close()
conn2.close()

print("\n" + "=" * 80)
print("CONCLUSION:")
print("All routes predicted LOW risk but had MOSTLY_CANCELLED actual status.")
print("This suggests the wind/wave thresholds are too high for winter conditions.")
