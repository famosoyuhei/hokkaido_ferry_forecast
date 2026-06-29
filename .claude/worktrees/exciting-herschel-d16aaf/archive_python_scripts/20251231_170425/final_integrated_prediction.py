#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final Integrated Transport Prediction System
Simplified, stable version combining ferry and flight predictions
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import json
from dataclasses import dataclass

# Use our initial prediction models
from initial_flight_prediction_model import InitialFlightPredictor, FlightPredictionInput

@dataclass
class TransportSummary:
    """Transport prediction summary"""
    transport_type: str
    route: str
    scheduled_time: str
    cancellation_risk: str  # "LOW", "MEDIUM", "HIGH"
    probability: float
    primary_factor: str
    recommendation: str

class FinalIntegratedSystem:
    """Final integrated transport prediction system"""
    
    def __init__(self):
        self.flight_predictor = InitialFlightPredictor()
        
        # Current weather conditions (would be from API in production)
        self.current_weather = {
            "temperature": 18.0,
            "humidity": 75.0,
            "wind_speed": 12.0,
            "wind_direction": 280,
            "visibility": 6000.0,
            "pressure": 1012.0,
            "precipitation": 0.5,
            "timestamp": datetime.now()
        }
        
        # Transport schedules
        self.ferry_schedules = {
            "稚内-利尻": ["08:00", "13:30", "17:15"],
            "稚内-礼文": ["08:30", "14:00", "16:45"],
            "利尻-礼文": ["10:00", "15:30"]
        }
        
        self.flight_schedules = {
            "札幌丘珠-利尻": ["08:30", "14:05", "16:45"],
            "新千歳-利尻": ["09:15", "15:30"]
        }
    
    def update_weather_conditions(self, weather_data: Dict):
        """Update current weather conditions"""
        self.current_weather.update(weather_data)
        self.current_weather["timestamp"] = datetime.now()
    
    def predict_ferry_operations(self) -> List[TransportSummary]:
        """Predict ferry operations using rule-based system"""
        
        predictions = []
        weather = self.current_weather
        
        for route, times in self.ferry_schedules.items():
            for time in times:
                
                # Ferry-specific risk calculation
                risk_score = 0.0
                risk_factors = []
                
                # Wind risk
                if weather["wind_speed"] > 25:
                    risk_score += 0.6
                    risk_factors.append("強風")
                elif weather["wind_speed"] > 18:
                    risk_score += 0.3
                    risk_factors.append("風やや強")
                
                # Wave height estimation
                estimated_wave_height = weather["wind_speed"] * 0.2
                if estimated_wave_height > 3.0:
                    risk_score += 0.4
                    risk_factors.append("高波")
                
                # Visibility
                if weather["visibility"] < 1000:
                    risk_score += 0.5
                    risk_factors.append("視界不良")
                elif weather["visibility"] < 3000:
                    risk_score += 0.2
                    risk_factors.append("視界やや悪")
                
                # Precipitation
                if weather["precipitation"] > 10:
                    risk_score += 0.3
                    risk_factors.append("強雨")
                elif weather["precipitation"] > 5:
                    risk_score += 0.1
                    risk_factors.append("雨")
                
                # Determine risk level
                if risk_score >= 0.6:
                    risk_level = "HIGH"
                    recommendation = "欠航の可能性が高いです。他の交通手段を検討してください。"
                elif risk_score >= 0.3:
                    risk_level = "MEDIUM"
                    recommendation = "遅延の可能性があります。時間に余裕を持ってください。"
                else:
                    risk_level = "LOW"
                    recommendation = "正常運航が見込まれます。"
                
                primary_factor = risk_factors[0] if risk_factors else "気象条件良好"
                
                predictions.append(TransportSummary(
                    transport_type="フェリー",
                    route=route,
                    scheduled_time=time,
                    cancellation_risk=risk_level,
                    probability=min(risk_score, 0.95),
                    primary_factor=primary_factor,
                    recommendation=recommendation
                ))
        
        return predictions
    
    def predict_flight_operations(self) -> List[TransportSummary]:
        """Predict flight operations using advanced model"""
        
        predictions = []
        weather = self.current_weather
        
        for route, times in self.flight_schedules.items():
            for time in times:
                
                # Create flight prediction input
                flight_input = FlightPredictionInput(
                    flight_date=datetime.now(),
                    flight_time=time,
                    route=route,
                    temperature=weather["temperature"],
                    humidity=weather["humidity"],
                    wind_speed=weather["wind_speed"],
                    wind_direction=weather["wind_direction"],
                    visibility=weather["visibility"],
                    pressure=weather["pressure"],
                    precipitation=weather["precipitation"],
                    sea_temperature_diff=abs(weather["temperature"] - 12.0),
                    mountain_wave_risk="medium"
                )
                
                # Get prediction
                prediction = self.flight_predictor.calculate_overall_prediction(flight_input)
                
                # Convert to risk level
                prob = prediction.cancellation_probability
                if prob >= 0.6:
                    risk_level = "HIGH"
                    recommendation = "欠航の可能性が高いです。フェリーをご検討ください。"
                elif prob >= 0.3:
                    risk_level = "MEDIUM"
                    recommendation = "遅延の可能性があります。最新情報をご確認ください。"
                else:
                    risk_level = "LOW"
                    recommendation = "正常運航が見込まれます。"
                
                predictions.append(TransportSummary(
                    transport_type="航空便",
                    route=route,
                    scheduled_time=time,
                    cancellation_risk=risk_level,
                    probability=prob,
                    primary_factor=prediction.primary_risk_factor,
                    recommendation=recommendation
                ))
        
        return predictions
    
    def get_integrated_forecast(self) -> Dict:
        """Get integrated transport forecast"""
        
        ferry_predictions = self.predict_ferry_operations()
        flight_predictions = self.predict_flight_operations()
        
        all_predictions = ferry_predictions + flight_predictions
        
        # Generate overall assessment
        high_risk_count = len([p for p in all_predictions if p.cancellation_risk == "HIGH"])
        medium_risk_count = len([p for p in all_predictions if p.cancellation_risk == "MEDIUM"])
        
        if high_risk_count > 0:
            overall_status = "🔴 注意"
            overall_message = f"{high_risk_count}路線で欠航リスクが高くなっています。"
        elif medium_risk_count > 0:
            overall_status = "🟡 警戒"
            overall_message = f"{medium_risk_count}路線で遅延の可能性があります。"
        else:
            overall_status = "🟢 良好"
            overall_message = "全路線で正常運航が見込まれます。"
        
        # Best options recommendation
        low_risk_options = [p for p in all_predictions if p.cancellation_risk == "LOW"]
        if low_risk_options:
            recommended_transport = low_risk_options[0].transport_type
            recommended_route = low_risk_options[0].route
            best_option = f"{recommended_transport}: {recommended_route}"
        else:
            best_option = "すべての路線でリスクがあります。"
        
        return {
            "timestamp": self.current_weather["timestamp"],
            "overall_status": overall_status,
            "overall_message": overall_message,
            "best_option": best_option,
            "ferry_predictions": ferry_predictions,
            "flight_predictions": flight_predictions,
            "weather_summary": self._generate_weather_summary(),
            "total_routes_checked": len(all_predictions),
            "high_risk_routes": high_risk_count,
            "medium_risk_routes": medium_risk_count,
            "low_risk_routes": len(all_predictions) - high_risk_count - medium_risk_count
        }
    
    def _generate_weather_summary(self) -> str:
        """Generate current weather summary"""
        
        weather = self.current_weather
        
        summary_parts = []
        summary_parts.append(f"気温: {weather['temperature']:.1f}°C")
        summary_parts.append(f"湿度: {weather['humidity']:.0f}%")
        summary_parts.append(f"風速: {weather['wind_speed']:.1f}kt")
        summary_parts.append(f"視界: {weather['visibility']/1000:.1f}km")
        
        if weather["precipitation"] > 0:
            summary_parts.append(f"降水: {weather['precipitation']:.1f}mm/h")
        
        return ", ".join(summary_parts)
    
    def generate_text_report(self) -> str:
        """Generate text-based forecast report"""
        
        forecast = self.get_integrated_forecast()
        
        report = f"""
=== 北海道交通予報レポート ===
更新時刻: {forecast['timestamp'].strftime('%Y年%m月%d日 %H:%M')}

【総合状況】 {forecast['overall_status']}
{forecast['overall_message']}

【推奨交通手段】
{forecast['best_option']}

【現在の気象状況】
{forecast['weather_summary']}

【フェリー運航予測】"""
        
        for pred in forecast['ferry_predictions']:
            risk_icon = "🔴" if pred.cancellation_risk == "HIGH" else "🟡" if pred.cancellation_risk == "MEDIUM" else "🟢"
            report += f"\n{risk_icon} {pred.route} {pred.scheduled_time}便"
            report += f"\n   リスク: {pred.cancellation_risk} ({pred.probability:.1%})"
            report += f"\n   要因: {pred.primary_factor}"
        
        report += f"\n\n【航空便運航予測】"
        
        for pred in forecast['flight_predictions']:
            risk_icon = "🔴" if pred.cancellation_risk == "HIGH" else "🟡" if pred.cancellation_risk == "MEDIUM" else "🟢"
            report += f"\n{risk_icon} {pred.route} {pred.scheduled_time}便"
            report += f"\n   リスク: {pred.cancellation_risk} ({pred.probability:.1%})"
            report += f"\n   要因: {pred.primary_factor}"
        
        report += f"""

【統計】
チェック路線数: {forecast['total_routes_checked']}
高リスク: {forecast['high_risk_routes']}路線
中リスク: {forecast['medium_risk_routes']}路線
低リスク: {forecast['low_risk_routes']}路線

このレポートは気象条件に基づく予測です。
最新の運航情報は各運航会社にご確認ください。
"""
        
        return report
    
    def simulate_different_weather(self) -> Dict:
        """Simulate predictions under different weather scenarios"""
        
        scenarios = {
            "晴天": {
                "temperature": 22.0, "humidity": 60.0, "wind_speed": 8.0,
                "wind_direction": 200, "visibility": 15000.0, "pressure": 1020.0,
                "precipitation": 0.0
            },
            "曇り": {
                "temperature": 18.0, "humidity": 75.0, "wind_speed": 12.0,
                "wind_direction": 270, "visibility": 8000.0, "pressure": 1015.0,
                "precipitation": 0.0
            },
            "雨": {
                "temperature": 16.0, "humidity": 90.0, "wind_speed": 15.0,
                "wind_direction": 280, "visibility": 3000.0, "pressure": 1008.0,
                "precipitation": 5.0
            },
            "強風": {
                "temperature": 15.0, "humidity": 80.0, "wind_speed": 30.0,
                "wind_direction": 310, "visibility": 8000.0, "pressure": 1005.0,
                "precipitation": 2.0
            },
            "霧": {
                "temperature": 12.0, "humidity": 98.0, "wind_speed": 5.0,
                "wind_direction": 180, "visibility": 500.0, "pressure": 1018.0,
                "precipitation": 0.0
            }
        }
        
        scenario_results = {}
        
        # Save original weather
        original_weather = self.current_weather.copy()
        
        for scenario_name, weather_condition in scenarios.items():
            # Update weather
            self.update_weather_conditions(weather_condition)
            
            # Get predictions
            forecast = self.get_integrated_forecast()
            
            scenario_results[scenario_name] = {
                "overall_status": forecast["overall_status"],
                "high_risk_routes": forecast["high_risk_routes"],
                "medium_risk_routes": forecast["medium_risk_routes"],
                "low_risk_routes": forecast["low_risk_routes"],
                "best_option": forecast["best_option"]
            }
        
        # Restore original weather
        self.current_weather = original_weather
        
        return scenario_results

def main():
    """Main demonstration of integrated system"""
    
    print("=== 北海道交通統合予報システム ===")
    
    # Initialize system
    system = FinalIntegratedSystem()
    
    # Generate current forecast
    print("現在の気象条件での運航予測を生成中...")
    report = system.generate_text_report()
    print(report)
    
    # Simulate different weather scenarios
    print("\n=== 気象条件別シミュレーション ===")
    scenarios = system.simulate_different_weather()
    
    for scenario, results in scenarios.items():
        print(f"\n【{scenario}の場合】")
        print(f"  総合状況: {results['overall_status']}")
        print(f"  高リスク路線: {results['high_risk_routes']}")
        print(f"  中リスク路線: {results['medium_risk_routes']}")
        print(f"  低リスク路線: {results['low_risk_routes']}")
        print(f"  推奨交通手段: {results['best_option']}")
    
    print("\n=== システム完成 ===")
    print("✅ フェリー予測システム")
    print("✅ 航空便予測システム")
    print("✅ 統合予報システム")
    print("✅ 気象条件シミュレーション")
    print("✅ レポート生成機能")

if __name__ == "__main__":
    main()