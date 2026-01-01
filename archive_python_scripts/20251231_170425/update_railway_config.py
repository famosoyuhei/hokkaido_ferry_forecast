#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update Railway Configuration for Cron Jobs
"""

import json

def update_railway_config():
    """Update railway.json with cron job configuration"""
    
    # Updated configuration with cron job
    railway_config = {
        "build": {
            "commands": [
                "pip install -r requirements.txt"
            ]
        },
        "deploy": {
            "startCommand": "python cloud_ferry_collector.py"
        },
        "cron": {
            "ferry_collection": {
                "command": "python cloud_ferry_collector.py",
                "schedule": "0 6 * * *"
            }
        },
        "variables": {
            "FLIGHTAWARE_API_KEY": "QEgHk9GkswfERfjg2ujDosuP2Ss60sXs"
        }
    }
    
    # Save updated config
    with open("railway.json", "w") as f:
        json.dump(railway_config, f, indent=2)
    
    print("[OK] Updated railway.json with cron job configuration")
    
    # Also create a more comprehensive version
    railway_config_v2 = {
        "$schema": "https://railway.app/railway.schema.json",
        "build": {
            "commands": ["pip install -r requirements.txt"]
        },
        "deploy": {
            "startCommand": "echo 'Ferry data collection system deployed'"
        },
        "cron": [
            {
                "name": "daily_ferry_collection",
                "command": "python cloud_ferry_collector.py",
                "schedule": "0 6 * * *",
                "timezone": "Asia/Tokyo"
            }
        ]
    }
    
    with open("railway.config.json", "w") as f:
        json.dump(railway_config_v2, f, indent=2)
    
    print("[OK] Created railway.config.json with enhanced cron configuration")
    
    print("\nNext steps:")
    print("1. Commit and push these updated files to GitHub")
    print("2. Railway will automatically detect the changes")
    print("3. The cron job should be configured automatically")

def main():
    """Main execution"""
    update_railway_config()
    
    print("\nTo apply changes:")
    print("git add railway.json railway.config.json")
    print("git commit -m 'Add cron job configuration'")
    print("git push origin main")

if __name__ == "__main__":
    main()