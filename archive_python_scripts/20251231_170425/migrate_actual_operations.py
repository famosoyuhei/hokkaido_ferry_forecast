#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migrate ferry_actual_operations.db data to heartland_ferry_real_data.db"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
from datetime import datetime

print("="*70)
print("MIGRATING ferry_actual_operations.db → heartland_ferry_real_data.db")
print("="*70)

# Connect to both databases
source_db = sqlite3.connect('ferry_actual_operations.db')
target_db = sqlite3.connect('heartland_ferry_real_data.db')

source_cursor = source_db.cursor()
target_cursor = target_db.cursor()

# Check source data
print("\n[INFO] Checking source database...")
source_cursor.execute("SELECT COUNT(*) FROM actual_operations")
total_records = source_cursor.fetchone()[0]
print(f"[OK] Found {total_records} records in ferry_actual_operations.db")

# Get all data from source
source_cursor.execute("""
    SELECT operation_date, route, status, cancellation_reason,
           actual_wind_speed, actual_wave_height, actual_visibility,
           actual_weather, collected_at, data_source
    FROM actual_operations
    ORDER BY operation_date
""")

records = source_cursor.fetchall()

# Display records
print(f"\n[INFO] Records to migrate:")
for record in records:
    operation_date, route, status, reason = record[0:4]
    print(f"  {operation_date} | {route:25s} | {status:10s} | {reason or 'N/A'}")

# Create archive table in target database
print(f"\n[INFO] Creating historical_operations table...")
target_cursor.execute("""
    CREATE TABLE IF NOT EXISTS historical_operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_date TEXT,
        route TEXT,
        status TEXT,
        cancellation_reason TEXT,
        actual_wind_speed REAL,
        actual_wave_height REAL,
        actual_visibility REAL,
        actual_weather TEXT,
        collected_at TEXT,
        data_source TEXT,
        migrated_at TEXT
    )
""")

# Insert records
print(f"[INFO] Migrating {len(records)} records...")
migrated = 0

for record in records:
    target_cursor.execute("""
        INSERT INTO historical_operations (
            operation_date, route, status, cancellation_reason,
            actual_wind_speed, actual_wave_height, actual_visibility,
            actual_weather, collected_at, data_source, migrated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (*record, datetime.now().isoformat()))
    migrated += 1

target_db.commit()
print(f"[OK] Migrated {migrated} records successfully")

# Verify migration
target_cursor.execute("SELECT COUNT(*) FROM historical_operations")
target_count = target_cursor.fetchone()[0]
print(f"[OK] Verified: {target_count} records in historical_operations table")

# Close connections
source_db.close()
target_db.close()

print("\n" + "="*70)
print("[SUCCESS] Migration completed")
print(f"  Source: ferry_actual_operations.db ({total_records} records)")
print(f"  Target: heartland_ferry_real_data.db/historical_operations ({target_count} records)")
print(f"  Status: Ready to delete ferry_actual_operations.db")
print("="*70)
