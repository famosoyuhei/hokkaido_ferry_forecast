#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferry Cancellation Notification Service
Sends alerts for high-risk days via multiple channels
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests

class NotificationService:
    """Multi-channel notification service for ferry cancellation alerts"""

    def __init__(self):
        self.db_file = "ferry_weather_forecast.db"

        # Notification channels configuration
        self.channels = {
            'discord': {
                'enabled': os.getenv('DISCORD_WEBHOOK_URL') is not None,
                'webhook_url': os.getenv('DISCORD_WEBHOOK_URL'),
                'name': 'Discord'
            },
            'line': {
                'enabled': os.getenv('LINE_NOTIFY_TOKEN') is not None,
                'token': os.getenv('LINE_NOTIFY_TOKEN'),
                'name': 'LINE Notify'
            },
            'slack': {
                'enabled': os.getenv('SLACK_WEBHOOK_URL') is not None,
                'webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
                'name': 'Slack'
            }
        }

        # Risk level emojis
        self.risk_emojis = {
            'HIGH': '🔴',
            'MEDIUM': '🟡',
            'LOW': '🟢',
            'MINIMAL': '⚪'
        }

    def get_high_risk_days(self, days_ahead: int = 7) -> List[Dict]:
        """Get high and medium risk days from forecast"""

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        end_date = (datetime.now() + timedelta(days=days_ahead)).date().isoformat()

        cursor.execute('''
            SELECT DISTINCT
                forecast_for_date,
                risk_level,
                AVG(risk_score) as avg_risk_score,
                AVG(wind_forecast) as avg_wind,
                AVG(wave_forecast) as avg_wave,
                AVG(visibility_forecast) as avg_vis,
                COUNT(DISTINCT route) as affected_routes,
                MIN(recommended_action) as action
            FROM cancellation_forecast
            WHERE forecast_for_date >= date('now')
            AND forecast_for_date <= ?
            AND risk_level IN ('HIGH', 'MEDIUM')
            GROUP BY forecast_for_date, risk_level
            ORDER BY forecast_for_date, avg_risk_score DESC
        ''', (end_date,))

        high_risk_days = []
        for row in cursor.fetchall():
            date, level, score, wind, wave, vis, routes, action = row
            high_risk_days.append({
                'date': date,
                'risk_level': level,
                'risk_score': score,
                'wind_speed': wind,
                'wave_height': wave,
                'visibility': vis,
                'affected_routes': routes,
                'recommended_action': action
            })

        conn.close()
        return high_risk_days

    def format_alert_message(self, high_risk_days: List[Dict]) -> str:
        """Format alert message for notifications"""

        if not high_risk_days:
            return None

        # Header
        message = "🚢 **フェリー欠航リスク警報**\n"
        message += f"発報時刻: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

        # Count by risk level
        high_count = sum(1 for d in high_risk_days if d['risk_level'] == 'HIGH')
        medium_count = sum(1 for d in high_risk_days if d['risk_level'] == 'MEDIUM')

        message += f"⚠️ 警戒が必要な日: **{len(high_risk_days)}日**\n"
        if high_count > 0:
            message += f"  🔴 高リスク: {high_count}日\n"
        if medium_count > 0:
            message += f"  🟡 中リスク: {medium_count}日\n"
        message += "\n"

        # Details for each high-risk day
        message += "📅 **詳細情報:**\n"
        for day in high_risk_days[:5]:  # Limit to top 5
            emoji = self.risk_emojis.get(day['risk_level'], '⚠️')

            message += f"\n{emoji} **{day['date']}** - {day['risk_level']}\n"
            message += f"  リスクスコア: {day['risk_score']:.0f}/100\n"
            message += f"  風速: {day['wind_speed']:.1f} m/s"

            if day['wave_height']:
                message += f" | 波高: {day['wave_height']:.1f} m"

            if day['visibility']:
                message += f" | 視界: {day['visibility']:.1f} km"

            message += f"\n  影響航路: {day['affected_routes']}航路\n"

        # Footer
        message += "\n💡 **推奨事項:**\n"
        if high_count > 0:
            message += "- 🔴高リスク日は旅行を避けるか、代替日を検討してください\n"
        if medium_count > 0:
            message += "- 🟡中リスク日は最新の気象情報を確認してください\n"

        message += "\n詳細: https://heartlandferry.jp/status/"

        return message

    def send_discord(self, message: str) -> bool:
        """Send notification via Discord webhook"""

        if not self.channels['discord']['enabled']:
            print("[INFO] Discord webhook not configured")
            return False

        webhook_url = self.channels['discord']['webhook_url']

        try:
            payload = {
                "content": message,
                "username": "Ferry Alert Bot",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/3774/3774278.png"
            }

            response = requests.post(webhook_url, json=payload, timeout=10)

            if response.status_code == 204:
                print("[OK] Discord notification sent successfully")
                return True
            else:
                print(f"[WARNING] Discord returned status {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] Discord notification failed: {e}")
            return False

    def send_line(self, message: str) -> bool:
        """Send notification via LINE Notify"""

        if not self.channels['line']['enabled']:
            print("[INFO] LINE Notify token not configured")
            return False

        token = self.channels['line']['token']
        url = "https://notify-api.line.me/api/notify"

        try:
            headers = {
                "Authorization": f"Bearer {token}"
            }

            # LINE Notify doesn't support markdown, convert to plain text
            plain_message = message.replace('**', '').replace('*', '')

            payload = {
                "message": plain_message
            }

            response = requests.post(url, headers=headers, data=payload, timeout=10)

            if response.status_code == 200:
                print("[OK] LINE notification sent successfully")
                return True
            else:
                print(f"[WARNING] LINE returned status {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] LINE notification failed: {e}")
            return False

    def send_slack(self, message: str) -> bool:
        """Send notification via Slack webhook"""

        if not self.channels['slack']['enabled']:
            print("[INFO] Slack webhook not configured")
            return False

        webhook_url = self.channels['slack']['webhook_url']

        try:
            # Convert markdown format for Slack
            slack_message = message.replace('**', '*')

            payload = {
                "text": slack_message,
                "username": "Ferry Alert Bot",
                "icon_emoji": ":ferry:"
            }

            response = requests.post(webhook_url, json=payload, timeout=10)

            if response.status_code == 200:
                print("[OK] Slack notification sent successfully")
                return True
            else:
                print(f"[WARNING] Slack returned status {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] Slack notification failed: {e}")
            return False

    def send_console(self, message: str) -> bool:
        """Print notification to console (always enabled)"""

        print("\n" + "=" * 80)
        print("NOTIFICATION MESSAGE")
        print("=" * 80)
        print(message)
        print("=" * 80 + "\n")
        return True

    def send_notifications(self, message: str) -> Dict[str, bool]:
        """Send notifications via all enabled channels"""

        if not message:
            print("[INFO] No message to send")
            return {}

        results = {}

        # Always send to console
        results['console'] = self.send_console(message)

        # Try each configured channel
        if self.channels['discord']['enabled']:
            results['discord'] = self.send_discord(message)

        if self.channels['line']['enabled']:
            results['line'] = self.send_line(message)

        if self.channels['slack']['enabled']:
            results['slack'] = self.send_slack(message)

        return results

    def check_and_notify(self) -> bool:
        """Check for high-risk days and send notifications"""

        print("=" * 80)
        print("FERRY CANCELLATION NOTIFICATION CHECK")
        print(f"Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Get high-risk days
        high_risk_days = self.get_high_risk_days(days_ahead=7)

        if not high_risk_days:
            print("\n✅ No high or medium risk days in the next 7 days")
            print("   All days show favorable conditions for ferry operations.\n")
            return False

        print(f"\n⚠️  Found {len(high_risk_days)} days with elevated risk:")
        for day in high_risk_days:
            emoji = self.risk_emojis.get(day['risk_level'], '⚠️')
            print(f"  {emoji} {day['date']}: {day['risk_level']} (Score: {day['risk_score']:.0f})")

        # Format and send notifications
        message = self.format_alert_message(high_risk_days)

        if message:
            print("\n[INFO] Sending notifications...")
            results = self.send_notifications(message)

            # Report results
            print("\n[INFO] Notification results:")
            for channel, success in results.items():
                status = "✅ Sent" if success else "❌ Failed"
                print(f"  {channel.capitalize()}: {status}")

            success_count = sum(1 for v in results.values() if v)
            print(f"\n[OK] Notifications sent successfully: {success_count}/{len(results)} channels")

            return True

        return False

def main():
    """Main execution"""

    service = NotificationService()

    # Check and send notifications
    notifications_sent = service.check_and_notify()

    if notifications_sent:
        print("\n✅ Notification process completed")
    else:
        print("\n✅ No notifications needed")

    return 0

if __name__ == "__main__":
    exit(main())
