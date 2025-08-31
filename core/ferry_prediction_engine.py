#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北海道フェリー欠航予測エンジン
Hokkaido Ferry Cancellation Prediction Engine

利尻島昆布予報システムの高度予測技術を活用し、
フェリー欠航リスクの早期予報を実現する。
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import asyncio
import logging
from pathlib import Path

# 気象データ処理用のクラス定義
from typing import Any

@dataclass
class WeatherCondition:
    """気象条件データ"""
    timestamp: datetime
    wind_speed: float
    wind_direction: float
    wave_height: float
    visibility: float
    temperature: float
    precipitation: float
    snow_depth: float = 0.0
    ice_coverage: float = 0.0

@dataclass
class FerryRoute:
    """フェリー航路情報"""
    route_id: str
    departure_port: str
    arrival_port: str
    departure_lat: float
    departure_lon: float
    arrival_lat: float
    arrival_lon: float
    typical_duration: int  # 分
    ferry_type: str
    winter_suspension: bool = False

@dataclass
class CancellationRisk:
    """欠航リスク評価"""
    risk_level: str  # "Low", "Medium", "High", "Critical"
    risk_score: float  # 0-100
    primary_factors: List[str]
    confidence: float
    forecast_horizon: int  # 時間
    detailed_analysis: Dict

