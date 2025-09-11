#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
View Real Ferry Data
Display actual collected ferry status data
"""

import sqlite3
from datetime import datetime

def view_real_ferry_data():
    """Display real ferry data collected from website"""
    
    print("=" * 60)
    print("REAL HEARTLAND FERRY DATA")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect('heartland_ferry_real_data.db')
        cursor = conn.cursor()
        
        # Get all ferry status records
        cursor.execute('''
            SELECT scrape_date, scrape_time, route, departure_time, 
                   operational_status, is_cancelled, is_delayed, status_update_time
            FROM ferry_status 
            ORDER BY collection_timestamp DESC
        ''')
        
        records = cursor.fetchall()
        
        print(f"Total real ferry records: {len(records)}")
        print()
        
        for i, record in enumerate(records, 1):
            scrape_date, scrape_time, route, departure, status, cancelled, delayed, update_time = record
            
            print(f"{i}. {scrape_date} {scrape_time}")
            print(f"   Route: {route}")
            print(f"   Departure: {departure}")
            print(f"   Status: {status}")
            print(f"   Cancelled: {'Yes' if cancelled else 'No'}")
            print(f"   Delayed: {'Yes' if delayed else 'No'}")
            print(f"   Updated: {update_time}")
            print()
        
        # Show daily summary
        cursor.execute('''
            SELECT date, total_sailings, cancelled_sailings, 
                   delayed_sailings, cancellation_rate
            FROM daily_summary 
            ORDER BY date DESC
        ''')
        
        daily_data = cursor.fetchall()
        
        if daily_data:
            print("=" * 40)
            print("DAILY SUMMARIES")
            print("=" * 40)
            
            for date, total, cancelled, delayed, rate in daily_data:
                print(f"{date}:")
                print(f"  Total sailings: {total}")
                print(f"  Cancelled: {cancelled}")
                print(f"  Delayed: {delayed}")
                print(f"  Cancellation rate: {rate:.1f}%")
                print()
        
        conn.close()
        
    except Exception as e:
        print(f"Error reading data: {e}")

if __name__ == "__main__":
    view_real_ferry_data()