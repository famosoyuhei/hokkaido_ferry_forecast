#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferry Forecast Dashboard
Web interface for 7-day ferry cancellation predictions
"""

import os
from functools import wraps
from flask import Flask, render_template, jsonify, request, send_from_directory
import sqlite3
from datetime import datetime, timedelta
import json
from pathlib import Path
from jst_utils import now_jst, today_jst_str, jst_isoformat, days_from_today_jst

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Ensure static directory exists
Path('static').mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------------------------
def _check_admin_token() -> bool:
    """Return True if the request carries a valid ADMIN_TOKEN."""
    expected = os.environ.get('ADMIN_TOKEN', '')
    if not expected:
        # Token not configured → open access (dev/local)
        return True
    provided = request.headers.get('X-Admin-Token') or request.args.get('token', '')
    return provided == expected


def require_admin(f):
    """Decorator: reject requests without a valid ADMIN_TOKEN with 403."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _check_admin_token():
            return jsonify({'status': 'error', 'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return wrapper

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
            WHERE forecast_for_date >= ?
            AND forecast_for_date <= ?
            GROUP BY forecast_for_date, risk_level
            ORDER BY forecast_for_date, avg_risk DESC
        ''', (today_jst_str(), days_from_today_jst(7)))

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

        today = today_jst_str()

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
            date = today_jst_str()

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cf.route, cf.risk_level, cf.risk_score,
                   cf.wind_forecast, cf.wave_forecast,
                   cf.visibility_forecast, cf.recommended_action
            FROM cancellation_forecast cf
            JOIN (
                SELECT route, MAX(risk_score) AS max_score
                FROM cancellation_forecast
                WHERE forecast_for_date = ?
                GROUP BY route
            ) m ON cf.route = m.route AND cf.risk_score = m.max_score
            WHERE cf.forecast_for_date = ?
            ORDER BY cf.risk_score DESC
        ''', (date, date))

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

    def get_next_sailings(self):
        """Get next upcoming sailing for each route"""
        from datetime import datetime, timedelta
        import pytz

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Use JST timezone
        jst = pytz.timezone('Asia/Tokyo')
        current_datetime = datetime.now(jst)
        current_date = current_datetime.date().isoformat()
        current_time = current_datetime.strftime('%H:%M')
        tomorrow_date = (current_datetime + timedelta(days=1)).date().isoformat()

        # Route name mapping
        route_names = {
            'wakkanai_oshidomari': '稚内 → 鴛泊（利尻）',
            'wakkanai_kafuka': '稚内 → 香深（礼文）',
            'oshidomari_wakkanai': '鴛泊（利尻）→ 稚内',
            'kafuka_wakkanai': '香深（礼文）→ 稚内',
            'oshidomari_kafuka': '鴛泊（利尻）→ 香深（礼文）',
            'kafuka_oshidomari': '香深（礼文）→ 鴛泊（利尻）'
        }

        next_sailings = []

        for route in route_names.keys():
            # Try to find next sailing today (after current time)
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
                    recommended_action
                FROM sailing_forecast
                WHERE route = ?
                AND forecast_date = ?
                AND departure_time > ?
                ORDER BY departure_time ASC
                LIMIT 1
            ''', (route, current_date, current_time))

            row = cursor.fetchone()

            # If no sailing found today, get tomorrow's first sailing
            if not row:
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
                        recommended_action
                    FROM sailing_forecast
                    WHERE route = ?
                    AND forecast_date = ?
                    ORDER BY departure_time ASC
                    LIMIT 1
                ''', (route, tomorrow_date))

                row = cursor.fetchone()

            if row:
                date, departure, arrival, risk, score, wind, wave, vis, action = row

                # Determine if it's today or tomorrow
                is_today = (date == current_date)
                timing_label = f"本日 {departure}発" if is_today else f"明日 {departure}発"

                next_sailings.append({
                    'route': route,
                    'route_name': route_names.get(route, route),
                    'date': date,
                    'departure_time': departure,
                    'arrival_time': arrival,
                    'timing_label': timing_label,
                    'risk_level': risk,
                    'risk_score': score,
                    'wind': wind,
                    'wave': wave,
                    'visibility': vis,
                    'action': action
                })

        conn.close()
        return next_sailings

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
            AND forecast_for_date >= ?
        ''', (today_jst_str(),))
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
    from flask import make_response
    import pytz

    forecast = dashboard.get_7day_forecast()
    today_detail = dashboard.get_today_detail()
    next_sailings = dashboard.get_next_sailings()
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

    # Get next sailings' max risk level
    next_max_risk = 'MINIMAL'
    if next_sailings:
        risk_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'MINIMAL': 1}
        next_max_risk = max(next_sailings, key=lambda r: risk_priority.get(r['risk_level'], 0))['risk_level']

    # Use JST timezone for display
    jst = pytz.timezone('Asia/Tokyo')
    current_time_jst = datetime.now(jst).strftime('%Y-%m-%d %H:%M JST')

    response = make_response(render_template('forecast_dashboard.html',
                         forecast=forecast,
                         today_detail=today_detail,
                         next_sailings=next_sailings,
                         next_max_risk=next_max_risk,
                         stats=stats,
                         status=status,
                         status_class=status_class,
                         current_time=current_time_jst))

    # Prevent caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response

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
    date = request.args.get('date', today_jst_str())
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
        AND forecast_date >= ?
        AND forecast_date <= ?
        ORDER BY forecast_date, departure_time
    ''', (route_id, today_jst_str(), days_from_today_jst(7)))

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
        target_date = days_from_today_jst(i)
        existing_day = next((d for d in forecast_list if d['date'] == target_date), None)

        if existing_day:
            all_days.append(existing_day)
        else:
            all_days.append({
                'date': target_date,
                'weekday': now_jst().date().strftime('%a'),
                'sailings': [],
                'max_risk': 'MINIMAL'
            })

    return render_template('route_details.html',
                         route_name=route_name,
                         route_id=route_id,
                         forecast_by_day=all_days)

