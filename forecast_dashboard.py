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
from jst_utils import (
    now_jst, today_jst_str, jst_isoformat, days_from_today_jst,
    get_timetable_sailings, get_active_routes_on,
)

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

        # Get forecast for next 7 days — 最新収集分のみ使用（古い予報を除外）
        # forecast_for_date × route ごとに MAX(id) = 最新レコードだけを集計する。
        # 旧実装は全過去レコードを AVG していたため、数日前の高風速予報が混入して
        # 実際には穏やかな日でも HIGH と誤表示されるバグがあった。
        cursor.execute('''
            SELECT
                cf.forecast_for_date as date,
                cf.risk_level,
                AVG(cf.risk_score)          as avg_risk,
                AVG(cf.wind_forecast)       as wind,
                AVG(cf.wave_forecast)       as wave,
                AVG(cf.visibility_forecast) as visibility,
                AVG(cf.temperature_forecast) as temp,
                COUNT(DISTINCT cf.route)    as routes
            FROM cancellation_forecast cf
            INNER JOIN (
                SELECT forecast_for_date, route, MAX(id) as max_id
                FROM cancellation_forecast
                WHERE forecast_for_date >= ? AND forecast_for_date <= ?
                GROUP BY forecast_for_date, route
            ) latest
              ON cf.id = latest.max_id
            GROUP BY cf.forecast_for_date, cf.risk_level
            ORDER BY cf.forecast_for_date, avg_risk DESC
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

        # 最新収集分（MAX(id)）のみ使用。旧実装は risk_score DESC で最高リスク記録を
        # 優先していたため、過去の高リスク予報が残り続けて誤表示されていた。
        cursor.execute('''
            SELECT route, risk_level, risk_score,
                   wind_forecast, wave_forecast,
                   visibility_forecast, recommended_action
            FROM cancellation_forecast
            WHERE forecast_for_date = ?
              AND id IN (
                  SELECT MAX(id)
                  FROM cancellation_forecast
                  WHERE forecast_for_date = ?
                  GROUP BY route
              )
            ORDER BY risk_score DESC
        ''', (date, date))

        routes = []
        for row in cursor.fetchall():
            route, risk, score, wind, wave, vis, action = row

            # Route name mapping（存在する全航路 + 廃止済み誤キーは除外）
            BANNED_ROUTES = {'wakkanai_kutsugata', 'kutsugata_wakkanai'}
            route_names = {
                'wakkanai_oshidomari': '稚内 → 鴛泊（利尻）',
                'wakkanai_kafuka':     '稚内 → 香深（礼文）',
                'oshidomari_wakkanai': '鴛泊（利尻）→ 稚内',
                'kafuka_wakkanai':     '香深（礼文）→ 稚内',
                'oshidomari_kafuka':   '鴛泊（利尻）→ 香深（礼文）',
                'kafuka_oshidomari':   '香深（礼文）→ 鴛泊（利尻）',
                'kutsugata_kafuka':    '沓形（利尻）→ 香深（礼文）',  # 夏季 6/1〜9/30
                'kafuka_kutsugata':    '香深（礼文）→ 沓形（利尻）',  # 夏季 6/1〜9/30
            }
            if route in BANNED_ROUTES:
                continue  # 存在しない航路キーは除外

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
        """Get next upcoming sailing for each route (timetable-based, no sailing_forecast needed)"""
        from datetime import datetime, timedelta
        import pytz

        # Use JST timezone
        jst = pytz.timezone('Asia/Tokyo')
        current_datetime = datetime.now(jst)
        current_date = current_datetime.date().isoformat()
        current_time = current_datetime.strftime('%H:%M')
        tomorrow_date = (current_datetime + timedelta(days=1)).date().isoformat()

        # Route name mapping（全8航路 + 夏季沓形便）
        route_names = {
            'wakkanai_oshidomari': '稚内 → 鴛泊（利尻）',
            'wakkanai_kafuka':     '稚内 → 香深（礼文）',
            'oshidomari_wakkanai': '鴛泊（利尻）→ 稚内',
            'kafuka_wakkanai':     '香深（礼文）→ 稚内',
            'oshidomari_kafuka':   '鴛泊（利尻）→ 香深（礼文）',
            'kafuka_oshidomari':   '香深（礼文）→ 鴛泊（利尻）',
            'kutsugata_kafuka':    '沓形（利尻）→ 香深（礼文）',
            'kafuka_kutsugata':    '香深（礼文）→ 沓形（利尻）',
        }

        # リスクデータを今日・明日分まとめて取得
        today_risks = _get_risks_for_date(self.db_file, current_date)
        tomorrow_risks = _get_risks_for_date(self.db_file, tomorrow_date)

        next_sailings = []

        for route in route_names.keys():
            # 今日の残り便（現在時刻より後）を探す
            today_timetable = get_timetable_sailings(route, current_date)
            found = None

            for dep, arr in today_timetable:
                if dep > current_time:
                    found = (current_date, dep, arr, today_risks)
                    break

            # 今日に該当がなければ明日の最初の便
            if not found:
                tomorrow_timetable = get_timetable_sailings(route, tomorrow_date)
                if tomorrow_timetable:
                    dep, arr = tomorrow_timetable[0]
                    found = (tomorrow_date, dep, arr, tomorrow_risks)

            if found:
                date, departure, arrival, risks_dict = found
                risk_info = risks_dict.get(route, {
                    'risk_level': 'MINIMAL', 'risk_score': 0,
                    'wind': None, 'wave': None, 'visibility': None,
                })

                is_today = (date == current_date)
                timing_label = f"本日 {departure}発" if is_today else f"明日 {departure}発"

                next_sailings.append({
                    'route': route,
                    'route_name': route_names.get(route, route),
                    'date': date,
                    'departure_time': departure,
                    'arrival_time': arrival,
                    'timing_label': timing_label,
                    'risk_level': risk_info['risk_level'],
                    'risk_score': risk_info['risk_score'],
                    'wind': risk_info['wind'],
                    'wave': risk_info['wave'],
                    'visibility': risk_info['visibility'],
                    'action': None,
                })

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

        # High risk days count — 最新レコード（MAX(id) per route）のみを対象とする
        cursor.execute('''
            SELECT COUNT(DISTINCT forecast_for_date)
            FROM cancellation_forecast
            WHERE risk_level = 'HIGH'
              AND forecast_for_date >= ?
              AND id IN (
                  SELECT MAX(id)
                  FROM cancellation_forecast
                  WHERE forecast_for_date >= ?
                  GROUP BY forecast_for_date, route
              )
        ''', (today_jst_str(), today_jst_str()))
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

    # Route name mapping（全8航路 + 夏季沓形便）
    ROUTE_NAMES = {
        'wakkanai_oshidomari': '稚内 ⇔ 利尻(鴛泊)',
        'wakkanai_kafuka':     '稚内 ⇔ 礼文(香深)',
        'oshidomari_wakkanai': '利尻(鴛泊) ⇔ 稚内',
        'oshidomari_kafuka':   '利尻(鴛泊) ⇔ 礼文(香深)',
        'kafuka_wakkanai':     '礼文(香深) ⇔ 稚内',
        'kafuka_oshidomari':   '礼文(香深) ⇔ 利尻(鴛泊)',
        'kutsugata_kafuka':    '利尻(沓形) ⇔ 礼文(香深)',
        'kafuka_kutsugata':    '礼文(香深) ⇔ 利尻(沓形)',
    }

    route_name = ROUTE_NAMES.get(route_id, route_id)

    # 時刻表 + cancellation_forecast で7日分のデータを構築
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    db_file = os.path.join(data_dir, 'ferry_weather_forecast.db')

    risk_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'MINIMAL': 1}
    all_days = []

    for i in range(7):
        target_date = days_from_today_jst(i)
        timetable = get_timetable_sailings(route_id, target_date)
        risks = _get_risks_for_date(db_file, target_date)
        risk_info = risks.get(route_id, {
            'risk_level': 'MINIMAL', 'risk_score': 0,
            'wind': None, 'wave': None, 'visibility': None,
        })

        sailings = []
        max_risk = 'MINIMAL'
        for dep, arr in timetable:
            sailings.append({
                'departure': dep,
                'arrival': arr,
                'risk_level': risk_info['risk_level'],
                'risk_score': risk_info['risk_score'],
                'wind': risk_info['wind'],
                'wave': risk_info['wave'],
                'visibility': risk_info['visibility'],
                'temperature': None,
                'recommended_action': None,
            })
            if risk_priority.get(risk_info['risk_level'], 0) > risk_priority.get(max_risk, 0):
                max_risk = risk_info['risk_level']

        all_days.append({
            'date': target_date,
            'weekday': datetime.fromisoformat(target_date).strftime('%a'),
            'sailings': sailings,
            'max_risk': max_risk,
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

    # Route name mapping（全8航路 + 夏季沓形便）
    ROUTE_NAMES = {
        'wakkanai_oshidomari': '稚内 ⇔ 利尻(鴛泊)',
        'wakkanai_kafuka':     '稚内 ⇔ 礼文(香深)',
        'oshidomari_wakkanai': '利尻(鴛泊) ⇔ 稚内',
        'oshidomari_kafuka':   '利尻(鴛泊) ⇔ 礼文(香深)',
        'kafuka_wakkanai':     '礼文(香深) ⇔ 稚内',
        'kafuka_oshidomari':   '礼文(香深) ⇔ 利尻(鴛泊)',
        'kutsugata_kafuka':    '利尻(沓形) ⇔ 礼文(香深)',
        'kafuka_kutsugata':    '礼文(香深) ⇔ 利尻(沓形)',
    }

    route_name = ROUTE_NAMES.get(route_id, route_id)

    # 時刻表から到着時刻を確認
    timetable = get_timetable_sailings(route_id, date)
    arrival_time = None
    for dep, arr in timetable:
        if dep == departure_time:
            arrival_time = arr
            break

    if arrival_time is None:
        return "Sailing not found", 404

    # リスクデータを cancellation_forecast から取得
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    db_file = os.path.join(data_dir, 'ferry_weather_forecast.db')
    risks = _get_risks_for_date(db_file, date)
    risk_info = risks.get(route_id, {
        'risk_level': 'MINIMAL', 'risk_score': 0,
        'wind': None, 'wave': None, 'visibility': None,
    })

    sailing = {
        'date': date,
        'departure': departure_time,
        'arrival': arrival_time,
        'risk_level': risk_info['risk_level'],
        'risk_score': risk_info['risk_score'],
        'wind': risk_info['wind'],
        'wave': risk_info['wave'],
        'visibility': risk_info['visibility'],
        'temperature': None,
        'risk_factors': None,
        'recommended_action': None,
    }

    return render_template('sailing_detail.html',
                         route_name=route_name,
                         route_id=route_id,
                         sailing=sailing)

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    return jsonify(dashboard.get_statistics())


@app.route('/api/db-health')
def api_db_health():
    """
    公開DBヘルスサマリー（認証不要）。
    system_review.py がローカル実行時に本番DBの鮮度を確認するために使用する。
    機密情報は含まない（日付・件数のみ）。
    """
    import os
    data_dir = (
        os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
        or os.environ.get('RAILWAY_VOLUME_MOUNT')
        or '.'
    )
    forecast_db  = os.path.join(data_dir, 'ferry_weather_forecast.db')
    realdata_db  = os.path.join(data_dir, 'heartland_ferry_real_data.db')

    result = {'checked_at': now_jst().isoformat()}

    def _safe_query(db_path, sql, params=()):
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute(sql, params).fetchone()
            conn.close()
            return row
        except Exception as e:
            return None

    # actual_weather
    row = _safe_query(forecast_db, 'SELECT MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(*) FROM actual_weather')
    result['actual_weather'] = {
        'min_date': row[0], 'max_date': row[1],
        'distinct_days': row[2], 'total_records': row[3],
    } if row else {'error': 'table not found'}

    # cancellation_forecast
    row = _safe_query(forecast_db,
        'SELECT MIN(forecast_for_date), MAX(forecast_for_date), COUNT(DISTINCT forecast_for_date), COUNT(*) FROM cancellation_forecast')
    result['cancellation_forecast'] = {
        'min_date': row[0], 'max_date': row[1],
        'distinct_days': row[2], 'total_records': row[3],
    } if row else {'error': 'table not found'}

    # forecast_collection_log 最終成功
    row = _safe_query(forecast_db,
        "SELECT timestamp FROM forecast_collection_log WHERE status='SUCCESS' ORDER BY timestamp DESC LIMIT 1")
    result['last_forecast_collection'] = row[0] if row else None

    # ferry_status_enhanced
    row = _safe_query(realdata_db, 'SELECT MIN(scrape_date), MAX(scrape_date), COUNT(DISTINCT scrape_date), COUNT(*) FROM ferry_status_enhanced')
    result['ferry_status_enhanced'] = {
        'min_date': row[0], 'max_date': row[1],
        'distinct_days': row[2], 'total_records': row[3],
    } if row else {'error': 'table not found'}

    return jsonify(result)


# ---------------------------------------------------------------------------
# 時刻表は jst_utils.get_timetable_sailings() / get_active_routes_on() を使う。
# 正ソース: skills/ferry-cancellation-research/references/heartland_{year}_timetable.json
# 年が変わったら heartland_{year}_timetable.json を追加するだけでよい。
# ---------------------------------------------------------------------------


def _get_risks_for_date(db_file: str, date_str: str) -> dict:
    """cancellation_forecast から指定日の航路別最新リスクを返す。{route: {...}}"""
    risks = {}
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT route, risk_level, risk_score, wind_forecast, wave_forecast, visibility_forecast
            FROM cancellation_forecast
            WHERE forecast_for_date = ?
              AND id IN (
                  SELECT MAX(id) FROM cancellation_forecast
                  WHERE forecast_for_date = ?
                  GROUP BY route
              )
        ''', (date_str, date_str))
        for row in cursor.fetchall():
            route, risk, score, wind, wave, vis = row
            risks[route] = {
                'risk_level': risk or 'MINIMAL',
                'risk_score': score or 0,
                'wind': wind,
                'wave': wave,
                'visibility': vis,
            }
        conn.close()
    except Exception as e:
        print(f'[api/sailings] DB error for {date_str}: {e}')
    return risks


