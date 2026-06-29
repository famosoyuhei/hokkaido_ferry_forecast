#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Real Data Collection Status
Verify if automated collection is working with real data
"""

import sqlite3
import os
from datetime import datetime, timedelta

def check_original_data():
    """Check for the original 54 records from August"""
    
    print("=" * 60)
    print("CHECKING ORIGINAL DATA VS CURRENT DATA")
    print("=" * 60)
    
    # Look for databases that might contain original data
    possible_dbs = []
    for file in os.listdir('.'):
        if file.endswith('.db'):
            possible_dbs.append(file)
    
    print(f"Found {len(possible_dbs)} database files to check:")
    for db in possible_dbs:
        print(f"  - {db}")
    print()
    
    original_data_found = False
    
    for db_file in possible_dbs:
        print(f"[CHECKING] {db_file}")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                try:
                    # Check if this table has ferry-related data
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in cursor.fetchall()]
                    
                    # Look for ferry-related columns
                    ferry_indicators = ['ferry', 'route', 'departure', 'cancelled', 'weather']
                    has_ferry_data = any(indicator in ' '.join(columns).lower() for indicator in ferry_indicators)
                    
                    if has_ferry_data:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        print(f"  Table '{table}': {count} records")
                        
                        if count > 0:
                            # Check date ranges
                            date_columns = ['timestamp', 'date', 'collection_date', 'created_at']
                            date_col = None
                            for col in date_columns:
                                if col in columns:
                                    date_col = col
                                    break
                            
                            if date_col:
                                cursor.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table}")
                                min_date, max_date = cursor.fetchone()
                                print(f"    Date range: {min_date} to {max_date}")
                                
                                # Check if this looks like the original 54 records
                                if count == 54 or '2025-08' in str(min_date):
                                    print(f"    -> POSSIBLE ORIGINAL DATA: {count} records")
                                    original_data_found = True
                                    
                                    # Show recent vs old data
                                    cursor.execute(f"""
                                        SELECT COUNT(*) FROM {table} 
                                        WHERE {date_col} >= datetime('now', '-24 hours')
                                    """)
                                    recent = cursor.fetchone()[0]
                                    print(f"    -> Recent (24h): {recent} records")
                                    
                                elif count == 480:
                                    print(f"    -> GENERATED SAMPLE DATA: {count} records")
                                
                except Exception as e:
                    continue
            
            conn.close()
            
        except Exception as e:
            print(f"  Error accessing {db_file}: {e}")
        
        print()
    
    return original_data_found

def check_automation_logs():
    """Check logs for automation activity"""
    
    print("=" * 60)
    print("CHECKING AUTOMATION LOGS")
    print("=" * 60)
    
    log_files = [f for f in os.listdir('.') if f.endswith('.log')]
    
    if not log_files:
        print("No log files found")
        return
    
    for log_file in log_files:
        try:
            stat = os.stat(log_file)
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            size = stat.st_size
            
            print(f"[LOG] {log_file}")
            print(f"  Size: {size} bytes")
            print(f"  Modified: {mod_time}")
            
            # Check if modified since yesterday
            hours_since_mod = (datetime.now() - mod_time).total_seconds() / 3600
            if hours_since_mod < 24:
                print(f"  Status: RECENT ({hours_since_mod:.1f}h ago)")
            else:
                print(f"  Status: OLD ({hours_since_mod:.1f}h ago)")
            
            # Read recent log entries
            if size > 0 and size < 50000:
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    if lines:
                        print(f"  Total lines: {len(lines)}")
                        
                        # Show last few entries
                        print("  Recent entries:")
                        for line in lines[-3:]:
                            print(f"    {line.strip()}")
                        
                        # Look for error patterns
                        error_count = sum(1 for line in lines if 'ERROR' in line.upper())
                        success_count = sum(1 for line in lines if any(word in line.upper() 
                                          for word in ['SUCCESS', 'COLLECTED', 'SAVED']))
                        
                        print(f"  Errors: {error_count}, Success: {success_count}")
                
                except Exception as e:
                    print(f"  Could not read log: {e}")
            
        except Exception as e:
            print(f"  Error checking {log_file}: {e}")
        
        print()

def check_task_scheduler_files():
    """Check if task scheduler batch files exist and are configured correctly"""
    
    print("=" * 60)
    print("CHECKING TASK SCHEDULER SETUP")
    print("=" * 60)
    
    batch_files = [
        'auto_data_collection_daemon.bat',
        'create_task_scheduler.bat'
    ]
    
    for batch_file in batch_files:
        if os.path.exists(batch_file):
            print(f"[OK] {batch_file} exists")
            
            try:
                with open(batch_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                print(f"  Content preview:")
                lines = content.split('\n')[:5]
                for line in lines:
                    if line.strip():
                        print(f"    {line.strip()}")
                
                # Check for common issues
                if 'python' in content.lower():
                    print("  -> Contains Python execution")
                if 'ferry_monitoring_system' in content:
                    print("  -> References ferry monitoring system")
                if 'cd' in content.lower():
                    print("  -> Changes directory")
                
            except Exception as e:
                print(f"  Error reading {batch_file}: {e}")
        else:
            print(f"[MISSING] {batch_file}")
        
        print()
    
    # Check if ferry monitoring script exists
    if os.path.exists('ferry_monitoring_system.py'):
        stat = os.stat('ferry_monitoring_system.py')
        mod_time = datetime.fromtimestamp(stat.st_mtime)
        print(f"[OK] ferry_monitoring_system.py exists")
        print(f"  Modified: {mod_time}")
    else:
        print(f"[MISSING] ferry_monitoring_system.py")

def analyze_data_authenticity():
    """Try to determine if data is real vs generated"""
    
    print("=" * 60)
    print("DATA AUTHENTICITY ANALYSIS")
    print("=" * 60)
    
    # Check ferry_forecast_data.db specifically
    if os.path.exists('ferry_forecast_data.db'):
        conn = sqlite3.connect('ferry_forecast_data.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM ferry_data")
            total = cursor.fetchone()[0]
            
            if total > 0:
                print(f"Ferry data records: {total}")
                
                # Check collection_status table for clues
                cursor.execute("SELECT * FROM collection_status ORDER BY timestamp DESC LIMIT 5")
                status_records = cursor.fetchall()
                
                print(f"Collection status entries: {len(status_records)}")
                for record in status_records:
                    timestamp, total_records, success, error_msg = record[1:5]
                    print(f"  {timestamp}: {total_records} records, Success: {success}")
                    if error_msg:
                        print(f"    Message: {error_msg}")
                        if "Initial data generation" in error_msg:
                            print(f"    -> IDENTIFIED: Generated sample data")
                        elif "collection" in error_msg.lower():
                            print(f"    -> IDENTIFIED: Real data collection attempt")
                
                # Check data patterns that suggest real vs generated data
                cursor.execute("""
                    SELECT weather_condition, COUNT(*) 
                    FROM ferry_data 
                    GROUP BY weather_condition
                """)
                weather_dist = cursor.fetchall()
                
                print(f"Weather condition distribution:")
                for condition, count in weather_dist:
                    percentage = (count / total * 100)
                    print(f"  {condition}: {count} ({percentage:.1f}%)")
                    
                # Perfect distributions suggest generated data
                if any(count == weather_dist[0][1] for _, count in weather_dist[1:]):
                    print("  -> PATTERN: Suspiciously even distribution (likely generated)")
                
        except Exception as e:
            print(f"Error analyzing data: {e}")
        
        conn.close()
    else:
        print("No ferry_forecast_data.db found")

def main():
    """Main analysis"""
    
    print("REAL DATA COLLECTION STATUS CHECK")
    print("Checking if the 54 original records have grown since yesterday...")
    print()
    
    # Check for original data
    original_found = check_original_data()
    
    # Check automation logs
    check_automation_logs()
    
    # Check task scheduler setup
    check_task_scheduler_files()
    
    # Analyze data authenticity
    analyze_data_authenticity()
    
    print("=" * 60)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 60)
    
    if original_found:
        print("[FOUND] Original data from August detected")
    else:
        print("[NOT FOUND] Could not locate original 54 records")
    
    print("\n[RECOMMENDATIONS]")
    print("1. Check if Task Scheduler task is actually running")
    print("2. Verify Python path in batch file")
    print("3. Test manual execution: python ferry_monitoring_system.py")
    print("4. Check Windows Event Viewer for task execution logs")

if __name__ == "__main__":
    main()