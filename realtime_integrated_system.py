#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time Integrated Transport Prediction System
Combines weather APIs, ML models, and transport data for live predictions
"""

import asyncio
import aiohttp
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import logging
import time
import sqlite3
from pathlib import Path

# Import our models
from advanced_ml_models import AdvancedTransportPredictor
from ferry_monitoring_system import FerryMonitoringSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class WeatherData:
    """Current weather data structure"""
    timestamp: datetime
    location: str
    temperature: float
    humidity: float
    wind_speed: float
    wind_direction: int
    visibility: float
    pressure: float
    precipitation: float
    weather_description: str
    
    # Derived/calculated fields
    pressure_tendency: Optional[float] = None
    temperature_change_24h: Optional[float] = None
    wind_gust: Optional[float] = None

@dataclass
class TransportStatus:
    """Transport operation status"""
    transport_type: str  # "ferry" or "flight"
    route: str
    scheduled_time: str
    current_status: str  # "scheduled", "delayed", "cancelled", "operating"
    predicted_status: str
    cancellation_probability: float
    delay_probability: float
    confidence: float
    last_updated: datetime

class RealTimeWeatherAPI:
    """Real-time weather data collection"""
    
    def __init__(self):
        # Multiple weather API endpoints for redundancy
        self.apis = {
            'openweathermap': {
                'base_url': 'https://api.openweathermap.org/data/2.5/weather',
                'key': 'YOUR_OWM_API_KEY',  # Free tier available
                'locations': {
                    'rishiri': {'lat': 45.2421, 'lon': 141.1864},
                    'wakkanai': {'lat': 45.4117, 'lon': 141.6739}
                }
            },
            'weatherapi': {
                'base_url': 'https://api.weatherapi.com/v1/current.json',
                'key': 'YOUR_WEATHER_API_KEY',  # Free tier available
                'locations': {
                    'rishiri': {'q': '45.2421,141.1864'},
                    'wakkanai': {'q': '45.4117,141.6739'}
                }
            }
        }
    
    async def get_current_weather(self, location: str = 'rishiri') -> Optional[WeatherData]:
        """Get current weather data"""
        
        # Try OpenWeatherMap first
        try:
            return await self._get_openweathermap_data(location)
        except Exception as e:
            logger.warning(f"OpenWeatherMap failed: {e}")
        
        # Fallback to WeatherAPI
        try:
            return await self._get_weatherapi_data(location)
        except Exception as e:
            logger.warning(f"WeatherAPI failed: {e}")
        
        # Final fallback - return default/estimated data
        logger.error("All weather APIs failed, using estimated data")
        return self._get_estimated_weather(location)
    
    async def _get_openweathermap_data(self, location: str) -> WeatherData:
        """Get data from OpenWeatherMap API"""
        
        api_config = self.apis['openweathermap']
        location_config = api_config['locations'][location]
        
        params = {
            'lat': location_config['lat'],
            'lon': location_config['lon'],
            'appid': api_config['key'],
            'units': 'metric'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_config['base_url'], params=params) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")
                
                data = await response.json()
                
                return WeatherData(
                    timestamp=datetime.now(),
                    location=location,
                    temperature=data['main']['temp'],
                    humidity=data['main']['humidity'],
                    wind_speed=data['wind'].get('speed', 0) * 1.94384,  # m/s to knots
                    wind_direction=data['wind'].get('deg', 0),
                    visibility=data.get('visibility', 10000),  # meters
                    pressure=data['main']['pressure'],
                    precipitation=data.get('rain', {}).get('1h', 0) + data.get('snow', {}).get('1h', 0),
                    weather_description=data['weather'][0]['description'],
                    wind_gust=data['wind'].get('gust', data['wind'].get('speed', 0)) * 1.94384
                )
    
    async def _get_weatherapi_data(self, location: str) -> WeatherData:
        """Get data from WeatherAPI"""
        
        api_config = self.apis['weatherapi']
        location_config = api_config['locations'][location]
        
        params = {
            'key': api_config['key'],
            'q': location_config['q'],
            'aqi': 'no'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_config['base_url'], params=params) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")
                
                data = await response.json()
                current = data['current']
                
                return WeatherData(
                    timestamp=datetime.now(),
                    location=location,
                    temperature=current['temp_c'],
                    humidity=current['humidity'],
                    wind_speed=current['wind_kph'] * 0.539957,  # kph to knots
                    wind_direction=current['wind_degree'],
                    visibility=current['vis_km'] * 1000,  # km to meters
                    pressure=current['pressure_mb'],
                    precipitation=current['precip_mm'],
                    weather_description=current['condition']['text'],
                    wind_gust=current['gust_kph'] * 0.539957
                )
    
    def _get_estimated_weather(self, location: str) -> WeatherData:
        """Get estimated weather when APIs fail"""
        
        # Return reasonable default values for September in Hokkaido
        return WeatherData(
            timestamp=datetime.now(),
            location=location,
            temperature=18.0,
            humidity=75.0,
            wind_speed=12.0,
            wind_direction=270,
            visibility=8000.0,
            pressure=1015.0,
            precipitation=0.0,
            weather_description="Estimated conditions",
            wind_gust=15.0
        )

class RealTimeTransportSystem:
    """Real-time integrated transport prediction system"""
    
    def __init__(self):
        # System status (initialize first)
        self.system_status = {
            'weather_api': 'unknown',
            'ferry_system': 'unknown', 
            'flight_system': 'unknown',
            'ml_models': 'unknown',
            'last_update': None
        }
        
        self.weather_api = RealTimeWeatherAPI()
        self.ferry_monitor = FerryMonitoringSystem()
        self.ml_predictor = AdvancedTransportPredictor()
        
        # Initialize database for storing historical predictions
        self.db_path = Path("transport_predictions.db")
        self._init_database()
        
        # Load pre-trained models if available
        self._load_models()
        
        # Prediction cache to avoid excessive API calls
        self.prediction_cache = {}
        self.cache_duration = timedelta(minutes=15)
    
    def _init_database(self):
        """Initialize SQLite database for storing predictions"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                location TEXT,
                transport_type TEXT,
                route TEXT,
                scheduled_time TEXT,
                cancellation_probability REAL,
                delay_probability REAL,
                actual_status TEXT,
                weather_data TEXT,
                model_version TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                location TEXT,
                weather_data TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_models(self):
        """Load pre-trained ML models"""
        
        model_file = Path("advanced_transport_models.pkl")
        if model_file.exists():
            try:
                self.ml_predictor.load_models(str(model_file))
                self.system_status['ml_models'] = 'loaded'
                logger.info("Pre-trained models loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load models: {e}")
                self.system_status['ml_models'] = 'training_required'
        else:
            # Train models with synthetic data if no pre-trained models
            logger.info("No pre-trained models found, training with synthetic data...")
            X, y = self.ml_predictor.generate_synthetic_training_data(n_samples=1000)
            self.ml_predictor.train_models(X, y)
            self.ml_predictor.save_models(str(model_file))
            self.system_status['ml_models'] = 'trained'
    
    async def get_real_time_predictions(self) -> List[TransportStatus]:
        """Get real-time transport predictions"""
        
        predictions = []
        
        # Get current weather
        weather_data = await self.weather_api.get_current_weather('rishiri')
        if weather_data:
            self._store_weather_data(weather_data)
            
            # Generate predictions for different transport options
            ferry_predictions = await self._predict_ferry_operations(weather_data)
            flight_predictions = await self._predict_flight_operations(weather_data)
            
            predictions.extend(ferry_predictions)
            predictions.extend(flight_predictions)
        
        # Store predictions in database
        for prediction in predictions:
            self._store_prediction(prediction, weather_data)
        
        self.system_status['last_update'] = datetime.now()
        return predictions
    
    async def _predict_ferry_operations(self, weather: WeatherData) -> List[TransportStatus]:
        """Predict ferry operations"""
        
        predictions = []
        
        ferry_routes = [
            {"route": "稚内-利尻", "times": ["08:00", "13:30", "17:15"]},
            {"route": "稚内-礼文", "times": ["08:30", "14:00", "16:45"]},
            {"route": "利尻-礼文", "times": ["10:00", "15:30"]}
        ]
        
        for route_config in ferry_routes:
            for scheduled_time in route_config["times"]:
                
                # Create features for ML prediction
                features = self._create_ml_features(weather, "ferry", scheduled_time)
                
                # Add missing features for consistency
                features['karman_vortex_risk'] = 0.1  # Low for ferries
                features['terrain_shielding'] = 0.5  # Moderate for marine routes
                
                # Get ML prediction
                ml_result = self.ml_predictor.predict_transport_cancellation(features, 'ensemble')
                
                # Create transport status
                status = TransportStatus(
                    transport_type="ferry",
                    route=route_config["route"],
                    scheduled_time=scheduled_time,
                    current_status="scheduled",  # Would be updated from real ferry API
                    predicted_status="delayed" if ml_result['cancellation_probability'] > 0.3 else "on_time",
                    cancellation_probability=ml_result['cancellation_probability'],
                    delay_probability=ml_result['cancellation_probability'] * 1.2,
                    confidence=ml_result['confidence'] if 'confidence' in ml_result else 0.75,
                    last_updated=datetime.now()
                )
                
                predictions.append(status)
        
        return predictions
    
    async def _predict_flight_operations(self, weather: WeatherData) -> List[TransportStatus]:
        """Predict flight operations"""
        
        predictions = []
        
        flight_routes = [
            {"route": "札幌丘珠-利尻", "times": ["08:30", "14:05", "16:45"]},
            {"route": "新千歳-利尻", "times": ["09:15", "15:30"]}  # Summer only
        ]
        
        for route_config in flight_routes:
            for scheduled_time in route_config["times"]:
                
                # Create features for ML prediction
                features = self._create_ml_features(weather, "flight", scheduled_time)
                
                # Add aviation-specific risk factors
                features['karman_vortex_risk'] = self._calculate_karman_risk(weather)
                features['terrain_shielding'] = 0.3  # Rishiri airport terrain effects
                
                # Get ML prediction
                ml_result = self.ml_predictor.predict_transport_cancellation(features, 'ensemble')
                
                # Create transport status
                status = TransportStatus(
                    transport_type="flight",
                    route=route_config["route"],
                    scheduled_time=scheduled_time,
                    current_status="scheduled",  # Would be updated from FlightAware API
                    predicted_status="cancelled" if ml_result['cancellation_probability'] > 0.5 else "on_time",
                    cancellation_probability=ml_result['cancellation_probability'],
                    delay_probability=ml_result['cancellation_probability'] * 0.8,
                    confidence=ml_result['confidence'] if 'confidence' in ml_result else 0.75,
                    last_updated=datetime.now()
                )
                
                predictions.append(status)
        
        return predictions
    
    def _create_ml_features(self, weather: WeatherData, transport_type: str, scheduled_time: str) -> Dict:
        """Create feature dictionary for ML prediction"""
        
        hour = int(scheduled_time.split(':')[0])
        current_time = datetime.now()
        
        features = {
            'temperature': weather.temperature,
            'humidity': weather.humidity,
            'wind_speed': weather.wind_speed,
            'wind_direction': weather.wind_direction,
            'visibility': weather.visibility,
            'pressure': weather.pressure,
            'precipitation': weather.precipitation,
            'pressure_tendency': weather.pressure_tendency or 0.0,
            'temperature_change_24h': weather.temperature_change_24h or 0.0,
            'wind_gust': weather.wind_gust or weather.wind_speed,
            'sea_temperature': weather.temperature - 3.0,  # Estimated
            'hour': hour,
            'month': current_time.month,
            'day_of_week': current_time.weekday(),
            'season': self._get_season(current_time.month),
            'transport_type': 1 if transport_type == 'flight' else 0,
            'route_type': 1,  # Medium distance
            'departure_time_category': 1 if 10 <= hour <= 16 else 0,  # Afternoon
            'sea_state': min(int(weather.wind_speed / 5), 6),  # Rough sea state calculation
        }
        
        return features
    
    def _calculate_karman_risk(self, weather: WeatherData) -> float:
        """Calculate Karman vortex risk for Mt. Rishiri"""
        
        # Critical wind directions (270-330 degrees from northwest)
        critical_directions = list(range(270, 331))
        
        if weather.wind_direction not in critical_directions:
            return 0.1
        
        # Wind speed based risk
        if weather.wind_speed >= 25:
            return 0.9
        elif weather.wind_speed >= 20:
            return 0.7
        elif weather.wind_speed >= 15:
            return 0.5
        elif weather.wind_speed >= 10:
            return 0.3
        else:
            return 0.1
    
    def _get_season(self, month: int) -> int:
        """Convert month to season number"""
        
        if month in [3, 4, 5]:
            return 1  # Spring
        elif month in [6, 7, 8]:
            return 2  # Summer
        elif month in [9, 10, 11]:
            return 3  # Autumn
        else:
            return 4  # Winter
    
    def _store_weather_data(self, weather: WeatherData):
        """Store weather data in database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO weather_history (timestamp, location, weather_data)
            VALUES (?, ?, ?)
        """, (weather.timestamp, weather.location, json.dumps(asdict(weather), default=str)))
        
        conn.commit()
        conn.close()
    
    def _store_prediction(self, prediction: TransportStatus, weather: WeatherData):
        """Store prediction in database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO predictions (timestamp, location, transport_type, route, 
                                   scheduled_time, cancellation_probability, delay_probability,
                                   actual_status, weather_data, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction.last_updated,
            weather.location,
            prediction.transport_type,
            prediction.route,
            prediction.scheduled_time,
            prediction.cancellation_probability,
            prediction.delay_probability,
            prediction.current_status,
            json.dumps(asdict(weather), default=str),
            "1.0"
        ))
        
        conn.commit()
        conn.close()
    
    async def run_continuous_monitoring(self, interval_minutes: int = 30):
        """Run continuous monitoring and prediction updates"""
        
        logger.info(f"Starting continuous monitoring (interval: {interval_minutes} minutes)")
        
        while True:
            try:
                logger.info("Updating transport predictions...")
                predictions = await self.get_real_time_predictions()
                
                logger.info(f"Generated {len(predictions)} predictions")
                
                # Log high-risk situations
                high_risk_predictions = [p for p in predictions if p.cancellation_probability > 0.5]
                if high_risk_predictions:
                    logger.warning(f"High risk conditions detected for {len(high_risk_predictions)} routes:")
                    for pred in high_risk_predictions:
                        logger.warning(f"  {pred.route} at {pred.scheduled_time}: {pred.cancellation_probability:.1%} risk")
                
                # Wait for next update
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in continuous monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    def get_system_status(self) -> Dict:
        """Get current system status"""
        
        return {
            **self.system_status,
            'database_size': self.db_path.stat().st_size if self.db_path.exists() else 0,
            'cache_entries': len(self.prediction_cache),
            'uptime': datetime.now() - (self.system_status['last_update'] or datetime.now())
        }

async def main():
    """Main real-time system demonstration"""
    
    print("=== Real-time Integrated Transport Prediction System ===")
    
    system = RealTimeTransportSystem()
    
    # Get current predictions
    print("Getting real-time predictions...")
    predictions = await system.get_real_time_predictions()
    
    print(f"\n=== Current Predictions ({len(predictions)} routes) ===")
    
    for pred in predictions:
        risk_level = "🔴 HIGH" if pred.cancellation_probability > 0.5 else "🟡 MEDIUM" if pred.cancellation_probability > 0.3 else "🟢 LOW"
        
        print(f"\n{pred.transport_type.upper()}: {pred.route}")
        print(f"  Time: {pred.scheduled_time}")
        print(f"  Risk: {risk_level} ({pred.cancellation_probability:.1%})")
        print(f"  Status: {pred.predicted_status}")
        print(f"  Confidence: {pred.confidence:.1%}")
    
    # Show system status
    print(f"\n=== System Status ===")
    status = system.get_system_status()
    for key, value in status.items():
        print(f"{key}: {value}")
    
    print("\n=== Continuous Monitoring ===")
    print("Starting continuous monitoring... (Press Ctrl+C to stop)")
    
    try:
        await system.run_continuous_monitoring(interval_minutes=1)  # 1 minute for demo
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")

if __name__ == "__main__":
    asyncio.run(main())