@app.route('/api/sailings')
def api_sailings():
    """
    時刻表ベースの便別予報 API。
    sailing_forecast テーブルではなく 2026年公式時刻表 + cancellation_forecast を使用。
    """
    import os
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or os.environ.get('RAILWAY_VOLUME_MOUNT') or '.'
    db_file = os.path.join(data_dir, 'ferry_weather_forecast.db')

    date_str = request.args.get('date', now_jst().strftime('%Y-%m-%d'))

    risks = _get_risks_for_date(db_file, date_str)

    sailings = []
    for route in get_active_routes_on(date_str):
        timetable = get_timetable_sailings(route, date_str)
        risk_info = risks.get(route, {
            'risk_level': 'MINIMAL', 'risk_score': 0,
            'wind': None, 'wave': None, 'visibility': None,
        })
        for dep, arr in timetable:
            sailings.append({
                'date': date_str,
                'route': route,
                'departure': dep,
                'arrival': arr,
                'risk_level': risk_info['risk_level'],
                'risk_score': risk_info['risk_score'],
                'wind': risk_info['wind'],
                'wave': risk_info['wave'],
                'visibility': risk_info['visibility'],
                'temperature': None,
                'risk_factors': None,
                'recommended_action': None,
            })

    sailings.sort(key=lambda s: (s['route'], s['departure']))
    return jsonify({
        'date': date_str,
        'total_sailings': len(sailings),
        'sailings': sailings,
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
            capture_output=True, text=True, timeout=270
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
            if 'LIKELY DOCK MAINTENANCE' in line.upper():
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


# ---------------------------------------------------------------------------
# LINE Messaging API webhook + 管理エンドポイント
# ---------------------------------------------------------------------------

try:
    from line_bot_service import get_service as _get_line_service
    from linebot.v3.exceptions import InvalidSignatureError as _LineInvalidSig
    _LINE_AVAILABLE = True
except ImportError:
    _LINE_AVAILABLE = False
    _LineInvalidSig = Exception


@app.route('/webhook/line', methods=['POST'])
def line_webhook():
    """LINE Messaging API webhook endpoint."""
    if not _LINE_AVAILABLE:
        return 'LINE SDK not installed', 503

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    line = _get_line_service()
    if not line.enabled:
        return 'LINE bot not configured', 503

    try:
        events = line.verify_and_parse(body, signature)
        line.handle_events(events)
    except _LineInvalidSig:
        return 'Invalid signature', 400
    except Exception as e:
        print(f'LINE webhook error: {e}')
        return 'Internal error', 500

    return 'OK'


@app.route('/admin/line-stats')
@require_admin
def admin_line_stats():
    """LINE Bot の登録ユーザー数・有効/無効状態を返す。"""
    if not _LINE_AVAILABLE:
        return jsonify({'error': 'line-bot-sdk not installed'}), 503
    stats = _get_line_service().get_stats()
    return jsonify(stats)


@app.route('/admin/send-line-test')
@require_admin
def admin_send_line_test():
    """手動で LINE 朝通知をテスト送信する（管理者用）。"""
    if not _LINE_AVAILABLE:
        return jsonify({'error': 'line-bot-sdk not installed'}), 503
    result = _get_line_service().send_morning_notifications()
    return jsonify(result)


@app.route('/admin/run-ui-monitor')
@require_admin
def admin_run_ui_monitor():
    """UI監査AI社員（ui_monitor.py）を実行し、ダッシュボードの健全性をチェックする。"""
    import subprocess, sys, os
    try:
        # sys.executable を使って同じ Python インタープリタで実行する
        # (python コマンドが Python 2 にマップされる環境でも正しく動く)
        script_path = os.path.join(os.path.dirname(__file__), 'ui_monitor.py')
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=60
        )
        all_ok = result.returncode == 0
        return jsonify({
            'status': 'success' if all_ok else 'issues_found',
            'all_ok': all_ok,
            'returncode': result.returncode,
            'stdout': result.stdout[-3000:],
            'stderr': result.stderr[-500:],
            'timestamp': jst_isoformat(),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/admin/run-line-audit')
@require_admin
def admin_run_line_audit():
    """LINE連携監査AI社員（line_audit.py）を実行し、LINE統合の健全性をチェックする。"""
    import subprocess
    try:
        result = subprocess.run(
            ['python', 'line_audit.py'],
            capture_output=True, text=True, timeout=60
        )
        all_ok = result.returncode == 0
        return jsonify({
            'status': 'success' if all_ok else 'issues_found',
            'all_ok': all_ok,
            'returncode': result.returncode,
            'stdout': result.stdout[-3000:],
            'stderr': result.stderr[-500:],
            'timestamp': jst_isoformat(),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


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
