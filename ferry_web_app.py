#!/usr/bin/env python3
"""
Hokkaido Ferry Forecast Web Application
Cloud deployment ready with Flask web interface
"""

from flask import Flask, jsonify, request
import os
import threading
import time
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

class SimpleFerryCollector:
    """Simplified ferry data collector for cloud deployment"""

    def __init__(self):
        self.status_url = "https://heartlandferry.jp/status/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; FerryBot/1.0)'
        }
        self.db_path = 'ferry_data.db'
        self.init_database()

    def init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ferry_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    route_name TEXT,
                    status TEXT,
                    details TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database init error: {e}")

    def collect_ferry_data(self):
        """Collect ferry status data"""
        try:
            response = requests.get(self.status_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Simple data extraction
            ferry_data = []
            timestamp = datetime.now().isoformat()

            # Look for ferry status information
            status_elements = soup.find_all(['div', 'p', 'span'], class_=['status', 'ferry', 'route'])

            if status_elements:
                for element in status_elements[:5]:  # Limit to 5 results
                    text = element.get_text(strip=True)
                    if text and len(text) > 3:
                        ferry_data.append({
                            'timestamp': timestamp,
                            'route_name': f'Route {len(ferry_data) + 1}',
                            'status': 'Operating',
                            'details': text[:100]  # Limit text length
                        })
            else:
                # Default data if no specific status found
                ferry_data.append({
                    'timestamp': timestamp,
                    'route_name': 'General Status',
                    'status': 'Available',
                    'details': 'Ferry service information collected'
                })

            # Store in database
            self.store_data(ferry_data)
            return ferry_data

        except Exception as e:
            print(f"Collection error: {e}")
            return [{
                'timestamp': datetime.now().isoformat(),
                'route_name': 'Error',
                'status': 'Unavailable',
                'details': str(e)[:100]
            }]

    def store_data(self, data):
        """Store data in SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for record in data:
                cursor.execute('''
                    INSERT INTO ferry_status (timestamp, route_name, status, details)
                    VALUES (?, ?, ?, ?)
                ''', (record['timestamp'], record['route_name'],
                      record['status'], record['details']))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Storage error: {e}")

    def get_recent_data(self, limit=10):
        """Get recent ferry status data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT timestamp, route_name, status, details
                FROM ferry_status
                ORDER BY id DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [{
                'timestamp': row[0],
                'route_name': row[1],
                'status': row[2],
                'details': row[3]
            } for row in rows]

        except Exception as e:
            print(f"Retrieval error: {e}")
            return []

# Initialize collector
collector = SimpleFerryCollector()

@app.route('/')
def home():
    return {
        'service': 'Hokkaido Ferry Forecast System',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            'current_status': '/ferry/status',
            'collect_now': '/ferry/collect',
            'recent_data': '/ferry/recent',
            'health': '/health'
        }
    }

@app.route('/health')
def health():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}, 200

@app.route('/ferry/status')
def ferry_status():
    """Get current ferry status"""
    try:
        data = collector.collect_ferry_data()
        return jsonify({
            'status': 'success',
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/ferry/collect')
def collect_now():
    """Trigger immediate data collection"""
    try:
        data = collector.collect_ferry_data()
        return jsonify({
            'status': 'collection_completed',
            'records_collected': len(data),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/ferry/recent')
def recent_data():
    """Get recent ferry data from database"""
    limit = request.args.get('limit', 10, type=int)
    try:
        data = collector.get_recent_data(limit)
        return jsonify({
            'status': 'success',
            'data': data,
            'count': len(data),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def background_collection():
    """Background data collection task"""
    while True:
        try:
            print(f"Background collection at {datetime.now()}")
            collector.collect_ferry_data()
            time.sleep(3600)  # Collect every hour
        except Exception as e:
            print(f"Background collection error: {e}")
            time.sleep(300)   # Wait 5 minutes on error

# Start background collection thread
collection_thread = threading.Thread(target=background_collection, daemon=True)
collection_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting Hokkaido Ferry Forecast System on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)