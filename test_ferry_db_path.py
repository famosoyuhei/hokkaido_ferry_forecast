#!/usr/bin/env python3
"""Test what database path the ferry collector uses"""
import os
from pathlib import Path

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
db_file = os.path.join(data_dir, "heartland_ferry_real_data.db")
csv_file = Path(data_dir) / "data" / "ferry_cancellation_log.csv"

print(f"Data dir: {data_dir}")
print(f"DB file: {db_file}")
print(f"CSV file: {csv_file}")
print(f"\nDB exists: {os.path.exists(db_file)}")

if os.path.exists(db_file):
    import sqlite3
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\nTables: {[t[0] for t in tables]}")

    cursor.execute("SELECT COUNT(*) FROM ferry_status")
    count = cursor.fetchone()[0]
    print(f"ferry_status records: {count}")

    cursor.execute("SELECT DISTINCT scrape_date FROM ferry_status ORDER BY scrape_date DESC LIMIT 5")
    dates = cursor.fetchall()
    print(f"\nLast 5 dates: {[d[0] for d in dates]}")

    conn.close()
