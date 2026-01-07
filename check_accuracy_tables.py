#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Accuracy Tracking System Status
Verifies that all tables exist and shows data counts
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import os
from datetime import datetime

def check_accuracy_system():
    """Check the status of accuracy tracking tables"""

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    db_file = os.path.join(data_dir, "ferry_weather_forecast.db")

    print("=" * 80)
    print("ACCURACY TRACKING SYSTEM STATUS CHECK")
    print("=" * 80)
    print(f"\nDatabase: {db_file}")
    print(f"Exists: {os.path.exists(db_file)}")

    if not os.path.exists(db_file):
        print("\n[ERROR] Database file not found!")
        return

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Check for accuracy-related tables
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND (name LIKE '%accuracy%' OR name LIKE '%threshold%')
        ORDER BY name
    """)

    tables = cursor.fetchall()

    print(f"\n📊 ACCURACY TABLES FOUND: {len(tables)}")
    print("-" * 80)

    expected_tables = [
        'weather_accuracy',
        'operation_accuracy',
        'daily_accuracy_summary',
        'threshold_adjustment_history'
    ]

    for expected in expected_tables:
        exists = any(expected in table[0] for table in tables)
        status = "✓" if exists else "✗"
        print(f"{status} {expected}")

    print("\n" + "=" * 80)
    print("TABLE DETAILS")
    print("=" * 80)

    for table in tables:
        table_name = table[0]

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]

        print(f"\n📋 {table_name}: {count} records")

        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print(f"   Columns: {len(columns)}")

        # Show recent data if exists
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 1")
            latest = cursor.fetchone()

            # Get column names
            col_names = [col[1] for col in columns]

            print(f"   Latest record:")
            for i, col_name in enumerate(col_names[:5]):  # Show first 5 columns
                value = latest[i] if i < len(latest) else 'N/A'
                print(f"     - {col_name}: {value}")

    # Check sailing_forecast table
    print("\n" + "=" * 80)
    print("SAILING FORECAST STATUS")
    print("=" * 80)

    cursor.execute("SELECT COUNT(*) FROM sailing_forecast")
    forecast_count = cursor.fetchone()[0]
    print(f"\n📅 sailing_forecast: {forecast_count} records")

    if forecast_count > 0:
        cursor.execute("""
            SELECT forecast_date, COUNT(*) as sailings
            FROM sailing_forecast
            GROUP BY forecast_date
            ORDER BY forecast_date DESC
            LIMIT 7
        """)

        print("\n   Recent 7 days:")
        for row in cursor.fetchall():
            print(f"     {row[0]}: {row[1]} sailings")

    conn.close()

    print("\n" + "=" * 80)
    print("STATUS CHECK COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    check_accuracy_system()
