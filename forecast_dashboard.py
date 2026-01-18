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
        # Support both RAILWAY_VOLUME_MOUNT_PATH and RAILWAY_VOLUME_MOUNT
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
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

        # Get accuracy metrics
        accuracy_stats = self.get_accuracy_stats()

        stats = {
            'weather_records': weather_count,
            'weather_days': weather_days,
            'forecast_days': cancel_days,
            'high_risk_days': high_risk_days,
            'last_updated': last_collection
        }

        # Add accuracy metrics if available
        if accuracy_stats:
            stats.update(accuracy_stats)

        return stats

    def get_accuracy_stats(self):
        """Get accuracy statistics from accuracy database"""

        import os
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        actual_db = os.path.join(data_dir, "ferry_actual_operations.db")

        # Check if accuracy database exists
        if not Path(actual_db).exists():
            return None

        try:
            conn = sqlite3.connect(actual_db)
            cursor = conn.cursor()

            # Get last 30 days accuracy
            cursor.execute('''
                SELECT
                    COUNT(*) as days,
                    AVG(accuracy_rate) as avg_accuracy,
                    AVG(precision) as avg_precision,
                    AVG(recall) as avg_recall,
                    SUM(total_predictions) as total_pred,
                    SUM(correct_predictions) as total_correct
                FROM accuracy_summary
                WHERE date >= date('now', '-30 days')
            ''')

            row = cursor.fetchone()
            conn.close()

            if not row or row[0] == 0:
                return None

            days, avg_acc, avg_prec, avg_rec, total_pred, total_correct = row

            return {
                'accuracy_days_tracked': days,
                'accuracy_rate': avg_acc,
                'accuracy_precision': avg_prec,
                'accuracy_recall': avg_rec,
                'accuracy_total_predictions': total_pred,
                'accuracy_total_correct': total_correct
            }

        except Exception as e:
            print(f"[WARNING] Could not get accuracy stats: {e}")
            return None

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

    # Get today's max risk level
    today_max_risk = 'MINIMAL'
    if today_routes:
        risk_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'MINIMAL': 1}
        today_max_risk = max(today_routes, key=lambda r: risk_priority.get(r['risk_level'], 0))['risk_level']

    return render_template('forecast_dashboard.html',
                         forecast=forecast,
                         today_detail=today_detail,
                         today_routes=today_routes,
                         today_max_risk=today_max_risk,
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

@app.route('/route/<route_id>')
def route_details(route_id):
    """Route-specific detailed forecast page for 7 days"""
    import os

    # Route name mapping
    ROUTE_NAMES = {
        'wakkanai_oshidomari': '稚内 ⇔ 利尻(鴛泊)',
        'wakkanai_kafuka': '稚内 ⇔ 礼文(香深)',
        'oshidomari_kafuka': '利尻(鴛泊) ⇔ 礼文(香深)',
        'oshidomari_wakkanai': '利尻(鴛泊) ⇔ 稚内',
        'kafuka_wakkanai': '礼文(香深) ⇔ 稚内',
        'kafuka_oshidomari': '礼文(香深) ⇔ 利尻(鴛泊)'
    }

    route_name = ROUTE_NAMES.get(route_id, route_id)

    # Get sailing forecast data for this route for next 7 days
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    conn = sqlite3.connect(os.path.join(data_dir, "ferry_weather_forecast.db"))
    cursor = conn.cursor()

    # Get 7 days of forecasts
    cursor.execute('''
        SELECT
            forecast_date,
            departure_time,
            arrival_time,
            risk_level,
            risk_score,
            wind_forecast,
            wave_forecast,
            visibility_forecast,
            temperature_forecast,
            recommended_action
        FROM sailing_forecast
        WHERE route = ?
        AND forecast_date >= date('now')
        AND forecast_date <= date('now', '+7 days')
        ORDER BY forecast_date, departure_time
    ''', (route_id,))

    rows = cursor.fetchall()
    conn.close()

    # Group by date
    forecast_by_day = {}
    for row in rows:
        date_str, departure, arrival, risk, score, wind, wave, vis, temp, action = row

        if date_str not in forecast_by_day:
            forecast_by_day[date_str] = {
                'date': date_str,
                'weekday': datetime.fromisoformat(date_str).strftime('%a'),
                'sailings': [],
                'max_risk': 'MINIMAL'
            }

        forecast_by_day[date_str]['sailings'].append({
            'departure': departure,
            'arrival': arrival,
            'risk_level': risk,
            'risk_score': score,
            'wind': wind,
            'wave': wave,
            'visibility': vis,
            'temperature': temp,
            'recommended_action': action
        })

        # Update max risk for the day
        risk_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'MINIMAL': 1}
        if risk_priority.get(risk, 0) > risk_priority.get(forecast_by_day[date_str]['max_risk'], 0):
            forecast_by_day[date_str]['max_risk'] = risk

    # Convert to list and sort by date
    forecast_list = sorted(forecast_by_day.values(), key=lambda x: x['date'])

    # Fill in missing dates with no sailings
    all_days = []
    for i in range(7):
        target_date = (datetime.now().date() + timedelta(days=i)).isoformat()
        existing_day = next((d for d in forecast_list if d['date'] == target_date), None)

        if existing_day:
            all_days.append(existing_day)
        else:
            all_days.append({
                'date': target_date,
                'weekday': (datetime.now().date() + timedelta(days=i)).strftime('%a'),
                'sailings': [],
                'max_risk': 'MINIMAL'
            })

    return render_template('route_details.html',
                         route_name=route_name,
                         route_id=route_id,
                         forecast_by_day=all_days)

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    return jsonify(dashboard.get_statistics())

