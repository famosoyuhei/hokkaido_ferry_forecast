# Hokkaido Ferry Forecast System

Real-time ferry cancellation prediction system for Hokkaido islands (Rishiri & Rebun).

📱 **NEW: Smartphone App Available!** Install as a Progressive Web App (PWA) on iOS/Android - see [PWA Guide](PWA_SMARTPHONE_APP_GUIDE.md)

## 🎉 Latest Updates (2025-10-22)

### 📱 Smartphone App (PWA) - NEW!
- **Progressive Web App**: Install on iPhone/Android home screen
- **Offline Support**: Works without internet connection (cached data)
- **App-like Experience**: Full-screen mode, no browser UI
- **Auto-refresh**: Fresh data every 30 minutes
- **Push Notifications**: Ready for high-risk day alerts (configurable)
- **Zero Cost**: No App Store fees or審査 required

### ✅ 7-Day Weather Forecast System - NEW!
- **JMA (Japan Meteorological Agency) API Integration**: Official weather forecasts for Wakkanai/Soya region
- **Dual-Source Weather Data**: JMA (wave height, official forecasts) + Open-Meteo (visibility, detailed hourly data)
- **7-Day Cancellation Risk Prediction**: Automated risk assessment for all ferry routes
- **Real-time Updates**: Forecasts updated 5 times daily via JMA
- **Comprehensive Data**: Wind speed, wave height, visibility, temperature, precipitation probability

### ✅ Enhanced Data Collection System
- **Real Ferry Schedule Collection**: Extracts detailed operational data from Heartland Ferry official website
- **Weather Data Integration**: Current weather + 7-day forecasts
- **Dual Storage**: SQLite database (enhanced analysis) + CSV files (compatibility)
- **Automated Collection**: Railway cron job runs daily at 6:00 AM JST

### 📊 Forecast Capability (NEW)
- **Forecast Period**: 7 days ahead
- **Update Frequency**: 5 times/day (JMA: 05:00, 11:00, 17:00 JST)
- **Data Sources**: JMA (official) + Open-Meteo (hourly detail)
- **Risk Levels**: HIGH / MEDIUM / LOW / MINIMAL
- **Example Forecast** (2025-10-22):
  - Today: HIGH RISK - Wind 25m/s, Wave 5m → Cancellations likely
  - Tomorrow: MEDIUM RISK - Wind 27m/s → Monitor closely
  - Next week: Weather improving

### 📊 Data Collection Status
- **Total Records**: 70 (CSV) + 16 (enhanced database) + 499 (weather forecasts)
- **Collection Period**: September 11, 2025 - Present
- **Data Quality**: Actual ferry operations + Current weather + 7-day forecasts
- **Latest Collection**: October 22, 2025
  - Current: Wind 21.8 m/s, Visibility 0.98 km
  - Forecast: Improving conditions expected in 3-4 days

## Features

- Real-time ferry status monitoring from Heartland Ferry
- Seasonal timetable integration
- Weather-based cancellation prediction with actual meteorological data
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

## Data Collection Scripts

### Weather Forecast Collector (NEW - Primary)
```bash
python weather_forecast_collector.py
```
- **7-day weather forecasts** from JMA + Open-Meteo
- **Cancellation risk prediction** for all ferry routes
- Wave height, wind speed, visibility, temperature
- Automated risk level assessment (HIGH/MEDIUM/LOW/MINIMAL)
- Updates 5 times/day
- **Recommended for production use**

### Current Conditions Collector
```bash
python improved_ferry_collector.py
```
- Scrapes actual ferry schedules from Heartland Ferry website
- Collects real-time weather data (current conditions only)
- Saves to both SQLite database and CSV files

### Legacy Collectors
- `ferry_data_collector.py`: Generates simulated data (for testing)
- `heartland_ferry_scraper.py`: Basic scraper without weather integration
- `cloud_ferry_collector.py`: Cloud deployment template (deprecated)

## Local Development

```bash
pip install -r requirements.txt
python improved_ferry_collector.py
```

## License

Private project for Hokkaido ferry prediction research.
