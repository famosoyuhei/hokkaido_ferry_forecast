#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API Setup Guide and Data Integration System
Step-by-step setup and automated data collection
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import time

class FlightAwareSetupGuide:
    """Interactive setup guide for FlightAware API"""
    
    def __init__(self):
        self.config_file = Path("flightaware_config.json")
        self.api_base = "https://aeroapi.flightaware.com/aeroapi"
        
    def show_setup_instructions(self):
        """Display step-by-step setup instructions"""
        
        instructions = """
=== FlightAware API Setup Instructions ===

STEP 1: Create FlightAware Account
1. Visit: https://www.flightaware.com/commercial/aeroapi/
2. Click "Get Started" or "Sign Up"
3. Choose "Personal Plan" (Free up to $5/month)
4. Complete account registration

STEP 2: Get API Key
1. Log in to your FlightAware account
2. Go to "My FlightAware" > "AeroAPI"
3. Click "Create API Key"
4. Copy your API key (keep it secure!)

STEP 3: Verify API Access
1. Test your API key using our verification tool
2. Check rate limits and usage quotas
3. Confirm Rishiri Airport (RIS/RJER) access

STEP 4: Configure Local System
1. Run this setup script to save your API key
2. Start automated data collection
3. Verify data integration with existing systems

Personal Plan Benefits:
- $5 free credits per month
- 90 days historical data access
- Real-time flight tracking
- Suitable for our prediction system

Let's begin the setup process!
"""
        print(instructions)
        return True
    
    def interactive_api_key_setup(self):
        """Interactive API key configuration"""
        
        print("\n=== API Key Configuration ===")
        
        if self.config_file.exists():
            print("Existing configuration found.")
            choice = input("Do you want to update your API key? (y/n): ").lower()
            if choice != 'y':
                return self.load_config()
        
        print("\nPlease enter your FlightAware API key:")
        print("(You can find this in your FlightAware account under AeroAPI)")
        
        api_key = input("API Key: ").strip()
        
        if not api_key:
            print("❌ No API key provided.")
            return None
        
        # Validate API key format (basic check)
        if len(api_key) < 20:
            print("⚠️  Warning: API key seems too short. Please verify.")
        
        # Test API key
        print("\n🧪 Testing API key...")
        if self.test_api_key(api_key):
            # Save configuration
            config = {
                "api_key": api_key,
                "setup_date": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "endpoints": {
                    "base_url": self.api_base,
                    "airports": f"{self.api_base}/airports",
                    "flights": f"{self.api_base}/flights"
                }
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ API key saved successfully!")
            return config
        else:
            print("❌ API key test failed. Please check your key and try again.")
            return None
    
    def test_api_key(self, api_key: str) -> bool:
        """Test API key functionality"""
        
        headers = {"x-apikey": api_key}
        
        try:
            # Test with Rishiri Airport endpoint
            response = requests.get(
                f"{self.api_base}/airports/RIS",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API Key Valid - Connected to {data.get('name', 'Airport')}")
                return True
            elif response.status_code == 401:
                print("❌ Invalid API Key - Authorization failed")
                return False
            elif response.status_code == 403:
                print("❌ API Access Denied - Check your subscription")
                return False
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def load_config(self) -> Optional[Dict]:
        """Load existing configuration"""
        
        if not self.config_file.exists():
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    def check_api_usage(self, config: Dict) -> Dict:
        """Check current API usage and limits"""
        
        headers = {"x-apikey": config["api_key"]}
        
        try:
            # Make a simple request to check headers for usage info
            response = requests.get(
                f"{self.api_base}/airports/RIS",
                headers=headers,
                timeout=10
            )
            
            usage_info = {
                "status_code": response.status_code,
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                "rate_limit_reset": response.headers.get("X-RateLimit-Reset"),
                "monthly_usage": response.headers.get("X-Monthly-Usage"),
                "monthly_limit": response.headers.get("X-Monthly-Limit")
            }
            
            return usage_info
            
        except Exception as e:
            return {"error": str(e)}
    
    def setup_automated_collection(self, config: Dict):
        """Setup automated data collection system"""
        
        print("\n=== Automated Data Collection Setup ===")
        
        # Create data collection script
        collection_script = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware Automated Data Collection
Generated by setup guide on {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

import sys
import os
sys.path.append(r"{os.getcwd()}")

from flightaware_integration import FlightAwareDataCollector
from datetime import datetime, timedelta

def main():
    """Run automated data collection"""
    
    config = {{
        "api_key": "{config['api_key']}",
        "base_url": "{config['endpoints']['base_url']}"
    }}
    
    collector = FlightAwareDataCollector(config["api_key"])
    
    print(f"Starting data collection at {{datetime.now().strftime('%Y-%m-%d %H:%M')}}")
    
    try:
        # Collect last 7 days of data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        result = collector.collect_airport_data("RIS", start_date, end_date)
        print(f"Collected {{len(result.get('flights', []))}} flight records")
        
        # Save to CSV
        csv_file = f"rishiri_flights_{{datetime.now().strftime('%Y%m%d_%H%M')}}.csv"
        collector.save_to_csv(result, csv_file)
        print(f"Data saved to {{csv_file}}")
        
    except Exception as e:
        print(f"Collection error: {{e}}")

if __name__ == "__main__":
    main()
'''
        
        script_path = Path("run_flight_collection.py")
        with open(script_path, 'w') as f:
            f.write(collection_script)
        
        print(f"✅ Collection script created: {script_path}")
        
        # Create batch file for Windows scheduling
        batch_content = f'''@echo off
echo FlightAware Data Collection - {datetime.now().strftime('%Y-%m-%d %H:%M')}
cd /d "{os.getcwd()}"
python run_flight_collection.py
pause
'''
        
        batch_path = Path("run_flight_collection.bat")
        with open(batch_path, 'w') as f:
            f.write(batch_content)
        
        print(f"✅ Batch script created: {batch_path}")
        
        print("\n📋 Next Steps:")
        print("1. Test the collection script manually first:")
        print(f"   python {script_path}")
        print("2. Set up Windows Task Scheduler (optional):")
        print(f"   Schedule: {batch_path}")
        print("   Frequency: Daily or weekly")
        print("3. Monitor API usage to stay within free limits")
        
        return True

class FlightAwareDataCollector:
    """Enhanced data collector with real API integration"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://aeroapi.flightaware.com/aeroapi"
        self.headers = {"x-apikey": api_key}
    
    def collect_airport_data(self, airport_code: str, start_date: datetime, end_date: datetime) -> Dict:
        """Collect comprehensive airport data"""
        
        results = {
            "airport": airport_code,
            "collection_time": datetime.now().isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "departures": [],
            "arrivals": [],
            "summary": {}
        }
        
        try:
            # Collect departures
            departures = self._get_departures(airport_code, start_date, end_date)
            results["departures"] = departures
            
            # Collect arrivals  
            arrivals = self._get_arrivals(airport_code, start_date, end_date)
            results["arrivals"] = arrivals
            
            # Generate summary
            results["summary"] = self._generate_summary(departures, arrivals)
            
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def _get_departures(self, airport_code: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get departure data"""
        
        url = f"{self.base_url}/airports/{airport_code}/flights/departures"
        params = {
            "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "max_pages": 10
        }
        
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("departures", [])
        else:
            raise Exception(f"Departures API error: {response.status_code} - {response.text}")
    
    def _get_arrivals(self, airport_code: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get arrival data"""
        
        url = f"{self.base_url}/airports/{airport_code}/flights/arrivals"
        params = {
            "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "max_pages": 10
        }
        
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("arrivals", [])
        else:
            raise Exception(f"Arrivals API error: {response.status_code} - {response.text}")
    
    def _generate_summary(self, departures: List[Dict], arrivals: List[Dict]) -> Dict:
        """Generate data summary"""
        
        total_flights = len(departures) + len(arrivals)
        
        # Count cancellations
        cancelled_departures = len([f for f in departures if f.get("cancelled", False)])
        cancelled_arrivals = len([f for f in arrivals if f.get("cancelled", False)])
        
        return {
            "total_flights": total_flights,
            "total_departures": len(departures),
            "total_arrivals": len(arrivals),
            "cancelled_departures": cancelled_departures,
            "cancelled_arrivals": cancelled_arrivals,
            "total_cancelled": cancelled_departures + cancelled_arrivals,
            "cancellation_rate": (cancelled_departures + cancelled_arrivals) / total_flights if total_flights > 0 else 0
        }
    
    def save_to_csv(self, data: Dict, filename: str):
        """Save collected data to CSV"""
        
        import pandas as pd
        
        # Combine all flights
        all_flights = []
        
        for flight in data.get("departures", []):
            flight_record = {
                "type": "departure",
                "flight_id": flight.get("fa_flight_id"),
                "ident": flight.get("ident"),
                "scheduled_time": flight.get("scheduled_out"),
                "actual_time": flight.get("actual_out"),
                "cancelled": flight.get("cancelled", False),
                "origin": flight.get("origin", {}).get("code"),
                "destination": flight.get("destination", {}).get("code"),
                "aircraft_type": flight.get("aircraft_type")
            }
            all_flights.append(flight_record)
        
        for flight in data.get("arrivals", []):
            flight_record = {
                "type": "arrival",
                "flight_id": flight.get("fa_flight_id"),
                "ident": flight.get("ident"),
                "scheduled_time": flight.get("scheduled_in"),
                "actual_time": flight.get("actual_in"),
                "cancelled": flight.get("cancelled", False),
                "origin": flight.get("origin", {}).get("code"),
                "destination": flight.get("destination", {}).get("code"),
                "aircraft_type": flight.get("aircraft_type")
            }
            all_flights.append(flight_record)
        
        # Create DataFrame and save
        df = pd.DataFrame(all_flights)
        df.to_csv(filename, index=False)
        
        print(f"Saved {len(all_flights)} flight records to {filename}")

def main():
    """Main setup flow"""
    
    print("=== FlightAware API Setup & Data Integration ===")
    
    guide = FlightAwareSetupGuide()
    
    # Show instructions
    guide.show_setup_instructions()
    
    # Setup API key
    config = guide.interactive_api_key_setup()
    
    if not config:
        print("❌ Setup failed. Please try again.")
        return
    
    # Check API usage
    print("\n📊 Checking API Usage...")
    usage = guide.check_api_usage(config)
    print(f"Current usage: {usage}")
    
    # Setup automation
    print("\n🤖 Setting up automation...")
    guide.setup_automated_collection(config)
    
    print("\n✅ FlightAware API Setup Complete!")
    print("\n🎯 What's Next:")
    print("1. Test your API connection")
    print("2. Run initial data collection")
    print("3. Integrate with existing prediction system")
    print("4. Monitor usage to stay within free limits")
    
    # Offer to run initial test
    test_choice = input("\nRun initial data collection test? (y/n): ").lower()
    if test_choice == 'y':
        print("\n🧪 Running test collection...")
        try:
            collector = FlightAwareDataCollector(config["api_key"])
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)  # Small test
            
            result = collector.collect_airport_data("RIS", start_date, end_date)
            
            print(f"\n📊 Test Results:")
            print(f"Total flights: {result['summary']['total_flights']}")
            print(f"Departures: {result['summary']['total_departures']}")
            print(f"Arrivals: {result['summary']['total_arrivals']}")
            print(f"Cancellations: {result['summary']['total_cancelled']}")
            print(f"Cancellation rate: {result['summary']['cancellation_rate']:.1%}")
            
            # Save test data
            test_file = f"test_rishiri_flights_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            collector.save_to_csv(result, test_file)
            
            print(f"✅ Test data saved to: {test_file}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()