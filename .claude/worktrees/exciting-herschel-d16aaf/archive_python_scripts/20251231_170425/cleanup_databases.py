#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cleanup unnecessary database files"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
from pathlib import Path
from datetime import datetime

print("="*70)
print("DATABASE CLEANUP - REMOVING LEGACY/TEST DATABASES")
print("="*70)

# Databases to delete
databases_to_delete = [
    'ferry_actual_operations.db',      # Migrated to heartland_ferry_real_data.db
    'ferry_forecast_data.db',          # Test/simulation data
    'ferry_timetable_data.db',         # Not used by current system
    'ferry_data.db',                   # Nearly empty test DB
    'rishiri_flight_data.db',          # Flight tracking (future feature)
    'transport_predictions.db',        # Empty
    'accuracy_analysis.db',            # Demo data
    'api_usage.db',                    # Empty API monitoring
]

# Databases to KEEP
databases_to_keep = [
    'ferry_weather_forecast.db',       # Main forecast system (ACTIVE)
    'heartland_ferry_real_data.db',    # Real operations data (ACTIVE)
    'notifications.db',                # Push notifications (FUTURE FEATURE)
]

print(f"\n[INFO] Databases to DELETE: {len(databases_to_delete)}")
for db in databases_to_delete:
    db_path = Path(db)
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"  ❌ {db:35s} ({size_kb:6.1f} KB)")
    else:
        print(f"  ⚠️  {db:35s} (not found)")

print(f"\n[INFO] Databases to KEEP: {len(databases_to_keep)}")
for db in databases_to_keep:
    db_path = Path(db)
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"  ✅ {db:35s} ({size_kb:6.1f} KB)")
    else:
        print(f"  ⚠️  {db:35s} (not found)")

# Create backup directory
backup_dir = Path('database_backups') / datetime.now().strftime('%Y%m%d_%H%M%S')
backup_dir.mkdir(parents=True, exist_ok=True)
print(f"\n[INFO] Backup directory created: {backup_dir}")

# Move databases to backup
deleted_count = 0
backup_count = 0

for db in databases_to_delete:
    db_path = Path(db)

    if not db_path.exists():
        print(f"[SKIP] {db} - File not found")
        continue

    try:
        # Move to backup instead of deleting
        backup_path = backup_dir / db
        db_path.rename(backup_path)
        backup_count += 1
        print(f"[MOVED] {db} → {backup_path}")

    except Exception as e:
        print(f"[ERROR] Failed to move {db}: {e}")

print(f"\n{'='*70}")
print(f"[SUCCESS] Database cleanup completed")
print(f"  Backed up: {backup_count} files")
print(f"  Kept: {len(databases_to_keep)} active databases")
print(f"  Backup location: {backup_dir}")
print(f"{'='*70}")

# Summary
print(f"\n📊 ACTIVE DATABASES (Production System)")
print(f"  1. ferry_weather_forecast.db     - 7-day forecasts + risk predictions")
print(f"  2. heartland_ferry_real_data.db  - Real operations + historical data")
print(f"  3. notifications.db              - Push notifications (future)")
print(f"\n💡 TIP: You can safely delete {backup_dir} after confirming the system works")