@app.route('/api/sailings')
def api_sailings():
    """API endpoint for sailing-by-sailing forecasts"""
    import os
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    db_file = os.path.join(data_dir, "ferry_weather_forecast.db")

    # Get date parameter (default: today)
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Get sailing forecasts for the specified date
    cursor.execute('''
        SELECT
            forecast_date,
            route,
            departure_time,
            arrival_time,
            risk_level,
            risk_score,
            wind_forecast,
            wave_forecast,
            visibility_forecast,
            temperature_forecast,
            risk_factors,
            recommended_action
        FROM sailing_forecast
        WHERE forecast_date = ?
        ORDER BY departure_time
    ''', (date_str,))

    sailings = []
    for row in cursor.fetchall():
        sailings.append({
            'date': row[0],
            'route': row[1],
            'departure': row[2],
            'arrival': row[3],
            'risk_level': row[4],
            'risk_score': row[5],
            'wind': row[6],
            'wave': row[7],
            'visibility': row[8],
            'temperature': row[9],
            'risk_factors': row[10],
            'recommended_action': row[11]
        })

    conn.close()

    return jsonify({
        'date': date_str,
        'total_sailings': len(sailings),
        'sailings': sailings
    })

@app.route('/admin/env')
def admin_env():
    """Admin endpoint to check environment variables"""
    import os
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    return jsonify({
        'RAILWAY_VOLUME_MOUNT_PATH': os.environ.get('RAILWAY_VOLUME_MOUNT_PATH'),
        'RAILWAY_VOLUME_MOUNT': os.environ.get('RAILWAY_VOLUME_MOUNT'),
        'PORT': os.environ.get('PORT'),
        'data_dir': data_dir,
        'data_dir_exists': os.path.exists(data_dir),
        'data_dir_is_dir': os.path.isdir(data_dir) if os.path.exists(data_dir) else False,
        'data_dir_writable': os.access(data_dir, os.W_OK) if os.path.exists(data_dir) else False,
        'data_dir_contents': os.listdir(data_dir) if os.path.exists(data_dir) and os.path.isdir(data_dir) else [],
        'all_env_keys': sorted([k for k in os.environ.keys() if 'RAILWAY' in k])
    })

@app.route('/admin/collect-data')
def admin_collect_data():
    """Admin endpoint to trigger data collection"""
    import subprocess
    import os

    # Get the data directory
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run weather forecast collector
        result = subprocess.run(
            ['python', 'weather_forecast_collector.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'stdout': result.stdout,
            'stderr': result.stderr,
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/admin/collect-ferry-data')
def admin_collect_ferry_data():
    """Admin endpoint to collect actual ferry operations data"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        result = subprocess.run(
            ['python', 'improved_ferry_collector.py'],
            capture_output=True,
            text=True,
            timeout=300
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'stdout': result.stdout[-1000:] if result.stdout else '',
            'stderr': result.stderr[-1000:] if result.stderr else '',
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/admin/run-accuracy-tracking')
def admin_run_accuracy_tracking():
    """Admin endpoint to run all accuracy tracking scripts"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        results = {}

        scripts = [
            'operation_accuracy_calculator.py',
            'dual_accuracy_tracker.py',
            'auto_threshold_adjuster.py'
        ]

        for script in scripts:
            result = subprocess.run(
                ['python', script],
                capture_output=True,
                text=True,
                timeout=120
            )

            results[script] = {
                'status': 'success' if result.returncode == 0 else 'error',
                'returncode': result.returncode
            }

        return jsonify({
            'status': 'success',
            'scripts_run': results,
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/admin/generate-sailing-forecasts')
def admin_generate_sailing_forecasts():
    """Admin endpoint to generate sailing-level forecasts"""
    import os
    import subprocess

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        result = subprocess.run(
            ['python', 'sailing_forecast_system.py'],
            capture_output=True,
            text=True,
            timeout=120
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'stdout': result.stdout[-1000:] if result.stdout else '',
            'stderr': result.stderr[-1000:] if result.stderr else '',
            'returncode': result.returncode,
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/admin/init-accuracy-tables')
def admin_init_accuracy_tables():
    """Admin endpoint to initialize accuracy tracking tables"""
    import os
    import subprocess

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run all initialization scripts
        results = {}

        scripts = [
            'sailing_forecast_system.py',  # Initialize sailing forecast first
            'operation_accuracy_calculator.py',
            'dual_accuracy_tracker.py',
            'auto_threshold_adjuster.py'
        ]

        for script in scripts:
            result = subprocess.run(
                ['python', script],
                capture_output=True,
                text=True,
                timeout=60
            )

            results[script] = {
                'status': 'success' if result.returncode == 0 else 'error',
                'returncode': result.returncode,
                'stdout': result.stdout[-500:] if result.stdout else '',  # Last 500 chars
                'stderr': result.stderr[-500:] if result.stderr else ''
            }

        # Check if tables were created
        conn = sqlite3.connect(os.path.join(data_dir, "ferry_weather_forecast.db"))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND (name LIKE '%accuracy%' OR name LIKE '%threshold%')
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'status': 'success',
            'tables_created': tables,
            'scripts_run': results,
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': datetime.now().isoformat()
        }), 500

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
