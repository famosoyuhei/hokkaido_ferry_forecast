#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepare Project for GitHub and Railway Deployment
"""

import os
import shutil
from pathlib import Path

def create_gitignore():
    """Create .gitignore file for the project"""
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Database files (keep local data private)
*.db
*.sqlite
*.sqlite3

# Environment variables
.env
.env.local

# Logs
*.log
logs/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Windows Task Scheduler files (local only)
*.bat

# Temporary files
*.tmp
temp/
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("[OK] Created .gitignore")

def create_readme():
    """Create README.md for the project"""
    
    readme_content = """# Hokkaido Ferry Forecast System

Real-time ferry cancellation prediction system for Hokkaido islands (Rishiri & Rebun).

## Features

- Real-time ferry status monitoring from Heartland Ferry
- Seasonal timetable integration 
- Weather-based cancellation prediction
- Flight data integration (Rishiri Airport)
- 24/7 cloud-based data collection

## Data Sources

- **Ferry Status**: https://heartlandferry.jp/status/
- **Timetables**: https://heartlandferry.jp/timetable/
- **Flight Data**: FlightAware API
- **Weather**: Integrated weather analysis

## Deployment

This system runs on Railway for 24/7 operation:

1. Automatic data collection every day at 6:00 AM JST
2. PostgreSQL database for reliable data storage
3. Real-time status monitoring and predictions

## Routes Covered

- Wakkanai ↔ Rishiri Island
- Wakkanai ↔ Rebun Island  
- Rishiri Island ↔ Rebun Island

## Technology Stack

- **Backend**: Python 3.11
- **Database**: PostgreSQL (Railway)
- **Web Scraping**: BeautifulSoup4, Requests
- **Scheduling**: Railway Cron Jobs
- **API**: FlightAware AeroAPI

## Environment Variables

- `FLIGHTAWARE_API_KEY`: FlightAware API key for flight data
- `DATABASE_URL`: PostgreSQL connection (auto-provided by Railway)

## Local Development

```bash
pip install -r requirements.txt
python cloud_ferry_collector.py
```

## License

Private project for Hokkaido ferry prediction research.
"""
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("[OK] Created README.md")

def select_deployment_files():
    """Select only necessary files for deployment"""
    
    # Essential files for cloud deployment
    essential_files = [
        'cloud_ferry_collector.py',
        'requirements.txt',
        'railway.json',
        'Procfile',
        'runtime.txt',
        '.env.template',
        'README.md',
        '.gitignore'
    ]
    
    # Optional additional files that work well in cloud
    cloud_compatible_files = [
        'ferry_timetable_system.py',
        'enhanced_ferry_forecast.py',
        'heartland_ferry_scraper.py'
    ]
    
    print("Essential deployment files:")
    for file in essential_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
    
    print("\nCloud-compatible additional files:")
    for file in cloud_compatible_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  - {file} (not found)")
    
    return essential_files + cloud_compatible_files

def create_deployment_checklist():
    """Create deployment checklist"""
    
    checklist = """# Railway Deployment Checklist

## Pre-deployment (Local)
- [ ] All files created and tested
- [ ] .gitignore configured
- [ ] README.md updated
- [ ] Environment variables documented

## GitHub Setup
- [ ] Create new repository: hokkaido-ferry-forecast
- [ ] Push all files to main branch
- [ ] Verify repository is public or accessible to Railway

## Railway Deployment  
- [ ] Log into Railway with GitHub account
- [ ] Click "Deploy from GitHub repo"
- [ ] Select hokkaido-ferry-forecast repository
- [ ] Confirm automatic deployment starts

## Environment Configuration
- [ ] Set FLIGHTAWARE_API_KEY in Railway dashboard
- [ ] Verify DATABASE_URL is auto-configured
- [ ] Check deployment logs for success

## Cron Job Setup
- [ ] Go to Railway project dashboard
- [ ] Navigate to "Cron" or "Deployments" section
- [ ] Add new cron job:
  - Command: `python cloud_ferry_collector.py`
  - Schedule: `0 6 * * *` (daily 6 AM JST)

## Testing & Verification
- [ ] Manual trigger test collection
- [ ] Check database for new records
- [ ] Verify logs show successful execution
- [ ] Confirm next scheduled run is set

## Monitoring Setup
- [ ] Bookmark Railway project dashboard
- [ ] Set up log monitoring
- [ ] Document access for future maintenance

## Completion
- [ ] System collecting data automatically
- [ ] No longer dependent on local PC
- [ ] 24/7 operation confirmed

Estimated completion time: 15-20 minutes
"""
    
    with open('DEPLOYMENT_CHECKLIST.md', 'w') as f:
        f.write(checklist)
    
    print("[OK] Created DEPLOYMENT_CHECKLIST.md")

def prepare_github_commands():
    """Generate Git commands for repository setup"""
    
    commands = """# Git Commands for Repository Setup

# 1. Initialize git repository (if not already done)
git init

# 2. Add all files
git add .

# 3. Create initial commit
git commit -m "Initial commit: Hokkaido Ferry Forecast System for Railway deployment"

# 4. Add GitHub repository (replace with your actual repo URL)
git remote add origin https://github.com/YOUR_USERNAME/hokkaido-ferry-forecast.git

# 5. Push to GitHub
git push -u origin main

# Alternative if you get permission denied:
git push -u origin main --force

# Check status
git status
git log --oneline
"""
    
    with open('GIT_COMMANDS.txt', 'w') as f:
        f.write(commands)
    
    print("[OK] Created GIT_COMMANDS.txt")
    print("\nNext steps:")
    print("1. Create GitHub repository: hokkaido-ferry-forecast")
    print("2. Run commands from GIT_COMMANDS.txt")
    print("3. Proceed to Railway deployment")

def main():
    """Main preparation process"""
    
    print("=" * 60)
    print("GITHUB & RAILWAY DEPLOYMENT PREPARATION")
    print("=" * 60)
    print()
    
    # Create necessary files
    create_gitignore()
    create_readme()
    create_deployment_checklist()
    prepare_github_commands()
    
    print()
    print("=" * 60)
    print("PREPARATION COMPLETE")
    print("=" * 60)
    
    # Show file selection
    deployment_files = select_deployment_files()
    
    print(f"\nTotal files ready for deployment: {len(deployment_files)}")
    print("\nNext steps:")
    print("1. Create GitHub repository: 'hokkaido-ferry-forecast'")
    print("2. Follow GIT_COMMANDS.txt instructions")  
    print("3. Deploy to Railway from GitHub")
    print("4. Follow DEPLOYMENT_CHECKLIST.md")

if __name__ == "__main__":
    main()