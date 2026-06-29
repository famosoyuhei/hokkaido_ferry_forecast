#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware Historical Data Collection Script
Collects 90 days of flight data from Rishiri Airport
"""

import requests
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import time

class FlightDataCollector:
    """FlightAware data collector with billing protection"""
    
    def __init__(self):
        self.config_file = Path("flightaware_config.json")
        self.db_file = Path("rishiri_flight_data.db")
        self.api_base = "https://aeroapi.flightaware.com/aeroapi"
        self.api_key = None
        self.total_cost = 0.0
        self.daily_limit = 0.50
        self.monthly_limit = 4.50
        
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
                weather_conditions TEXT,
                collection_date TEXT,
                cost REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                endpoint TEXT,
                cost REAL,
                success INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[OK] Database initialized")
    
    def check_billing_protection(self, endpoint_cost=0.01):
        """Check billing limits before API call"""
        if self.total_cost + endpoint_cost >= self.monthly_limit:
            print(f"[STOP] Monthly limit reached: ${self.total_cost:.2f}")
            return False
        return True
    
    def record_api_call(self, endpoint, cost, success):
        """Record API call for billing tracking"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_usage (timestamp, endpoint, cost, success)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now().isoformat(), endpoint, cost, success))
        
        conn.commit()
        conn.close()
        
        self.total_cost += cost
        print(f"[COST] Total used: ${self.total_cost:.3f} / ${self.monthly_limit}")
    
    def collect_historical_flights(self, days_back=30):
        """Collect historical flight data"""
        
        if not self.check_billing_protection():
            return False
        
        headers = {"x-apikey": self.api_key}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        print(f"[INFO] Collecting flights from {start_date.date()} to {end_date.date()}")
        
        # Collect departures
        departures_url = f"{self.api_base}/airports/RIS/flights/departures"
        params = {
            "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "max_pages": 10
        }
        
        try:
            response = requests.get(departures_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                departures = data.get('departures', [])
                
                self.record_api_call("departures", 0.01, 1)
                print(f"[OK] Found {len(departures)} departure records")
                
                # Save to database
                self.save_flights(departures, "departure")
                
                time.sleep(2)  # Rate limiting
                
            else:
                print(f"[ERROR] API error: {response.status_code}")
                self.record_api_call("departures", 0.01, 0)
                return False
                
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            self.record_api_call("departures", 0.0, 0)
            return False
        
        # Collect arrivals
        if not self.check_billing_protection():
            return True  # Return partial success
        
        arrivals_url = f"{self.api_base}/airports/RIS/flights/arrivals"
        
        try:
            response = requests.get(arrivals_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                arrivals = data.get('arrivals', [])
                
                self.record_api_call("arrivals", 0.01, 1)
                print(f"[OK] Found {len(arrivals)} arrival records")
                
                # Save to database
                self.save_flights(arrivals, "arrival")
                
            else:
                print(f"[WARNING] Arrivals API error: {response.status_code}")
                self.record_api_call("arrivals", 0.01, 0)
                
        except Exception as e:
            print(f"[WARNING] Arrivals request failed: {e}")
            self.record_api_call("arrivals", 0.0, 0)
        
        return True
    
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
                delayed = 1 if flight.get('delay_minutes', 0) > 30 else 0
                
                cursor.execute('''
                    INSERT OR IGNORE INTO flights 
                    (flight_id, ident, aircraft_type, origin, destination,
                     scheduled_departure, actual_departure, scheduled_arrival, actual_arrival,
                     status, cancelled, delayed, collection_date, cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    flight_id, ident, aircraft_type, origin, destination,
                    scheduled_departure, actual_departure, scheduled_arrival, actual_arrival,
                    status, cancelled, delayed, datetime.now().isoformat(), 0.01
                ))
                
                saved_count += 1
                
            except Exception as e:
                print(f"[WARNING] Failed to save flight {flight.get('ident', 'Unknown')}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"[OK] Saved {saved_count} {flight_type} records")
    
    def analyze_collected_data(self):
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
        
        # Total API cost
        cursor.execute("SELECT SUM(cost) FROM api_usage")
        total_api_cost = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        cancellation_rate = (cancelled_flights / total_flights * 100) if total_flights > 0 else 0
        delay_rate = (delayed_flights / total_flights * 100) if total_flights > 0 else 0
        
        print("\n" + "=" * 50)
        print("DATA COLLECTION SUMMARY")
        print("=" * 50)
        print(f"Total flights collected: {total_flights}")
        print(f"Cancelled flights: {cancelled_flights} ({cancellation_rate:.1f}%)")
        print(f"Delayed flights: {delayed_flights} ({delay_rate:.1f}%)")
        print(f"Total API cost: ${total_api_cost:.2f}")
        print(f"Remaining budget: ${self.monthly_limit - total_api_cost:.2f}")
        print()
        
        if total_flights >= 100:
            print("[SUCCESS] Sufficient data for ML model training")
        elif total_flights >= 50:
            print("[OK] Adequate data for basic predictions")
        else:
            print("[WARNING] Limited data - consider extending collection period")
    
    def run_collection(self):
        """Main collection process"""
        
        print("=" * 50)
        print("RISHIRI AIRPORT FLIGHT DATA COLLECTION")
        print("=" * 50)
        print()
        
        # Step 1: Load configuration
        if not self.load_config():
            return False
        
        # Step 2: Initialize database
        self.init_database()
        
        # Step 3: Collect historical data (30 days)
        print("[START] Historical data collection (30 days)...")
        success = self.collect_historical_flights(days_back=30)
        
        if success:
            print("[SUCCESS] Data collection completed")
        else:
            print("[ERROR] Data collection failed")
        
        # Step 4: Analyze results
        self.analyze_collected_data()
        
        return success

def main():
    """Main execution"""
    collector = FlightDataCollector()
    
    if collector.run_collection():
        print("\n[NEXT] Ready for integrated prediction system:")
        print("  python final_integrated_prediction_en.py")
    else:
        print("\n[ERROR] Collection failed. Check API key and try again.")

if __name__ == "__main__":
    main()