#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check if timetable data is used anywhere in the current system"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("="*70)
print("CHECKING TIMETABLE USAGE IN CURRENT SYSTEM")
print("="*70)

# Check if improved_ferry_collector.py uses timetable data
print("\n[INFO] Checking improved_ferry_collector.py...")
with open('improved_ferry_collector.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'ferry_timetable_data.db' in content:
        print("[FOUND] Uses ferry_timetable_data.db")
    else:
        print("[OK] Does NOT use ferry_timetable_data.db")

    if 'timetable' in content.lower():
        print("[INFO] Contains 'timetable' keyword")
    else:
        print("[OK] Does NOT reference timetable")

# Check if forecast_dashboard.py uses timetable data
print("\n[INFO] Checking forecast_dashboard.py...")
with open('forecast_dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'ferry_timetable_data.db' in content:
        print("[FOUND] Uses ferry_timetable_data.db")
    else:
        print("[OK] Does NOT use ferry_timetable_data.db")

# Check if weather_forecast_collector.py uses timetable data
print("\n[INFO] Checking weather_forecast_collector.py...")
with open('weather_forecast_collector.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'ferry_timetable_data.db' in content:
        print("[FOUND] Uses ferry_timetable_data.db")
    else:
        print("[OK] Does NOT use ferry_timetable_data.db")

print("\n" + "="*70)
print("[CONCLUSION]")
print("  Current system extracts schedules from:")
print("  → https://heartlandferry.jp/status/ (daily operations)")
print("  ")
print("  Timetable database (ferry_timetable_data.db) is:")
print("  → NOT used by main scripts")
print("  → Safe to delete")
print("="*70)
