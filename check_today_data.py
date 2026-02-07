#!/usr/bin/env python3
"""Check what dates have data"""
import sqlite3
import os

data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
real_data_db = os.path.join(data_dir, "heartland_ferry_real_data.db")

conn = sqlite3.connect(real_data_db)
cursor = conn.cursor()

cursor.execute('''
    SELECT DISTINCT scrape_date, COUNT(*)
    FROM ferry_status
    GROUP BY scrape_date
    ORDER BY scrape_date DESC
    LIMIT 10
''')

print("Dates with ferry_status data:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} records")

conn.close()
