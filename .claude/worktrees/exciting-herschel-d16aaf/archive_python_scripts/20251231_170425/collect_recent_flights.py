#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware Recent Flight Data Collection
Focus on recent data collection without date range filters
"""

import requests
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import time

class RecentFlightCollector:
    """Recent flight data collector"""
    
    def __init__(self):
        self.config_file = Path("flightaware_config.json")
        self.db_file = Path("rishiri_flight_data.db")
        self.api_base = "https://aeroapi.flightaware.com/aeroapi"
        self.api_key = None
        self.total_cost = 0.0
        
    def load_config(self):
        """Load API configuration"""
        try:
            with open(self.config_file) as f:
                config = json.load(f)
            self.api_key = config["api_key"]
            print(f"[OK] API key loaded: {self.api_key[:10]}...")
            return True
        except Exception as e:
            print(f"[ERROR] Config load failed: {e}")
            return False
    
    def init_database(self):
        """Initialize flight data database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_id TEXT UNIQUE,
                ident TEXT,
                aircraft_type TEXT,
                origin TEXT,
                destination TEXT,
                scheduled_departure TEXT,
                actual_departure TEXT,
                scheduled_arrival TEXT,
                actual_arrival TEXT,
                status TEXT,
                cancelled INTEGER,
                delayed INTEGER,
                collection_date TEXT,
                api_cost REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                endpoint TEXT,
                records_collected INTEGER,
                cost REAL,
                success INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[OK] Database initialized")
    
    def collect_recent_flights(self):
        """Collect recent flight data without date filters"""
        
        headers = {"x-apikey": self.api_key}
        
        print("[INFO] Collecting recent flight data...")
        
        # Collect recent departures (multiple pages for more data)
        departures_collected = 0
        arrivals_collected = 0
        
        for page in range(1, 6):  # Collect up to 5 pages
            print(f"[INFO] Collecting departures page {page}...")
            
            try:
                response = requests.get(
                    f"{self.api_base}/airports/RIS/flights/departures",
                    headers=headers,
                    params={"max_pages": 1},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    departures = data.get('departures', [])
                    
                    if not departures:
                        print(f"[INFO] No more departures on page {page}")
                        break
                    
                    saved = self.save_flights(departures, "departure")
                    departures_collected += saved
                    self.total_cost += 0.01
                    
                    print(f"[OK] Page {page}: {saved} departures saved")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                    # Check if we have next page
                    if not data.get('links', {}).get('next'):
                        break
                        
                else:
                    print(f"[WARNING] Departures page {page} failed: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"[ERROR] Departures page {page} exception: {e}")
                break
        
        # Collect recent arrivals
        for page in range(1, 6):  # Collect up to 5 pages
            print(f"[INFO] Collecting arrivals page {page}...")
            
            try:
                response = requests.get(
                    f"{self.api_base}/airports/RIS/flights/arrivals",
                    headers=headers,
                    params={"max_pages": 1},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    arrivals = data.get('arrivals', [])
                    
                    if not arrivals:
                        print(f"[INFO] No more arrivals on page {page}")
                        break
                    
                    saved = self.save_flights(arrivals, "arrival")
                    arrivals_collected += saved
                    self.total_cost += 0.01
                    
                    print(f"[OK] Page {page}: {saved} arrivals saved")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                    # Check if we have next page
                    if not data.get('links', {}).get('next'):
                        break
                        
                else:
                    print(f"[WARNING] Arrivals page {page} failed: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"[ERROR] Arrivals page {page} exception: {e}")
                break
        
        # Log collection
        self.log_collection("departures", departures_collected)
        self.log_collection("arrivals", arrivals_collected)
        
        print(f"[SUMMARY] Collected {departures_collected} departures, {arrivals_collected} arrivals")
        print(f"[COST] Total API cost: ${self.total_cost:.2f}")
        
        return departures_collected + arrivals_collected > 0
    
    def save_flights(self, flights, flight_type):
        """Save flight records to database"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        saved_count = 0
        
        for flight in flights:
            try:
                # Extract flight data
                flight_id = flight.get('fa_flight_id', '')
                ident = flight.get('ident', '')
                aircraft_type = flight.get('aircraft_type', '')
                
                # Handle origin/destination based on flight type
                if flight_type == "departure":
                    origin = "RIS"
                    destination = flight.get('destination', {}).get('code', '')
                else:
                    origin = flight.get('origin', {}).get('code', '')
                    destination = "RIS"
                
                scheduled_departure = flight.get('scheduled_out', '')
                actual_departure = flight.get('actual_out', '')
                scheduled_arrival = flight.get('scheduled_in', '')
                actual_arrival = flight.get('actual_in', '')
                
                status = flight.get('status', '')
                cancelled = 1 if status == 'Cancelled' else 0
                
                # More sophisticated delay detection
                delay_minutes = 0
                if actual_departure and scheduled_departure:
                    try:
                        actual_dt = datetime.fromisoformat(actual_departure.replace('Z', '+00:00'))
                        scheduled_dt = datetime.fromisoformat(scheduled_departure.replace('Z', '+00:00'))
                        delay_minutes = (actual_dt - scheduled_dt).total_seconds() / 60
                    except:
                        pass
                
                delayed = 1 if delay_minutes > 30 else 0
                
                cursor.execute('''
                    INSERT OR IGNORE INTO flights 
                    (flight_id, ident, aircraft_type, origin, destination,
                     scheduled_departure, actual_departure, scheduled_arrival, actual_arrival,
                     status, cancelled, delayed, collection_date, api_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    flight_id, ident, aircraft_type, origin, destination,
                    scheduled_departure, actual_departure, scheduled_arrival, actual_arrival,
                    status, cancelled, delayed, datetime.now().isoformat(), 0.01
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                
            except Exception as e:
                print(f"[WARNING] Failed to save flight {flight.get('ident', 'Unknown')}: {e}")
        
        conn.commit()
        conn.close()
        
        return saved_count
    
    def log_collection(self, endpoint, records_collected):
        """Log collection results"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO collection_log (timestamp, endpoint, records_collected, cost, success)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), endpoint, records_collected, 0.01, 1))
        
        conn.commit()
        conn.close()
    
    def analyze_data(self):
        """Analyze collected flight data"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Total flights
        cursor.execute("SELECT COUNT(*) FROM flights")
        total_flights = cursor.fetchone()[0]
        
        # Cancelled flights
        cursor.execute("SELECT COUNT(*) FROM flights WHERE cancelled = 1")
        cancelled_flights = cursor.fetchone()[0]
        
        # Delayed flights
        cursor.execute("SELECT COUNT(*) FROM flights WHERE delayed = 1")
        delayed_flights = cursor.fetchone()[0]
        
        # Recent trends (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) FROM flights 
            WHERE datetime(scheduled_departure) >= datetime('now', '-7 days')
        """)
        recent_flights = cursor.fetchone()[0]
        
        # Flight routes analysis
        cursor.execute("""
            SELECT destination, COUNT(*) as count 
            FROM flights WHERE origin = 'RIS' 
            GROUP BY destination ORDER BY count DESC LIMIT 5
        """)
        top_destinations = cursor.fetchall()
        
        conn.close()
        
        cancellation_rate = (cancelled_flights / total_flights * 100) if total_flights > 0 else 0
        delay_rate = (delayed_flights / total_flights * 100) if total_flights > 0 else 0
        
        print("\n" + "=" * 50)
        print("RISHIRI AIRPORT DATA ANALYSIS")
        print("=" * 50)
        print(f"Total flights collected: {total_flights}")
        print(f"Recent flights (7 days): {recent_flights}")
        print(f"Cancelled flights: {cancelled_flights} ({cancellation_rate:.1f}%)")
        print(f"Delayed flights (>30min): {delayed_flights} ({delay_rate:.1f}%)")
        print(f"Total API cost: ${self.total_cost:.2f}")
        print()
        
        print("Top Destinations from Rishiri:")
        for dest, count in top_destinations:
            print(f"  {dest}: {count} flights")
        print()
        
        if total_flights >= 50:
            print("[SUCCESS] Good data collection for initial predictions")
        elif total_flights >= 20:
            print("[OK] Basic data available for system development")
        else:
            print("[WARNING] Limited data - recommend daily collection")
        
        return {
            "total_flights": total_flights,
            "cancelled_flights": cancelled_flights,
            "delayed_flights": delayed_flights,
            "cancellation_rate": cancellation_rate,
            "delay_rate": delay_rate,
            "cost": self.total_cost
        }
    
    def run_collection(self):
        """Main collection process"""
        
        print("=" * 50)
        print("RISHIRI AIRPORT RECENT DATA COLLECTION")
        print("=" * 50)
        print()
        
        # Step 1: Load configuration
        if not self.load_config():
            return False
        
        # Step 2: Initialize database
        self.init_database()
        
        # Step 3: Collect recent flight data
        print("[START] Recent flight data collection...")
        success = self.collect_recent_flights()
        
        if success:
            print("[SUCCESS] Data collection completed")
        else:
            print("[ERROR] Data collection failed")
            return False
        
        # Step 4: Analyze results
        results = self.analyze_data()
        
        return results

def main():
    """Main execution"""
    collector = RecentFlightCollector()
    
    results = collector.run_collection()
    
    if results and results["total_flights"] > 0:
        print("\n[READY] Flight data available for prediction system")
        print("Next step: Integrate with ferry prediction system")
        print("  python final_integrated_prediction_en.py")
    else:
        print("\n[ERROR] Collection failed or no data available")

if __name__ == "__main__":
    main()