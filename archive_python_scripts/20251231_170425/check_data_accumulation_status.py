#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Data Accumulation Status
Comprehensive check of all data collection systems
"""

import sqlite3
import os
from datetime import datetime, timedelta
import json

class DataAccumulationChecker:
    """Check status of all data collection systems"""
    
    def __init__(self):
        self.databases = [
            {
                'name': 'Real Ferry Status',
                'file': 'heartland_ferry_real_data.db',
                'table': 'ferry_status',
                'date_column': 'collection_timestamp'
            },
            {
                'name': 'Ferry Timetables',
                'file': 'ferry_timetable_data.db', 
                'table': 'seasonal_schedules',
                'date_column': 'scraped_date'
            },
            {
                'name': 'Flight Data',
                'file': 'rishiri_flight_data.db',
                'table': 'flights',
                'date_column': 'collection_date'
            },
            {
                'name': 'Generated Ferry Data',
                'file': 'ferry_forecast_data.db',
                'table': 'ferry_data',
                'date_column': 'collection_date'
            },
            {
                'name': 'Transport Predictions',
                'file': 'transport_predictions.db',
                'table': 'predictions',
                'date_column': None
            }
        ]
    
    def check_database_status(self, db_info):
        """Check individual database status"""
        
        db_file = db_info['file']
        
        if not os.path.exists(db_file):
            return {
                'exists': False,
                'total_records': 0,
                'latest_record': None,
                'collection_days': 0,
                'recent_records_24h': 0,
                'file_size': 0,
                'last_modified': None
            }
        
        try:
            # File statistics
            stat = os.stat(db_file)
            file_size = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (db_info['table'],))
            if not cursor.fetchone():
                conn.close()
                return {
                    'exists': True,
                    'table_exists': False,
                    'total_records': 0,
                    'latest_record': None,
                    'collection_days': 0,
                    'recent_records_24h': 0,
                    'file_size': file_size,
                    'last_modified': last_modified
                }
            
            # Total records
            cursor.execute(f"SELECT COUNT(*) FROM {db_info['table']}")
            total_records = cursor.fetchone()[0]
            
            # Latest record
            latest_record = None
            collection_days = 0
            recent_records_24h = 0
            
            if db_info['date_column'] and total_records > 0:
                try:
                    cursor.execute(f"SELECT MAX({db_info['date_column']}) FROM {db_info['table']}")
                    latest_record = cursor.fetchone()[0]
                    
                    # Collection days
                    cursor.execute(f"SELECT COUNT(DISTINCT DATE({db_info['date_column']})) FROM {db_info['table']}")
                    collection_days = cursor.fetchone()[0]
                    
                    # Recent records (24 hours)
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM {db_info['table']} 
                        WHERE {db_info['date_column']} >= datetime('now', '-24 hours')
                    """)
                    recent_records_24h = cursor.fetchone()[0]
                    
                except Exception as e:
                    print(f"[WARNING] Date analysis failed for {db_info['name']}: {e}")
            
            conn.close()
            
            return {
                'exists': True,
                'table_exists': True,
                'total_records': total_records,
                'latest_record': latest_record,
                'collection_days': collection_days,
                'recent_records_24h': recent_records_24h,
                'file_size': file_size,
                'last_modified': last_modified
            }
            
        except Exception as e:
            return {
                'exists': True,
                'error': str(e),
                'file_size': file_size if 'file_size' in locals() else 0,
                'last_modified': last_modified if 'last_modified' in locals() else None
            }
    
    def check_automation_status(self):
        """Check automation systems status"""
        
        print("=" * 60)
        print("AUTOMATION SYSTEMS STATUS")
        print("=" * 60)
        
        # Check batch files
        automation_files = [
            'heartland_ferry_scraper_task.bat',
            'setup_daily_ferry_collection.bat',
            'auto_data_collection_daemon.bat'
        ]
        
        for batch_file in automation_files:
            if os.path.exists(batch_file):
                stat = os.stat(batch_file)
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                print(f"[OK] {batch_file} - Modified: {mod_time}")
            else:
                print(f"[MISSING] {batch_file}")
        
        print()
        
        # Check Python scripts
        collection_scripts = [
            'heartland_ferry_scraper.py',
            'ferry_timetable_system.py',
            'collect_flight_data.py',
            'ferry_monitoring_system.py'
        ]
        
        for script in collection_scripts:
            if os.path.exists(script):
                stat = os.stat(script)
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                print(f"[OK] {script} - Modified: {mod_time}")
            else:
                print(f"[MISSING] {script}")
        
        print()
    
    def check_log_activity(self):
        """Check recent log activity"""
        
        print("=" * 60)
        print("RECENT LOG ACTIVITY")
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
                
                hours_since_mod = (datetime.now() - mod_time).total_seconds() / 3600
                status = "RECENT" if hours_since_mod < 24 else "OLD"
                
                print(f"[{status}] {log_file}")
                print(f"  Size: {size} bytes")
                print(f"  Modified: {mod_time} ({hours_since_mod:.1f}h ago)")
                
                # Check for recent activity indicators
                if size > 0 and size < 10000:
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Look for today's entries
                        today = datetime.now().strftime('%Y-%m-%d')
                        today_entries = content.count(today)
                        
                        error_count = content.upper().count('ERROR')
                        success_count = content.upper().count('SUCCESS')
                        
                        print(f"  Today's entries: {today_entries}")
                        print(f"  Errors: {error_count}, Success: {success_count}")
                        
                    except Exception as e:
                        print(f"  Could not read log: {e}")
                
                print()
                
            except Exception as e:
                print(f"[ERROR] {log_file}: {e}")
    
    def generate_accumulation_report(self):
        """Generate comprehensive data accumulation report"""
        
        print("=" * 70)
        print("COMPREHENSIVE DATA ACCUMULATION STATUS REPORT")
        print("=" * 70)
        print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        total_records = 0
        active_databases = 0
        recent_activity = 0
        
        for db_info in self.databases:
            print(f"[CHECKING] {db_info['name']}")
            status = self.check_database_status(db_info)
            
            if status.get('exists', False):
                if status.get('table_exists', False):
                    active_databases += 1
                    total_records += status['total_records']
                    recent_activity += status['recent_records_24h']
                    
                    print(f"  Database: {db_info['file']}")
                    print(f"  Total records: {status['total_records']}")
                    print(f"  Collection days: {status['collection_days']}")
                    print(f"  Recent (24h): {status['recent_records_24h']}")
                    print(f"  Latest record: {status['latest_record']}")
                    print(f"  File size: {status['file_size']:,} bytes")
                    print(f"  Last modified: {status['last_modified']}")
                    
                    # Assessment
                    if status['recent_records_24h'] > 0:
                        print(f"  Status: ACTIVE - Recent data collection")
                    elif status['total_records'] > 0:
                        print(f"  Status: INACTIVE - No recent collection")
                    else:
                        print(f"  Status: EMPTY - No data collected")
                        
                else:
                    print(f"  Status: TABLE MISSING in {db_info['file']}")
                    
            else:
                print(f"  Status: DATABASE NOT FOUND - {db_info['file']}")
            
            print()
        
        # Overall summary
        print("=" * 70)
        print("OVERALL SUMMARY")
        print("=" * 70)
        print(f"Active databases: {active_databases}/{len(self.databases)}")
        print(f"Total records across all systems: {total_records:,}")
        print(f"Recent activity (24h): {recent_activity} new records")
        print()
        
        # Status assessment
        if recent_activity > 0:
            print("[STATUS] DATA COLLECTION ACTIVE")
            print("✓ Systems are actively collecting data")
        elif total_records > 100:
            print("[STATUS] DATA COLLECTION STAGNANT") 
            print("⚠ Historical data exists but no recent collection")
        else:
            print("[STATUS] DATA COLLECTION INACTIVE")
            print("✗ Limited or no data collection occurring")
        
        print()
        
        # Recommendations
        print("RECOMMENDATIONS:")
        if recent_activity == 0:
            print("1. Check Windows Task Scheduler status")
            print("2. Run manual data collection tests:")
            print("   python heartland_ferry_scraper.py")
            print("3. Verify Python path in batch files")
        else:
            print("1. Data collection appears to be working")
            print("2. Monitor daily for consistent accumulation")
        
        return {
            'active_databases': active_databases,
            'total_records': total_records,
            'recent_activity': recent_activity,
            'status': 'ACTIVE' if recent_activity > 0 else 'INACTIVE'
        }
    
    def run_full_check(self):
        """Run comprehensive data accumulation check"""
        
        # Main report
        summary = self.generate_accumulation_report()
        
        # Automation status
        self.check_automation_status()
        
        # Log activity
        self.check_log_activity()
        
        return summary

def main():
    """Main execution"""
    
    checker = DataAccumulationChecker()
    summary = checker.run_full_check()
    
    print("\n" + "="*50)
    print("FINAL ASSESSMENT")
    print("="*50)
    
    if summary['status'] == 'ACTIVE':
        print("✅ Data accumulation is PROGRESSING")
        print(f"   {summary['recent_activity']} new records in last 24 hours")
    else:
        print("❌ Data accumulation is NOT progressing")
        print("   Manual intervention required")

if __name__ == "__main__":
    main()