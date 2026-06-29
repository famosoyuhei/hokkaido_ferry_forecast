#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API Test Script
Simple test for FlightAware API functionality
"""

import requests
import json
from datetime import datetime, timedelta

class FlightAwareAPITest:
    """FlightAware API Test Class"""
    
    def __init__(self):
        # Demo API key for testing (will be replaced with real one)
        self.api_key = "YOUR_API_KEY_HERE" 
        self.base_url = "https://aeroapi.flightaware.com/aeroapi"
        self.headers = {"x-apikey": self.api_key}
        
    def test_api_connection(self):
        """Test API connection and endpoint availability"""
        
        print("=== FlightAware API Connection Test ===")
        
        # Test basic connectivity
        try:
            # Use airports endpoint for basic test
            url = f"{self.base_url}/airports/RIS"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 401:
                print("AUTH ERROR: Invalid or missing API key")
                print("Action needed: Sign up for FlightAware API key")
                return False
            elif response.status_code == 200:
                print("SUCCESS: API connection established")
                data = response.json()
                print(f"Airport data: {json.dumps(data, indent=2)}")
                return True
            else:
                print(f"ERROR: Unexpected status code {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"CONNECTION ERROR: {e}")
            return False
    
    def test_flight_search(self):
        """Test flight search for Rishiri Airport"""
        
        print("\n=== Flight Search Test ===")
        
        # Test departures from Rishiri Airport
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Last 7 days
            
            url = f"{self.base_url}/airports/RIS/flights/departures"
            params = {
                "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "max_pages": 1
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            print(f"Departures Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                flights = data.get('departures', [])
                print(f"Found {len(flights)} flights in last 7 days")
                
                if flights:
                    sample_flight = flights[0]
                    print("Sample flight data:")
                    print(json.dumps(sample_flight, indent=2))
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Search error: {e}")
    
    def show_api_setup_instructions(self):
        """Show instructions for API setup"""
        
        print("\n=== FlightAware API Setup Instructions ===")
        print("1. Visit: https://www.flightaware.com/commercial/aeroapi/")
        print("2. Sign up for Personal Plan (Free up to $5/month)")
        print("3. Get your API key from the dashboard")
        print("4. Replace 'YOUR_API_KEY_HERE' in the script")
        print("\nPersonal Plan Limits:")
        print("- $5 free credits per month")
        print("- Historical data: 90 days")
        print("- Suitable for our development needs")

def main():
    """Main test execution"""
    
    tester = FlightAwareAPITest()
    
    # Test API connection
    if tester.test_api_connection():
        tester.test_flight_search()
    else:
        tester.show_api_setup_instructions()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()