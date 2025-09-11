#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
航空気象データAPI統合モジュール
Aviation Weather Data API Integration Module

利尻空港向けの航空気象データを複数ソースから統合取得
"""

import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import asyncio
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AviationWeatherData:
    """航空気象データ"""
    timestamp: datetime
    airport_code: str
    wind_direction: Optional[int]
    wind_speed: Optional[float]
    wind_gust: Optional[float]
    visibility: Optional[float]
    cloud_ceiling: Optional[int]
    temperature: Optional[float]
    dewpoint: Optional[float]
    pressure: Optional[float]
    weather_phenomena: List[str]
    raw_metar: Optional[str]
    raw_taf: Optional[str]

class AviationWeatherAPI:
    """航空気象データAPI統合クラス"""
    
    def __init__(self):
        # 利尻空港情報
        self.rishiri_airport = {
            'icao_code': 'RJER',
            'iata_code': 'RIS', 
            'name': '利尻空港',
            'latitude': 45.2421,
            'longitude': 141.1864,
            'elevation': 40  # meters
        }
        
        # APIエンドポイント
        self.api_endpoints = {
            'jma_aviation': 'https://www.data.jma.go.jp/airinfo/data/',
            'aviationweather_gov': 'https://aviationweather.gov/api/data/',
            'checkwx': 'https://api.checkwx.com/',
            'metar_taf_com': 'https://metar-taf.com/api/',
            'openweather_aviation': 'https://api.openweathermap.org/data/2.5/',
        }
        
        # APIキー（設定が必要）
        self.api_keys = {
            'checkwx': None,  # 要設定
            'openweather': None,  # 要設定
            'metar_taf_com': None  # 要設定
        }
        
    async def get_jma_aviation_data(self) -> Optional[AviationWeatherData]:
        """気象庁航空気象データ取得"""
        try:
            # 気象庁の航空気象情報から利尻空港データ取得
            url = f"{self.api_endpoints['jma_aviation']}awfo_taf.html"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        return self._parse_jma_aviation_data(html_content)
            
        except Exception as e:
            logger.error(f"気象庁航空気象データ取得エラー: {e}")
            return None
    
    async def get_aviationweather_gov_data(self) -> Optional[AviationWeatherData]:
        """NOAA Aviation Weather データ取得"""
        try:
            # NOAA Aviation Weather Service API
            metar_url = f"{self.api_endpoints['aviationweather_gov']}metar"
            taf_url = f"{self.api_endpoints['aviationweather_gov']}taf"
            
            params = {
                'ids': self.rishiri_airport['icao_code'],
                'format': 'json',
                'hours': 2
            }
            
            async with aiohttp.ClientSession() as session:
                # METAR取得
                async with session.get(metar_url, params=params) as response:
                    if response.status == 200:
                        metar_data = await response.json()
                        
                # TAF取得
                async with session.get(taf_url, params=params) as response:
                    if response.status == 200:
                        taf_data = await response.json()
                        
                return self._parse_aviationweather_data(metar_data, taf_data)
                        
        except Exception as e:
            logger.error(f"NOAA Aviation Weather データ取得エラー: {e}")
            return None
    
    async def get_checkwx_data(self) -> Optional[AviationWeatherData]:
        """CheckWX API データ取得"""
        if not self.api_keys['checkwx']:
            logger.warning("CheckWX APIキーが設定されていません")
            return None
            
        try:
            headers = {
                'X-API-Key': self.api_keys['checkwx']
            }
            
            # METAR取得
            metar_url = f"{self.api_endpoints['checkwx']}metar/{self.rishiri_airport['icao_code']}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(metar_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_checkwx_data(data)
                        
        except Exception as e:
            logger.error(f"CheckWX データ取得エラー: {e}")
            return None
    
    async def get_integrated_aviation_weather(self) -> Dict:
        """複数ソースから航空気象データ統合取得"""
        results = {}
        
        # 並列でデータ取得
        tasks = [
            ('jma', self.get_jma_aviation_data()),
            ('noaa', self.get_aviationweather_gov_data()),
            ('checkwx', self.get_checkwx_data())
        ]
        
        for source_name, task in tasks:
            try:
                data = await task
                if data:
                    results[source_name] = data
                    logger.info(f"{source_name}からのデータ取得成功")
                else:
                    logger.warning(f"{source_name}からのデータ取得失敗")
            except Exception as e:
                logger.error(f"{source_name}データ取得エラー: {e}")
        
        # データ統合・検証
        integrated_data = self._integrate_weather_data(results)
        
        return {
            'integrated': integrated_data,
            'sources': results,
            'timestamp': datetime.now(),
            'airport': self.rishiri_airport
        }
    
    def _parse_jma_aviation_data(self, html_content: str) -> Optional[AviationWeatherData]:
        """気象庁航空気象データ解析"""
        try:
            # HTMLから利尻空港のMETAR/TAFデータを抽出
            # 実装注意: 気象庁のHTMLフォーマットに依存
            
            # 簡易実装例（実際はHTMLパーサーが必要）
            if 'RJER' in html_content:
                # METARデータ抽出ロジック
                return AviationWeatherData(
                    timestamp=datetime.now(),
                    airport_code='RJER',
                    wind_direction=None,
                    wind_speed=None,
                    wind_gust=None,
                    visibility=None,
                    cloud_ceiling=None,
                    temperature=None,
                    dewpoint=None,
                    pressure=None,
                    weather_phenomena=[],
                    raw_metar=None,
                    raw_taf=None
                )
            
        except Exception as e:
            logger.error(f"気象庁データ解析エラー: {e}")
            return None
    
    def _parse_aviationweather_data(self, metar_data: Dict, taf_data: Dict) -> Optional[AviationWeatherData]:
        """NOAA Aviation Weather データ解析"""
        try:
            if not metar_data or len(metar_data) == 0:
                return None
                
            latest_metar = metar_data[0]  # 最新データ
            
            return AviationWeatherData(
                timestamp=datetime.fromisoformat(latest_metar.get('obsTime', '')),
                airport_code=latest_metar.get('icaoId', ''),
                wind_direction=latest_metar.get('wdir'),
                wind_speed=latest_metar.get('wspd'),
                wind_gust=latest_metar.get('wgst'),
                visibility=latest_metar.get('visib'),
                cloud_ceiling=latest_metar.get('ceiling'),
                temperature=latest_metar.get('temp'),
                dewpoint=latest_metar.get('dewp'),
                pressure=latest_metar.get('altim'),
                weather_phenomena=latest_metar.get('wxString', '').split(),
                raw_metar=latest_metar.get('rawOb', ''),
                raw_taf=taf_data[0].get('rawTAF', '') if taf_data else None
            )
            
        except Exception as e:
            logger.error(f"NOAA データ解析エラー: {e}")
            return None
    
    def _parse_checkwx_data(self, data: Dict) -> Optional[AviationWeatherData]:
        """CheckWX データ解析"""
        try:
            if not data or 'data' not in data:
                return None
                
            metar_data = data['data'][0]
            
            return AviationWeatherData(
                timestamp=datetime.fromisoformat(metar_data.get('observed', '')),
                airport_code=metar_data.get('icao', ''),
                wind_direction=metar_data.get('wind', {}).get('degrees'),
                wind_speed=metar_data.get('wind', {}).get('speed_kts'),
                wind_gust=metar_data.get('wind', {}).get('gust_kts'),
                visibility=metar_data.get('visibility', {}).get('meters_float'),
                cloud_ceiling=metar_data.get('ceiling', {}).get('feet'),
                temperature=metar_data.get('temperature', {}).get('celsius'),
                dewpoint=metar_data.get('dewpoint', {}).get('celsius'),
                pressure=metar_data.get('barometer', {}).get('hpa'),
                weather_phenomena=metar_data.get('conditions', []),
                raw_metar=metar_data.get('raw_text', ''),
                raw_taf=None
            )
            
        except Exception as e:
            logger.error(f"CheckWX データ解析エラー: {e}")
            return None
    
    def _integrate_weather_data(self, sources: Dict) -> Optional[AviationWeatherData]:
        """複数ソースのデータ統合"""
        if not sources:
            return None
        
        # 優先順位: 気象庁 > NOAA > CheckWX
        priority_sources = ['jma', 'noaa', 'checkwx']
        
        base_data = None
        for source in priority_sources:
            if source in sources and sources[source]:
                base_data = sources[source]
                break
        
        if not base_data:
            return None
        
        # データ補完・検証
        integrated = base_data
        
        # 他のソースからの補完データ
        for source_name, source_data in sources.items():
            if source_data and source_data != base_data:
                # データ品質チェック・補完ロジック
                integrated = self._merge_weather_data(integrated, source_data)
        
        return integrated
    
    def _merge_weather_data(self, primary: AviationWeatherData, secondary: AviationWeatherData) -> AviationWeatherData:
        """気象データのマージ"""
        # 欠損値の補完
        merged = primary
        
        if merged.wind_direction is None and secondary.wind_direction is not None:
            merged.wind_direction = secondary.wind_direction
        
        if merged.wind_speed is None and secondary.wind_speed is not None:
            merged.wind_speed = secondary.wind_speed
        
        if merged.visibility is None and secondary.visibility is not None:
            merged.visibility = secondary.visibility
        
        if merged.temperature is None and secondary.temperature is not None:
            merged.temperature = secondary.temperature
        
        return merged

class RishiriAirportPredictor:
    """利尻空港向け欠航予測エンジン"""
    
    def __init__(self):
        self.weather_api = AviationWeatherAPI()
        
        # 利尻空港特有の運航制限値
        self.operational_limits = {
            'wind_speed': {
                'caution': 15,      # kt
                'warning': 25,      # kt  
                'critical': 35      # kt
            },
            'crosswind': {
                'caution': 15,      # kt
                'warning': 25,      # kt
                'critical': 30      # kt
            },
            'visibility': {
                'critical': 1600,   # meters
                'warning': 3200,    # meters
                'caution': 5000     # meters
            },
            'ceiling': {
                'critical': 200,    # feet
                'warning': 500,     # feet
                'caution': 1000     # feet
            }
        }
        
        # 地形効果パラメータ
        self.terrain_effects = {
            'mountain_height': 1721,  # 利尻山標高
            'runway_orientation': [70, 250],  # 07/25
            'karman_vortex_threshold': 10  # 風速閾値
        }
    
    async def predict_flight_risk(self, hours_ahead: int = 24) -> Dict:
        """航空便欠航リスク予測"""
        try:
            # 現在の気象データ取得
            current_weather = await self.weather_api.get_integrated_aviation_weather()
            
            if not current_weather['integrated']:
                return {'error': '気象データ取得失敗'}
            
            # リスク評価
            risks = self._assess_aviation_risks(current_weather['integrated'])
            
            # 地形効果評価
            terrain_risks = self._assess_terrain_effects(current_weather['integrated'])
            
            # 統合リスク計算
            integrated_risk = self._calculate_integrated_risk(risks, terrain_risks)
            
            return {
                'timestamp': datetime.now(),
                'airport': 'RJER (利尻空港)',
                'current_weather': current_weather,
                'basic_risks': risks,
                'terrain_risks': terrain_risks,
                'integrated_risk': integrated_risk,
                'recommendation': self._generate_recommendation(integrated_risk)
            }
            
        except Exception as e:
            logger.error(f"航空便リスク予測エラー: {e}")
            return {'error': str(e)}
    
    def _assess_aviation_risks(self, weather: AviationWeatherData) -> Dict:
        """基本航空気象リスク評価"""
        risks = {}
        
        # 風速リスク
        if weather.wind_speed:
            if weather.wind_speed >= self.operational_limits['wind_speed']['critical']:
                risks['wind'] = 'critical'
            elif weather.wind_speed >= self.operational_limits['wind_speed']['warning']:
                risks['wind'] = 'warning'
            elif weather.wind_speed >= self.operational_limits['wind_speed']['caution']:
                risks['wind'] = 'caution'
            else:
                risks['wind'] = 'safe'
        
        # 視界リスク
        if weather.visibility:
            if weather.visibility <= self.operational_limits['visibility']['critical']:
                risks['visibility'] = 'critical'
            elif weather.visibility <= self.operational_limits['visibility']['warning']:
                risks['visibility'] = 'warning'
            elif weather.visibility <= self.operational_limits['visibility']['caution']:
                risks['visibility'] = 'caution'
            else:
                risks['visibility'] = 'safe'
        
        # 雲高リスク
        if weather.cloud_ceiling:
            if weather.cloud_ceiling <= self.operational_limits['ceiling']['critical']:
                risks['ceiling'] = 'critical'
            elif weather.cloud_ceiling <= self.operational_limits['ceiling']['warning']:
                risks['ceiling'] = 'warning'
            elif weather.cloud_ceiling <= self.operational_limits['ceiling']['caution']:
                risks['ceiling'] = 'caution'
            else:
                risks['ceiling'] = 'safe'
        
        return risks
    
    def _assess_terrain_effects(self, weather: AviationWeatherData) -> Dict:
        """地形効果リスク評価"""
        terrain_risks = {}
        
        if weather.wind_speed and weather.wind_direction:
            # カルマン渦リスク
            karman_risk = self._calculate_karman_vortex_risk(
                weather.wind_speed, weather.wind_direction
            )
            terrain_risks['karman_vortex'] = karman_risk
            
            # 横風成分計算
            crosswind = self._calculate_crosswind_component(
                weather.wind_speed, weather.wind_direction
            )
            terrain_risks['crosswind'] = crosswind
            
            # 山岳波リスク
            mountain_wave_risk = self._assess_mountain_wave_risk(
                weather.wind_speed, weather.wind_direction
            )
            terrain_risks['mountain_wave'] = mountain_wave_risk
        
        return terrain_risks
    
    def _calculate_karman_vortex_risk(self, wind_speed: float, wind_direction: int) -> str:
        """カルマン渦リスク計算"""
        # 利尻山からの風向（北西〜西風でリスク高）
        if 270 <= wind_direction <= 330 and wind_speed >= self.terrain_effects['karman_vortex_threshold']:
            if wind_speed >= 20:
                return 'critical'
            elif wind_speed >= 15:
                return 'warning'
            else:
                return 'caution'
        return 'safe'
    
    def _calculate_crosswind_component(self, wind_speed: float, wind_direction: int) -> float:
        """横風成分計算"""
        import math
        
        runway_headings = self.terrain_effects['runway_orientation']
        
        # より有利な滑走路を選択
        crosswind_components = []
        for heading in runway_headings:
            angle_diff = abs(wind_direction - heading)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            
            crosswind = wind_speed * math.sin(math.radians(angle_diff))
            crosswind_components.append(abs(crosswind))
        
        return min(crosswind_components)  # 最小横風成分
    
    def _assess_mountain_wave_risk(self, wind_speed: float, wind_direction: int) -> str:
        """山岳波リスク評価"""
        # 利尻山を越える風向（北西〜北風）での山岳波リスク
        if 300 <= wind_direction <= 360 or 0 <= wind_direction <= 30:
            if wind_speed >= 25:
                return 'critical'
            elif wind_speed >= 20:
                return 'warning'
            elif wind_speed >= 15:
                return 'caution'
        return 'safe'
    
    def _calculate_integrated_risk(self, basic_risks: Dict, terrain_risks: Dict) -> Dict:
        """統合リスク計算"""
        risk_scores = {
            'safe': 0,
            'caution': 25,
            'warning': 50,
            'critical': 100
        }
        
        # 基本リスクスコア
        basic_score = 0
        for risk_type, level in basic_risks.items():
            basic_score += risk_scores.get(level, 0)
        
        # 地形効果リスクスコア
        terrain_score = 0
        karman_risk = terrain_risks.get('karman_vortex', 'safe')
        mountain_wave_risk = terrain_risks.get('mountain_wave', 'safe')
        
        terrain_score += risk_scores.get(karman_risk, 0) * 0.3
        terrain_score += risk_scores.get(mountain_wave_risk, 0) * 0.2
        
        # 横風リスク
        crosswind = terrain_risks.get('crosswind', 0)
        if crosswind >= 30:
            terrain_score += 100
        elif crosswind >= 25:
            terrain_score += 75
        elif crosswind >= 15:
            terrain_score += 50
        
        # 統合スコア
        total_score = (basic_score * 0.7) + (terrain_score * 0.3)
        
        # リスクレベル判定
        if total_score >= 80:
            risk_level = 'critical'
        elif total_score >= 60:
            risk_level = 'high'
        elif total_score >= 40:
            risk_level = 'medium'
        elif total_score >= 20:
            risk_level = 'low'
        else:
            risk_level = 'minimal'
        
        return {
            'score': round(total_score, 1),
            'level': risk_level,
            'basic_score': round(basic_score, 1),
            'terrain_score': round(terrain_score, 1)
        }
    
    def _generate_recommendation(self, integrated_risk: Dict) -> str:
        """運航推奨事項生成"""
        risk_level = integrated_risk['level']
        
        recommendations = {
            'minimal': '気象条件良好。正常運航が可能です。',
            'low': '概ね良好な条件。通常運航を継続してください。',
            'medium': '注意が必要な気象条件。運航判断時に慎重な検討を推奨します。',
            'high': '危険な気象条件。運航には細心の注意が必要です。',
            'critical': '極めて危険な条件。運航中止を強く推奨します。'
        }
        
        return recommendations.get(risk_level, '気象条件の詳細な確認が必要です。')

# 使用例
async def main():
    """メイン実行例"""
    predictor = RishiriAirportPredictor()
    
    print("=== 利尻空港航空便欠航予測 ===")
    
    try:
        result = await predictor.predict_flight_risk()
        
        if 'error' in result:
            print(f"エラー: {result['error']}")
        else:
            print(f"空港: {result['airport']}")
            print(f"統合リスク: {result['integrated_risk']['level']} (スコア: {result['integrated_risk']['score']})")
            print(f"推奨事項: {result['recommendation']}")
            
            if result['current_weather']['integrated']:
                weather = result['current_weather']['integrated']
                print(f"現在の気象: 風速{weather.wind_speed}kt, 視界{weather.visibility}m")
    
    except Exception as e:
        print(f"予測エラー: {e}")

if __name__ == "__main__":
    asyncio.run(main())