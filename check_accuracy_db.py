#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check accuracy tracking database"""

import sqlite3

# Check actual operations database
print("=== Checking Accuracy Database ===\n")

conn = sqlite3.connect('ferry_actual_operations.db')
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables:")
for table in tables:
    print(f"  - {table[0]}")

print("\n=== Actual Operations ===")
cur.execute('SELECT COUNT(*) FROM actual_operations')
print(f"Total records: {cur.fetchone()[0]}")

cur.execute('SELECT operation_date, route, status FROM actual_operations ORDER BY operation_date DESC LIMIT 5')
print("\nRecent records:")
for row in cur.fetchall():
    print(f"  {row[0]} - {row[1]}: {row[2]}")

print("\n=== Accuracy Metrics ===")
cur.execute('SELECT COUNT(*) FROM accuracy_metrics')
print(f"Total records: {cur.fetchone()[0]}")

print("\n=== Accuracy Summary ===")
cur.execute('SELECT COUNT(*) FROM accuracy_summary')
print(f"Total summaries: {cur.fetchone()[0]}")

cur.execute('SELECT * FROM accuracy_summary ORDER BY date DESC LIMIT 5')
summaries = cur.fetchall()
if summaries:
    print("\nRecent summaries:")
    for row in summaries:
        print(f"  Date: {row[1]}, Accuracy: {row[6]:.1%}, Predictions: {row[2]}")
else:
    print("No accuracy summaries yet - need more data collection")

conn.close()

# Check forecast database
print("\n\n=== Checking Forecast Database ===\n")
conn = sqlite3.connect('ferry_weather_forecast.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM cancellation_forecast')
print(f"Total forecast records: {cur.fetchone()[0]}")

cur.execute('PRAGMA table_info(cancellation_forecast)')
cols = cur.fetchall()
print("\nTable columns:")
for col in cols:
    print(f"  - {col[1]} ({col[2]})")

conn.close()
