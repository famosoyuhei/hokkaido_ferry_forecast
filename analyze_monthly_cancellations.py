#!/usr/bin/env python3
"""
Analyze monthly cancellation rates and weather conditions from historical data.
Goal: Determine appropriate seasonal thresholds for the full year.
"""
import sqlite3
import os

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
real_db = os.path.join(data_dir, 'heartland_ferry_real_data.db')
forecast_db = os.path.join(data_dir, 'ferry_weather_forecast.db')

print("MONTHLY CANCELLATION ANALYSIS")
print("=" * 70)

# --- 1. Monthly cancellation rate from real operations ---
conn = sqlite3.connect(real_db)
cur = conn.cursor()

# Show available tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables in real_data DB: {tables}")

print("\n[1] Monthly cancellation rate")
print("-" * 70)
# Try ferry_status_enhanced first, then ferry_status
table = 'ferry_status_enhanced' if 'ferry_status_enhanced' in tables else 'ferry_status'
try:
    cur.execute(f"""
        SELECT
            strftime('%Y-%m', scrape_date) as month,
            COUNT(*) as total,
            SUM(CASE WHEN is_cancelled = 1 THEN 1 ELSE 0 END) as cancelled
        FROM {table}
        GROUP BY month
        ORDER BY month
    """)
    rows = cur.fetchall()
    print(f"Source: {table}")
    print(f"{'Month':<12} {'Total':<8} {'Cancelled':<12} {'Cancel%'}")
    print("-" * 40)
    for month, total, cancelled in rows:
        pct = (cancelled / total * 100) if total > 0 else 0
        bar = '#' * int(pct / 5)
        print(f"{month:<12} {total:<8} {cancelled:<12} {pct:5.1f}% {bar}")
except Exception as e:
    print(f"  Error: {e}")

# --- 2. Monthly summary from daily_summary ---
print("\n[2] Monthly data from daily_summary table")
print("-" * 70)
cur.execute("""
    SELECT
        strftime('%Y-%m', summary_date) as month,
        COUNT(*) as days,
        SUM(total_sailings) as total_sailings,
        SUM(cancelled_sailings) as cancelled_sailings
    FROM daily_summary
    GROUP BY month
    ORDER BY month
""")
rows2 = cur.fetchall()
if rows2:
    print(f"{'Month':<12} {'Days':<6} {'Sailings':<10} {'Cancelled':<12} {'Cancel%'}")
    print("-" * 50)
    for month, days, total, cancelled in rows2:
        if total and total > 0:
            pct = (cancelled / total * 100)
            print(f"{month:<12} {days:<6} {total:<10} {cancelled:<12} {pct:5.1f}%")
else:
    print("  No data in daily_summary")

conn.close()

# --- 3. Monthly weather conditions from cancellation predictions ---
print("\n[3] Monthly weather conditions at time of cancellation (from accuracy data)")
print("-" * 70)
conn2 = sqlite3.connect(forecast_db)
cur2 = conn2.cursor()

cur2.execute("""
    SELECT
        strftime('%Y-%m', operation_date) as month,
        COUNT(*) as total,
        SUM(CASE WHEN is_correct = 0 AND actual_status LIKE '%CANCELLED%' THEN 1 ELSE 0 END) as false_neg,
        AVG(CASE WHEN actual_status LIKE '%CANCELLED%' THEN predicted_wind END) as avg_wind_cancelled,
        AVG(CASE WHEN actual_status LIKE '%CANCELLED%' THEN predicted_wave END) as avg_wave_cancelled,
        MIN(CASE WHEN actual_status LIKE '%CANCELLED%' THEN predicted_wind END) as min_wind_cancelled,
        MAX(CASE WHEN actual_status LIKE '%CANCELLED%' THEN predicted_wind END) as max_wind_cancelled
    FROM unified_operation_accuracy
    GROUP BY month
    ORDER BY month
""")
rows3 = cur2.fetchall()
if rows3:
    print(f"{'Month':<12} {'Total':<8} {'FalseNeg':<10} {'AvgWind':<10} {'AvgWave':<10} {'MinWind':<10} {'MaxWind'}")
    print("-" * 70)
    for row in rows3:
        month, total, fn, avg_w, avg_wave, min_w, max_w = row
        avg_w = avg_w or 0
        avg_wave = avg_wave or 0
        min_w = min_w or 0
        max_w = max_w or 0
        print(f"{month:<12} {total:<8} {fn:<10} {avg_w:<10.1f} {avg_wave:<10.1f} {min_w:<10.1f} {max_w:.1f}")
else:
    print("  No unified_operation_accuracy data")

# --- 4. Show all data by month/wind range ---
print("\n[4] Wind speed at cancellation events by month")
print("-" * 70)
cur2.execute("""
    SELECT
        strftime('%Y-%m', operation_date) as month,
        predicted_wind,
        predicted_wave,
        predicted_risk,
        actual_status
    FROM unified_operation_accuracy
    WHERE actual_status LIKE '%CANCELLED%'
    ORDER BY month, predicted_wind
""")
rows4 = cur2.fetchall()
if rows4:
    current_month = None
    winds = []
    for month, wind, wave, risk, status in rows4:
        if month != current_month:
            if winds and current_month:
                min_w = min(winds)
                max_w = max(winds)
                avg_w = sum(winds)/len(winds)
                print(f"  {current_month}: min={min_w:.1f} avg={avg_w:.1f} max={max_w:.1f} m/s  ({len(winds)//6} days)")
            current_month = month
            winds = []
        if wind:
            winds.append(wind)
    if winds and current_month:
        min_w = min(winds)
        max_w = max(winds)
        avg_w = sum(winds)/len(winds)
        print(f"  {current_month}: min={min_w:.1f} avg={avg_w:.1f} max={max_w:.1f} m/s  ({len(winds)//6} days)")
else:
    print("  No cancelled events data")

conn2.close()

print("\n" + "=" * 70)
print("CONCLUSION:")
print("Use above data to set month-specific thresholds.")
print("Key question: What is the minimum wind/wave that causes cancellation each month?")
