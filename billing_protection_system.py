#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API Billing Protection System
Comprehensive cost control and usage monitoring
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class APICall:
    """API call tracking"""
    timestamp: datetime
    endpoint: str
    cost: float
    success: bool
    response_size: int
    cache_hit: bool = False

class BillingProtectionSystem:
    """Comprehensive billing protection and usage monitoring"""
    
    def __init__(self):
        self.db_path = Path("api_usage.db")
        self._init_database()
        
        # Cost limits and thresholds
        self.cost_limits = {
            "daily_limit": 0.50,      # $0.50 per day
            "weekly_limit": 2.00,     # $2.00 per week  
            "monthly_limit": 4.50,    # $4.50 per month (under $5 limit)
            "emergency_stop": 4.90    # Emergency stop at $4.90
        }
        
        # API endpoint costs (per FlightAware pricing)
        self.endpoint_costs = {
            "/airports/": 0.0025,           # Airport info
            "/flights/search": 0.005,       # Flight search
            "/flights/": 0.01,              # Flight details
            "/airports/.*/flights/": 0.01,  # Airport departures/arrivals
            "/history/": 0.01               # Historical data
        }
        
        # Rate limiting (requests per time period)
        self.rate_limits = {
            "requests_per_minute": 10,      # Conservative limit
            "requests_per_hour": 100,       # Well below API limits
            "requests_per_day": 500         # Daily safety limit
        }
        
        # Cache settings
        self.cache_duration = {
            "airport_info": timedelta(hours=24),     # Airport info rarely changes
            "flight_search": timedelta(minutes=15),  # Recent flights cache
            "historical": timedelta(hours=6)         # Historical data cache
        }
        
        self.cache = {}
        self.request_history = []
    
    def _init_database(self):
        """Initialize usage tracking database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                endpoint TEXT,
                cost REAL,
                success BOOLEAN,
                response_size INTEGER,
                cache_hit BOOLEAN DEFAULT FALSE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                date TEXT PRIMARY KEY,
                total_calls INTEGER,
                total_cost REAL,
                cached_calls INTEGER,
                failed_calls INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                alert_type TEXT,
                threshold REAL,
                actual_cost REAL,
                action_taken TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def check_call_permission(self, endpoint: str) -> Tuple[bool, str]:
        """Check if API call is permitted based on cost and rate limits"""
        
        # Get current usage
        current_usage = self.get_current_usage()
        
        # Calculate call cost
        call_cost = self._calculate_endpoint_cost(endpoint)
        
        # Check emergency stop
        if current_usage["monthly_cost"] + call_cost >= self.cost_limits["emergency_stop"]:
            self._create_alert("EMERGENCY_STOP", self.cost_limits["emergency_stop"], 
                             current_usage["monthly_cost"] + call_cost)
            return False, f"EMERGENCY STOP: Would exceed ${self.cost_limits['emergency_stop']:.2f} limit"
        
        # Check monthly limit
        if current_usage["monthly_cost"] + call_cost > self.cost_limits["monthly_limit"]:
            self._create_alert("MONTHLY_LIMIT", self.cost_limits["monthly_limit"],
                             current_usage["monthly_cost"] + call_cost)
            return False, f"Monthly limit exceeded: ${self.cost_limits['monthly_limit']:.2f}"
        
        # Check daily limit
        if current_usage["daily_cost"] + call_cost > self.cost_limits["daily_limit"]:
            return False, f"Daily limit exceeded: ${self.cost_limits['daily_limit']:.2f}"
        
        # Check rate limiting
        rate_check = self._check_rate_limits()
        if not rate_check[0]:
            return False, f"Rate limit exceeded: {rate_check[1]}"
        
        return True, "OK"
    
    def _calculate_endpoint_cost(self, endpoint: str) -> float:
        """Calculate cost for specific endpoint"""
        
        for pattern, cost in self.endpoint_costs.items():
            if pattern in endpoint:
                return cost
        
        # Default cost if endpoint not recognized
        return 0.01
    
    def _check_rate_limits(self) -> Tuple[bool, str]:
        """Check rate limiting constraints"""
        
        now = datetime.now()
        
        # Clean old requests
        self.request_history = [
            req_time for req_time in self.request_history
            if now - req_time < timedelta(hours=1)
        ]
        
        # Check minute limit
        minute_ago = now - timedelta(minutes=1)
        recent_requests = [
            req_time for req_time in self.request_history
            if req_time > minute_ago
        ]
        
        if len(recent_requests) >= self.rate_limits["requests_per_minute"]:
            return False, "Too many requests per minute"
        
        # Check hour limit
        hour_ago = now - timedelta(hours=1)
        hourly_requests = [
            req_time for req_time in self.request_history
            if req_time > hour_ago
        ]
        
        if len(hourly_requests) >= self.rate_limits["requests_per_hour"]:
            return False, "Too many requests per hour"
        
        return True, "OK"
    
    def check_cache(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Check if data is available in cache"""
        
        cache_key = self._generate_cache_key(endpoint, params)
        
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            
            # Check if cache is still valid
            cache_age = datetime.now() - cache_entry["timestamp"]
            max_age = self._get_cache_duration(endpoint)
            
            if cache_age < max_age:
                logger.info(f"Cache HIT for {endpoint}")
                return cache_entry["data"]
            else:
                # Remove expired cache
                del self.cache[cache_key]
        
        logger.info(f"Cache MISS for {endpoint}")
        return None
    
    def store_cache(self, endpoint: str, params: Dict, data: Dict):
        """Store data in cache"""
        
        cache_key = self._generate_cache_key(endpoint, params)
        
        self.cache[cache_key] = {
            "timestamp": datetime.now(),
            "data": data
        }
        
        # Limit cache size (remove oldest entries if needed)
        if len(self.cache) > 100:
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]
    
    def _generate_cache_key(self, endpoint: str, params: Dict = None) -> str:
        """Generate cache key for endpoint and parameters"""
        
        if params:
            param_str = json.dumps(sorted(params.items()))
            return f"{endpoint}:{hash(param_str)}"
        return endpoint
    
    def _get_cache_duration(self, endpoint: str) -> timedelta:
        """Get cache duration for endpoint type"""
        
        if "/airports/" in endpoint and "/flights/" not in endpoint:
            return self.cache_duration["airport_info"]
        elif "/history/" in endpoint:
            return self.cache_duration["historical"] 
        else:
            return self.cache_duration["flight_search"]
    
    def record_api_call(self, endpoint: str, cost: float, success: bool, 
                       response_size: int, cache_hit: bool = False):
        """Record API call for usage tracking"""
        
        call = APICall(
            timestamp=datetime.now(),
            endpoint=endpoint,
            cost=cost,
            success=success,
            response_size=response_size,
            cache_hit=cache_hit
        )
        
        # Add to request history for rate limiting
        if not cache_hit:
            self.request_history.append(call.timestamp)
        
        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO api_calls 
            (timestamp, endpoint, cost, success, response_size, cache_hit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            call.timestamp, call.endpoint, call.cost, 
            call.success, call.response_size, call.cache_hit
        ))
        
        conn.commit()
        conn.close()
        
        # Update daily usage summary
        self._update_daily_usage()
        
        logger.info(f"API call recorded: {endpoint} (${cost:.4f}) Cache: {cache_hit}")
    
    def _update_daily_usage(self):
        """Update daily usage summary"""
        
        today = datetime.now().date().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate today's usage
        cursor.execute("""
            SELECT 
                COUNT(*) as total_calls,
                SUM(cost) as total_cost,
                SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cached_calls,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed_calls
            FROM api_calls 
            WHERE DATE(timestamp) = ?
        """, (today,))
        
        result = cursor.fetchone()
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_usage 
            (date, total_calls, total_cost, cached_calls, failed_calls)
            VALUES (?, ?, ?, ?, ?)
        """, (today, result[0], result[1] or 0, result[2], result[3]))
        
        conn.commit()
        conn.close()
    
    def get_current_usage(self) -> Dict:
        """Get current usage statistics"""
        
        now = datetime.now()
        today = now.date().isoformat()
        week_start = (now - timedelta(days=now.weekday())).date().isoformat()
        month_start = now.replace(day=1).date().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Daily usage
        cursor.execute("""
            SELECT COALESCE(SUM(cost), 0) FROM api_calls 
            WHERE DATE(timestamp) = ?
        """, (today,))
        daily_cost = cursor.fetchone()[0]
        
        # Weekly usage
        cursor.execute("""
            SELECT COALESCE(SUM(cost), 0) FROM api_calls 
            WHERE DATE(timestamp) >= ?
        """, (week_start,))
        weekly_cost = cursor.fetchone()[0]
        
        # Monthly usage
        cursor.execute("""
            SELECT COALESCE(SUM(cost), 0) FROM api_calls 
            WHERE DATE(timestamp) >= ?
        """, (month_start,))
        monthly_cost = cursor.fetchone()[0]
        
        # Call counts
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cached
            FROM api_calls 
            WHERE DATE(timestamp) = ?
        """, (today,))
        
        calls_today = cursor.fetchone()
        
        conn.close()
        
        return {
            "daily_cost": daily_cost,
            "weekly_cost": weekly_cost,
            "monthly_cost": monthly_cost,
            "calls_today": calls_today[0],
            "cached_today": calls_today[1],
            "daily_limit_remaining": self.cost_limits["daily_limit"] - daily_cost,
            "monthly_limit_remaining": self.cost_limits["monthly_limit"] - monthly_cost,
            "cache_hit_rate": calls_today[1] / calls_today[0] if calls_today[0] > 0 else 0
        }
    
    def _create_alert(self, alert_type: str, threshold: float, actual_cost: float):
        """Create cost alert"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO cost_alerts 
            (timestamp, alert_type, threshold, actual_cost, action_taken)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.now(), alert_type, threshold, actual_cost,
            "API_BLOCKED" if alert_type == "EMERGENCY_STOP" else "WARNING_SENT"
        ))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"COST ALERT: {alert_type} - Threshold: ${threshold:.2f}, Actual: ${actual_cost:.2f}")
    
    def generate_usage_report(self) -> str:
        """Generate comprehensive usage report"""
        
        usage = self.get_current_usage()
        
        report = f"""
