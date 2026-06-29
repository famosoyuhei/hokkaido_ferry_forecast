#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Initialize Ferry Database with Sample Data
Create initial ferry data for system testing
"""

import sqlite3
from datetime import datetime, timedelta
import random

class FerryDataInitializer:
    """Initialize ferry data with realistic sample data"""
    
    def __init__(self):
        self.db_file = "ferry_forecast_data.db"
        
    def init_database(self):
        """Initialize ferry database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Drop existing table to recreate with correct schema
        cursor.execute('DROP TABLE IF EXISTS ferry_data')
        
        cursor.execute('''
            CREATE TABLE ferry_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                route TEXT,
                departure_time TEXT,
                status TEXT,
                weather_condition TEXT,
                wind_speed REAL,
                wave_height REAL,
                temperature REAL,
                humidity REAL,
                cancelled INTEGER,
                delayed INTEGER,
                collection_date TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                total_records INTEGER,
                success INTEGER,
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[OK] Ferry database initialized")
    
    def generate_sample_data(self, days_back=30):
        """Generate realistic ferry data for past days"""
        
        print(f"[INFO] Generating {days_back} days of sample ferry data...")
        
        ferry_routes = [
            {"route": "Wakkanai-Rishiri", "times": ["08:00", "13:30", "17:15"]},
            {"route": "Rishiri-Wakkanai", "times": ["09:45", "15:15", "19:00"]},
            {"route": "Wakkanai-Rebun", "times": ["08:30", "14:00", "16:45"]},
            {"route": "Rebun-Wakkanai", "times": ["10:15", "15:45", "18:30"]},
            {"route": "Rishiri-Rebun", "times": ["10:00", "15:30"]},
            {"route": "Rebun-Rishiri", "times": ["11:30", "16:15"]},
        ]
        
        weather_conditions = [
            "Clear", "Partly Cloudy", "Cloudy", "Light Rain", 
            "Rain", "Strong Wind", "Fog", "Snow"
        ]
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        records_created = 0
        base_date = datetime.now() - timedelta(days=days_back)
        
        for day in range(days_back):
            current_date = base_date + timedelta(days=day)
            
            # Generate weather conditions for the day
            weather_condition = random.choice(weather_conditions)
            
            # Weather parameters based on condition
            if weather_condition == "Strong Wind":
                wind_speed = random.uniform(20, 35)
                wave_height = random.uniform(2.5, 4.0)
            elif weather_condition in ["Rain", "Snow"]:
                wind_speed = random.uniform(10, 20)
                wave_height = random.uniform(1.5, 2.5)
            elif weather_condition == "Fog":
                wind_speed = random.uniform(5, 15)
                wave_height = random.uniform(0.5, 1.5)
            else:
                wind_speed = random.uniform(3, 12)
                wave_height = random.uniform(0.3, 1.8)
            
            temperature = random.uniform(5, 25)
            humidity = random.uniform(60, 90)
            
            # Process each route
            for route_info in ferry_routes:
                route = route_info["route"]
                
                for departure_time in route_info["times"]:
                    # Determine status based on weather
                    status, cancelled, delayed = self.determine_status(
                        weather_condition, wind_speed, wave_height
                    )
                    
                    # Create timestamp for this departure
                    hour, minute = map(int, departure_time.split(':'))
                    departure_datetime = current_date.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    
                    cursor.execute('''
                        INSERT INTO ferry_data 
                        (timestamp, route, departure_time, status, weather_condition,
                         wind_speed, wave_height, temperature, humidity, cancelled, delayed, collection_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        departure_datetime.isoformat(),
                        route,
                        departure_time,
                        status,
                        weather_condition,
                        round(wind_speed, 1),
                        round(wave_height, 1),
                        round(temperature, 1),
                        round(humidity, 1),
                        cancelled,
                        delayed,
                        current_date.date().isoformat()
                    ))
                    
                    records_created += 1
        
        conn.commit()
        conn.close()
        
        print(f"[OK] Created {records_created} ferry records")
        
        # Log the initialization
        self.log_initialization(records_created)
        
        return records_created
    
    def determine_status(self, weather_condition, wind_speed, wave_height):
        """Determine ferry status based on conditions"""
        
        # High probability cancellation conditions
        if weather_condition == "Strong Wind" or wind_speed > 25 or wave_height > 3.0:
            if random.random() < 0.8:  # 80% cancellation rate
                return "Cancelled", 1, 0
            else:
                return "Delayed", 0, 1
        
        # Medium risk conditions
        elif weather_condition in ["Rain", "Snow"] or wind_speed > 15 or wave_height > 2.0:
            rand = random.random()
            if rand < 0.2:  # 20% cancellation
                return "Cancelled", 1, 0
            elif rand < 0.5:  # 30% delay
                return "Delayed", 0, 1
            else:
                return "On Schedule", 0, 0
        
        # Fog conditions (visibility issues)
        elif weather_condition == "Fog":
            rand = random.random()
            if rand < 0.1:  # 10% cancellation
                return "Cancelled", 1, 0
            elif rand < 0.3:  # 20% delay
                return "Delayed", 0, 1
            else:
                return "On Schedule", 0, 0
        
        # Good conditions
        else:
            rand = random.random()
            if rand < 0.02:  # 2% random cancellation
                return "Cancelled", 1, 0
            elif rand < 0.08:  # 6% random delay
                return "Delayed", 0, 1
            else:
                return "On Schedule", 0, 0
    
    def log_initialization(self, records):
        """Log initialization status"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO collection_status (timestamp, total_records, success, error_message)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now().isoformat(), records, 1, "Initial data generation"))
        
        conn.commit()
        conn.close()
    
    def analyze_generated_data(self):
        """Analyze the generated ferry data"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Total records
        cursor.execute("SELECT COUNT(*) FROM ferry_data")
        total_records = cursor.fetchone()[0]
        
        # Cancelled ferries
        cursor.execute("SELECT COUNT(*) FROM ferry_data WHERE cancelled = 1")
        cancelled_count = cursor.fetchone()[0]
        
        # Delayed ferries
        cursor.execute("SELECT COUNT(*) FROM ferry_data WHERE delayed = 1")
        delayed_count = cursor.fetchone()[0]
        
        # Collection days
        cursor.execute("SELECT COUNT(DISTINCT DATE(timestamp)) FROM ferry_data")
        collection_days = cursor.fetchone()[0]
        
        # Route analysis
        cursor.execute("""
            SELECT route, COUNT(*) as total, 
                   SUM(cancelled) as cancelled,
                   SUM(delayed) as delayed
            FROM ferry_data 
            GROUP BY route 
            ORDER BY total DESC
        """)
        route_stats = cursor.fetchall()
        
        # Weather condition analysis
        cursor.execute("""
            SELECT weather_condition, COUNT(*) as total,
                   SUM(cancelled) as cancelled
            FROM ferry_data 
            GROUP BY weather_condition 
            ORDER BY cancelled DESC
        """)
        weather_stats = cursor.fetchall()
        
        conn.close()
        
        cancellation_rate = (cancelled_count / total_records * 100) if total_records > 0 else 0
        delay_rate = (delayed_count / total_records * 100) if total_records > 0 else 0
        
        print("\n" + "=" * 60)
        print("FERRY DATA ANALYSIS")
        print("=" * 60)
        print(f"Total ferry records: {total_records}")
        print(f"Collection days: {collection_days}")
        print(f"Cancelled services: {cancelled_count} ({cancellation_rate:.1f}%)")
        print(f"Delayed services: {delayed_count} ({delay_rate:.1f}%)")
        print(f"On-time services: {total_records - cancelled_count - delayed_count}")
        print()
        
        print("Route Statistics:")
        for route, total, cancelled, delayed in route_stats:
            route_cancel_rate = (cancelled / total * 100) if total > 0 else 0
            route_delay_rate = (delayed / total * 100) if total > 0 else 0
            print(f"  {route}:")
            print(f"    Total: {total} services")
            print(f"    Cancelled: {cancelled} ({route_cancel_rate:.1f}%)")
            print(f"    Delayed: {delayed} ({route_delay_rate:.1f}%)")
        print()
        
        print("Weather Impact Analysis:")
        for condition, total, cancelled in weather_stats:
            impact_rate = (cancelled / total * 100) if total > 0 else 0
            print(f"  {condition}: {total} records, {cancelled} cancelled ({impact_rate:.1f}%)")
        print()
        
        if total_records >= 500:
            print("[SUCCESS] Excellent data collection - ready for ML training")
        elif total_records >= 200:
            print("[SUCCESS] Good data collection - suitable for predictions")
        else:
            print("[OK] Basic data available - continue collection")
        
        return {
            "total_records": total_records,
            "collection_days": collection_days,
            "cancellation_rate": cancellation_rate,
            "delay_rate": delay_rate
        }
    
    def run_initialization(self, days=30):
        """Main initialization process"""
        
        print("=" * 60)
        print("FERRY DATABASE INITIALIZATION")
        print("=" * 60)
        
        # Initialize database
        self.init_database()
        
        # Generate sample data
        records_created = self.generate_sample_data(days)
        
        if records_created > 0:
            print(f"[SUCCESS] Created {records_created} ferry records")
            
            # Analyze generated data
            results = self.analyze_generated_data()
            
            return results
        else:
            print("[ERROR] No ferry data created")
            return None

def main():
    """Main execution"""
    
    initializer = FerryDataInitializer()
    results = initializer.run_initialization(days=30)
    
    if results:
        print("\n[READY] Ferry database initialized with sample data")
        print("The system now has historical data for prediction training")
        print("\nNext steps:")
        print("1. Set up automated real data collection")
        print("2. Validate predictions against actual ferry status")
        print("3. Train ML models with accumulated data")
    else:
        print("\n[ERROR] Ferry database initialization failed")

if __name__ == "__main__":
    main()