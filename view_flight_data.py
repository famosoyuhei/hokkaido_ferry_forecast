#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
View collected flight data
"""

import sqlite3

def view_flight_data():
    """Display collected flight data"""
    
    conn = sqlite3.connect('rishiri_flight_data.db')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("COLLECTED FLIGHT DATA")
    print("=" * 60)
    
    cursor.execute('''
        SELECT ident, origin, destination, status, 
               scheduled_departure, actual_departure, cancelled, delayed
        FROM flights ORDER BY scheduled_departure DESC
    ''')
    
    flights = cursor.fetchall()
    
    for i, flight in enumerate(flights, 1):
        ident, origin, dest, status, sched, actual, cancelled, delayed = flight
        
        print(f"{i}. Flight {ident}")
        print(f"   Route: {origin} -> {dest}")
        print(f"   Status: {status}")
        print(f"   Scheduled: {sched[:19] if sched else 'N/A'}")
        print(f"   Actual: {actual[:19] if actual else 'N/A'}")
        print(f"   Cancelled: {'Yes' if cancelled else 'No'}")
        print(f"   Delayed: {'Yes' if delayed else 'No'}")
        print()
    
    # Summary
    cursor.execute("SELECT COUNT(*) FROM flights")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM flights WHERE cancelled = 1")
    cancelled = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM flights WHERE delayed = 1")
    delayed = cursor.fetchone()[0]
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total flights: {total}")
    print(f"Cancelled: {cancelled}")
    print(f"Delayed: {delayed}")
    print(f"On-time: {total - cancelled - delayed}")
    
    conn.close()

if __name__ == "__main__":
    view_flight_data()