=== FlightAware API Usage Report ===
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

CURRENT USAGE
=============
Daily Cost: ${usage['daily_cost']:.4f} / ${self.cost_limits['daily_limit']:.2f}
Weekly Cost: ${usage['weekly_cost']:.4f} / ${self.cost_limits['weekly_limit']:.2f}
Monthly Cost: ${usage['monthly_cost']:.4f} / ${self.cost_limits['monthly_limit']:.2f}

REMAINING BUDGET
================
Daily: ${usage['daily_limit_remaining']:.4f}
Monthly: ${usage['monthly_limit_remaining']:.4f}

EFFICIENCY METRICS
==================
Calls Today: {usage['calls_today']}
Cache Hit Rate: {usage['cache_hit_rate']:.1%}
Cached Calls: {usage['cached_today']}

SAFETY STATUS
============="""
        
        if usage['monthly_cost'] > self.cost_limits['monthly_limit'] * 0.9:
            report += "\n[WARNING] Approaching monthly limit!"
        elif usage['monthly_cost'] > self.cost_limits['monthly_limit'] * 0.7:
            report += "\n[CAUTION] 70% of monthly budget used"
        else:
            report += "\n[SAFE] Well within budget limits"
        
        if usage['cache_hit_rate'] < 0.3:
            report += "\n[WARNING] LOW CACHE EFFICIENCY: Consider optimizing requests"
        
        return report
    
    def reset_daily_limits(self):
        """Reset daily usage (for testing or manual reset)"""
        
        today = datetime.now().date().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM daily_usage WHERE date = ?", (today,))
        cursor.execute("DELETE FROM api_calls WHERE DATE(timestamp) = ?", (today,))
        
        conn.commit()
        conn.close()
        
        logger.info("Daily usage limits reset")

class ProtectedFlightAwareClient:
    """FlightAware client with built-in billing protection"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.billing_protection = BillingProtectionSystem()
        self.base_url = "https://aeroapi.flightaware.com/aeroapi"
    
    def make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make protected API request with billing controls"""
        
        # Check cache first
        cached_data = self.billing_protection.check_cache(endpoint, params)
        if cached_data:
            self.billing_protection.record_api_call(
                endpoint, 0.0, True, len(str(cached_data)), cache_hit=True
            )
            return cached_data
        
        # Check if call is permitted
        permission, reason = self.billing_protection.check_call_permission(endpoint)
        if not permission:
            logger.error(f"API call blocked: {reason}")
            return None
        
        # Calculate cost
        cost = self.billing_protection._calculate_endpoint_cost(endpoint)
        
        try:
            import requests
            
            headers = {"x-apikey": self.api_key}
            url = f"{self.base_url}{endpoint}"
            
            response = requests.get(url, headers=headers, params=params or {}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Store in cache
                self.billing_protection.store_cache(endpoint, params or {}, data)
                
                # Record successful call
                self.billing_protection.record_api_call(
                    endpoint, cost, True, len(response.content)
                )
                
                return data
            else:
                # Record failed call (no cost charged for failures)
                self.billing_protection.record_api_call(
                    endpoint, 0.0, False, 0
                )
                logger.error(f"API call failed: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            # Record failed call
            self.billing_protection.record_api_call(endpoint, 0.0, False, 0)
            logger.error(f"API request exception: {e}")
            return None

def main():
    """Demonstrate billing protection system"""
    
    print("=== FlightAware API Billing Protection System ===")
    
    protection = BillingProtectionSystem()
    
    # Show current limits
    print(f"\nConfigured Limits:")
    print(f"Daily: ${protection.cost_limits['daily_limit']:.2f}")
    print(f"Weekly: ${protection.cost_limits['weekly_limit']:.2f}")
    print(f"Monthly: ${protection.cost_limits['monthly_limit']:.2f}")
    print(f"Emergency Stop: ${protection.cost_limits['emergency_stop']:.2f}")
    
    # Show current usage
    usage = protection.get_current_usage()
    print(f"\nCurrent Usage:")
    print(f"Today: ${usage['daily_cost']:.4f}")
    print(f"This Month: ${usage['monthly_cost']:.4f}")
    print(f"Remaining Budget: ${usage['monthly_limit_remaining']:.4f}")
    
    # Test permission check
    print(f"\nTesting API Call Permissions:")
    endpoints_to_test = [
        "/airports/RIS",
        "/airports/RIS/flights/departures",
        "/flights/search"
    ]
    
    for endpoint in endpoints_to_test:
        permission, reason = protection.check_call_permission(endpoint)
        status = "[ALLOWED]" if permission else "[BLOCKED]"
        print(f"{endpoint}: {status} - {reason}")
    
    print(f"\n=== Protection Features ===")
    print("[OK] Daily cost limits ($0.50)")
    print("[OK] Monthly cost limits ($4.50)")
    print("[OK] Emergency stop at $4.90")
    print("[OK] Rate limiting (10/min, 100/hour)")
    print("[OK] Intelligent caching system")
    print("[OK] Usage tracking and reporting")
    print("[OK] Automatic call blocking")
    print("[OK] Cache hit optimization")
    
    print(f"\nDatabase: {protection.db_path}")
    print("Billing protection active and monitoring all API calls.")

if __name__ == "__main__":
    main()