class FerryPredictionEngine:
    """フェリー欠航予測エンジン"""
    
    def __init__(self):
        # 気象エンジン（利尻島技術継承予定）
        self.advanced_engine = None  # TODO: AdvancedPredictionEngine()
        self.weather_api = None  # TODO: MultiSourceWeatherAPI()
        
        # 実績データ連携
        self.enable_feedback = True
        self.feedback_data_file = Path(__file__).parent.parent / "data" / "ferry_cancellation_log.csv"
        
        # フェリー航路定義
        self.ferry_routes = self._initialize_ferry_routes()
        
        # 欠航判定閾値（冬季特化）
        self.cancellation_thresholds = {
            "wind_speed": {
                "low": 10.0,      # 注意レベル
                "medium": 15.0,   # 警戒レベル
                "high": 20.0,     # 危険レベル
                "critical": 25.0  # 欠航レベル
            },
            "wave_height": {
                "low": 2.0,
                "medium": 3.0,
                "high": 4.0,
                "critical": 5.0
            },
            "visibility": {  # km
                "critical": 0.5,
                "high": 1.0,
                "medium": 2.0,
                "low": 5.0
            },
            "temperature": {  # 船体凍結リスク
                "critical": -15.0,
                "high": -10.0,
                "medium": -5.0,
                "low": 0.0
            },
            "snowfall_rate": {  # mm/h
                "low": 5.0,
                "medium": 10.0,
                "high": 20.0,
                "critical": 30.0
            }
        }
        
        # 冬季特化重み（11-3月）
        self.winter_weights = {
            "wind_speed": 1.3,
            "wave_height": 1.2,
            "temperature": 1.5,
            "visibility": 1.4,
            "snowfall": 1.6,
            "sea_ice": 2.0
        }
        
        # 航路別補正係数
        self.route_corrections = {
            "wakkanai_oshidomari": {"exposure": 1.2, "distance": 1.0},
            "wakkanai_kutsugata": {"exposure": 1.1, "distance": 1.1},
            "wakkanai_kafuka": {"exposure": 1.0, "distance": 0.9}
        }
        
        self.logger = logging.getLogger(__name__)
        
    def _initialize_ferry_routes(self) -> Dict[str, FerryRoute]:
        """フェリー航路初期化"""
        routes = {}
        
        # 稚内 - 鴛泊（利尻島）
        routes["wakkanai_oshidomari"] = FerryRoute(
            route_id="wakkanai_oshidomari",
            departure_port="稚内",
            arrival_port="鴛泊",
            departure_lat=45.4094,
            departure_lon=141.6739,
            arrival_lat=45.2398,
            arrival_lon=141.2042,
            typical_duration=100,  # 1時間40分
            ferry_type="regular",
            winter_suspension=False
        )
        
        # 稚内 - 沓形（利尻島）
        routes["wakkanai_kutsugata"] = FerryRoute(
            route_id="wakkanai_kutsugata",
            departure_port="稚内",
            arrival_port="沓形",
            departure_lat=45.4094,
            departure_lon=141.6739,
            arrival_lat=45.2480,
            arrival_lon=141.2198,
            typical_duration=100,
            ferry_type="regular",
            winter_suspension=False
        )
        
        # 稚内 - 香深（礼文島）
        routes["wakkanai_kafuka"] = FerryRoute(
            route_id="wakkanai_kafuka",
            departure_port="稚内",
            arrival_port="香深",
            departure_lat=45.4094,
            departure_lon=141.6739,
            arrival_lat=45.3456,
            arrival_lon=141.0311,
            typical_duration=55,
            ferry_type="regular",
            winter_suspension=False
        )
        
        return routes
    
    async def predict_cancellation_risk(self, route_id: str, 
                                       forecast_hours: int = 72) -> List[CancellationRisk]:
        """欠航リスク予測（メイン関数）"""
        if route_id not in self.ferry_routes:
            raise ValueError(f"Unknown route: {route_id}")
        
        route = self.ferry_routes[route_id]
        
        # 航路中点座標計算
        mid_lat = (route.departure_lat + route.arrival_lat) / 2
        mid_lon = (route.departure_lon + route.arrival_lon) / 2
        
        # 気象データ取得
        weather_conditions = await self._fetch_marine_weather(
            mid_lat, mid_lon, forecast_hours
        )
        
        # 欠航リスク評価
        risk_predictions = []
        for i, condition in enumerate(weather_conditions):
            forecast_time = datetime.now() + timedelta(hours=i)
            risk = self._assess_cancellation_risk(
                condition, route, forecast_time, i + 1
            )
            risk_predictions.append(risk)
        
        return risk_predictions
    
    async def _fetch_marine_weather(self, lat: float, lon: float, 
                                  hours: int) -> List[WeatherCondition]:
        """海上気象データ取得"""
        try:
            # 多源気象データ統合を使用
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=hours)
            
            integrated_data = await self.weather_api.get_integrated_weather_data(
                lat, lon, start_time, end_time
            )
            
            # WeatherCondition形式に変換
            conditions = []
            for data_point in integrated_data:
                condition = WeatherCondition(
                    timestamp=data_point.timestamp,
                    temperature=data_point.temperature,
                    humidity=data_point.humidity,
                    wind_speed=data_point.wind_speed,
                    wind_direction=data_point.wind_direction,
                    pressure=data_point.pressure,
                    precipitation=data_point.precipitation,
                    cloud_cover=data_point.cloud_cover,
                    visibility=10.0,  # デフォルト値、実装時は気象データから取得
                    uv_index=0.0      # 夜間・冬季は不要
                )
                conditions.append(condition)
            
            return conditions
            
        except Exception as e:
            self.logger.error(f"Marine weather fetch error: {e}")
            # フォールバック: 模擬データ
            return self._generate_fallback_marine_conditions(hours)
    
    def _generate_fallback_marine_conditions(self, hours: int) -> List[WeatherCondition]:
        """海上気象フォールバックデータ"""
        conditions = []
        base_time = datetime.now()
        
        for i in range(hours):
            # 冬季北海道の典型的な海上気象パターン
            time_offset = i
            current_time = base_time + timedelta(hours=time_offset)
            
            # 季節性を考慮した基本パラメータ
            month = current_time.month
            is_winter = month in [11, 12, 1, 2, 3]
            
            if is_winter:
                base_temp = -5 + np.random.normal(0, 5)
                base_wind = 12 + np.random.normal(0, 4)
                base_humidity = 75 + np.random.normal(0, 10)
            else:
                base_temp = 10 + np.random.normal(0, 3)
                base_wind = 8 + np.random.normal(0, 3)
                base_humidity = 70 + np.random.normal(0, 10)
            
            condition = WeatherCondition(
                timestamp=current_time,
                temperature=max(-20, min(30, base_temp)),
                humidity=max(30, min(95, base_humidity)),
                wind_speed=max(0, base_wind),
                wind_direction=np.random.randint(0, 360),
                pressure=1010 + np.random.normal(0, 8),
                precipitation=max(0, np.random.exponential(1.0) if is_winter else 0),
                cloud_cover=max(0, min(100, 60 + np.random.normal(0, 25))),
                visibility=max(0.5, 15 - np.random.exponential(2) if is_winter else 20),
                uv_index=0
            )
            conditions.append(condition)
        
        return conditions
    
    def _assess_cancellation_risk(self, condition: WeatherCondition, 
                                route: FerryRoute, forecast_time: datetime,
                                hours_ahead: int) -> CancellationRisk:
        """欠航リスク評価"""
        # 冬季判定
        is_winter = forecast_time.month in [11, 12, 1, 2, 3]
        
        # 各要因のリスクスコア計算
        risk_factors = {}
        risk_factors["wind"] = self._calculate_wind_risk(condition, is_winter)
        risk_factors["wave"] = self._calculate_wave_risk(condition, is_winter)
        risk_factors["visibility"] = self._calculate_visibility_risk(condition, is_winter)
        risk_factors["temperature"] = self._calculate_temperature_risk(condition, is_winter)
        risk_factors["precipitation"] = self._calculate_precipitation_risk(condition, is_winter)
        
        if is_winter:
            risk_factors["ice"] = self._calculate_ice_risk(condition, forecast_time)
        
        # 航路補正適用
        route_correction = self.route_corrections.get(route.route_id, {"exposure": 1.0})
        for factor in ["wind", "wave", "visibility"]:
            risk_factors[factor] *= route_correction.get("exposure", 1.0)
        
        # 統合リスクスコア計算
        if is_winter:
            weights = {"wind": 0.25, "wave": 0.20, "visibility": 0.20, 
                      "temperature": 0.15, "precipitation": 0.10, "ice": 0.10}
        else:
            weights = {"wind": 0.30, "wave": 0.25, "visibility": 0.25,
                      "temperature": 0.05, "precipitation": 0.15}
        
        integrated_risk = sum(risk_factors[factor] * weights.get(factor, 0) 
                            for factor in risk_factors.keys())
        
        # リスクレベル判定
        risk_level, primary_factors = self._determine_risk_level(
            integrated_risk, risk_factors
        )
        
        # 信頼度計算（予報期間による減衰）
        confidence = max(0.4, 1.0 - (hours_ahead - 1) * 0.1)
        
        # 詳細分析
        detailed_analysis = {
            "weather_conditions": {
                "wind_speed": condition.wind_speed,
                "wind_direction": condition.wind_direction,
                "temperature": condition.temperature,
                "visibility": condition.visibility,
                "precipitation": condition.precipitation,
                "pressure": condition.pressure
            },
            "risk_breakdown": risk_factors,
            "winter_mode": is_winter,
            "route_corrections": route_correction,
            "forecast_uncertainty": 1.0 - confidence
        }
        
        return CancellationRisk(
            risk_level=risk_level,
            risk_score=integrated_risk,
            primary_factors=primary_factors,
            confidence=confidence,
            forecast_horizon=hours_ahead,
            detailed_analysis=detailed_analysis
        )
    
    def _calculate_wind_risk(self, condition: WeatherCondition, is_winter: bool) -> float:
        """風速リスク計算"""
        wind_speed = condition.wind_speed
        thresholds = self.cancellation_thresholds["wind_speed"]
        
        if wind_speed >= thresholds["critical"]:
            risk = 100
        elif wind_speed >= thresholds["high"]:
            risk = 70 + (wind_speed - thresholds["high"]) / (thresholds["critical"] - thresholds["high"]) * 30
        elif wind_speed >= thresholds["medium"]:
            risk = 40 + (wind_speed - thresholds["medium"]) / (thresholds["high"] - thresholds["medium"]) * 30
        elif wind_speed >= thresholds["low"]:
            risk = 15 + (wind_speed - thresholds["low"]) / (thresholds["medium"] - thresholds["low"]) * 25
        else:
            risk = wind_speed / thresholds["low"] * 15
        
        # 冬季補正
        if is_winter:
            risk *= self.winter_weights["wind_speed"]
        
        return min(100, risk)
    
    def _calculate_wave_risk(self, condition: WeatherCondition, is_winter: bool) -> float:
        """波浪リスク計算（風速から推定）"""
        # 簡易波高推定（実装では海上保安庁データを使用）
        estimated_wave_height = condition.wind_speed * 0.25  # 簡易換算
        
        thresholds = self.cancellation_thresholds["wave_height"]
        
        if estimated_wave_height >= thresholds["critical"]:
            risk = 100
        elif estimated_wave_height >= thresholds["high"]:
            risk = 75 + (estimated_wave_height - thresholds["high"]) / (thresholds["critical"] - thresholds["high"]) * 25
        elif estimated_wave_height >= thresholds["medium"]:
            risk = 45 + (estimated_wave_height - thresholds["medium"]) / (thresholds["high"] - thresholds["medium"]) * 30
        elif estimated_wave_height >= thresholds["low"]:
            risk = 20 + (estimated_wave_height - thresholds["low"]) / (thresholds["medium"] - thresholds["low"]) * 25
        else:
            risk = estimated_wave_height / thresholds["low"] * 20
        
        if is_winter:
            risk *= self.winter_weights["wave_height"]
        
        return min(100, risk)
    
    def _calculate_visibility_risk(self, condition: WeatherCondition, is_winter: bool) -> float:
        """視界リスク計算"""
        visibility = condition.visibility
        thresholds = self.cancellation_thresholds["visibility"]
        
        if visibility <= thresholds["critical"]:
            risk = 100
        elif visibility <= thresholds["high"]:
            risk = 80 + (thresholds["high"] - visibility) / (thresholds["high"] - thresholds["critical"]) * 20
        elif visibility <= thresholds["medium"]:
            risk = 50 + (thresholds["medium"] - visibility) / (thresholds["medium"] - thresholds["high"]) * 30
        elif visibility <= thresholds["low"]:
            risk = 20 + (thresholds["low"] - visibility) / (thresholds["low"] - thresholds["medium"]) * 30
        else:
            risk = max(0, (10 - visibility) / 5 * 20)
        
        if is_winter:
            risk *= self.winter_weights["visibility"]
        
        return min(100, max(0, risk))
    
    def _calculate_temperature_risk(self, condition: WeatherCondition, is_winter: bool) -> float:
        """気温リスク計算（船体凍結）"""
        if not is_winter:
            return 0  # 冬季以外は気温リスクなし
        
        temperature = condition.temperature
        thresholds = self.cancellation_thresholds["temperature"]
        
        if temperature <= thresholds["critical"]:
            risk = 100
        elif temperature <= thresholds["high"]:
            risk = 70 + (thresholds["high"] - temperature) / (thresholds["high"] - thresholds["critical"]) * 30
        elif temperature <= thresholds["medium"]:
            risk = 40 + (thresholds["medium"] - temperature) / (thresholds["medium"] - thresholds["high"]) * 30
        elif temperature <= thresholds["low"]:
            risk = 15 + (thresholds["low"] - temperature) / (thresholds["low"] - thresholds["medium"]) * 25
        else:
            risk = 0
        
        return min(100, risk)
    
    def _calculate_precipitation_risk(self, condition: WeatherCondition, is_winter: bool) -> float:
        """降水リスク計算"""
        precipitation = condition.precipitation
        
        if is_winter:
            # 冬季は降雪として扱い、視界悪化要因
            thresholds = self.cancellation_thresholds["snowfall_rate"]
            
            if precipitation >= thresholds["critical"]:
                risk = 100
            elif precipitation >= thresholds["high"]:
                risk = 75 + (precipitation - thresholds["high"]) / (thresholds["critical"] - thresholds["high"]) * 25
            elif precipitation >= thresholds["medium"]:
                risk = 45 + (precipitation - thresholds["medium"]) / (thresholds["high"] - thresholds["medium"]) * 30
            elif precipitation >= thresholds["low"]:
                risk = 20 + (precipitation - thresholds["low"]) / (thresholds["medium"] - thresholds["low"]) * 25
            else:
                risk = precipitation / thresholds["low"] * 20
            
            risk *= self.winter_weights["snowfall"]
        else:
            # 夏季は通常の降水
            if precipitation > 20:
                risk = 50
            elif precipitation > 10:
                risk = 30
            elif precipitation > 5:
                risk = 15
            else:
                risk = precipitation * 3
        
        return min(100, risk)
    
    def _calculate_ice_risk(self, condition: WeatherCondition, forecast_time: datetime) -> float:
        """流氷リスク計算（2-3月）"""
        month = forecast_time.month
        
        if month not in [2, 3]:
            return 0  # 流氷期以外はリスクなし
        
        # 簡易流氷リスク（実装では海氷情報APIを使用）
        # 気温と風向から流氷接近可能性を推定
        temp_factor = max(0, (-5 - condition.temperature) / 10)  # -5°C以下で増加
        
        # 北寄りの風で流氷南下促進
        wind_dir = condition.wind_direction
        if 315 <= wind_dir <= 360 or 0 <= wind_dir <= 45:  # 北寄り
            wind_factor = 1.5
        elif 270 <= wind_dir <= 315 or 45 <= wind_dir <= 90:  # 北西・北東
            wind_factor = 1.2
        else:
            wind_factor = 0.8
        
        base_risk = 30 if month == 2 else 20  # 2月がピーク
        ice_risk = base_risk * temp_factor * wind_factor
        
        return min(100, ice_risk)
    
    def _determine_risk_level(self, integrated_risk: float, 
                            risk_factors: Dict[str, float]) -> Tuple[str, List[str]]:
        """リスクレベル判定"""
        # 主要リスク要因特定
        primary_factors = []
        for factor, score in risk_factors.items():
            if score > 60:
                primary_factors.append(f"高{self._translate_factor(factor)}リスク")
            elif score > 40:
                primary_factors.append(f"中程度{self._translate_factor(factor)}リスク")
        
        # 統合リスクレベル判定
        if integrated_risk >= 80:
            return "Critical", primary_factors or ["極めて危険な気象条件"]
        elif integrated_risk >= 60:
            return "High", primary_factors or ["危険な気象条件"]
        elif integrated_risk >= 40:
            return "Medium", primary_factors or ["注意が必要な気象条件"]
        else:
            return "Low", primary_factors or ["概ね安全な気象条件"]
    
    def _translate_factor(self, factor: str) -> str:
        """要因名日本語変換"""
        translations = {
            "wind": "風速",
            "wave": "波浪", 
            "visibility": "視界",
            "temperature": "低温",
            "precipitation": "降水",
            "ice": "流氷"
        }
        return translations.get(factor, factor)
    
    def generate_risk_summary(self, route_id: str, risk_predictions: List[CancellationRisk]) -> Dict:
        """リスク要約生成"""
        if not risk_predictions:
            return {"error": "予測データがありません"}
        
        route = self.ferry_routes[route_id]
        
        # 期間別統計
        next_24h = risk_predictions[:24]
        next_48h = risk_predictions[:48] 
        next_72h = risk_predictions[:72]
        
        summary = {
            "route_info": {
                "route_name": f"{route.departure_port} ⇔ {route.arrival_port}",
                "duration": f"{route.typical_duration}分",
                "distance": self._calculate_route_distance(route)
            },
            "current_risk": {
                "level": next_24h[0].risk_level,
                "score": next_24h[0].risk_score,
                "factors": next_24h[0].primary_factors
            },
            "period_outlook": {
                "24h": self._calculate_period_risk(next_24h),
                "48h": self._calculate_period_risk(next_48h),
                "72h": self._calculate_period_risk(next_72h)
            },
            "peak_risk_times": self._find_peak_risk_periods(risk_predictions),
            "safe_windows": self._find_safe_windows(risk_predictions),
            "recommendations": self._generate_recommendations(risk_predictions, route)
        }
        
        return summary
    
    def _calculate_route_distance(self, route: FerryRoute) -> str:
        """航路距離計算"""
        # 簡易距離計算（実装では正確な航路距離）
        lat_diff = route.arrival_lat - route.departure_lat
        lon_diff = route.arrival_lon - route.departure_lon
        distance_km = ((lat_diff**2 + lon_diff**2)**0.5) * 111  # 度→km概算
        return f"{distance_km:.1f}km"
    
    def _calculate_period_risk(self, period_risks: List[CancellationRisk]) -> Dict:
        """期間リスク計算"""
        if not period_risks:
            return {"average_risk": 0, "max_risk": 0, "risk_level": "Unknown"}
        
        scores = [r.risk_score for r in period_risks]
        average_risk = np.mean(scores)
        max_risk = max(scores)
        
        # 期間代表リスクレベル
        if max_risk >= 80:
            level = "Critical"
        elif max_risk >= 60:
            level = "High" 
        elif average_risk >= 40:
            level = "Medium"
        else:
            level = "Low"
        
        return {
            "average_risk": round(average_risk, 1),
            "max_risk": round(max_risk, 1),
            "risk_level": level
        }
    
    def _find_peak_risk_periods(self, risk_predictions: List[CancellationRisk]) -> List[Dict]:
        """ピークリスク期間特定"""
        peaks = []
        
        for i, risk in enumerate(risk_predictions):
            if risk.risk_score >= 70:  # 高リスク以上
                peak_time = datetime.now() + timedelta(hours=i)
                peaks.append({
                    "time": peak_time.strftime("%m/%d %H:%M"),
                    "risk_score": risk.risk_score,
                    "risk_level": risk.risk_level,
                    "primary_factors": risk.primary_factors[:2]  # 主要2要因
                })
        
        return peaks[:5]  # 最大5件
    
    def _find_safe_windows(self, risk_predictions: List[CancellationRisk]) -> List[Dict]:
        """安全運航時間帯特定"""
        safe_windows = []
        window_start = None
        
        for i, risk in enumerate(risk_predictions):
            if risk.risk_score < 30:  # 低リスク
                if window_start is None:
                    window_start = i
            else:
                if window_start is not None:
                    # 安全期間終了
                    start_time = datetime.now() + timedelta(hours=window_start)
                    end_time = datetime.now() + timedelta(hours=i)
                    duration = i - window_start
                    
                    if duration >= 3:  # 3時間以上の安全期間
                        safe_windows.append({
                            "start_time": start_time.strftime("%m/%d %H:%M"),
                            "end_time": end_time.strftime("%m/%d %H:%M"),
                            "duration_hours": duration,
                            "average_risk": np.mean([r.risk_score for r in risk_predictions[window_start:i]])
                        })
                    
                    window_start = None
        
        return safe_windows[:3]  # 最大3件
    
    def _generate_recommendations(self, risk_predictions: List[CancellationRisk], 
                                route: FerryRoute) -> List[str]:
        """推奨事項生成"""
        recommendations = []
        
        current_risk = risk_predictions[0]
        next_24h_risks = [r.risk_score for r in risk_predictions[:24]]
        avg_24h_risk = np.mean(next_24h_risks)
        max_24h_risk = max(next_24h_risks)
        
        # 現在リスク基準推奨
        if current_risk.risk_level == "Critical":
            recommendations.append("現在極めて危険な状況です。運航は困難と予想されます。")
        elif current_risk.risk_level == "High":
            recommendations.append("現在危険な状況です。運航判断に注意が必要です。")
        elif current_risk.risk_level == "Medium":
            recommendations.append("現在注意が必要な状況です。気象情報を継続監視してください。")
        
        # 24時間予測基準推奨
        if max_24h_risk >= 80:
            recommendations.append("今後24時間以内に運航困難となる可能性が高いです。")
        elif avg_24h_risk >= 50:
            recommendations.append("今後24時間は不安定な気象条件が予想されます。")
        
        # 冬季特化推奨
        current_month = datetime.now().month
        if current_month in [11, 12, 1, 2, 3]:
            high_temp_risks = [r for r in risk_predictions[:24] 
                             if "低温" in " ".join(r.primary_factors)]
            if high_temp_risks:
                recommendations.append("船体凍結リスクがあります。防寒対策を十分に行ってください。")
            
            ice_risks = [r for r in risk_predictions[:48]
                        if "流氷" in " ".join(r.primary_factors)]
            if ice_risks:
                recommendations.append("流氷接近の可能性があります。海氷情報を確認してください。")
        
        # 安全時間帯推奨
        safe_windows = self._find_safe_windows(risk_predictions)
        if safe_windows:
            first_safe = safe_windows[0]
            recommendations.append(f"最も安全な運航時間帯: {first_safe['start_time']}頃から{first_safe['duration_hours']}時間程度")
        
        return recommendations[:5]  # 最大5件
    
    def apply_feedback_learning(self, route_id: str) -> Dict:
        """実績フィードバックによる学習適用"""
        if not self.enable_feedback:
            return {"status": "feedback_disabled"}
        
        try:
            import pandas as pd
            from pathlib import Path
            
            if not self.feedback_data_file.exists():
                return {"status": "no_feedback_data"}
            
            # 実績データ読み込み
            df = pd.read_csv(self.feedback_data_file, encoding='utf-8')
            
            # 該当航路データフィルタ
            route_data = df[df['出航場所'].str.contains('稚内') & 
                          df['着場所'].isin(['鴛泊港', '沓形港', '香深港'])]
            
            if len(route_data) < 10:
                return {"status": "insufficient_data", "count": len(route_data)}
            
            # 閾値調整
            adjustments = self._calculate_threshold_adjustments(route_data)
            
            # 閾値更新
            if adjustments:
                self._update_thresholds(adjustments)
                
            return {
                "status": "feedback_applied",
                "data_count": len(route_data),
                "adjustments": adjustments
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _calculate_threshold_adjustments(self, route_data) -> Dict:
        """閾値調整計算"""
        try:
            import pandas as pd
            
            adjustments = {}
            
            # 欠航データのみ抽出
            cancellation_data = route_data[route_data['運航状況'] == '欠航']
            
            if len(cancellation_data) == 0:
                return adjustments
            
            # 風速閾値調整
            avg_wind_at_cancellation = cancellation_data['風速_ms'].mean()
            if pd.notna(avg_wind_at_cancellation):
                current_threshold = self.cancellation_thresholds["wind_speed"]["medium"]
                if avg_wind_at_cancellation < current_threshold:
                    adjustment = min(0.9, avg_wind_at_cancellation / current_threshold)
                    adjustments["wind_speed_factor"] = adjustment
            
            # 波高閾値調整
            avg_wave_at_cancellation = cancellation_data['波高_m'].mean()
            if pd.notna(avg_wave_at_cancellation):
                current_threshold = self.cancellation_thresholds["wave_height"]["medium"]
                if avg_wave_at_cancellation < current_threshold:
                    adjustment = min(0.9, avg_wave_at_cancellation / current_threshold)
                    adjustments["wave_height_factor"] = adjustment
            
            # 視界閾値調整
            avg_visibility_at_cancellation = cancellation_data['視界_km'].mean()
            if pd.notna(avg_visibility_at_cancellation):
                current_threshold = self.cancellation_thresholds["visibility"]["medium"]
                if avg_visibility_at_cancellation > current_threshold:
                    adjustment = max(1.1, avg_visibility_at_cancellation / current_threshold)
                    adjustments["visibility_factor"] = adjustment
            
            return adjustments
            
        except Exception as e:
            self.logger.error(f"閾値調整計算でエラー: {e}")
            return {}
    
    def _update_thresholds(self, adjustments: Dict):
        """閾値更新適用"""
        try:
            if "wind_speed_factor" in adjustments:
                factor = adjustments["wind_speed_factor"]
                for level in self.cancellation_thresholds["wind_speed"]:
                    self.cancellation_thresholds["wind_speed"][level] *= factor
                self.logger.info(f"風速閾値を調整しました: factor={factor:.3f}")
            
            if "wave_height_factor" in adjustments:
                factor = adjustments["wave_height_factor"]
                for level in self.cancellation_thresholds["wave_height"]:
                    self.cancellation_thresholds["wave_height"][level] *= factor
                self.logger.info(f"波高閾値を調整しました: factor={factor:.3f}")
            
            if "visibility_factor" in adjustments:
                factor = adjustments["visibility_factor"]
                for level in self.cancellation_thresholds["visibility"]:
                    self.cancellation_thresholds["visibility"][level] *= factor
                self.logger.info(f"視界閾値を調整しました: factor={factor:.3f}")
                
        except Exception as e:
            self.logger.error(f"閾値更新でエラー: {e}")
    
    def get_prediction_accuracy_metrics(self) -> Dict:
        """予測精度メトリクス取得"""
        try:
            if not self.feedback_data_file.exists():
                return {"error": "フィードバックデータがありません"}
            
            import pandas as pd
            from datetime import datetime, timedelta
            
            df = pd.read_csv(self.feedback_data_file, encoding='utf-8')
            
            # 直近30日のデータ
            recent_date = datetime.now() - timedelta(days=30)
            df['日付'] = pd.to_datetime(df['日付'])
            recent_data = df[df['日付'] >= recent_date]
            
            if len(recent_data) == 0:
                return {"error": "直近のデータがありません"}
            
            # 精度計算（簡易版）
            total = len(recent_data)
            cancellations = len(recent_data[recent_data['運航状況'] == '欠航'])
            delays = len(recent_data[recent_data['運航状況'] == '遅延'])
            
            metrics = {
                "period": f"{recent_date.date()} - {datetime.now().date()}",
                "total_records": total,
                "cancellation_count": cancellations,
                "delay_count": delays,
                "cancellation_rate": (cancellations / total * 100) if total > 0 else 0,
                "avg_wind_at_cancellation": float(recent_data[recent_data['運航状況'] == '欠航']['風速_ms'].mean()) if cancellations > 0 else None,
                "avg_wave_at_cancellation": float(recent_data[recent_data['運航状況'] == '欠航']['波高_m'].mean()) if cancellations > 0 else None,
                "feedback_status": "active" if self.enable_feedback else "disabled"
            }
            
            return metrics
            
        except Exception as e:
            return {"error": str(e)}

# 使用例
async def main():
    """メイン実行例"""
    print("=== 北海道フェリー欠航予測システム ===")
    
    engine = FerryPredictionEngine()
    
    # テスト航路
    test_routes = ["wakkanai_oshidomari", "wakkanai_kutsugata", "wakkanai_kafuka"]
    
    for route_id in test_routes:
        print(f"\n--- {route_id} ---")
        
        try:
            # 72時間予測
            risk_predictions = await engine.predict_cancellation_risk(route_id, 72)
            
            # 要約生成
            summary = engine.generate_risk_summary(route_id, risk_predictions)
            
            print(f"航路: {summary['route_info']['route_name']}")
            print(f"現在リスク: {summary['current_risk']['level']} (スコア: {summary['current_risk']['score']:.1f})")
            print(f"24時間予測: {summary['period_outlook']['24h']['risk_level']}")
            print(f"推奨事項: {summary['recommendations'][0] if summary['recommendations'] else 'なし'}")
            
        except Exception as e:
            print(f"予測エラー: {e}")

if __name__ == "__main__":
    asyncio.run(main())