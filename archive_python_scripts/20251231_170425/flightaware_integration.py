#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlightAware API統合システム
FlightAware API Integration System

90日分の利尻空港運航データ取得と分析
"""

import requests
import json
import csv
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import logging
from pathlib import Path
import os
from dataclasses import dataclass
from billing_protection_system import ProtectedFlightAwareClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FlightData:
    """フライトデータクラス"""
    flight_id: str
    airline: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    scheduled_departure: datetime
    actual_departure: Optional[datetime]
    scheduled_arrival: datetime
    actual_arrival: Optional[datetime]
    status: str
    delay_minutes: int
    cancelled: bool
    cancellation_reason: Optional[str]
    aircraft_type: Optional[str]

class FlightAwareAPI:
    """FlightAware API統合クラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://aeroapi.flightaware.com/aeroapi"
        self.headers = {
            "x-apikey": api_key or "YOUR_API_KEY_HERE"
        }
        
        # 利尻空港関連の空港コード
        self.airports = {
            "rishiri": {"icao": "RJER", "iata": "RIS", "name": "利尻空港"},
            "okadama": {"icao": "RJCO", "iata": "OKD", "name": "札幌丘珠空港"},
            "chitose": {"icao": "RJCC", "iata": "CTS", "name": "新千歳空港"}
        }
        
        # データ保存ディレクトリ
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # 出力ファイル
        self.flight_data_file = self.data_dir / "rishiri_flight_history.csv"
        
    def setup_api_key(self):
        """APIキー設定ガイド"""
        setup_guide = """
        🔑 FlightAware API設定手順:
        
        1. FlightAware AeroAPIアカウント作成
           https://www.flightaware.com/commercial/aeroapi/
        
        2. Personal Planを選択（月$5まで無料）
           
        3. APIキーを取得
        
        4. 環境変数またはファイルでAPIキー設定
           - 環境変数: FLIGHTAWARE_API_KEY
           - または config/api_keys.json
        
        5. APIキーをこのコードに設定
        
        注意: 無料枠（月$5）を超過すると課金されます
        """
        
        print(setup_guide)
        
        # 設定ファイル確認
        config_file = Path("config") / "api_keys.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if "flightaware" in config:
                        self.api_key = config["flightaware"]
                        self.headers["x-apikey"] = self.api_key
                        print("✅ APIキーを設定ファイルから読み込みました")
                        return True
            except Exception as e:
                print(f"⚠️ 設定ファイル読み込みエラー: {e}")
        
        # 環境変数確認
        env_key = os.getenv("FLIGHTAWARE_API_KEY")
        if env_key:
            self.api_key = env_key
            self.headers["x-apikey"] = self.api_key
            print("✅ APIキーを環境変数から読み込みました")
            return True
        
        print("❌ APIキーが設定されていません。上記手順に従って設定してください。")
        return False
    
    def test_api_connection(self) -> bool:
        """API接続テスト"""
        try:
            # FlightAware API status endpoint
            url = f"{self.base_url}/flights/search/advanced"
            params = {
                "query": "-destination RJER -maxPages 1"
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ FlightAware API接続成功")
                return True
            elif response.status_code == 401:
                logger.error("❌ APIキーが無効です")
                return False
            elif response.status_code == 403:
                logger.error("❌ API使用制限に達しています")
                return False
            else:
                logger.error(f"❌ API接続エラー: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 接続エラー: {e}")
            return False
    
    def get_airport_flights(self, airport_code: str, start_date: datetime, 
                          end_date: datetime, direction: str = "departures") -> List[Dict]:
        """空港の運航データ取得"""
        
        flights_data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                # API endpoint
                url = f"{self.base_url}/airports/{airport_code}/flights/{direction}"
                
                params = {
                    "start": current_date.isoformat(),
                    "end": (current_date + timedelta(days=1)).isoformat(),
                    "max_pages": 5
                }
                
                logger.info(f"取得中: {airport_code} {direction} {current_date.date()}")
                
                response = requests.get(url, headers=self.headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "flights" in data:
                        for flight in data["flights"]:
                            flights_data.append(flight)
                        logger.info(f"✅ {len(data['flights'])}便のデータを取得")
                    else:
                        logger.info("📭 該当する便がありません")
                        
                elif response.status_code == 429:
                    logger.warning("⏳ API制限に達しました。60秒待機...")
                    time.sleep(60)
                    continue
                    
                else:
                    logger.error(f"❌ APIエラー: {response.status_code}")
                
                # API制限を避けるため少し待機
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"データ取得エラー: {e}")
            
            current_date += timedelta(days=1)
        
        return flights_data
    
    def collect_rishiri_flight_history(self, days_back: int = 90) -> Dict:
        """利尻空港90日分のフライト履歴収集"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"📊 利尻空港フライト履歴収集開始: {start_date.date()} - {end_date.date()}")
        
        all_flights = []
        
        # 利尻空港発便
        departures = self.get_airport_flights("RJER", start_date, end_date, "departures")
        for flight in departures:
            flight["direction"] = "departure"
        all_flights.extend(departures)
        
        # 利尻空港着便
        arrivals = self.get_airport_flights("RJER", start_date, end_date, "arrivals")
        for flight in arrivals:
            flight["direction"] = "arrival"
        all_flights.extend(arrivals)
        
        logger.info(f"📋 総収集件数: {len(all_flights)}便")
        
        return {
            "total_flights": len(all_flights),
            "period": f"{start_date.date()} - {end_date.date()}",
            "flights": all_flights,
            "collection_timestamp": datetime.now()
        }
    
    def process_flight_data(self, raw_flights: List[Dict]) -> List[FlightData]:
        """生データをFlightDataオブジェクトに変換"""
        
        processed_flights = []
        
        for flight in raw_flights:
            try:
                # 基本情報取得
                flight_id = flight.get("fa_flight_id", "")
                airline = flight.get("operator", "").split()[0] if flight.get("operator") else ""
                flight_number = flight.get("flight_number", "")
                
                # 空港情報
                departure_airport = flight.get("origin", {}).get("code", "")
                arrival_airport = flight.get("destination", {}).get("code", "")
                
                # 時刻情報
                scheduled_departure = self._parse_datetime(flight.get("scheduled_out"))
                actual_departure = self._parse_datetime(flight.get("actual_out"))
                scheduled_arrival = self._parse_datetime(flight.get("scheduled_in"))
                actual_arrival = self._parse_datetime(flight.get("actual_in"))
                
                # ステータス情報
                status = flight.get("status", "")
                cancelled = status in ["Cancelled", "Canceled"]
                
                # 遅延計算
                delay_minutes = 0
                if actual_departure and scheduled_departure:
                    delay_minutes = int((actual_departure - scheduled_departure).total_seconds() / 60)
                
                # 欠航理由
                cancellation_reason = None
                if cancelled:
                    cancellation_reason = flight.get("cancellation_reason", "Weather")
                
                # 機材情報
                aircraft_type = flight.get("aircraft_type", "")
                
                flight_data = FlightData(
                    flight_id=flight_id,
                    airline=airline,
                    flight_number=flight_number,
                    departure_airport=departure_airport,
                    arrival_airport=arrival_airport,
                    scheduled_departure=scheduled_departure,
                    actual_departure=actual_departure,
                    scheduled_arrival=scheduled_arrival,
                    actual_arrival=actual_arrival,
                    status=status,
                    delay_minutes=delay_minutes,
                    cancelled=cancelled,
                    cancellation_reason=cancellation_reason,
                    aircraft_type=aircraft_type
                )
                
                processed_flights.append(flight_data)
                
            except Exception as e:
                logger.error(f"フライトデータ処理エラー: {e}")
                continue
        
        return processed_flights
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """日時文字列をdatetimeオブジェクトに変換"""
        if not datetime_str:
            return None
        
        try:
            # ISO format parsing
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except:
            try:
                # Alternative format
                return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
            except:
                return None
    
    def save_to_csv(self, flights: List[FlightData]) -> str:
        """データをCSVファイルに保存"""
        
        csv_data = []
        
        for flight in flights:
            csv_data.append({
                "flight_id": flight.flight_id,
                "airline": flight.airline,
                "flight_number": flight.flight_number,
                "departure_airport": flight.departure_airport,
                "arrival_airport": flight.arrival_airport,
                "scheduled_departure": flight.scheduled_departure.isoformat() if flight.scheduled_departure else "",
                "actual_departure": flight.actual_departure.isoformat() if flight.actual_departure else "",
                "scheduled_arrival": flight.scheduled_arrival.isoformat() if flight.scheduled_arrival else "",
                "actual_arrival": flight.actual_arrival.isoformat() if flight.actual_arrival else "",
                "status": flight.status,
                "delay_minutes": flight.delay_minutes,
                "cancelled": flight.cancelled,
                "cancellation_reason": flight.cancellation_reason or "",
                "aircraft_type": flight.aircraft_type or ""
            })
        
        # CSV出力
        df = pd.DataFrame(csv_data)
        df.to_csv(self.flight_data_file, index=False, encoding='utf-8')
        
        logger.info(f"📁 データを保存しました: {self.flight_data_file}")
        return str(self.flight_data_file)
    
    def analyze_flight_data(self, flights: List[FlightData]) -> Dict:
        """収集したフライトデータの分析"""
        
        if not flights:
            return {"error": "分析対象データがありません"}
        
        # 基本統計
        total_flights = len(flights)
        cancelled_flights = len([f for f in flights if f.cancelled])
        delayed_flights = len([f for f in flights if f.delay_minutes > 15])
        
        cancellation_rate = (cancelled_flights / total_flights * 100) if total_flights > 0 else 0
        delay_rate = (delayed_flights / total_flights * 100) if total_flights > 0 else 0
        
        # 航空会社別分析
        airlines = {}
        for flight in flights:
            if flight.airline not in airlines:
                airlines[flight.airline] = {"total": 0, "cancelled": 0, "delayed": 0}
            
            airlines[flight.airline]["total"] += 1
            if flight.cancelled:
                airlines[flight.airline]["cancelled"] += 1
            if flight.delay_minutes > 15:
                airlines[flight.airline]["delayed"] += 1
        
        # 路線別分析
        routes = {}
        for flight in flights:
            route = f"{flight.departure_airport}-{flight.arrival_airport}"
            if route not in routes:
                routes[route] = {"total": 0, "cancelled": 0, "delayed": 0}
            
            routes[route]["total"] += 1
            if flight.cancelled:
                routes[route]["cancelled"] += 1
            if flight.delay_minutes > 15:
                routes[route]["delayed"] += 1
        
        # 欠航理由分析
        cancellation_reasons = {}
        for flight in flights:
            if flight.cancelled and flight.cancellation_reason:
                reason = flight.cancellation_reason
                cancellation_reasons[reason] = cancellation_reasons.get(reason, 0) + 1
        
        return {
            "period_summary": {
                "total_flights": total_flights,
                "cancelled_flights": cancelled_flights,
                "delayed_flights": delayed_flights,
                "cancellation_rate": round(cancellation_rate, 2),
                "delay_rate": round(delay_rate, 2)
            },
            "airline_analysis": airlines,
            "route_analysis": routes,
            "cancellation_reasons": cancellation_reasons,
            "data_quality": {
                "complete_records": len([f for f in flights if f.scheduled_departure and f.departure_airport]),
                "missing_actual_times": len([f for f in flights if not f.actual_departure and not f.cancelled])
            }
        }
    
    def find_september_1_flight(self, flights: List[FlightData]) -> Optional[FlightData]:
        """9月1日14時台の便を検索"""
        
        target_date = datetime(2025, 9, 1)
        
        for flight in flights:
            if (flight.scheduled_departure and 
                flight.scheduled_departure.date() == target_date.date() and
                flight.scheduled_departure.hour >= 13 and flight.scheduled_departure.hour <= 15 and
                flight.departure_airport == "RJER"):
                
                return flight
        
        return None

class RishiriFlightCollector:
    """利尻空港フライトデータ収集メインクラス"""
    
    def __init__(self):
        self.flightaware = FlightAwareAPI()
        
    def run_full_collection(self) -> Dict:
        """フル収集プロセス実行"""
        
        print("[START] 利尻空港フライトデータ収集開始")
        
        # Step 1: API設定確認
        if not self.flightaware.setup_api_key():
            return {"error": "APIキー設定が必要です"}
        
        # Step 2: 接続テスト
        if not self.flightaware.test_api_connection():
            return {"error": "API接続に失敗しました"}
        
        # Step 3: データ収集
        raw_data = self.flightaware.collect_rishiri_flight_history(90)
        
        # Step 4: データ処理
        processed_flights = self.flightaware.process_flight_data(raw_data["flights"])
        
        # Step 5: CSV保存
        csv_file = self.flightaware.save_to_csv(processed_flights)
        
        # Step 6: 分析実行
        analysis = self.flightaware.analyze_flight_data(processed_flights)
        
        # Step 7: 9月1日便検索
        september_1_flight = self.flightaware.find_september_1_flight(processed_flights)
        
        result = {
            "collection_summary": raw_data,
            "processed_flights": len(processed_flights),
            "analysis": analysis,
            "csv_file": csv_file,
            "september_1_verification": september_1_flight
        }
        
        self._print_summary(result)
        
        return result
    
    def _print_summary(self, result: Dict):
        """結果サマリー表示"""
        
        print("\n" + "="*50)
        print("📊 利尻空港フライトデータ収集結果")
        print("="*50)
        
        if "error" in result:
            print(f"❌ エラー: {result['error']}")
            return
        
        analysis = result["analysis"]
        period = analysis["period_summary"]
        
        print(f"📅 収集期間: {result['collection_summary']['period']}")
        print(f"✈️ 総フライト数: {period['total_flights']}便")
        print(f"❌ 欠航便数: {period['cancelled_flights']}便 ({period['cancellation_rate']}%)")
        print(f"⏰ 遅延便数: {period['delayed_flights']}便 ({period['delay_rate']}%)")
        
        print(f"\n📁 データファイル: {result['csv_file']}")
        
        if result["september_1_verification"]:
            flight = result["september_1_verification"]
            print(f"\n🔍 9月1日該当便発見:")
            print(f"   便名: {flight.flight_number}")
            print(f"   予定: {flight.scheduled_departure}")
            print(f"   状況: {'欠航' if flight.cancelled else '運航'}")
        else:
            print(f"\n❓ 9月1日該当便: 見つかりませんでした")

def main():
    """メイン実行"""
    collector = RishiriFlightCollector()
    result = collector.run_full_collection()
    
    if "error" not in result:
        print(f"\n[SUCCESS] データ収集完了！次のステップに進めます。")

if __name__ == "__main__":
    main()