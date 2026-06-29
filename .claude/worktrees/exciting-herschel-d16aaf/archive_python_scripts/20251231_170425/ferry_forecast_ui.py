#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北海道フェリー運航予報UIシステム
Hokkaido Ferry Operation Forecast UI System

7日間の各航路・各便の詳細運航予報を表示
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Optional
import pandas as pd
from dataclasses import dataclass

# 既存システムのインポート
from core.ferry_prediction_engine import FerryPredictionEngine, CancellationRisk
from prediction_data_integration import PredictionDataIntegration
from data_collection_manager import DataCollectionManager
from adaptive_prediction_system import AdaptivePredictionSystem

@dataclass
class ScheduledService:
    """運航便情報"""
    route_id: str
    route_name: str
    departure_port: str
    arrival_port: str
    departure_time: str
    arrival_time: str
    service_number: int
    date: datetime

@dataclass
class ForecastResult:
    """予報結果"""
    service: ScheduledService
    risk_level: str  # "Low", "Medium", "High", "Critical"
    risk_score: float  # 0-100
    weather_conditions: Dict
    primary_factors: List[str]
    recommendation: str
    confidence: float
    prediction_method: str  # "initial_rules", "hybrid", "ml_only"

class FerryForecastUI:
    """フェリー運航予報UIシステム"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        
        # 既存システム初期化
        self.prediction_engine = FerryPredictionEngine()
        self.data_integration = PredictionDataIntegration()
        self.data_manager = DataCollectionManager(self.data_dir)
        self.adaptive_system = AdaptivePredictionSystem(self.data_dir)
        
        # 運航スケジュール
        self.schedules = self._load_ferry_schedules()
        
        # 初期欠航条件（データ不足時に使用）
        self.initial_conditions = {
            "wind_speed_critical": 15.0,  # m/s
            "wave_height_critical": 3.0,  # m
            "visibility_critical": 1.0,   # km
            "temperature_critical": -10.0, # °C
            "combined_risk_threshold": 60.0 # 複合リスク閾値
        }
        
    def _load_ferry_schedules(self) -> Dict:
        """運航スケジュール読み込み"""
        try:
            config_file = self.base_dir / "config" / "ferry_routes.json"
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config["ferry_routes"]
        except Exception as e:
            print(f"スケジュール読み込みエラー: {e}")
            return self._get_default_schedules()
    
    def _get_default_schedules(self) -> Dict:
        """デフォルトスケジュール"""
        return {
            "wakkanai_oshidomari": {
                "route_name": "稚内 ⇔ 鴛泊",
                "schedules": {
                    "winter": [
                        {"departure": "08:00", "arrival": "09:40", "service_number": 1},
                        {"departure": "15:00", "arrival": "16:40", "service_number": 2}
                    ],
                    "summer": [
                        {"departure": "06:00", "arrival": "07:40", "service_number": 1},
                        {"departure": "10:00", "arrival": "11:40", "service_number": 2},
                        {"departure": "14:00", "arrival": "15:40", "service_number": 3},
                        {"departure": "17:30", "arrival": "19:10", "service_number": 4}
                    ]
                }
            },
            "wakkanai_kutsugata": {
                "route_name": "稚内 ⇔ 沓形",
                "schedules": {
                    "winter": [
                        {"departure": "09:00", "arrival": "10:40", "service_number": 1},
                        {"departure": "14:30", "arrival": "16:10", "service_number": 2}
                    ],
                    "summer": [
                        {"departure": "07:30", "arrival": "09:10", "service_number": 1},
                        {"departure": "12:00", "arrival": "13:40", "service_number": 2},
                        {"departure": "16:30", "arrival": "18:10", "service_number": 3}
                    ]
                }
            },
            "wakkanai_kafuka": {
                "route_name": "稚内 ⇔ 香深",
                "schedules": {
                    "winter": [
                        {"departure": "08:30", "arrival": "09:25", "service_number": 1},
                        {"departure": "12:00", "arrival": "12:55", "service_number": 2},
                        {"departure": "15:30", "arrival": "16:25", "service_number": 3}
                    ],
                    "summer": [
                        {"departure": "06:30", "arrival": "07:25", "service_number": 1},
                        {"departure": "09:00", "arrival": "09:55", "service_number": 2},
                        {"departure": "12:30", "arrival": "13:25", "service_number": 3},
                        {"departure": "15:00", "arrival": "15:55", "service_number": 4},
                        {"departure": "18:00", "arrival": "18:55", "service_number": 5}
                    ]
                }
            }
        }
    
    def generate_7day_schedule(self) -> List[ScheduledService]:
        """7日間の運航スケジュール生成"""
        services = []
        start_date = datetime.now().date()
        
        for day_offset in range(7):
            forecast_date = datetime.combine(start_date + timedelta(days=day_offset), datetime.min.time())
            
            # 季節判定（簡易版）
            season = "winter" if forecast_date.month in [11, 12, 1, 2, 3] else "summer"
            
            for route_id, route_data in self.schedules.items():
                route_name = route_data.get("route_name", route_id)
                schedules = route_data.get("schedules", {}).get(season, [])
                
                # 出発地・到着地設定
                if "鴛泊" in route_name:
                    departure_port, arrival_port = "稚内港", "鴛泊港"
                elif "沓形" in route_name:
                    departure_port, arrival_port = "稚内港", "沓形港"
                elif "香深" in route_name:
                    departure_port, arrival_port = "稚内港", "香深港"
                else:
                    departure_port, arrival_port = "稚内港", "不明港"
                
                for schedule in schedules:
                    service = ScheduledService(
                        route_id=route_id,
                        route_name=route_name,
                        departure_port=departure_port,
                        arrival_port=arrival_port,
                        departure_time=schedule["departure"],
                        arrival_time=schedule["arrival"],
                        service_number=schedule["service_number"],
                        date=forecast_date
                    )
                    services.append(service)
        
        return services
    
    async def generate_forecast_for_service(self, service: ScheduledService) -> ForecastResult:
        """個別運航便の予報生成"""
        try:
            # 適応的調整チェック・実行
            if self.adaptive_system.should_trigger_adaptation():
                self.adaptive_system.apply_adaptive_adjustments()
            
            # 現在の予測パラメータ取得
            prediction_params = self.adaptive_system.get_current_prediction_parameters()
            data_count = prediction_params["data_count"]
            
            # 気象データ取得（模擬）
            weather_conditions = await self._get_weather_forecast(service.date, service.departure_time)
            
            # 予測方法選択（データ量に応じて）
            if data_count >= 200:
                # 十分なデータ：ハイブリッド予測
                prediction_result = self.data_integration.create_hybrid_prediction(
                    service.route_id, 
                    service.departure_time,
                    weather_conditions
                )
                prediction_method = "hybrid"
                
                if "hybrid" in prediction_result.get("predictions", {}):
                    hybrid_pred = prediction_result["predictions"]["hybrid"]
                    risk_score = hybrid_pred["risk_score"]
                    risk_level = hybrid_pred["risk_level"]
                    confidence = 0.85
                else:
                    # フォールバック
                    risk_score, risk_level, confidence = self._apply_initial_rules(weather_conditions)
                    prediction_method = "initial_rules"
                    
            elif data_count >= 50:
                # 基本データ：機械学習 + 初期ルール
                ml_result = self.data_integration.predict_with_ml_model(
                    weather_conditions, service.route_id, service.departure_time
                )
                
                if "error" not in ml_result:
                    ml_risk = ml_result["cancellation_probability"] * 100
                    rule_risk, _, _ = self._apply_initial_rules(weather_conditions)
                    
                    # 重み付き平均
                    risk_score = (ml_risk * 0.6 + rule_risk * 0.4)
                    risk_level = self._determine_risk_level(risk_score)
                    confidence = 0.70
                    prediction_method = "hybrid"
                else:
                    risk_score, risk_level, confidence = self._apply_initial_rules(weather_conditions)
                    prediction_method = "initial_rules"
                    
            else:
                # データ不足：初期ルールのみ
                risk_score, risk_level, confidence = self._apply_initial_rules(weather_conditions)
                prediction_method = "initial_rules"
            
            # 主要要因特定
            primary_factors = self._identify_primary_factors(weather_conditions, service.date.month)
            
            # 推奨事項生成
            recommendation = self._generate_recommendation(risk_level, primary_factors, service)
            
            return ForecastResult(
                service=service,
                risk_level=risk_level,
                risk_score=risk_score,
                weather_conditions=weather_conditions,
                primary_factors=primary_factors,
                recommendation=recommendation,
                confidence=confidence,
                prediction_method=prediction_method
            )
            
        except Exception as e:
            print(f"予報生成エラー: {e}")
            # エラー時のフォールバック
            return ForecastResult(
                service=service,
                risk_level="Unknown",
                risk_score=50.0,
                weather_conditions={},
                primary_factors=["予報データ取得エラー"],
                recommendation="気象情報を個別に確認してください",
                confidence=0.0,
                prediction_method="error"
            )
    
    def _apply_initial_rules(self, weather: Dict) -> tuple:
        """初期ルールベース予測（適応的閾値使用）"""
        wind_speed = weather.get("wind_speed", 0)
        wave_height = weather.get("wave_height", 0) 
        visibility = weather.get("visibility", 20)
        temperature = weather.get("temperature", 0)
        
        # 適応的閾値取得
        adapted_thresholds = self.adaptive_system.current_config["adapted_thresholds"]
        
        # 各要因のリスクスコア計算（適応的閾値使用）
        wind_threshold = adapted_thresholds["wind_speed"]["medium"]
        wind_risk = min(100, (wind_speed / wind_threshold) * 100)
        
        wave_threshold = adapted_thresholds["wave_height"]["medium"]
        wave_risk = min(100, (wave_height / wave_threshold) * 100)
        
        visibility_threshold = adapted_thresholds["visibility"]["medium"]
        visibility_risk = max(0, (visibility_threshold - visibility) / visibility_threshold * 100)
        
        temp_threshold = adapted_thresholds["temperature"]["medium"]
        temp_risk = max(0, (temp_threshold - temperature) / 20 * 100) if temperature < 0 else 0
        
        # 複合リスク計算
        combined_risk = (wind_risk * 0.4 + wave_risk * 0.3 + visibility_risk * 0.2 + temp_risk * 0.1)
        
        risk_level = self._determine_risk_level(combined_risk)
        confidence = 0.60  # 初期ルールの信頼度
        
        return combined_risk, risk_level, confidence
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """リスクレベル判定"""
        if risk_score >= 80:
            return "Critical"
        elif risk_score >= 60:
            return "High"
        elif risk_score >= 30:
            return "Medium"
        else:
            return "Low"
    
    async def _get_weather_forecast(self, forecast_date: datetime, departure_time: str) -> Dict:
        """気象予報取得（模擬データ）"""
        import random
        import numpy as np
        
        # 日付からの季節性
        month = forecast_date.month
        is_winter = month in [11, 12, 1, 2, 3]
        
        # 時間帯の影響
        hour = int(departure_time.split(':')[0])
        is_morning = hour < 12
        
        # 季節・時間帯を考慮した模擬データ
        if is_winter:
            base_wind = 12 + random.gauss(0, 4)
            base_temp = -3 + random.gauss(0, 6)
            visibility_base = 8 if is_morning else 6
        else:
            base_wind = 7 + random.gauss(0, 3)
            base_temp = 15 + random.gauss(0, 4)
            visibility_base = 15 if is_morning else 12
        
        # 日間変動
        day_factor = 1 + 0.2 * np.sin((forecast_date - datetime.now()).days * np.pi / 3)
        
        return {
            "wind_speed": max(0, base_wind * day_factor),
            "wave_height": max(0, base_wind * 0.3 * day_factor),
            "visibility": max(0.5, visibility_base + random.gauss(0, 3)),
            "temperature": base_temp,
            "forecast_time": forecast_date.isoformat()
        }
    
    def _identify_primary_factors(self, weather: Dict, month: int) -> List[str]:
        """主要リスク要因特定"""
        factors = []
        
        wind_speed = weather.get("wind_speed", 0)
        wave_height = weather.get("wave_height", 0)
        visibility = weather.get("visibility", 20)
        temperature = weather.get("temperature", 0)
        
        if wind_speed >= self.initial_conditions["wind_speed_critical"] * 0.8:
            factors.append(f"強風 ({wind_speed:.1f}m/s)")
        
        if wave_height >= self.initial_conditions["wave_height_critical"] * 0.8:
            factors.append(f"高波 ({wave_height:.1f}m)")
        
        if visibility <= self.initial_conditions["visibility_critical"] * 1.5:
            factors.append(f"視界不良 ({visibility:.1f}km)")
        
        if temperature <= self.initial_conditions["temperature_critical"] and month in [11, 12, 1, 2, 3]:
            factors.append(f"低温 ({temperature:.1f}°C)")
        
        if month in [2, 3] and temperature <= -5:
            factors.append("流氷リスク")
        
        return factors if factors else ["良好な気象条件"]
    
    def _generate_recommendation(self, risk_level: str, factors: List[str], service: ScheduledService) -> str:
        """推奨事項生成"""
        if risk_level == "Critical":
            return f"⚠️ 運航困難の可能性が高いです。{service.departure_time}便の利用は避けることをお勧めします。"
        elif risk_level == "High":
            return f"⚠️ 運航に注意が必要です。{service.departure_time}便は遅延・欠航の可能性があります。"
        elif risk_level == "Medium":
            return f"⚡ 運航可能ですが注意してください。{service.departure_time}便の最新情報を確認してください。"
        else:
            return f"✅ 良好な運航条件です。{service.departure_time}便は予定通り運航される見込みです。"
    
    def display_7day_forecast(self):
        """7日間予報表示"""
        print("=" * 80)
        print("🚢 北海道フェリー 7日間運航予報")
        print("=" * 80)
        
        # システム状況表示
        prediction_params = self.adaptive_system.get_current_prediction_parameters()
        data_count = prediction_params["data_count"]
        
        print(f"📊 予測システム状況: {prediction_params['stage']} ({prediction_params['prediction_method']})")
        print(f"📈 蓄積データ数: {data_count}件 / 進捗: {prediction_params['progress']:.1%}")
        print(f"🎯 予測信頼度: {prediction_params['confidence_base']:.0%}")
        
        # 適応状況表示
        if prediction_params.get('last_adaptation'):
            print(f"⚙️ 最終適応調整: {prediction_params['last_adaptation'][:19]} ({prediction_params['adaptation_count']}回)")
        
        print()
        
        # 7日間のスケジュール生成
        services = self.generate_7day_schedule()
        
        # 日付別にグループ化
        services_by_date = {}
        for service in services:
            date_key = service.date.strftime("%Y-%m-%d")
            if date_key not in services_by_date:
                services_by_date[date_key] = []
            services_by_date[date_key].append(service)
        
        # 予報生成・表示
        for date_key in sorted(services_by_date.keys()):
            date_services = services_by_date[date_key]
            forecast_date = datetime.strptime(date_key, "%Y-%m-%d")
            
            print(f"📅 {forecast_date.strftime('%Y年%m月%d日 (%A)')}")
            print("-" * 80)
            
            # 各便の予報を非同期で生成
            forecasts = asyncio.run(self._generate_forecasts_for_date(date_services))
            
            # 航路別に表示
            routes = {}
            for forecast in forecasts:
                route_name = forecast.service.route_name
                if route_name not in routes:
                    routes[route_name] = []
                routes[route_name].append(forecast)
            
            for route_name, route_forecasts in routes.items():
                print(f"\n🛳️  {route_name}")
                
                for forecast in sorted(route_forecasts, key=lambda x: x.service.departure_time):
                    self._display_service_forecast(forecast)
            
            print("\n" + "=" * 80)
    
    async def _generate_forecasts_for_date(self, services: List[ScheduledService]) -> List[ForecastResult]:
        """指定日の全便予報生成"""
        tasks = [self.generate_forecast_for_service(service) for service in services]
        return await asyncio.gather(*tasks)
    
    def _display_service_forecast(self, forecast: ForecastResult):
        """個別便予報表示"""
        service = forecast.service
        
        # リスクレベル用絵文字
        risk_icons = {
            "Low": "🟢",
            "Medium": "🟡",
            "High": "🟠",
            "Critical": "🔴",
            "Unknown": "❓"
        }
        
        icon = risk_icons.get(forecast.risk_level, "❓")
        
        print(f"  {icon} {service.departure_time} → {service.arrival_time} "
              f"(第{service.service_number}便) "
              f"[{forecast.risk_level}: {forecast.risk_score:.0f}%]")
        
        # 気象条件表示
        weather = forecast.weather_conditions
        if weather:
            print(f"    💨 風速:{weather.get('wind_speed', 0):.1f}m/s "
                  f"🌊 波高:{weather.get('wave_height', 0):.1f}m "
                  f"👁️ 視界:{weather.get('visibility', 0):.1f}km "
                  f"🌡️ 気温:{weather.get('temperature', 0):.1f}°C")
        
        # 主要要因表示
        if forecast.primary_factors:
            factors_text = " | ".join(forecast.primary_factors)
            print(f"    📝 要因: {factors_text}")
        
        # 推奨事項表示
        print(f"    💡 {forecast.recommendation}")
        
        # 信頼度・予測手法表示
        print(f"    🎯 信頼度:{forecast.confidence:.0%} | 手法:{self._format_prediction_method(forecast.prediction_method)}")
        print()
    
    def _get_current_prediction_method(self, data_count: int) -> str:
        """現在の予測手法説明"""
        if data_count >= 200:
            return "高精度ハイブリッド予測（実績データ + 機械学習）"
        elif data_count >= 50:
            return "改良予測（基本機械学習 + ルールベース）"
        else:
            return "初期予測（気象条件ルールベース）"
    
    def _get_confidence_description(self, data_count: int) -> str:
        """信頼度説明"""
        if data_count >= 500:
            return "最高 (500+件の実績データ)"
        elif data_count >= 200:
            return "高 (200+件の学習データ)"
        elif data_count >= 50:
            return "中 (50+件の基礎データ)"
        else:
            return f"低 ({data_count}件のデータ不足)"
    
    def _format_prediction_method(self, method: str) -> str:
        """予測手法の日本語表示"""
        method_names = {
            "initial_rules": "初期ルール",
            "hybrid": "ハイブリッド",
            "ml_only": "機械学習",
            "error": "エラー"
        }
        return method_names.get(method, method)
    
    def export_forecast_to_json(self, output_file: str = "7day_ferry_forecast.json"):
        """予報結果をJSONで出力"""
        try:
            services = self.generate_7day_schedule()
            forecasts = asyncio.run(self._generate_forecasts_for_date(services))
            
            export_data = {
                "generated_at": datetime.now().isoformat(),
                "data_status": self.data_manager.get_current_status(),
                "forecast_period": {
                    "start": services[0].date.isoformat() if services else None,
                    "end": services[-1].date.isoformat() if services else None
                },
                "forecasts": []
            }
            
            for forecast in forecasts:
                forecast_dict = {
                    "date": forecast.service.date.strftime("%Y-%m-%d"),
                    "route": forecast.service.route_name,
                    "departure_time": forecast.service.departure_time,
                    "arrival_time": forecast.service.arrival_time,
                    "service_number": forecast.service.service_number,
                    "risk_level": forecast.risk_level,
                    "risk_score": forecast.risk_score,
                    "weather_conditions": forecast.weather_conditions,
                    "primary_factors": forecast.primary_factors,
                    "recommendation": forecast.recommendation,
                    "confidence": forecast.confidence,
                    "prediction_method": forecast.prediction_method
                }
                export_data["forecasts"].append(forecast_dict)
            
            output_path = self.data_dir / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"📄 予報データを出力しました: {output_path}")
            
        except Exception as e:
            print(f"JSON出力エラー: {e}")

def main():
    """メイン実行"""
    print("🚢 北海道フェリー運航予報システム")
    
    ui_system = FerryForecastUI()
    
    try:
        print("\n実行オプション:")
        print("1. 7日間予報表示（推奨）")
        print("2. JSON形式で予報出力") 
        print("3. データ収集状況確認")
        
        choice = input("選択 (1-3): ").strip()
        
        if choice == "1":
            ui_system.display_7day_forecast()
        elif choice == "2":
            ui_system.display_7day_forecast()
            ui_system.export_forecast_to_json()
        elif choice == "3":
            data_status = ui_system.data_manager.get_current_status()
            print("\nデータ収集状況:")
            print(json.dumps(data_status, ensure_ascii=False, indent=2))
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n実行を中断しました")
    except Exception as e:
        print(f"実行エラー: {e}")

if __name__ == "__main__":
    main()