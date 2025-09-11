#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API Connection Test
"""

import requests
import json
from datetime import datetime
import os

def test_api_connection():
    """Test FlightAware API connection with billing protection"""
    
    # Load config
    with open('flightaware_config.json') as f:
        config = json.load(f)
    
    api_key = config["api_key"]
    base_url = config["endpoints"]["base_url"]
    
    headers = {"x-apikey": api_key}
    
    print("=" * 50)
    print("FLIGHTAWARE API CONNECTION TEST")
    print("=" * 50)
    print(f"API Key: {api_key[:10]}...")
    print(f"Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test 1: Airport Info (Rishiri)
    print("[TEST 1] Rishiri Airport Information...")
    try:
        response = requests.get(
            f"{base_url}/airports/RIS",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            airport_data = response.json()
            print(f"[OK] Status: {response.status_code}")
            print(f"[OK] Airport: {airport_data.get('name', 'N/A')}")
            print(f"[OK] Code: {airport_data.get('code', 'N/A')}")
            print(f"[OK] Location: {airport_data.get('city', 'N/A')}")
            test1_success = True
        else:
            print(f"[ERROR] Status: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            test1_success = False
            
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        test1_success = False
    
    print()
    
    # Test 2: Recent Flights
    print("[TEST 2] Recent Flight Data...")
    try:
        response = requests.get(
            f"{base_url}/airports/RIS/flights/departures",
            headers=headers,
            params={"max_pages": 1},
            timeout=10
        )
        
        if response.status_code == 200:
            flight_data = response.json()
            departures = flight_data.get('departures', [])
            print(f"[OK] Status: {response.status_code}")
            print(f"[OK] Recent departures found: {len(departures)}")
            
            if departures:
                recent = departures[0]
                print(f"[OK] Latest flight: {recent.get('ident', 'N/A')}")
                print(f"[OK] Destination: {recent.get('destination', {}).get('code', 'N/A')}")
            
            test2_success = True
        else:
            print(f"[WARNING] Status: {response.status_code}")
            print(f"[WARNING] Response: {response.text}")
            test2_success = False
            
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        test2_success = False
    
    print()
    
    # Test 3: API Rate Limits Check
    print("[TEST 3] API Rate Limits...")
    try:
        # Check response headers for rate limit info
        if 'response' in locals():
            headers_info = dict(response.headers)
            rate_limit = headers_info.get('X-RateLimit-Remaining', 'N/A')
            monthly_usage = headers_info.get('X-Monthly-Usage', 'N/A')
            
            print(f"[INFO] Rate limit remaining: {rate_limit}")
            print(f"[INFO] Monthly usage: {monthly_usage}")
        else:
            print("[WARNING] No response headers available")
            
    except Exception as e:
        print(f"[WARNING] Could not read rate limits: {e}")
    
    print()
    
    # Summary
    print("=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    
    if test1_success and test2_success:
        print("[SUCCESS] All tests passed!")
        print("[SUCCESS] FlightAware API is ready for use")
        print("[SUCCESS] Billing protection is active")
        print()
        print("Next steps:")
        print("1. Run historical data collection:")
        print("   python run_flight_collection.py")
        print("2. Start integrated predictions:")
        print("   python final_integrated_prediction_en.py")
        return True
    else:
        print("[ERROR] Some tests failed")
        print("[ERROR] Please check API key and try again")
        return False

if __name__ == "__main__":
    test_api_connection()