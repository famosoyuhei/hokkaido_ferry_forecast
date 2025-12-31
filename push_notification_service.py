#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Push Notification Service for Ferry Forecast
Sends notifications for high-risk weather conditions
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict
from pywebpush import webpush, WebPushException
import os

class PushNotificationService:
    """Send push notifications for high-risk forecasts"""

    def __init__(self):
        # Database paths
        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")
        self.subscription_db = os.path.join(data_dir, "push_subscriptions.db")

        # VAPID keys (should be stored securely in production)
        self.vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY')
        self.vapid_public_key = os.environ.get('VAPID_PUBLIC_KEY')
        self.vapid_claims = {
            "sub": "mailto:noreply@ferryfore cast.app"
        }

        # Initialize subscription database
        self.init_subscription_db()

    def init_subscription_db(self):
        """Initialize push subscription database"""

        conn = sqlite3.connect(self.subscription_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                subscribed_at TEXT NOT NULL,
                last_notification_sent TEXT,
                notification_preferences TEXT DEFAULT '{"risk_levels": ["HIGH", "MEDIUM"]}'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER,
                notification_type TEXT,
                title TEXT,
                body TEXT,
                sent_at TEXT,
                success BOOLEAN,
                error_message TEXT
            )
        ''')

        conn.commit()
        conn.close()
        print("[OK] Push subscription database initialized")

    def save_subscription(self, subscription: Dict) -> bool:
        """Save push subscription from client"""

        try:
            conn = sqlite3.connect(self.subscription_db)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO push_subscriptions (
                    endpoint, p256dh, auth, subscribed_at
                ) VALUES (?, ?, ?, ?)
            ''', (
                subscription['endpoint'],
                subscription['keys']['p256dh'],
                subscription['keys']['auth'],
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            print(f"[OK] Saved subscription: {subscription['endpoint'][:50]}...")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to save subscription: {e}")
            return False

    def get_active_subscriptions(self) -> List[Dict]:
        """Get all active push subscriptions"""

        conn = sqlite3.connect(self.subscription_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, endpoint, p256dh, auth, notification_preferences
            FROM push_subscriptions
        ''')

        subscriptions = []
        for row in cursor.fetchall():
            sub_id, endpoint, p256dh, auth, prefs = row
            subscriptions.append({
                'id': sub_id,
                'endpoint': endpoint,
                'keys': {
                    'p256dh': p256dh,
                    'auth': auth
                },
                'preferences': json.loads(prefs) if prefs else {}
            })

        conn.close()
        return subscriptions

    def check_high_risk_tomorrow(self) -> Dict:
        """Check if tomorrow has high risk forecast"""

        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(DISTINCT route) as high_risk_routes,
                MAX(risk_score) as max_risk_score,
                GROUP_CONCAT(DISTINCT route) as routes
            FROM cancellation_forecast
            WHERE forecast_for_date = ?
            AND risk_level = 'HIGH'
        ''', (tomorrow,))

        row = cursor.fetchone()
        conn.close()

        if row and row[0] > 0:
            return {
                'has_high_risk': True,
                'date': tomorrow,
                'high_risk_routes': row[0],
                'max_risk_score': row[1],
                'routes': row[2].split(',') if row[2] else []
            }

        return {'has_high_risk': False}

    def send_notification(self, subscription: Dict, title: str, body: str, url: str = '/') -> bool:
        """Send push notification to a subscription"""

        if not self.vapid_private_key or not self.vapid_public_key:
            print("[WARNING] VAPID keys not configured, skipping push notification")
            return False

        try:
            subscription_info = {
                'endpoint': subscription['endpoint'],
                'keys': subscription['keys']
            }

            notification_data = json.dumps({
                'title': title,
                'body': body,
                'url': url
            })

            webpush(
                subscription_info=subscription_info,
                data=notification_data,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )

            # Log success
            self._log_notification(
                subscription['id'],
                'high_risk_alert',
                title,
                body,
                True,
                None
            )

            print(f"[OK] Sent notification to {subscription['endpoint'][:50]}...")
            return True

        except WebPushException as e:
            print(f"[ERROR] WebPush failed: {e}")

            # Remove subscription if it's no longer valid
            if e.response and e.response.status_code in [404, 410]:
                self._remove_subscription(subscription['id'])
                print(f"[INFO] Removed invalid subscription")

            self._log_notification(
                subscription['id'],
                'high_risk_alert',
                title,
                body,
                False,
                str(e)
            )

            return False

        except Exception as e:
            print(f"[ERROR] Notification failed: {e}")
            self._log_notification(
                subscription['id'],
                'high_risk_alert',
                title,
                body,
                False,
                str(e)
            )
            return False

    def _log_notification(self, subscription_id: int, notification_type: str,
                         title: str, body: str, success: bool, error_message: str = None):
        """Log notification send attempt"""

        try:
            conn = sqlite3.connect(self.subscription_db)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO notification_log (
                    subscription_id, notification_type, title, body,
                    sent_at, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                subscription_id,
                notification_type,
                title,
                body,
                datetime.now().isoformat(),
                success,
                error_message
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"[WARNING] Failed to log notification: {e}")

    def _remove_subscription(self, subscription_id: int):
        """Remove invalid subscription"""

        try:
            conn = sqlite3.connect(self.subscription_db)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM push_subscriptions WHERE id = ?', (subscription_id,))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"[WARNING] Failed to remove subscription: {e}")

    def send_high_risk_alerts(self):
        """Check for high risk and send notifications"""

        print("\n" + "=" * 80)
        print("HIGH RISK ALERT CHECK")
        print("=" * 80)

        # Check tomorrow's forecast
        risk_info = self.check_high_risk_tomorrow()

        if not risk_info['has_high_risk']:
            print("\n[INFO] No high risk forecast for tomorrow")
            print("=" * 80)
            return

        print(f"\n⚠️ HIGH RISK detected for {risk_info['date']}")
        print(f"   Routes affected: {risk_info['high_risk_routes']}")
        print(f"   Max risk score: {risk_info['max_risk_score']:.1f}/100")

        # Get subscriptions
        subscriptions = self.get_active_subscriptions()

        if not subscriptions:
            print("\n[INFO] No active subscriptions")
            print("=" * 80)
            return

        print(f"\n[INFO] Sending notifications to {len(subscriptions)} subscribers...")

        # Send notifications
        success_count = 0
        for subscription in subscriptions:
            # Check user preferences
            prefs = subscription.get('preferences', {})
            risk_levels = prefs.get('risk_levels', ['HIGH', 'MEDIUM'])

            if 'HIGH' not in risk_levels:
                continue

            title = '🚢 フェリー欠航警報'
            body = f'明日 {risk_info["date"]} は高リスクです。{risk_info["high_risk_routes"]}航路で欠航の可能性があります。'

            if self.send_notification(subscription, title, body):
                success_count += 1

        print(f"\n[OK] Sent {success_count}/{len(subscriptions)} notifications")
        print("=" * 80)

def main():
    """Main execution"""

    service = PushNotificationService()

    # Send high risk alerts
    service.send_high_risk_alerts()

if __name__ == '__main__':
    main()
