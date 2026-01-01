#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Winter Weather Adaptation System for Hokkaido Transport
Enhanced prediction models for winter-specific conditions
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
import json

@dataclass
class WinterWeatherConditions:
    """Winter-specific weather data structure"""
    temperature: float
    wind_speed: float
    wind_direction: int
    visibility: float
    pressure: float
    precipitation: float
    snow_depth: Optional[float] = None
    snow_rate: Optional[float] = None  # cm/hour
    wind_chill: Optional[float] = None
    blowing_snow: bool = False
    ground_blizzard: bool = False
    ice_accumulation: bool = False
    
    def __post_init__(self):
        """Calculate derived values"""
        if self.wind_chill is None:
            self.wind_chill = self.calculate_wind_chill()
    
    def calculate_wind_chill(self) -> float:
        """Calculate wind chill temperature"""
        if self.temperature >= 10 or self.wind_speed < 4.8:
            return self.temperature
        
        # Wind chill formula (metric)
        v_kmh = self.wind_speed * 1.852  # knots to km/h
        wc = 13.12 + 0.6215 * self.temperature - 11.37 * (v_kmh ** 0.16) + 0.3965 * self.temperature * (v_kmh ** 0.16)
        return wc

class WinterTransportPredictor:
    """Winter-specific transport prediction system"""
    
    def __init__(self):
        # Winter-specific thresholds
        self.winter_thresholds = {
            "ferry": {
                "temperature_critical": -15,  # Celsius
                "wind_speed_critical": 35,    # knots
                "wave_height_critical": 4.0,  # meters
                "ice_formation_temp": -5,     # Ice on deck risk
                "visibility_critical": 500    # meters
            },
            "flight": {
                "temperature_critical": -25,  # Aircraft operating limit
                "wind_speed_critical": 25,    # Crosswind limit
                "snow_rate_critical": 2,      # cm/hour
                "visibility_critical": 800,   # meters
                "ceiling_critical": 200       # feet
            }
        }
        
        # Winter weather patterns for Hokkaido
        self.winter_patterns = {
            "siberian_high": {
                "months": [12, 1, 2],
                "characteristics": "Clear, very cold, strong NW winds",
                "temperature_range": (-20, -5),
                "wind_pattern": "NW 15-30kt",
                "visibility": "Usually good",
                "transport_impact": "High wind, extreme cold"
            },
            "west_coast_snow": {
                "months": [12, 1, 2, 3],
                "characteristics": "Heavy snow from Japan Sea effect",
                "precipitation_type": "Snow",
                "wind_pattern": "W-NW 10-25kt",
                "visibility": "Poor in snow",
                "transport_impact": "Heavy snow, poor visibility"
            },
            "spring_transition": {
                "months": [3, 4],
                "characteristics": "Variable conditions, ice breakup",
                "temperature_range": (-5, 5),
                "wind_pattern": "Variable",
                "visibility": "Variable",
                "transport_impact": "Unpredictable conditions"
            }
        }
    
    def predict_winter_ferry_risk(self, conditions: WinterWeatherConditions, route: str) -> Dict:
        """Predict ferry operations risk in winter conditions"""
        
        risk_factors = []
        risk_score = 0.0
        
        # Extreme cold risk
        if conditions.temperature < self.winter_thresholds["ferry"]["temperature_critical"]:
            risk_score += 0.4
            risk_factors.append(f"Extreme cold ({conditions.temperature:.1f}°C)")
        
        # Wind and wave risk (enhanced in winter)
        if conditions.wind_speed > self.winter_thresholds["ferry"]["wind_speed_critical"]:
            risk_score += 0.6
            risk_factors.append(f"Dangerous winds ({conditions.wind_speed:.1f}kt)")
        elif conditions.wind_speed > 25:
            risk_score += 0.3
            risk_factors.append(f"Strong winds ({conditions.wind_speed:.1f}kt)")
        
        # Sea spray icing risk
        if conditions.temperature < self.winter_thresholds["ferry"]["ice_formation_temp"] and conditions.wind_speed > 20:
            risk_score += 0.5
            risk_factors.append("Sea spray icing risk")
            conditions.ice_accumulation = True
        
        # Blowing snow visibility
        if conditions.snow_rate and conditions.snow_rate > 1 and conditions.wind_speed > 15:
            risk_score += 0.3
            risk_factors.append("Blowing snow reducing visibility")
            conditions.blowing_snow = True
        
        # Low visibility
        if conditions.visibility < self.winter_thresholds["ferry"]["visibility_critical"]:
            risk_score += 0.6
            risk_factors.append(f"Poor visibility ({conditions.visibility}m)")
        elif conditions.visibility < 1000:
            risk_score += 0.2
            risk_factors.append("Reduced visibility")
        
        # Wind chill factor for crew safety
        if conditions.wind_chill < -20:
            risk_score += 0.2
            risk_factors.append(f"Dangerous wind chill ({conditions.wind_chill:.1f}°C)")
        
        # Determine overall risk level
        if risk_score >= 0.7:
            risk_level = "CRITICAL"
            recommendation = "Ferry operations extremely dangerous. Cancellation highly likely."
        elif risk_score >= 0.5:
            risk_level = "HIGH"
            recommendation = "High cancellation risk. Monitor conditions closely."
        elif risk_score >= 0.3:
            risk_level = "MEDIUM"
            recommendation = "Possible delays due to winter conditions."
        else:
            risk_level = "LOW"
            recommendation = "Normal winter operations expected."
        
        return {
            "risk_level": risk_level,
            "risk_score": min(risk_score, 1.0),
            "risk_factors": risk_factors,
            "recommendation": recommendation,
            "winter_specific_hazards": {
                "ice_accumulation": conditions.ice_accumulation,
                "blowing_snow": conditions.blowing_snow,
                "extreme_cold": conditions.temperature < -15,
                "wind_chill_danger": conditions.wind_chill < -20
            }
        }
    
    def predict_winter_flight_risk(self, conditions: WinterWeatherConditions, route: str) -> Dict:
        """Predict flight operations risk in winter conditions"""
        
        risk_factors = []
        risk_score = 0.0
        
        # Aircraft cold weather limits
        if conditions.temperature < self.winter_thresholds["flight"]["temperature_critical"]:
            risk_score += 0.7
            risk_factors.append(f"Aircraft operating limit ({conditions.temperature:.1f}°C)")
        elif conditions.temperature < -15:
            risk_score += 0.3
            risk_factors.append("Cold weather operations")
        
        # Snow rate and accumulation
        if conditions.snow_rate:
            if conditions.snow_rate > self.winter_thresholds["flight"]["snow_rate_critical"]:
                risk_score += 0.6
                risk_factors.append(f"Heavy snow ({conditions.snow_rate:.1f}cm/h)")
            elif conditions.snow_rate > 0.5:
                risk_score += 0.2
                risk_factors.append("Light to moderate snow")
        
        # Runway conditions (estimated)
        if conditions.snow_depth and conditions.snow_depth > 5:
            risk_score += 0.4
            risk_factors.append("Snow accumulation on runway")
        
        # Wind conditions (more critical in winter)
        winter_wind_threshold = self.winter_thresholds["flight"]["wind_speed_critical"] - 5  # Lower threshold in winter
        if conditions.wind_speed > winter_wind_threshold:
            risk_score += 0.5
            risk_factors.append(f"Strong crosswinds ({conditions.wind_speed:.1f}kt)")
        
        # Ground blizzard conditions
        if conditions.wind_speed > 20 and conditions.snow_depth and conditions.snow_depth > 2:
            conditions.ground_blizzard = True
            risk_score += 0.6
            risk_factors.append("Ground blizzard conditions")
        
        # Low visibility in snow
        if conditions.visibility < self.winter_thresholds["flight"]["visibility_critical"]:
            risk_score += 0.7
            risk_factors.append(f"Poor visibility ({conditions.visibility}m)")
        elif conditions.visibility < 1600:
            risk_score += 0.3
            risk_factors.append("Reduced visibility")
        
        # Icing conditions
        if -10 <= conditions.temperature <= 0 and conditions.precipitation > 0:
            risk_score += 0.4
            risk_factors.append("Aircraft icing conditions")
        
        # Mountain wave effects (enhanced in winter)
        if 270 <= conditions.wind_direction <= 330 and conditions.wind_speed > 15:
            risk_score += 0.3
            risk_factors.append("Mountain wave turbulence (winter enhanced)")
        
        # Determine overall risk level
        if risk_score >= 0.8:
            risk_level = "CRITICAL"
            recommendation = "Flight operations extremely dangerous. Cancellation certain."
        elif risk_score >= 0.6:
            risk_level = "HIGH"
            recommendation = "High cancellation risk due to winter weather."
        elif risk_score >= 0.4:
            risk_level = "MEDIUM"
            recommendation = "Possible delays for de-icing and weather."
        else:
            risk_level = "LOW"
            recommendation = "Normal winter flight operations expected."
        
        return {
            "risk_level": risk_level,
            "risk_score": min(risk_score, 1.0),
            "risk_factors": risk_factors,
            "recommendation": recommendation,
            "winter_specific_hazards": {
                "ground_blizzard": conditions.ground_blizzard,
                "aircraft_icing": -10 <= conditions.temperature <= 0 and conditions.precipitation > 0,
                "extreme_cold": conditions.temperature < -20,
                "snow_accumulation": conditions.snow_depth and conditions.snow_depth > 5
            }
        }
    
    def analyze_winter_pattern(self, conditions: WinterWeatherConditions, date: datetime) -> Dict:
        """Analyze current weather pattern against typical winter patterns"""
        
        month = date.month
        
        # Identify most likely pattern
        pattern_scores = {}
        
        for pattern_name, pattern_data in self.winter_patterns.items():
            score = 0
            
            # Month matching
            if month in pattern_data["months"]:
                score += 3
            
            # Temperature matching
            temp_range = pattern_data.get("temperature_range")
            if temp_range and temp_range[0] <= conditions.temperature <= temp_range[1]:
                score += 2
            
            # Wind pattern matching (simplified)
            if "NW" in pattern_data.get("wind_pattern", "") and 270 <= conditions.wind_direction <= 330:
                score += 2
            
            pattern_scores[pattern_name] = score
        
        # Find best matching pattern
        best_pattern = max(pattern_scores, key=pattern_scores.get)
        confidence = pattern_scores[best_pattern] / 7.0  # Normalize
        
        return {
            "identified_pattern": best_pattern,
            "confidence": confidence,
            "pattern_details": self.winter_patterns[best_pattern],
            "all_scores": pattern_scores
        }
    
    def generate_winter_forecast(self, conditions: WinterWeatherConditions, date: datetime) -> Dict:
        """Generate comprehensive winter transport forecast"""
        
        # Analyze weather pattern
        pattern_analysis = self.analyze_winter_pattern(conditions, date)
        
        # Get predictions for both transport types
        ferry_risk = self.predict_winter_ferry_risk(conditions, "wakkanai_rishiri")
        flight_risk = self.predict_winter_flight_risk(conditions, "okadama_rishiri")
        
        # Generate overall assessment
        max_risk_score = max(ferry_risk["risk_score"], flight_risk["risk_score"])
        
        if max_risk_score >= 0.7:
            overall_status = "EXTREME WINTER CONDITIONS"
            overall_color = "[CRITICAL]"
        elif max_risk_score >= 0.5:
            overall_status = "SEVERE WINTER WEATHER"
            overall_color = "[HIGH]"
        elif max_risk_score >= 0.3:
            overall_status = "WINTER WEATHER IMPACT"
            overall_color = "[MEDIUM]"
        else:
            overall_status = "MANAGEABLE WINTER CONDITIONS"
            overall_color = "[LOW]"
        
        # Winter-specific recommendations
        winter_recommendations = []
        
        if conditions.temperature < -15:
            winter_recommendations.append("Extreme cold - minimize outdoor exposure")
        if conditions.wind_chill < -20:
            winter_recommendations.append("Dangerous wind chill - frostbite risk")
        if conditions.blowing_snow or conditions.ground_blizzard:
            winter_recommendations.append("Blizzard conditions - avoid travel")
        if conditions.ice_accumulation:
            winter_recommendations.append("Icing conditions - maritime operations dangerous")
        
        return {
            "forecast_time": datetime.now(),
            "conditions_date": date,
            "overall_status": overall_status,
            "status_indicator": overall_color,
            "weather_pattern": pattern_analysis,
            "ferry_forecast": ferry_risk,
            "flight_forecast": flight_risk,
            "winter_conditions": {
                "temperature": conditions.temperature,
                "wind_chill": conditions.wind_chill,
                "snow_conditions": {
                    "snow_rate": conditions.snow_rate,
                    "snow_depth": conditions.snow_depth,
                    "blowing_snow": conditions.blowing_snow
                },
                "visibility": conditions.visibility,
                "special_hazards": {
                    "ground_blizzard": conditions.ground_blizzard,
                    "ice_accumulation": conditions.ice_accumulation,
                    "extreme_cold": conditions.temperature < -15
                }
            },
            "winter_recommendations": winter_recommendations,
            "seasonal_advice": self._get_seasonal_advice(date.month)
        }
    
    def _get_seasonal_advice(self, month: int) -> List[str]:
        """Get month-specific seasonal advice"""
        
        advice_map = {
            12: [
                "Peak winter season begins - expect frequent disruptions",
                "Sea spray icing becomes major ferry hazard",
                "Daylight hours very limited - affects visual operations"
            ],
            1: [
                "Coldest month - highest transport disruption risk",
                "Blizzard frequency peaks in January",
                "Ice formation on aircraft critical concern"
            ],
            2: [
                "Continued harsh conditions but some improvement",
                "Snow accumulation reaches seasonal maximum",
                "Wind patterns remain predominantly NW"
            ],
            3: [
                "Spring transition begins - highly variable conditions",
                "Ice breakup creates maritime navigation hazards",
                "Temperature swings can cause rapid weather changes"
            ],
            11: [
                "Winter preparations essential",
                "First snow events expected",
                "Begin monitoring winter forecast models"
            ]
        }
        
        return advice_map.get(month, ["Monitor conditions closely for seasonal changes"])

