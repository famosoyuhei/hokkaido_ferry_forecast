#!/usr/bin/env python3
"""Check route name mappings between predictions and actual operations"""
import sqlite3
import os

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
real_data_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

print("ROUTE NAMES IN PREDICTIONS (cancellation_forecast):")
conn1 = sqlite3.connect(forecast_db)
cursor1 = conn1.cursor()
cursor1.execute("SELECT DISTINCT route FROM cancellation_forecast ORDER BY route")
pred_routes = [r[0] for r in cursor1.fetchall()]
for r in pred_routes:
    print(f"  - {r}")
conn1.close()

print("\nROUTE NAMES IN ACTUAL OPERATIONS (ferry_status_enhanced):")
conn2 = sqlite3.connect(real_data_db)
cursor2 = conn2.cursor()
cursor2.execute("SELECT DISTINCT route FROM ferry_status_enhanced ORDER BY route")
actual_routes = [r[0] for r in cursor2.fetchall()]
for r in actual_routes:
    print(f"  - {r}")
conn2.close()

print("\nMATCHING:")
matched = set(pred_routes) & set(actual_routes)
pred_only = set(pred_routes) - set(actual_routes)
actual_only = set(actual_routes) - set(pred_routes)

print(f"  Matched routes: {len(matched)}")
for r in matched:
    print(f"    - {r}")

if pred_only:
    print(f"\n  Only in predictions: {len(pred_only)}")
    for r in pred_only:
        print(f"    - {r}")

if actual_only:
    print(f"\n  Only in actual operations: {len(actual_only)}")
    for r in actual_only:
        print(f"    - {r}")
