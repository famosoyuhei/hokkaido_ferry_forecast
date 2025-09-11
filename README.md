# Hokkaido Ferry Forecast System

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
