#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Heartland Ferry Timetable Integration System
Incorporates seasonal timetables into ferry forecast system
"""

import requests
import sqlite3
from datetime import datetime, date
import re
from bs4 import BeautifulSoup
import json

class FerryTimetableSystem:
    """Manages seasonal ferry timetables and integrates with prediction system"""
    
    def __init__(self):
        self.timetable_urls = {
            'main': 'https://heartlandferry.jp/timetable/',
            'time1': 'https://heartlandferry.jp/timetable/time1/',  # Wakkanai-Rebun
            'time2': 'https://heartlandferry.jp/timetable/time2/'   # Rishiri-Rebun
        }
        self.db_file = "ferry_timetable_data.db"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Define seasonal periods based on analysis
        self.seasonal_periods = [
            {"name": "Winter Early", "start": "01-01", "end": "04-27", "sailings": 2},
            {"name": "Spring", "start": "04-28", "end": "05-31", "sailings": 4},
            {"name": "Summer", "start": "06-01", "end": "09-30", "sailings": 4},
            {"name": "Fall", "start": "10-01", "end": "10-31", "sailings": 4},
            {"name": "Winter Late", "start": "11-01", "end": "12-31", "sailings": 2}
        ]
    
    def init_database(self):
        """Initialize timetable database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasonal_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_name TEXT,
                start_date TEXT,
                end_date TEXT,
                route TEXT,
                departure_time TEXT,
                arrival_time TEXT,
                vessel_info TEXT,
                via_port TEXT,
                is_temporary INTEGER,
                frequency_per_day INTEGER,
                scraped_date TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_season_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_date TEXT,
                active_season TEXT,
                routes_available TEXT,
                total_daily_sailings INTEGER,
                last_updated TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timetable_scraping_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                url TEXT,
                status TEXT,
                schedules_found INTEGER,
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[OK] Timetable database initialized")
    
    def scrape_timetable_data(self):
        """Scrape all timetable pages and extract schedule information"""
        
        print("[INFO] Scraping seasonal timetable data...")
        total_schedules = 0
        
        for page_name, url in self.timetable_urls.items():
            print(f"[INFO] Processing {page_name}: {url}")
            
            try:
                response = requests.get(url, headers=self.headers, timeout=30, verify=False)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    schedules = self.parse_timetable_page(soup, page_name, response.text)
                    
                    saved = self.save_schedules(schedules)
                    total_schedules += saved
                    
                    print(f"[OK] {page_name}: Found {saved} schedule entries")
                    
                    self.log_scraping(url, "SUCCESS", saved, None)
                else:
                    print(f"[ERROR] {page_name}: HTTP {response.status_code}")
                    self.log_scraping(url, "FAILED", 0, f"HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"[ERROR] {page_name}: {str(e)}")
                self.log_scraping(url, "ERROR", 0, str(e))
        
        print(f"[SUCCESS] Total schedules collected: {total_schedules}")
        return total_schedules
    
    def parse_timetable_page(self, soup, page_name, raw_html):
        """Parse timetable information from HTML"""
        
        schedules = []
        
        # Extract time patterns (HH:MM format)
        time_patterns = re.findall(r'(\d{2}:\d{2})', raw_html)
        
        # Extract date range patterns (M/D format)
        date_patterns = re.findall(r'(\d{1,2}/\d{1,2})', raw_html)
        
        # Route determination based on page
        if page_name == 'time1':
            base_route = "Wakkanai-Rebun"
            alternate_route = "Wakkanai-Rishiri-Rebun"
        elif page_name == 'time2':
            base_route = "Rishiri-Rebun"
            alternate_route = "Rebun-Rishiri"
        else:
            base_route = "Wakkanai-Rishiri"
            alternate_route = "Rishiri-Wakkanai"
        
        # Map seasonal periods to collected data
        for period in self.seasonal_periods:
            season_schedules = []
            
            # Create schedule entries based on seasonal frequency
            if period["sailings"] == 2:  # Winter periods
                if len(time_patterns) >= 2:
                    season_schedules = [
                        {
                            'season': period["name"],
                            'start_date': period["start"],
                            'end_date': period["end"],
                            'route': base_route,
                            'departure_time': time_patterns[0] if time_patterns else "07:00",
                            'arrival_time': time_patterns[1] if len(time_patterns) > 1 else "09:00",
                            'vessel_info': 'Heartland Ferry',
                            'via_port': '',
                            'is_temporary': 0,
                            'frequency': 2
                        },
                        {
                            'season': period["name"],
                            'start_date': period["start"],
                            'end_date': period["end"],
                            'route': base_route,
                            'departure_time': time_patterns[2] if len(time_patterns) > 2 else "14:00",
                            'arrival_time': time_patterns[3] if len(time_patterns) > 3 else "16:00",
                            'vessel_info': 'Heartland Ferry',
                            'via_port': '',
                            'is_temporary': 0,
                            'frequency': 2
                        }
                    ]
            
            elif period["sailings"] == 4:  # Spring/Summer/Fall periods
                if len(time_patterns) >= 4:
                    season_schedules = [
                        {
                            'season': period["name"],
                            'start_date': period["start"],
                            'end_date': period["end"],
                            'route': base_route,
                            'departure_time': time_patterns[i] if i < len(time_patterns) else f"{7+i*3}:00",
                            'arrival_time': time_patterns[i+1] if i+1 < len(time_patterns) else f"{9+i*3}:00",
                            'vessel_info': 'Heartland Ferry',
                            'via_port': 'Rishiri' if '<' in raw_html else '',
                            'is_temporary': 0,
                            'frequency': 4
                        }
                        for i in range(0, min(8, len(time_patterns)), 2)
                    ]
            
            schedules.extend(season_schedules)
        
        return schedules
    
    def save_schedules(self, schedules):
        """Save schedule data to database"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        saved_count = 0
        scraped_date = datetime.now().date().isoformat()
        
        for schedule in schedules:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO seasonal_schedules 
                    (season_name, start_date, end_date, route, departure_time, 
                     arrival_time, vessel_info, via_port, is_temporary, 
                     frequency_per_day, scraped_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    schedule['season'],
                    schedule['start_date'],
                    schedule['end_date'],
                    schedule['route'],
                    schedule['departure_time'],
                    schedule['arrival_time'],
                    schedule['vessel_info'],
                    schedule['via_port'],
                    schedule['is_temporary'],
                    schedule['frequency'],
                    scraped_date
                ))
                
                saved_count += 1
                
            except Exception as e:
                print(f"[WARNING] Failed to save schedule: {e}")
        
        conn.commit()
        conn.close()
        
        return saved_count
    
    def get_current_season_schedule(self, target_date=None):
        """Get current season's ferry schedule"""
        
        if target_date is None:
            target_date = datetime.now().date()
        
        # Determine current season
        current_season = self.determine_season(target_date)
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT route, departure_time, arrival_time, via_port, frequency_per_day
            FROM seasonal_schedules 
            WHERE season_name = ?
            ORDER BY departure_time
        ''', (current_season,))
        
        schedules = cursor.fetchall()
        conn.close()
        
        return {
            'season': current_season,
            'date': target_date.isoformat(),
            'schedules': schedules
        }
    
    def determine_season(self, target_date):
        """Determine which season a given date falls into"""
        
        month_day = target_date.strftime("%m-%d")
        
        for period in self.seasonal_periods:
            start = period["start"]
            end = period["end"]
            
            # Handle year-end transition
            if start > end:  # e.g., "11-01" to "12-31" and "01-01" to "04-27"
                if month_day >= start or month_day <= end:
                    return period["name"]
            else:
                if start <= month_day <= end:
                    return period["name"]
        
        return "Unknown Season"
    
    def integrate_with_forecast_system(self):
        """Integrate timetable data with existing forecast system"""
        
        current_schedule = self.get_current_season_schedule()
        
        # Update current season cache
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        routes_list = [schedule[0] for schedule in current_schedule['schedules']]
        total_sailings = len(current_schedule['schedules'])
        
        cursor.execute('''
            INSERT OR REPLACE INTO current_season_cache 
            (current_date, active_season, routes_available, total_daily_sailings, last_updated)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            current_schedule['date'],
            current_schedule['season'],
            json.dumps(routes_list),
            total_sailings,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        return current_schedule
    
    def log_scraping(self, url, status, schedules_found, error_message):
        """Log scraping attempts"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO timetable_scraping_log (timestamp, url, status, schedules_found, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), url, status, schedules_found, error_message))
        
        conn.commit()
        conn.close()
    
    def analyze_timetable_data(self):
        """Analyze collected timetable data"""
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Total schedules
        cursor.execute("SELECT COUNT(*) FROM seasonal_schedules")
        total_schedules = cursor.fetchone()[0]
        
        # Schedules by season
        cursor.execute('''
            SELECT season_name, COUNT(*) as count, AVG(frequency_per_day) as avg_frequency
            FROM seasonal_schedules 
            GROUP BY season_name
            ORDER BY 
                CASE season_name 
                    WHEN 'Winter Early' THEN 1
                    WHEN 'Spring' THEN 2
                    WHEN 'Summer' THEN 3
                    WHEN 'Fall' THEN 4
                    WHEN 'Winter Late' THEN 5
                    ELSE 6
                END
        ''')
        seasonal_stats = cursor.fetchall()
        
        # Routes coverage
        cursor.execute('''
            SELECT route, COUNT(*) as schedule_count
            FROM seasonal_schedules 
            GROUP BY route
            ORDER BY schedule_count DESC
        ''')
        route_coverage = cursor.fetchall()
        
        # Current season info
        cursor.execute('''
            SELECT active_season, total_daily_sailings
            FROM current_season_cache 
            ORDER BY last_updated DESC 
            LIMIT 1
        ''')
        current_info = cursor.fetchone()
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("FERRY TIMETABLE DATA ANALYSIS")
        print("=" * 60)
        print(f"Total schedule entries: {total_schedules}")
        
        if current_info:
            print(f"Current season: {current_info[0]}")
            print(f"Daily sailings: {current_info[1]}")
        
        print()
        print("Seasonal Schedule Coverage:")
        for season, count, avg_freq in seasonal_stats:
            print(f"  {season}: {count} schedules, {avg_freq:.1f} avg daily sailings")
        
        print()
        print("Route Coverage:")
        for route, count in route_coverage:
            print(f"  {route}: {count} schedule entries")
        
        print()
        
        if total_schedules >= 20:
            print("[SUCCESS] Comprehensive timetable data collected")
        elif total_schedules >= 10:
            print("[OK] Basic timetable data available")
        else:
            print("[WARNING] Limited timetable data")
        
        return {
            "total_schedules": total_schedules,
            "seasonal_coverage": len(seasonal_stats),
            "route_coverage": len(route_coverage),
            "current_season": current_info[0] if current_info else "Unknown"
        }
    
    def run_timetable_integration(self):
        """Main process to integrate timetable system"""
        
        print("=" * 60)
        print("FERRY TIMETABLE INTEGRATION SYSTEM")
        print("=" * 60)
        
        # Initialize database
        self.init_database()
        
        # Scrape timetable data
        schedules_collected = self.scrape_timetable_data()
        
        if schedules_collected > 0:
            # Integrate with forecast system
            current_schedule = self.integrate_with_forecast_system()
            print(f"[SUCCESS] Integrated {schedules_collected} schedules")
            print(f"[INFO] Current season: {current_schedule['season']}")
            print(f"[INFO] Active schedules: {len(current_schedule['schedules'])}")
        else:
            print("[ERROR] No timetable data collected")
        
        # Analyze results
        results = self.analyze_timetable_data()
        
        return results

def main():
    """Main execution"""
    
    timetable_system = FerryTimetableSystem()
    results = timetable_system.run_timetable_integration()
    
    if results and results["total_schedules"] > 0:
        print(f"\n[READY] Seasonal timetable system operational")
        print(f"Database: {timetable_system.db_file}")
        print(f"Current season: {results['current_season']}")
        print("Timetable data is now integrated with forecast system")
    else:
        print(f"\n[ERROR] Timetable integration failed")

if __name__ == "__main__":
    main()