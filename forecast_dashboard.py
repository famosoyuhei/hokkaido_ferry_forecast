#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferry Forecast Dashboard
Web interface for 7-day ferry cancellation predictions
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import sqlite3
from datetime import datetime, timedelta
import json
from pathlib import Path

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Ensure static directory exists
Path('static').mkdir(exist_ok=True)

class ForecastDashboard:
    """Dashboard data provider"""

    def __init__(self):
        # Use /data volume if available (Railway persistent storage)
        import os
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.db_file = os.path.join(data_dir, "ferry_weather_forecast.db")

    def get_7day_forecast(self):
        """Get 7-day forecast summary"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get forecast for next 7 days
        cursor.execute('''
            SELECT DISTINCT
                forecast_for_date as date,
                risk_level,
                AVG(risk_score) as avg_risk,
                AVG(wind_forecast) as wind,
                AVG(wave_forecast) as wave,
                AVG(visibility_forecast) as visibility,
                AVG(temperature_forecast) as temp,
                COUNT(DISTINCT route) as routes
            FROM cancellation_forecast
            WHERE forecast_for_date >= date('now')
            AND forecast_for_date <= date('now', '+7 days')
            GROUP BY forecast_for_date, risk_level
            ORDER BY forecast_for_date, avg_risk DESC
        ''')

        forecasts = {}
        for row in cursor.fetchall():
            date, risk, score, wind, wave, vis, temp, routes = row

            if date not in forecasts:
                forecasts[date] = {
                    'date': date,
                    'risks': [],
                    'max_risk': 'MINIMAL',
                    'max_score': 0
                }

            risk_data = {
                'level': risk,
                'score': score,
                'wind': wind,
                'wave': wave,
                'visibility': vis,
                'temperature': temp,
                'affected_routes': routes
            }

            forecasts[date]['risks'].append(risk_data)

            # Track highest risk
            if score > forecasts[date]['max_score']:
                forecasts[date]['max_risk'] = risk
                forecasts[date]['max_score'] = score

        conn.close()

        # Convert to list and sort
        forecast_list = list(forecasts.values())
        forecast_list.sort(key=lambda x: x['date'])

        return forecast_list

    def get_today_detail(self):
        """Get detailed forecast for today"""

        today = datetime.now().date().isoformat()

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get hourly forecast for today
        cursor.execute('''
            SELECT
                forecast_hour,
                location,
                AVG(wind_speed_max) as wind_max,
                AVG(wave_height_max) as wave_max,
                AVG(visibility) as visibility,
                AVG(temperature) as temp,
                weather_text
            FROM weather_forecast
            WHERE forecast_date = ?
            GROUP BY forecast_hour, location
            ORDER BY forecast_hour
            LIMIT 24
        ''', (today,))

        hourly = []
        for row in cursor.fetchall():
            hour, location, wind, wave, vis, temp, weather = row

            if wind or wave or vis:
                hourly.append({
                    'hour': hour if hour is not None else 0,
                    'location': location,
                    'wind': wind,
                    'wave': wave,
                    'visibility': vis,
                    'temperature': temp,
                    'weather': weather
                })

        conn.close()
        return hourly

    def get_routes_forecast(self, date=None):
        """Get forecast by route"""

        if date is None:
            date = datetime.now().date().isoformat()

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                route,
                risk_level,
                risk_score,
                wind_forecast,
                wave_forecast,
                visibility_forecast,
                recommended_action
            FROM cancellation_forecast
            WHERE forecast_for_date = ?
            GROUP BY route
            ORDER BY risk_score DESC
        ''', (date,))

        routes = []
        for row in cursor.fetchall():
            route, risk, score, wind, wave, vis, action = row

            # Route name mapping
            route_names = {
                'wakkanai_oshidomari': '稚内 → 鴛泊（利尻）',
                'wakkanai_kafuka': '稚内 → 香深（礼文）',
                'oshidomari_wakkanai': '鴛泊（利尻）→ 稚内',
                'kafuka_wakkanai': '香深（礼文）→ 稚内',
                'oshidomari_kafuka': '鴛泊（利尻）→ 香深（礼文）',
                'kafuka_oshidomari': '香深（礼文）→ 鴛泊（利尻）'
            }

            routes.append({
                'route': route,
                'route_name': route_names.get(route, route),
                'risk_level': risk,
                'risk_score': score,
                'wind': wind,
                'wave': wave,
                'visibility': vis,
                'action': action
            })

        conn.close()
        return routes

    def get_statistics(self):
        """Get collection statistics"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Weather forecast count
        cursor.execute('SELECT COUNT(*), COUNT(DISTINCT forecast_date) FROM weather_forecast')
        weather_count, weather_days = cursor.fetchone()

        # Cancellation forecast count
        cursor.execute('SELECT COUNT(DISTINCT forecast_for_date) FROM cancellation_forecast')
        cancel_days = cursor.fetchone()[0]

        # High risk days count
        cursor.execute('''
            SELECT COUNT(DISTINCT forecast_for_date)
            FROM cancellation_forecast
            WHERE risk_level = 'HIGH'
            AND forecast_for_date >= date('now')
        ''')
        high_risk_days = cursor.fetchone()[0]

        # Last collection
        cursor.execute('''
            SELECT MAX(timestamp) FROM forecast_collection_log
            WHERE status = 'SUCCESS'
        ''')
        last_collection = cursor.fetchone()[0]

        conn.close()

        return {
            'weather_records': weather_count,
            'weather_days': weather_days,
            'forecast_days': cancel_days,
            'high_risk_days': high_risk_days,
            'last_updated': last_collection
        }

# Initialize dashboard
dashboard = ForecastDashboard()

@app.route('/')
def index():
    """Main dashboard page"""

    forecast = dashboard.get_7day_forecast()
    today_detail = dashboard.get_today_detail()
    today_routes = dashboard.get_routes_forecast()
    stats = dashboard.get_statistics()

    # Determine page title and status
    high_risk_count = sum(1 for f in forecast if f['max_risk'] == 'HIGH')

    if high_risk_count > 0:
        status = f"⚠️ {high_risk_count}日間 高リスク"
        status_class = "danger"
    elif any(f['max_risk'] == 'MEDIUM' for f in forecast):
        status = "注意 中リスク日あり"
        status_class = "warning"
    else:
        status = "✅ 良好"
        status_class = "success"

    return render_template('forecast_dashboard.html',
                         forecast=forecast,
                         today_detail=today_detail,
                         today_routes=today_routes,
                         stats=stats,
                         status=status,
                         status_class=status_class,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M'))

@app.route('/api/forecast')
def api_forecast():
    """API endpoint for 7-day forecast"""
    return jsonify(dashboard.get_7day_forecast())

@app.route('/api/today')
def api_today():
    """API endpoint for today's detail"""
    return jsonify(dashboard.get_today_detail())

@app.route('/api/routes')
def api_routes():
    """API endpoint for route forecasts"""
    date = request.args.get('date', datetime.now().date().isoformat())
    return jsonify(dashboard.get_routes_forecast(date))

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    return jsonify(dashboard.get_statistics())

@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest"""
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

@app.route('/service-worker.js')
def service_worker():
    """Serve service worker"""
    return send_from_directory('static', 'service-worker.js', mimetype='application/javascript')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    Path('templates').mkdir(exist_ok=True)

    print("=" * 80)
    print("FERRY FORECAST DASHBOARD")
    print("=" * 80)
    print("\n🌐 Starting web server...")
    print("📊 Dashboard URL: http://localhost:5000")
    print("\n✅ Press Ctrl+C to stop\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
