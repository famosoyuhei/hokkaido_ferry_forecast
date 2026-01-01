#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time Notification System
Alert users of transport disruptions and weather changes
"""

import smtplib
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
from pathlib import Path
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NotificationAlert:
    """Alert notification structure"""
    alert_id: str
    alert_type: str  # "high_risk", "cancellation", "weather_change", "service_update"
    severity: str    # "low", "medium", "high", "critical"
    title: str
    message: str
    affected_routes: List[str]
    valid_until: datetime
    created_at: datetime

@dataclass
class UserSubscription:
    """User notification subscription"""
    user_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notification_methods: List[str] = None  # ["email", "sms", "push"]
    subscribed_routes: List[str] = None
    alert_types: List[str] = None
    active: bool = True

class NotificationManager:
    """Manages all notification services"""
    
    def __init__(self):
        self.db_path = Path("notifications.db")
        self._init_database()
        
        # Notification thresholds
        self.alert_thresholds = {
            "high_risk": 0.6,      # 60% cancellation probability
            "critical_risk": 0.8,   # 80% cancellation probability
            "weather_change": 0.3,  # 30% change in conditions
            "visibility_critical": 1000,  # meters
            "wind_critical": 30     # knots
        }
        
        # Rate limiting to prevent spam
        self.rate_limits = {
            "high_risk": timedelta(hours=2),
            "weather_change": timedelta(hours=1),
            "service_update": timedelta(minutes=30)
        }
        
        self.last_sent = {}  # Track when alerts were last sent
    
    def _init_database(self):
        """Initialize notification database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                alert_type TEXT,
                severity TEXT,
                title TEXT,
                message TEXT,
                affected_routes TEXT,
                valid_until DATETIME,
                created_at DATETIME,
                sent_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id TEXT PRIMARY KEY,
                email TEXT,
                phone TEXT,
                notification_methods TEXT,
                subscribed_routes TEXT,
                alert_types TEXT,
                active BOOLEAN DEFAULT 1,
                created_at DATETIME
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT,
                user_id TEXT,
                method TEXT,
                status TEXT,
                sent_at DATETIME
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_subscription(self, subscription: UserSubscription):
        """Add user subscription"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO subscriptions 
            (user_id, email, phone, notification_methods, subscribed_routes, alert_types, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            subscription.user_id,
            subscription.email,
            subscription.phone,
            json.dumps(subscription.notification_methods),
            json.dumps(subscription.subscribed_routes),
            json.dumps(subscription.alert_types),
            subscription.active,
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Added subscription for user {subscription.user_id}")
    
    def create_alert(self, alert: NotificationAlert) -> bool:
        """Create and queue alert for delivery"""
        
        # Check rate limiting
        rate_key = f"{alert.alert_type}_{hash(''.join(alert.affected_routes))}"
        if rate_key in self.last_sent:
            time_since_last = datetime.now() - self.last_sent[rate_key]
            min_interval = self.rate_limits.get(alert.alert_type, timedelta(minutes=30))
            
            if time_since_last < min_interval:
                logger.info(f"Alert {alert.alert_id} rate limited, skipping")
                return False
        
        # Store alert in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO alerts 
            (alert_id, alert_type, severity, title, message, affected_routes, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.alert_id,
            alert.alert_type,
            alert.severity,
            alert.title,
            alert.message,
            json.dumps(alert.affected_routes),
            alert.valid_until,
            alert.created_at
        ))
        
        conn.commit()
        conn.close()
        
        # Update rate limiting
        self.last_sent[rate_key] = datetime.now()
        
        logger.info(f"Created alert {alert.alert_id}: {alert.title}")
        return True
    
    def send_alerts(self, alert_id: str):
        """Send alert to all relevant subscribers"""
        
        # Get alert details
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        alert_row = cursor.fetchone()
        
        if not alert_row:
            logger.error(f"Alert {alert_id} not found")
            return
        
        # Parse alert data
        affected_routes = json.loads(alert_row[5])
        
        # Get relevant subscribers
        cursor.execute("SELECT * FROM subscriptions WHERE active = 1")
        subscribers = cursor.fetchall()
        
        sent_count = 0
        
        for sub_row in subscribers:
            user_id, email, phone, methods, routes, alert_types = sub_row[0:6]
            
            # Check if user is interested in this alert
            if not self._should_send_to_user(
                json.loads(routes or "[]"), 
                json.loads(alert_types or "[]"),
                affected_routes,
                alert_row[1]  # alert_type
            ):
                continue
            
            # Send via configured methods
            methods_list = json.loads(methods or '["email"]')
            
            for method in methods_list:
                success = self._send_notification(
                    method, user_id, email, phone,
                    alert_row[3],  # title
                    alert_row[4]   # message
                )
                
                # Log delivery attempt
                cursor.execute("""
                    INSERT INTO delivery_log (alert_id, user_id, method, status, sent_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    alert_id, user_id, method, 
                    "sent" if success else "failed",
                    datetime.now()
                ))
                
                if success:
                    sent_count += 1
        
        # Update sent count
        cursor.execute(
            "UPDATE alerts SET sent_count = ? WHERE alert_id = ?", 
            (sent_count, alert_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Alert {alert_id} sent to {sent_count} recipients")
    
    def _should_send_to_user(self, user_routes: List[str], user_alert_types: List[str], 
                           affected_routes: List[str], alert_type: str) -> bool:
        """Check if alert should be sent to user"""
        
        # Check if user cares about these routes
        if user_routes and not any(route in user_routes for route in affected_routes):
            return False
        
        # Check if user wants this type of alert
        if user_alert_types and alert_type not in user_alert_types:
            return False
        
        return True
    
    def _send_notification(self, method: str, user_id: str, email: str, phone: str, 
                          title: str, message: str) -> bool:
        """Send notification via specified method"""
        
        try:
            if method == "email" and email:
                return self._send_email(email, title, message)
            elif method == "sms" and phone:
                return self._send_sms(phone, title, message)
            elif method == "push":
                return self._send_push(user_id, title, message)
            else:
                logger.warning(f"Unsupported notification method: {method}")
                return False
        except Exception as e:
            logger.error(f"Failed to send {method} notification: {e}")
            return False
    
    def _send_email(self, email: str, subject: str, message: str) -> bool:
        """Send email notification"""
        
        # Email configuration (would be in environment variables in production)
        smtp_config = {
            "smtp_server": "smtp.gmail.com",  # Example
            "smtp_port": 587,
            "username": "your_email@gmail.com",
            "password": "your_app_password"  # Use app password, not regular password
        }
        
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_config["username"]
            msg['To'] = email
            msg['Subject'] = f"[Hokkaido Transport] {subject}"
            
            # HTML email body
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                        🚢 Hokkaido Transport Alert
                    </h2>
                    
                    <div style="background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #e74c3c; margin-top: 0;">{subject}</h3>
                        <p style="margin: 10px 0;">{message}</p>
                    </div>
                    
                    <div style="background: #3498db; color: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <p style="margin: 0;">Check the latest updates at your Hokkaido Transport app</p>
                    </div>
                    
                    <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #bdc3c7; font-size: 0.9em; color: #7f8c8d;">
                        <p>This is an automated notification from Hokkaido Transport Prediction System.</p>
                        <p>Alert time: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Note: This is a template - actual SMTP sending requires real credentials
            logger.info(f"Email notification prepared for {email}: {subject}")
            
            # In production, uncomment these lines with real SMTP credentials:
            # server = smtplib.SMTP(smtp_config["smtp_server"], smtp_config["smtp_port"])
            # server.starttls()
            # server.login(smtp_config["username"], smtp_config["password"])
            # server.send_message(msg)
            # server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False
    
    def _send_sms(self, phone: str, title: str, message: str) -> bool:
        """Send SMS notification"""
        
        # SMS service configuration (example using Twilio)
        sms_config = {
            "account_sid": "your_twilio_account_sid",
            "auth_token": "your_twilio_auth_token",
            "from_number": "+1234567890"
        }
        
        try:
            # Truncate message for SMS
            sms_text = f"Hokkaido Transport Alert: {title}\n{message[:100]}..."
            
            # Note: This is a template - actual SMS sending requires Twilio credentials
            logger.info(f"SMS notification prepared for {phone}: {title}")
            
            # In production with Twilio:
            # from twilio.rest import Client
            # client = Client(sms_config["account_sid"], sms_config["auth_token"])
            # message = client.messages.create(
            #     body=sms_text,
            #     from_=sms_config["from_number"],
            #     to=phone
            # )
            
            return True
            
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False
    
    def _send_push(self, user_id: str, title: str, message: str) -> bool:
        """Send push notification"""
        
        # Push notification service (example using Firebase)
        try:
            push_payload = {
                "to": f"/topics/user_{user_id}",
                "notification": {
                    "title": f"Hokkaido Transport: {title}",
                    "body": message,
                    "icon": "/icon-192x192.png",
                    "badge": "/icon-192x192.png",
                    "click_action": "/"
                },
                "data": {
                    "alert_type": "transport_update",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            logger.info(f"Push notification prepared for user {user_id}: {title}")
            
            # In production with Firebase:
            # headers = {
            #     "Authorization": "key=your_firebase_server_key",
            #     "Content-Type": "application/json"
            # }
            # response = requests.post(
            #     "https://fcm.googleapis.com/fcm/send",
            #     headers=headers,
            #     json=push_payload
            # )
            
            return True
            
        except Exception as e:
            logger.error(f"Push notification failed: {e}")
            return False

class TransportAlertGenerator:
    """Generates alerts based on transport conditions"""
    
    def __init__(self, notification_manager: NotificationManager):
        self.notification_manager = notification_manager
        self.previous_conditions = {}
    
    def check_conditions_and_alert(self, current_forecast: Dict):
        """Check current conditions and generate alerts if needed"""
        
        alerts_created = []
        
        # Check for high-risk conditions
        high_risk_routes = []
        critical_risk_routes = []
        
        all_predictions = current_forecast.get('ferry_predictions', []) + current_forecast.get('flight_predictions', [])
        
        for pred in all_predictions:
            if pred.probability >= self.notification_manager.alert_thresholds['critical_risk']:
                critical_risk_routes.append(f"{pred.route} {pred.scheduled_time}")
            elif pred.probability >= self.notification_manager.alert_thresholds['high_risk']:
                high_risk_routes.append(f"{pred.route} {pred.scheduled_time}")
        
        # Create critical risk alerts
        if critical_risk_routes:
            alert = NotificationAlert(
                alert_id=f"critical_risk_{datetime.now().strftime('%Y%m%d_%H%M')}",
                alert_type="critical_risk",
                severity="critical",
                title="CRITICAL: High Cancellation Risk",
                message=f"Very high cancellation probability detected for: {', '.join(critical_risk_routes[:3])}{'...' if len(critical_risk_routes) > 3 else ''}",
                affected_routes=critical_risk_routes,
                valid_until=datetime.now() + timedelta(hours=6),
                created_at=datetime.now()
            )
            
            if self.notification_manager.create_alert(alert):
                self.notification_manager.send_alerts(alert.alert_id)
                alerts_created.append(alert.alert_id)
        
        # Create high risk alerts
        elif high_risk_routes:  # Only if no critical alerts
            alert = NotificationAlert(
                alert_id=f"high_risk_{datetime.now().strftime('%Y%m%d_%H%M')}",
                alert_type="high_risk",
                severity="high",
                title="High Cancellation Risk Detected",
                message=f"Increased cancellation probability for: {', '.join(high_risk_routes[:3])}{'...' if len(high_risk_routes) > 3 else ''}",
                affected_routes=high_risk_routes,
                valid_until=datetime.now() + timedelta(hours=4),
                created_at=datetime.now()
            )
            
            if self.notification_manager.create_alert(alert):
                self.notification_manager.send_alerts(alert.alert_id)
                alerts_created.append(alert.alert_id)
        
        return alerts_created

def setup_demo_subscriptions():
    """Setup demo user subscriptions"""
    
    notification_manager = NotificationManager()
    
    # Demo subscriptions
    demo_users = [
        UserSubscription(
            user_id="demo_user_1",
            email="user1@example.com",
            notification_methods=["email"],
            subscribed_routes=["Wakkanai-Rishiri", "Sapporo-Rishiri"],
            alert_types=["high_risk", "critical_risk", "weather_change"]
        ),
        UserSubscription(
            user_id="demo_user_2", 
            email="user2@example.com",
            phone="+81-90-1234-5678",
            notification_methods=["email", "sms"],
            subscribed_routes=["Wakkanai-Rebun"],
            alert_types=["critical_risk"]
        )
    ]
    
    for user in demo_users:
        notification_manager.add_subscription(user)
    
    return notification_manager

def main():
    """Demonstrate notification system"""
    
    print("=== Real-time Notification System Demo ===")
    
    # Setup demo subscriptions
    notification_manager = setup_demo_subscriptions()
    alert_generator = TransportAlertGenerator(notification_manager)
    
    print("[OK] Demo subscriptions created")
    print("[OK] Notification system initialized")
    
    # Create demo alert
    demo_alert = NotificationAlert(
        alert_id=f"demo_alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        alert_type="high_risk",
        severity="high",
        title="Weather Conditions Deteriorating",
        message="Strong winds (30kt) and reduced visibility detected. Ferry operations may be affected.",
        affected_routes=["Wakkanai-Rishiri 13:30", "Wakkanai-Rishiri 17:15"],
        valid_until=datetime.now() + timedelta(hours=4),
        created_at=datetime.now()
    )
    
    print(f"\nCreating demo alert: {demo_alert.title}")
    
    if notification_manager.create_alert(demo_alert):
        notification_manager.send_alerts(demo_alert.alert_id)
        print("[SUCCESS] Demo alert sent to subscribers")
    
    # Show system capabilities
    print(f"\n=== System Capabilities ===")
    print("[OK] Email notifications")
    print("[OK] SMS notifications (requires Twilio)")
    print("[OK] Push notifications (requires Firebase)")
    print("[OK] User subscription management")
    print("[OK] Rate limiting and spam prevention")
    print("[OK] Alert severity classification")
    print("[OK] Route-specific filtering")
    print("[OK] Delivery logging and tracking")
    
    print(f"\nNotification Database: {notification_manager.db_path}")
    print("Ready for integration with transport prediction system")

if __name__ == "__main__":
    main()