@app.route('/select-sailing')
def select_sailing():
    """3-step sailing selection page"""
    return render_template('sailing_selector.html')

@app.route('/sailing/<route_id>/<date>/<departure_time>')
def sailing_detail(route_id, date, departure_time):
    """Detailed forecast for a specific sailing"""
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

    # Get sailing data
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    conn = sqlite3.connect(os.path.join(data_dir, "ferry_weather_forecast.db"))
    cursor = conn.cursor()

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
            risk_factors,
            recommended_action
        FROM sailing_forecast
        WHERE route = ?
        AND forecast_date = ?
        AND departure_time = ?
    ''', (route_id, date, departure_time))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Sailing not found", 404

    date_str, departure, arrival, risk, score, wind, wave, vis, temp, factors, action = row

    sailing = {
        'date': date_str,
        'departure': departure,
        'arrival': arrival,
        'risk_level': risk,
        'risk_score': score,
        'wind': wind,
        'wave': wave,
        'visibility': vis,
        'temperature': temp,
        'risk_factors': factors,
        'recommended_action': action
    }

    return render_template('sailing_detail.html',
                         route_name=route_name,
                         route_id=route_id,
                         sailing=sailing)

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
    date_str = request.args.get('date', now_jst().strftime('%Y-%m-%d'))

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
@require_admin
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
@require_admin
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
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/collect-ferry-data')
@require_admin
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
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/run-accuracy-tracking')
@require_admin
def admin_run_accuracy_tracking():
    """Admin endpoint to run all accuracy tracking scripts"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        results = {}

        scripts = [
            'actual_weather_collector.py',   # collect actual weather first
            'unified_accuracy_tracker.py'    # then calculate accuracy against it
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
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }

        return jsonify({
            'status': 'success',
            'scripts_run': results,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/run-actual-weather')
@require_admin
def admin_run_actual_weather():
    """Run only actual_weather_collector.py (separated from accuracy tracking)."""
    import subprocess
    try:
        result = subprocess.run(
            ['python', 'actual_weather_collector.py'],
            capture_output=True, text=True, timeout=180
        )
        lines = result.stdout.strip().split('\n')
        records_added = 0
        for line in lines:
            if 'Inserted' in line or 'inserted' in line or 'records' in line.lower():
                import re as _re
                m = _re.search(r'(\d+)', line)
                if m:
                    records_added = int(m.group(1))
                    break
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'records_added': records_added,
            'stdout': result.stdout[-3000:],
            'stderr': result.stderr[-1000:],
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/admin/run-accuracy-only')
@require_admin
def admin_run_accuracy_only():
    """Run only unified_accuracy_tracker.py for yesterday (separated from weather collection)."""
    import subprocess
    try:
        result = subprocess.run(
            ['python', 'unified_accuracy_tracker.py'],
            capture_output=True, text=True, timeout=180
        )
        # Parse key metrics from stdout
        accuracy = precision = recall = f1 = None
        is_maint = False
        for line in result.stdout.split('\n'):
            if 'Accuracy:' in line and 'Precision:' in line:
                import re as _re
                m = _re.search(r'Accuracy:\s*([\d.]+)%', line)
                if m: accuracy = float(m.group(1))
                m = _re.search(r'Precision:\s*([\d.]+)', line)
                if m: precision = float(m.group(1))
                m = _re.search(r'Recall:\s*([\d.]+)', line)
                if m: recall = float(m.group(1))
                m = _re.search(r'F1:\s*([\d.]+)', line)
                if m: f1 = float(m.group(1))
            if 'MAINTENANCE' in line.upper():
                is_maint = True
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'result': {
                'accuracy_rate': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'is_likely_maintenance': is_maint,
            },
            'stdout': result.stdout[-3000:],
            'stderr': result.stderr[-1000:],
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/admin/run-bulk-accuracy')
@require_admin
def admin_run_bulk_accuracy():
    """Re-calculate accuracy for a date range using backfilled actual weather."""
    import subprocess
    from flask import request as flask_request
    start_date = flask_request.args.get('start', '2026-04-05')
    end_date   = flask_request.args.get('end', '')
    if not end_date:
        import pytz as _pytz
        from datetime import datetime as _dt, timedelta as _td
        end_date = (_dt.now(_pytz.timezone('Asia/Tokyo')) - _td(days=1)).strftime('%Y-%m-%d')
    try:
        result = subprocess.run(
            ['python', 'unified_accuracy_tracker.py', start_date, end_date],
            capture_output=True,
            text=True,
            timeout=600
        )
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'start_date': start_date,
            'end_date': end_date,
            'stdout': result.stdout[-6000:] if len(result.stdout) > 6000 else result.stdout,
            'stderr': result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'timeout', 'message': 'Still running (>10min)'}), 202
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/admin/ferry-status-raw')
@require_admin
def admin_ferry_status_raw():
    """Return raw ferry_status_enhanced records for a given date."""
    from flask import request as flask_request
    import sqlite3, os
    target_date = flask_request.args.get('date', '')
    if not target_date:
        import pytz as _pytz
        from datetime import datetime as _dt, timedelta as _td
        target_date = (_dt.now(_pytz.timezone('Asia/Tokyo')) - _td(days=1)).strftime('%Y-%m-%d')
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    real_db = os.path.join(data_dir, 'heartland_ferry_real_data.db')
    try:
        conn = sqlite3.connect(real_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT scrape_date, route, departure_time, operational_status, is_cancelled '
            'FROM ferry_status_enhanced WHERE scrape_date = ? ORDER BY route, departure_time',
            (target_date,)
        ).fetchall()
        conn.close()
        return jsonify({
            'date': target_date,
            'count': len(rows),
            'records': [dict(r) for r in rows]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/run-backfill')
@require_admin
def admin_run_backfill():
    """Admin endpoint to backfill historical actual weather data."""
    import subprocess
    from flask import request as flask_request
    start_date = flask_request.args.get('start', '2025-10-01')
    end_date   = flask_request.args.get('end', '')
    cmd = ['python', 'backfill_actual_weather.py', start_date]
    if end_date:
        cmd.append(end_date)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'stdout': result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout,
            'stderr': result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
            'start_date': start_date,
            'end_date': end_date or 'yesterday',
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'timeout', 'message': 'Backfill is still running (>10min)'}), 202
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/admin/generate-sailing-forecasts')
@require_admin
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
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/init-accuracy-tables')
@require_admin
def admin_init_accuracy_tables():
    """Admin endpoint to initialize accuracy tracking tables via unified_accuracy_tracker."""
    import os
    import subprocess
    from jst_utils import jst_isoformat

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        result = subprocess.run(
            ['python', 'unified_accuracy_tracker.py'],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Check which accuracy tables exist
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
            'status': 'success' if result.returncode == 0 else 'error',
            'tables_created': tables,
            'returncode': result.returncode,
            'stdout': result.stdout[-500:],
            'stderr': result.stderr[-500:],
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/analyze-accuracy')
@require_admin
def admin_analyze_accuracy():
    """Admin endpoint to run accuracy analysis"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run analyze_accuracy.py
        result = subprocess.run(
            ['python', 'analyze_accuracy.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/debug-accuracy-data')
@require_admin
def admin_debug_accuracy_data():
    """Admin endpoint to run debug script"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run debug_accuracy_data.py
        result = subprocess.run(
            ['python', 'debug_accuracy_data.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/test-ferry-db-path')
@require_admin
def admin_test_ferry_db_path():
    """Admin endpoint to test ferry DB path"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run test_ferry_db_path.py
        result = subprocess.run(
            ['python', 'test_ferry_db_path.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/check-route-names')
@require_admin
def admin_check_route_names():
    """Admin endpoint to check route name mappings"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run check_route_names.py
        result = subprocess.run(
            ['python', 'check_route_names.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/check-prediction-count')
@require_admin
def admin_check_prediction_count():
    """Admin endpoint to check prediction counts with/without DISTINCT"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run check_prediction_count.py
        result = subprocess.run(
            ['python', 'check_prediction_count.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/investigate-bad-day')
@require_admin
def admin_investigate_bad_day():
    """Admin endpoint to investigate why certain days had low accuracy"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run investigate_bad_day.py
        result = subprocess.run(
            ['python', 'investigate_bad_day.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/analyze-threshold-accuracy')
@require_admin
def admin_analyze_threshold_accuracy():
    """Admin endpoint to analyze threshold accuracy by weather conditions"""
    import subprocess
    import os

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'

    try:
        # Run analyze_threshold_accuracy.py
        result = subprocess.run(
            ['python', 'analyze_threshold_accuracy.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'returncode': result.returncode,
            'output': result.stdout,
            'errors': result.stderr,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/analyze-monthly')
@require_admin
def admin_analyze_monthly():
    """Admin endpoint to analyze monthly cancellation patterns"""
    try:
        import subprocess, os as _os
        script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'analyze_monthly_cancellations.py')
        result = subprocess.run(
            ['python', script],
            capture_output=True, text=True, timeout=30
        )
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'errors': result.stderr,
            'timestamp': jst_isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/admin/validate-seasonal-fix')
@require_admin
def admin_validate_seasonal_fix():
    """Admin endpoint to validate seasonal adjustment fixes historical errors"""
    try:
        result = subprocess.run(
            ['python', 'validate_seasonal_fix.py'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'errors': result.stderr,
            'returncode': result.returncode,
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'timeout',
            'error': 'Script execution timed out after 30 seconds',
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 504
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'data_directory': data_dir,
            'timestamp': jst_isoformat()
        }), 500

@app.route('/admin/db-coverage')
@require_admin
def admin_db_coverage():
    """Show date coverage of all key tables in both DBs."""
    import os
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    forecast_db  = os.path.join(data_dir, 'ferry_weather_forecast.db')
    realdata_db  = os.path.join(data_dir, 'heartland_ferry_real_data.db')

    result = {}
    try:
        conn = sqlite3.connect(forecast_db)
        cur  = conn.cursor()
        for table, date_col in [
            ('actual_weather',             'date'),
            ('cancellation_forecast',      'forecast_for_date'),
            ('unified_operation_accuracy', 'operation_date'),
        ]:
            try:
                cur.execute(f'''
                    SELECT MIN({date_col}), MAX({date_col}),
                           COUNT(DISTINCT {date_col}), COUNT(*)
                    FROM {table}
                ''')
                row = cur.fetchone()
                result[table] = {
                    'min_date': row[0], 'max_date': row[1],
                    'distinct_days': row[2], 'total_records': row[3]
                }
                if table == 'actual_weather':
                    cur.execute('''
                        SELECT location, MIN(date), MAX(date),
                               COUNT(DISTINCT date), COUNT(*)
                        FROM actual_weather GROUP BY location ORDER BY location
                    ''')
                    result['actual_weather_by_port'] = [
                        {'location': r[0], 'min': r[1], 'max': r[2],
                         'days': r[3], 'records': r[4]}
                        for r in cur.fetchall()
                    ]
            except Exception as e:
                result[table] = {'error': str(e)}
        conn.close()
    except Exception as e:
        result['forecast_db_error'] = str(e)

    try:
        conn = sqlite3.connect(realdata_db)
        cur  = conn.cursor()
        for table, date_col in [
            ('ferry_status_enhanced', 'scrape_date'),
            ('ferry_status',          'scrape_date'),
        ]:
            try:
                cur.execute(f'''
                    SELECT MIN({date_col}), MAX({date_col}),
                           COUNT(DISTINCT {date_col}), COUNT(*)
                    FROM {table}
                ''')
                row = cur.fetchone()
                result[table] = {
                    'min_date': row[0], 'max_date': row[1],
                    'distinct_days': row[2], 'total_records': row[3]
                }
            except Exception as e:
                result[table] = {'error': str(e)}
        conn.close()
    except Exception as e:
        result['realdata_db_error'] = str(e)

    return jsonify(result)


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
    print("\nStarting web server...")
    print("Dashboard URL: http://localhost:5000")
    print("\nPress Ctrl+C to stop\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
