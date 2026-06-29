#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze all Python scripts and categorize them"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import os

print("="*70)
print("PYTHON SCRIPTS ANALYSIS")
print("="*70)

# Get all Python files
py_files = list(Path('.').glob('*.py'))

# Categorize scripts
categories = {
    'PRODUCTION': [],
    'COLLECTORS': [],
    'UTILITIES': [],
    'TESTING': [],
    'LEGACY': [],
    'SETUP_GUIDES': [],
    'TEMPORARY': []
}

# Known production scripts (from railway.json and analysis)
production_scripts = {
    'forecast_dashboard.py': 'Web dashboard (Railway main service)',
    'weather_forecast_collector.py': 'Weather forecast collector (Cron 4x/day)',
    'improved_ferry_collector.py': 'Ferry operations collector (Cron daily)',
    'accuracy_tracker.py': 'Accuracy tracking (Cron daily)',
    'notification_service.py': 'Notification system (Cron daily)',
}

# Collector scripts
collector_scripts = {
    'heartland_ferry_scraper.py': 'Basic ferry scraper (legacy)',
    'ferry_data_collector.py': 'Simulated data generator (legacy)',
    'cloud_ferry_collector.py': 'Cloud deployment template (deprecated)',
    'collect_ferry_data_now.py': 'Manual ferry data collection',
    'collect_flight_data.py': 'Flight data collector (FlightAware)',
    'collect_recent_flights.py': 'Recent flights collector',
}

# Utility scripts
utility_scripts = {
    'generate_pwa_icons.py': 'PWA icon generator',
    'generate_forecast_data.py': 'Forecast data generator',
}

# Testing scripts
test_scripts = [f for f in py_files if 'test' in f.name.lower() or 'check' in f.name.lower() or 'verify' in f.name.lower() or 'view' in f.name.lower()]

# Setup/guide scripts
setup_scripts = [f for f in py_files if 'setup' in f.name.lower() or 'guide' in f.name.lower() or 'interactive' in f.name.lower()]

# Temporary/debug scripts
temp_scripts = [f for f in py_files if 'debug' in f.name.lower() or 'demo' in f.name.lower()]

# Categorize each file
for py_file in py_files:
    name = py_file.name
    size_kb = py_file.stat().st_size / 1024

    if name in production_scripts:
        categories['PRODUCTION'].append((name, size_kb, production_scripts[name]))
    elif name in collector_scripts:
        categories['COLLECTORS'].append((name, size_kb, collector_scripts[name]))
    elif name in utility_scripts:
        categories['UTILITIES'].append((name, size_kb, utility_scripts[name]))
    elif py_file in test_scripts:
        categories['TESTING'].append((name, size_kb, 'Testing/verification script'))
    elif py_file in setup_scripts:
        categories['SETUP_GUIDES'].append((name, size_kb, 'Setup/guide script'))
    elif py_file in temp_scripts:
        categories['TEMPORARY'].append((name, size_kb, 'Temporary/debug script'))
    else:
        categories['LEGACY'].append((name, size_kb, 'Uncategorized'))

# Print results
for category, scripts in categories.items():
    if scripts:
        print(f"\n{'='*70}")
        print(f"📁 {category} ({len(scripts)} files)")
        print(f"{'='*70}")

        for name, size, desc in scripts:
            print(f"  {name:45s} {size:6.1f} KB  {desc}")

print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"  Total Python files: {len(py_files)}")
print(f"  Production scripts: {len(categories['PRODUCTION'])}")
print(f"  Collectors: {len(categories['COLLECTORS'])}")
print(f"  Utilities: {len(categories['UTILITIES'])}")
print(f"  Testing: {len(categories['TESTING'])}")
print(f"  Setup/Guides: {len(categories['SETUP_GUIDES'])}")
print(f"  Temporary: {len(categories['TEMPORARY'])}")
print(f"  Legacy/Other: {len(categories['LEGACY'])}")
print(f"{'='*70}")
