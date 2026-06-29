#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check all database files for structure and content"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
from pathlib import Path
from datetime import datetime

db_files = [
    'ferry_weather_forecast.db',
    'ferry_actual_operations.db',
    'heartland_ferry_real_data.db',
    'transport_predictions.db',
    'notifications.db',
    'accuracy_analysis.db',
    'api_usage.db',
    'rishiri_flight_data.db',
    'ferry_forecast_data.db',
    'ferry_timetable_data.db',
    'ferry_data.db'
]

for db_file in db_files:
    db_path = Path(db_file)

    if not db_path.exists():
        print(f"\n❌ {db_file} - NOT FOUND")
        continue

    size_mb = db_path.stat().st_size / 1024 / 1024
    modified = datetime.fromtimestamp(db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')

    print(f"\n{'='*70}")
    print(f"📁 {db_file}")
    print(f"   Size: {size_mb:.2f} MB | Modified: {modified}")
    print(f"{'='*70}")

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        if not tables:
            print("   ⚠️  No tables found (empty database)")
            conn.close()
            continue

        print(f"   Tables: {len(tables)}")

        for (table_name,) in tables:
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]

            # Get columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_names = [col[1] for col in columns]

            print(f"\n   📊 {table_name}: {count} rows")
            print(f"      Columns: {', '.join(col_names[:5])}")
            if len(col_names) > 5:
                print(f"               {', '.join(col_names[5:])}")

            # Get recent record if exists
            if count > 0:
                try:
                    cursor.execute(f"SELECT * FROM {table_name} ORDER BY ROWID DESC LIMIT 1")
                    recent = cursor.fetchone()
                    if recent:
                        print(f"      Latest: {str(recent)[:100]}...")
                except:
                    pass

        conn.close()

    except Exception as e:
        print(f"   ❌ Error: {e}")

print(f"\n{'='*70}")
print("Database analysis complete")
print(f"{'='*70}")
