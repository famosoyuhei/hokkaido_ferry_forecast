#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Ferry Data Collection Status
"""

import sqlite3
from datetime import datetime, timedelta
import os

def check_all_databases():
    """Check all database files for ferry data"""
    
    print("=" * 60)
    print("FERRY DATA COLLECTION STATUS CHECK")
    print("=" * 60)
    print()
    
    # List all database files
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    
    print(f"Found {len(db_files)} database files:")
    for db_file in db_files:
        print(f"  - {db_file}")
    print()
    
    # Check each database for ferry-related tables
    for db_file in db_files:
        print(f"[CHECKING] {db_file}")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            if tables:
                print(f"  Tables: {', '.join([t[0] for t in tables])}")
                
                # Look for ferry-related data
                for table_name, in tables:
                    if 'ferry' in table_name.lower() or 'transport' in table_name.lower():
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        print(f"  -> {table_name}: {count} records")
                        
                        if count > 0:
                            # Get date range
                            try:
                                cursor.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {table_name}")
                                min_date, max_date = cursor.fetchone()
                                if min_date and max_date:
                                    print(f"     Date range: {min_date[:19]} to {max_date[:19]}")
                                    
                                    # Check recent activity
                                    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE timestamp >= datetime('now', '-24 hours')")
                                    recent = cursor.fetchone()[0]
                                    print(f"     Recent (24h): {recent} records")
                            except:
                                print(f"     (No timestamp column)")
                        
            else:
                print("  No tables found")
                
            conn.close()
            
        except Exception as e:
            print(f"  Error: {e}")
        
        print()
    
def check_task_scheduler():
    """Check if Windows Task Scheduler is running data collection"""
    
    print("=" * 60)
    print("AUTOMATED COLLECTION STATUS")
    print("=" * 60)
    
    try:
        # Check if batch files exist
        batch_files = ['auto_data_collection_daemon.bat', 'create_task_scheduler.bat']
        
        for batch_file in batch_files:
            if os.path.exists(batch_file):
                print(f"[OK] {batch_file} exists")
                
                # Read the batch file to see what it does
                try:
                    with open(batch_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if 'ferry_monitoring_system.py' in content:
                        print(f"     -> Runs ferry data collection")
                    if 'python' in content:
                        print(f"     -> Python script execution configured")
                except:
                    print(f"     -> Could not read file content")
            else:
                print(f"[MISSING] {batch_file}")
        
        print()
        
        # Check Python monitoring script
        if os.path.exists('ferry_monitoring_system.py'):
            print("[OK] ferry_monitoring_system.py exists")
            
            # Check if it's the data collection version
            try:
                with open('ferry_monitoring_system.py', 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'collect_ferry_data' in content:
                    print("     -> Contains data collection function")
                if 'sqlite' in content.lower():
                    print("     -> Uses SQLite database")
                if 'requests' in content:
                    print("     -> Makes web requests")
            except Exception as e:
                print(f"     -> Could not analyze script: {e}")
        else:
            print("[MISSING] ferry_monitoring_system.py")
            
    except Exception as e:
        print(f"Error checking task scheduler: {e}")

def check_recent_activity():
    """Check for recent data collection activity"""
    
    print("=" * 60)
    print("RECENT COLLECTION ACTIVITY")
    print("=" * 60)
    
    # Check log files
    log_files = [f for f in os.listdir('.') if f.endswith('.log')]
    
    if log_files:
        print(f"Found {len(log_files)} log files:")
        for log_file in log_files:
            try:
                stat = os.stat(log_file)
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                size = stat.st_size
                print(f"  {log_file}: {size} bytes, modified {mod_time}")
                
                # Read recent entries
                if size > 0 and size < 10000:  # Only read small files
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        if lines:
                            print(f"    Last entry: {lines[-1].strip()}")
                    except:
                        print(f"    (Could not read log content)")
                        
            except Exception as e:
                print(f"  {log_file}: Error - {e}")
    else:
        print("No log files found")
    
    print()
    
    # Check database modification times
    print("Database file modification times:")
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    
    for db_file in db_files:
        try:
            stat = os.stat(db_file)
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            size = stat.st_size
            
            # Check if modified recently
            hours_ago = (datetime.now() - mod_time).total_seconds() / 3600
            status = "RECENT" if hours_ago < 24 else "OLD"
            
            print(f"  {db_file}: {status} ({hours_ago:.1f}h ago) - {size} bytes")
            
        except Exception as e:
            print(f"  {db_file}: Error - {e}")

def main():
    """Main check function"""
    
    check_all_databases()
    check_task_scheduler()
    check_recent_activity()
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    # Check if ferry_monitoring_system.py exists and run it once
    if os.path.exists('ferry_monitoring_system.py'):
        print("[ACTION] Run manual data collection to verify:")
        print("  python ferry_monitoring_system.py")
    else:
        print("[ACTION] Ferry monitoring system not found")
        print("  Need to set up automated data collection")
    
    print("\n[ACTION] Check Windows Task Scheduler:")
    print("  schtasks /query /tn \"Ferry Data Collection\"")

if __name__ == "__main__":
    main()