def simulate_winter_scenarios():
    """Simulate various winter weather scenarios"""
    
    predictor = WinterTransportPredictor()
    
    scenarios = {
        "Severe Blizzard": WinterWeatherConditions(
            temperature=-18.0,
            wind_speed=35.0,
            wind_direction=310,
            visibility=200.0,
            pressure=995.0,
            precipitation=0.0,
            snow_depth=25.0,
            snow_rate=3.5,
            blowing_snow=True,
            ground_blizzard=True
        ),
        "Extreme Cold": WinterWeatherConditions(
            temperature=-28.0,
            wind_speed=15.0,
            wind_direction=320,
            visibility=8000.0,
            pressure=1035.0,
            precipitation=0.0,
            snow_depth=10.0,
            snow_rate=0.0
        ),
        "Ice Storm": WinterWeatherConditions(
            temperature=-3.0,
            wind_speed=25.0,
            wind_direction=280,
            visibility=1500.0,
            pressure=1005.0,
            precipitation=2.0,
            snow_depth=5.0,
            snow_rate=0.0,
            ice_accumulation=True
        ),
        "Typical Winter": WinterWeatherConditions(
            temperature=-8.0,
            wind_speed=18.0,
            wind_direction=300,
            visibility=4000.0,
            pressure=1020.0,
            precipitation=0.5,
            snow_depth=15.0,
            snow_rate=0.5
        )
    }
    
    return scenarios, predictor

