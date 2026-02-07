#!/usr/bin/env python3
"""
Debug script to check what data exists for accuracy tracking
"""
import sqlite3
import os
from datetime import datetime, timedelta
import pytz

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
real_data_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

jst = pytz.timezone('Asia/Tokyo')
yesterday = (datetime.now(jst) - timedelta(days=1)).strftime('%Y-%m-%d')

print(f"Checking data for {yesterday}")
print("=" * 80)

# Check predictions
print("\n1. PREDICTIONS (cancellation_forecast table):")
conn1 = sqlite3.connect(forecast_db)
cursor1 = conn1.cursor()

cursor1.execute('''
    SELECT DISTINCT
        forecast_for_date,
        route,
        risk_level,
        risk_score
    FROM cancellation_forecast
    WHERE forecast_for_date = ?
    ORDER BY route
''', (yesterday,))

predictions = cursor1.fetchall()
print(f"   Found {len(predictions)} predictions")
for pred in predictions[:10]:
    print(f"     {pred}")

# Check actual operations
print("\n2. ACTUAL OPERATIONS (ferry_status table):")
conn2 = sqlite3.connect(real_data_db)
cursor2 = conn2.cursor()

cursor2.execute('''
    SELECT
        scrape_date,
        route,
        departure_time,
        operational_status,
        is_cancelled
    FROM ferry_status
    WHERE scrape_date = ?
    ORDER BY route, departure_time
''', (yesterday,))

actual_ops = cursor2.fetchall()
print(f"   Found {len(actual_ops)} actual operations")
for op in actual_ops[:10]:
    print(f"     {op}")

# Check if accuracy tables have any data
print("\n3. ACCURACY TABLES:")

cursor1.execute('SELECT COUNT(*) FROM unified_operation_accuracy')
op_count = cursor1.fetchone()[0]
print(f"   unified_operation_accuracy: {op_count} records")

cursor1.execute('SELECT COUNT(*) FROM unified_daily_summary')
summary_count = cursor1.fetchone()[0]
print(f"   unified_daily_summary: {summary_count} records")

if op_count > 0:
    cursor1.execute('SELECT * FROM unified_operation_accuracy LIMIT 5')
    print("\n   Sample operation_accuracy records:")
    for row in cursor1.fetchall():
        print(f"     {row}")

conn1.close()
conn2.close()

print("\n" + "=" * 80)
print("Debug complete")
