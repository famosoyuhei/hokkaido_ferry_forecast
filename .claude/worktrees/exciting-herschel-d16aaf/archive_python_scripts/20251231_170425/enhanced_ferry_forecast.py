#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Ferry Forecast System with Seasonal Timetables
Integrates real-time status data with seasonal schedules for accurate predictions
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
import requests

class EnhancedFerryForecast:
    """Enhanced ferry forecast system with seasonal timetable integration"""
    
    def __init__(self):
        self.timetable_db = "ferry_timetable_data.db"
        self.status_db = "heartland_ferry_real_data.db"
        
        # Weather conditions impact mapping
        self.weather_impact = {
            'Strong Wind': {'cancel_prob': 0.8, 'delay_prob': 0.15},
            'Rain': {'cancel_prob': 0.2, 'delay_prob': 0.3},
            'Snow': {'cancel_prob': 0.3, 'delay_prob': 0.4},
            'Fog': {'cancel_prob': 0.1, 'delay_prob': 0.2},
            'Partly Cloudy': {'cancel_prob': 0.02, 'delay_prob': 0.05},
            'Cloudy': {'cancel_prob': 0.03, 'delay_prob': 0.08},
            'Clear': {'cancel_prob': 0.01, 'delay_prob': 0.03}
        }
    
    def get_current_season_schedule(self, target_date=None):
        """Get current season's ferry schedule from timetable system"""
        
        if target_date is None:
            target_date = datetime.now().date()
        
        try:
            conn = sqlite3.connect(self.timetable_db)
            cursor = conn.cursor()
            
            # Get current season info
            cursor.execute('''
                SELECT active_season, routes_available, total_daily_sailings
                FROM current_season_cache 
                ORDER BY last_updated DESC 
                LIMIT 1
            ''')
            
            cache_info = cursor.fetchone()
            
            if cache_info:
                season_name = cache_info[0]
                routes = json.loads(cache_info[1]) if cache_info[1] else []
                total_sailings = cache_info[2]
                
                # Get detailed schedules for current season
                cursor.execute('''
                    SELECT route, departure_time, arrival_time, via_port, frequency_per_day
                    FROM seasonal_schedules 
                    WHERE season_name = ?
                    ORDER BY route, departure_time
                ''', (season_name,))
                
                schedules = cursor.fetchall()
                
                conn.close()
                
                return {
                    'season': season_name,
                    'date': target_date.isoformat(),
                    'total_daily_sailings': total_sailings,
                    'schedules': schedules
                }
            else:
                conn.close()
                return self._default_schedule()
                
        except Exception as e:
            print(f"[WARNING] Could not load timetable data: {e}")
            return self._default_schedule()
    
    def _default_schedule(self):
        """Default schedule when timetable data is unavailable"""
        return {
            'season': 'Default',
            'date': datetime.now().date().isoformat(),
            'total_daily_sailings': 8,
            'schedules': [
                ('Wakkanai-Rishiri', '08:00', '10:00', '', 4),
                ('Rishiri-Wakkanai', '09:45', '11:45', '', 4),
                ('Wakkanai-Rebun', '08:30', '10:30', '', 4),
                ('Rebun-Wakkanai', '10:15', '12:15', '', 4),
                ('Rishiri-Rebun', '10:00', '11:00', '', 4),
                ('Rebun-Rishiri', '11:30', '12:30', '', 4)
            ]
        }
    
    def get_recent_operational_history(self, days=7):
        """Get recent operational history from status database"""
        
        try:
            conn = sqlite3.connect(self.status_db)
            cursor = conn.cursor()
            
            # Get recent operational data
            cursor.execute('''
                SELECT scrape_date, route, operational_status, is_cancelled, is_delayed
                FROM ferry_status 
                WHERE scrape_date >= date('now', '-{} days')
                ORDER BY scrape_date DESC, route
            '''.format(days))
            
            history = cursor.fetchall()
            
            # Calculate recent statistics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(is_cancelled) as cancelled,
                    SUM(is_delayed) as delayed
                FROM ferry_status 
                WHERE scrape_date >= date('now', '-{} days')
            '''.format(days))
            
            stats = cursor.fetchone()
            conn.close()
            
            if stats and stats[0] > 0:
                total, cancelled, delayed = stats
                return {
                    'history': history,
                    'total_operations': total,
                    'cancelled_operations': cancelled,
                    'delayed_operations': delayed,
                    'cancellation_rate': (cancelled / total) * 100,
                    'delay_rate': (delayed / total) * 100
                }
            else:
                return self._default_history()
                
        except Exception as e:
            print(f"[WARNING] Could not load operational history: {e}")
            return self._default_history()
    
    def _default_history(self):
        """Default operational history when data is unavailable"""
        return {
            'history': [],
            'total_operations': 0,
            'cancelled_operations': 0,
            'delayed_operations': 0,
            'cancellation_rate': 15.0,  # Conservative estimate
            'delay_rate': 10.0
        }
    
    def predict_ferry_operations(self, target_date=None, weather_condition='Partly Cloudy'):
        """Enhanced ferry operation prediction with seasonal schedules"""
        
        if target_date is None:
            target_date = datetime.now().date()
        
        # Get current season's schedule
        current_schedule = self.get_current_season_schedule(target_date)
        
        # Get operational history
        operational_history = self.get_recent_operational_history()
        
        # Weather impact factors
        weather_factors = self.weather_impact.get(weather_condition, 
                                                 self.weather_impact['Partly Cloudy'])
        
        # Historical performance adjustment
        historical_cancel_rate = operational_history['cancellation_rate'] / 100
        historical_delay_rate = operational_history['delay_rate'] / 100
        
        # Generate predictions for each scheduled route
        predictions = []
        
        for route, departure, arrival, via_port, frequency in current_schedule['schedules']:
            # Base risk calculation
            cancel_risk = min(0.9, weather_factors['cancel_prob'] + (historical_cancel_rate * 0.3))
            delay_risk = min(0.8, weather_factors['delay_prob'] + (historical_delay_rate * 0.3))
            
            # Route-specific adjustments
            if 'Rebun' in route and weather_condition == 'Strong Wind':
                cancel_risk *= 1.2  # Inter-island routes more affected by wind
            
            if 'via' in via_port.lower():
                delay_risk *= 1.1  # Via routes have higher delay risk
            
            # Risk level classification
            if cancel_risk > 0.6:
                risk_level = "HIGH"
            elif cancel_risk > 0.3 or delay_risk > 0.4:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            predictions.append({
                'route': route,
                'departure_time': departure,
                'arrival_time': arrival,
                'via_port': via_port,
                'risk_level': risk_level,
                'cancel_probability': cancel_risk * 100,
                'delay_probability': delay_risk * 100,
                'weather_condition': weather_condition,
                'season': current_schedule['season']
            })
        
        return {
            'forecast_date': target_date.isoformat(),
            'season': current_schedule['season'],
            'weather_condition': weather_condition,
            'total_scheduled_services': len(predictions),
            'predictions': predictions,
            'overall_risk_summary': self._calculate_overall_risk(predictions)
        }
    
    def _calculate_overall_risk(self, predictions):
        """Calculate overall risk summary"""
        
        high_risk = sum(1 for p in predictions if p['risk_level'] == 'HIGH')
        medium_risk = sum(1 for p in predictions if p['risk_level'] == 'MEDIUM')
        low_risk = sum(1 for p in predictions if p['risk_level'] == 'LOW')
        
        if high_risk > len(predictions) * 0.5:
            overall_status = "HIGH RISK - Multiple cancellations expected"
        elif high_risk > 0 or medium_risk > len(predictions) * 0.3:
            overall_status = "MEDIUM RISK - Some delays/cancellations possible"
        else:
            overall_status = "LOW RISK - Normal operations expected"
        
        return {
            'overall_status': overall_status,
            'high_risk_routes': high_risk,
            'medium_risk_routes': medium_risk,
            'low_risk_routes': low_risk,
            'recommended_routes': [p['route'] for p in predictions if p['risk_level'] == 'LOW']
        }
    
    def generate_daily_forecast_report(self, target_date=None, weather_condition='Partly Cloudy'):
        """Generate comprehensive daily forecast report"""
        
        if target_date is None:
            target_date = datetime.now().date()
        
        forecast = self.predict_ferry_operations(target_date, weather_condition)
        
        print("=" * 70)
        print("ENHANCED FERRY FORECAST REPORT")
        print("=" * 70)
        print(f"Date: {forecast['forecast_date']}")
        print(f"Season: {forecast['season']}")
        print(f"Weather: {forecast['weather_condition']}")
        print(f"Total Scheduled Services: {forecast['total_scheduled_services']}")
        print()
        
        print("OVERALL STATUS:")
        print(f"  {forecast['overall_risk_summary']['overall_status']}")
        print(f"  High Risk: {forecast['overall_risk_summary']['high_risk_routes']} routes")
        print(f"  Medium Risk: {forecast['overall_risk_summary']['medium_risk_routes']} routes")
        print(f"  Low Risk: {forecast['overall_risk_summary']['low_risk_routes']} routes")
        print()
        
        print("ROUTE PREDICTIONS:")
        for pred in forecast['predictions']:
            risk_indicator = {
                'HIGH': '[HIGH RISK]',
                'MEDIUM': '[MED RISK] ',
                'LOW': '[LOW RISK] '
            }[pred['risk_level']]
            
            print(f"{risk_indicator} {pred['route']} {pred['departure_time']}-{pred['arrival_time']}")
            print(f"            Cancel: {pred['cancel_probability']:.1f}%, Delay: {pred['delay_probability']:.1f}%")
            if pred['via_port']:
                print(f"            Via: {pred['via_port']}")
        
        print()
        
        if forecast['overall_risk_summary']['recommended_routes']:
            print("RECOMMENDED ROUTES:")
            for route in forecast['overall_risk_summary']['recommended_routes']:
                print(f"  • {route}")
        else:
            print("TRAVEL ADVISORY: Consider alternative transport or delay travel")
        
        print()
        print("=" * 70)
        
        return forecast

def main():
    """Main execution for enhanced ferry forecast"""
    
    print("ENHANCED FERRY FORECAST WITH SEASONAL TIMETABLES")
    print()
    
    forecast_system = EnhancedFerryForecast()
    
    # Generate forecast for different weather conditions
    weather_scenarios = ['Clear', 'Partly Cloudy', 'Rain', 'Strong Wind', 'Fog']
    
    for weather in weather_scenarios:
        print(f"\n{'='*50}")
        print(f"SCENARIO: {weather} Weather")
        print('='*50)
        
        forecast = forecast_system.generate_daily_forecast_report(weather_condition=weather)
        
        # Brief summary
        summary = forecast['overall_risk_summary']
        print(f"Summary: {summary['overall_status']}")
        if summary['recommended_routes']:
            print(f"Best options: {', '.join(summary['recommended_routes'][:2])}")
        print()

if __name__ == "__main__":
    main()