#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API Debug Script
"""

import requests
import json
from datetime import datetime, timedelta

def debug_api_request():
    """Debug FlightAware API request"""
    
    # Load API key
    with open('flightaware_config.json') as f:
        config = json.load(f)
    
    api_key = config["api_key"]
    headers = {"x-apikey": api_key}
    base_url = "https://aeroapi.flightaware.com/aeroapi"
    
    print("=" * 50)
    print("FLIGHTAWARE API DEBUG")
    print("=" * 50)
    
    # Test 1: Simple airport info
    print("[TEST 1] Airport information...")
    try:
        response = requests.get(f"{base_url}/airports/RIS", headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Airport: {data.get('name', 'N/A')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    
    print()
    
    # Test 2: Recent departures (no date filter)
    print("[TEST 2] Recent departures (no date filter)...")
    try:
        response = requests.get(
            f"{base_url}/airports/RIS/flights/departures",
            headers=headers,
            params={"max_pages": 1},
            timeout=10
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            departures = data.get('departures', [])
            print(f"Found {len(departures)} departures")
            if departures:
                flight = departures[0]
                print(f"Latest: {flight.get('ident')} to {flight.get('destination', {}).get('code')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    
    print()
    
    # Test 3: Historical with shorter period (7 days)
    print("[TEST 3] Historical data (7 days)...")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        response = requests.get(
            f"{base_url}/airports/RIS/flights/departures",
            headers=headers,
            params={
                "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "max_pages": 1
            },
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(f"Request URL: {response.url}")
        if response.status_code == 200:
            data = response.json()
            departures = data.get('departures', [])
            print(f"Found {len(departures)} historical departures")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    
    print()
    
    # Test 4: Different airport code format
    print("[TEST 4] Alternative airport codes...")
    for airport_code in ["RIS", "RJER"]:
        try:
            response = requests.get(f"{base_url}/airports/{airport_code}", headers=headers, timeout=10)
            print(f"{airport_code}: Status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Name: {data.get('name', 'N/A')}")
            elif response.status_code != 404:
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"  Exception: {e}")

if __name__ == "__main__":
    debug_api_request()