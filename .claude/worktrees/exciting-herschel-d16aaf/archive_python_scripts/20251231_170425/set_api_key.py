#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API Key Setup Script
"""

import json
import os
from pathlib import Path

def setup_api_key():
    """Set up FlightAware API key"""
    
    print("=" * 50)
    print("FLIGHTAWARE API KEY SETUP")
    print("=" * 50)
    print()
    
    api_key = input("Please enter your FlightAware API key: ").strip()
    
    if not api_key:
        print("[ERROR] No API key entered.")
        return False
    
    if len(api_key) < 30:
        print("[WARNING] API key seems too short. Please verify.")
    
    # Save to config file
    config = {
        "api_key": api_key,
        "plan_type": "Personal",
        "monthly_limit": 5.00,
        "base_url": "https://aeroapi.flightaware.com/aeroapi"
    }
    
    config_file = Path("flightaware_config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"[OK] API key saved to: {config_file}")
    
    # Set environment variable
    os.environ['FLIGHTAWARE_API_KEY'] = api_key
    print("[OK] Environment variable set")
    
    # Test the API key
    print("\n[TEST] Testing API connection...")
    return test_api_key(api_key)

def test_api_key(api_key):
    """Test the API key"""
    
    try:
        import requests
        
        headers = {"x-apikey": api_key}
        response = requests.get(
            "https://aeroapi.flightaware.com/aeroapi/airports/RIS",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            airport_data = response.json()
            print(f"[OK] API Key Valid!")
            print(f"[OK] Connected to: {airport_data.get('name', 'Rishiri Airport')}")
            print(f"[OK] Airport code: {airport_data.get('code', 'RIS')}")
            return True
        elif response.status_code == 401:
            print("[ERROR] Invalid API Key")
            return False
        elif response.status_code == 403:
            print("[ERROR] API Access Denied")
            return False
        else:
            print(f"[WARNING] Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = setup_api_key()
    
    if success:
        print("\n[SUCCESS] FlightAware API setup complete!")
        print("Next step: Run data collection")
        print("  python run_flight_collection.py")
    else:
        print("\n[ERROR] Setup failed. Please check your API key.")