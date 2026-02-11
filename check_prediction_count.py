#!/usr/bin/env python3
"""Check how many predictions per date/route"""
import sqlite3
import os
from datetime import datetime, timedelta
import pytz

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")

jst = pytz.timezone('Asia/Tokyo')
yesterday = (datetime.now(jst) - timedelta(days=1)).strftime('%Y-%m-%d')

conn = sqlite3.connect(forecast_db)
cursor = conn.cursor()

print(f"Predictions for {yesterday}:\n")

# Without DISTINCT
cursor.execute('''
    SELECT route, COUNT(*) as count
    FROM cancellation_forecast
    WHERE forecast_for_date = ?
    GROUP BY route
    ORDER BY route
''', (yesterday,))

print("WITHOUT DISTINCT (actual prediction count per route):")
total_without = 0
for route, count in cursor.fetchall():
    print(f"  {route}: {count} predictions")
    total_without += count
print(f"  TOTAL: {total_without}\n")

# With DISTINCT
cursor.execute('''
    SELECT COUNT(*)
    FROM (
        SELECT DISTINCT forecast_for_date, route, risk_level, risk_score,
                        wind_forecast, wave_forecast, visibility_forecast
        FROM cancellation_forecast
        WHERE forecast_for_date = ?
    )
''', (yesterday,))

total_with = cursor.fetchone()[0]
print(f"WITH DISTINCT (what unified_accuracy_tracker.py gets): {total_with}")
print(f"\nDIFFERENCE: {total_without - total_with} predictions lost due to DISTINCT\n")

# Show duplicates
print("Sample of duplicate predictions (same date/route, different forecast_hour):")
cursor.execute('''
    SELECT forecast_for_date, route, forecast_hour, risk_level, risk_score
    FROM cancellation_forecast
    WHERE forecast_for_date = ?
    ORDER BY route, forecast_hour
    LIMIT 20
''', (yesterday,))

for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