def main():
    """Demonstrate winter weather system"""
    
    print("=== Hokkaido Winter Weather Transport System ===")
    
    # Simulate winter scenarios
    scenarios, predictor = simulate_winter_scenarios()
    
    for scenario_name, conditions in scenarios.items():
        print(f"\n=== {scenario_name} Scenario ===")
        
        # Generate forecast
        forecast = predictor.generate_winter_forecast(conditions, datetime(2025, 1, 15))
        
        print(f"Overall Status: {forecast['status_indicator']} {forecast['overall_status']}")
        print(f"Weather Pattern: {forecast['weather_pattern']['identified_pattern']} ({forecast['weather_pattern']['confidence']:.1%} confidence)")
        
        print(f"\nConditions:")
        print(f"  Temperature: {conditions.temperature:.1f}°C (feels like {conditions.wind_chill:.1f}°C)")
        print(f"  Wind: {conditions.wind_speed:.1f}kt from {conditions.wind_direction}°")
        print(f"  Visibility: {conditions.visibility}m")
        if conditions.snow_rate:
            print(f"  Snow rate: {conditions.snow_rate:.1f}cm/h")
        
        print(f"\nTransport Risk Assessment:")
        print(f"  Ferry: {forecast['ferry_forecast']['risk_level']} ({forecast['ferry_forecast']['risk_score']:.1%})")
        print(f"  Flight: {forecast['flight_forecast']['risk_level']} ({forecast['flight_forecast']['risk_score']:.1%})")
        
        if forecast['winter_recommendations']:
            print(f"\nWinter Safety:")
            for rec in forecast['winter_recommendations']:
                print(f"  - {rec}")
    
    print("\n=== Winter System Features ===")
    print("[OK] Extreme cold threshold monitoring")
    print("[OK] Wind chill calculations")
    print("[OK] Blizzard condition detection")
    print("[OK] Sea spray icing assessment")
    print("[OK] Ground blizzard prediction")
    print("[OK] Seasonal pattern recognition")
    print("[OK] Winter-specific safety recommendations")

if __name__ == "__main__":
    main()