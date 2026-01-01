#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cleanup Python scripts - move legacy/unused files to archive"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
from datetime import datetime
import shutil

print("="*70)
print("PYTHON SCRIPTS CLEANUP")
print("="*70)

# Files to KEEP (7 files)
keep_files = {
    'forecast_dashboard.py',           # Web dashboard (Production)
    'weather_forecast_collector.py',   # Weather collector (Production)
    'improved_ferry_collector.py',     # Ferry collector (Production)
    'accuracy_tracker.py',             # Accuracy tracking (Production)
    'notification_service.py',         # Notification (Production)
    'push_notification_service.py',    # Push notification (Future)
    'generate_pwa_icons.py',           # PWA icons (Utility)
}

# Get all Python files
all_py_files = set(f.name for f in Path('.').glob('*.py'))

# Files to archive
archive_files = all_py_files - keep_files

print(f"\n📊 Analysis:")
print(f"  Total Python files: {len(all_py_files)}")
print(f"  Files to KEEP: {len(keep_files)}")
print(f"  Files to ARCHIVE: {len(archive_files)}")

# Create archive directory
archive_dir = Path('archive_python_scripts') / datetime.now().strftime('%Y%m%d_%H%M%S')
archive_dir.mkdir(parents=True, exist_ok=True)

print(f"\n📁 Archive directory: {archive_dir}")

# Show files to keep
print(f"\n{'='*70}")
print(f"✅ FILES TO KEEP ({len(keep_files)} files)")
print(f"{'='*70}")
for filename in sorted(keep_files):
    if Path(filename).exists():
        size_kb = Path(filename).stat().st_size / 1024
        print(f"  {filename:45s} {size_kb:6.1f} KB")
    else:
        print(f"  {filename:45s} (not found)")

# Show files to archive
print(f"\n{'='*70}")
print(f"🗂️  FILES TO ARCHIVE ({len(archive_files)} files)")
print(f"{'='*70}")

# Categorize archived files
categories = {
    'Notification Systems (Legacy)': [],
    'Mobile Apps (Legacy)': [],
    'Prediction Systems (Legacy)': [],
    'Flight Tracking': [],
    'Testing/Verification': [],
    'Setup Guides': [],
    'Data Collection (Legacy)': [],
    'Temporary/Debug': [],
    'Other': []
}

for filename in sorted(archive_files):
    if not Path(filename).exists():
        continue

    # Categorize
    if any(x in filename for x in ['discord', 'line', 'notification_system']):
        categories['Notification Systems (Legacy)'].append(filename)
    elif any(x in filename for x in ['mobile_app', 'mobile_web', 'simple_mobile', 'ferry_web_app']):
        categories['Mobile Apps (Legacy)'].append(filename)
    elif any(x in filename for x in ['prediction', 'model', 'ml', 'adaptive', 'integrated']):
        categories['Prediction Systems (Legacy)'].append(filename)
    elif any(x in filename for x in ['flight', 'aviation']):
        categories['Flight Tracking'].append(filename)
    elif any(x in filename for x in ['test', 'check', 'verify', 'view', 'analyze']):
        categories['Testing/Verification'].append(filename)
    elif any(x in filename for x in ['setup', 'guide', 'interactive']):
        categories['Setup Guides'].append(filename)
    elif any(x in filename for x in ['collect', 'scraper', 'heartland', 'cloud_ferry']):
        categories['Data Collection (Legacy)'].append(filename)
    elif any(x in filename for x in ['debug', 'demo', 'temp', 'cleanup', 'migrate']):
        categories['Temporary/Debug'].append(filename)
    else:
        categories['Other'].append(filename)

for category, files in categories.items():
    if files:
        print(f"\n  📂 {category} ({len(files)} files):")
        for f in sorted(files):
            size_kb = Path(f).stat().st_size / 1024
            print(f"     {f:43s} {size_kb:6.1f} KB")

# Move files to archive
print(f"\n{'='*70}")
print(f"Moving files to archive...")
print(f"{'='*70}")

moved_count = 0
for filename in archive_files:
    filepath = Path(filename)

    if not filepath.exists():
        continue

    try:
        dest = archive_dir / filename
        shutil.move(str(filepath), str(dest))
        moved_count += 1
        print(f"  ✓ {filename}")
    except Exception as e:
        print(f"  ✗ {filename} - Error: {e}")

print(f"\n{'='*70}")
print(f"✅ CLEANUP COMPLETED")
print(f"{'='*70}")
print(f"  Files kept: {len(keep_files)}")
print(f"  Files archived: {moved_count}")
print(f"  Archive location: {archive_dir}")
print(f"\n💡 TIP: Review the archive and delete it after confirming the system works")
print(f"{'='*70}")

# Create summary file
summary_file = archive_dir / 'ARCHIVE_SUMMARY.txt'
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("Python Scripts Archive Summary\n")
    f.write("="*70 + "\n")
    f.write(f"Archived on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Total archived: {moved_count} files\n\n")

    f.write("Files kept in production:\n")
    for filename in sorted(keep_files):
        f.write(f"  - {filename}\n")

    f.write("\n" + "="*70 + "\n")
    f.write("Archived files by category:\n")
    f.write("="*70 + "\n\n")

    for category, files in categories.items():
        if files:
            f.write(f"{category} ({len(files)} files):\n")
            for filename in sorted(files):
                f.write(f"  - {filename}\n")
            f.write("\n")

print(f"\n📄 Summary file created: {summary_file}")
