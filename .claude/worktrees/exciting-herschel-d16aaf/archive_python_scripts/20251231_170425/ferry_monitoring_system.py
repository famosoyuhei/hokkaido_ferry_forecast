#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ハートランドフェリー欠航監視システム
Heartland Ferry Cancellation Monitoring System

ハートランドフェリーの運航状況を定期監視し、
欠航情報を自動的にCSVファイルに記録する。
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import time
from datetime import datetime, timedelta
import asyncio
import aiohttp
import logging
import schedule
from pathlib import Path
import pandas as pd
from typing import Dict, List, Optional, Tuple

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ferry_monitoring.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FerryMonitoringSystem:
    """フェリー欠航監視システム"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # CSVファイルパス
        self.csv_file = self.data_dir / "ferry_cancellation_log.csv"
        
        # データ収集制限
        self.max_data_count = 500
        self.auto_stop_enabled = True
        
        # 通知システム
        try:
            from discord_notification_system import DiscordNotificationSystem
            self.discord_system = DiscordNotificationSystem(self.data_dir)
            self.discord_enabled = True
        except ImportError:
            self.discord_system = None
            self.discord_enabled = False
            logger.warning("Discord通知システムは利用できません")
            
        try:
            from line_notification_system import LINENotificationSystem
            self.line_system = LINENotificationSystem(self.data_dir)
            self.line_enabled = True
        except ImportError:
            self.line_system = None
            self.line_enabled = False
            logger.warning("LINE通知システムは利用できません")
        
        # 監視対象URL
        self.status_url = "https://heartlandferry.jp/status/"
        self.timetable_urls = {
            "wakkanai_oshidomari": "https://heartlandferry.jp/timetable/",
            "wakkanai_kutsugata": "https://heartlandferry.jp/timetable/",
            "wakkanai_kafuka": "https://heartlandferry.jp/timetable/time1/"
        }
        
        # 航路情報
        self.routes = self._load_route_config()
        
        # 前回の運航状況（変化検知用）
        self.previous_status = {}
        
        # 気象データAPI設定
        self.weather_api_key = None  # 必要に応じて設定
        
        # CSV初期化
        self._initialize_csv()
        
    def _load_route_config(self) -> Dict:
        """航路設定読み込み"""
        config_file = self.base_dir / "config" / "ferry_routes.json"
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config["ferry_routes"]
        except FileNotFoundError:
            logger.warning("航路設定ファイルが見つかりません。デフォルト設定を使用します。")
            return self._get_default_routes()
    
    def _get_default_routes(self) -> Dict:
        """デフォルト航路設定"""
        return {
            "wakkanai_oshidomari": {
                "route_name": "稚内 - 鴛泊",
                "departure": {"port": "稚内港", "lat": 45.4094, "lon": 141.6739},
                "arrival": {"port": "鴛泊港", "lat": 45.2398, "lon": 141.2042}
            },
            "wakkanai_kutsugata": {
                "route_name": "稚内 - 沓形", 
                "departure": {"port": "稚内港", "lat": 45.4094, "lon": 141.6739},
                "arrival": {"port": "沓形港", "lat": 45.2480, "lon": 141.2198}
            },
            "wakkanai_kafuka": {
                "route_name": "稚内 - 香深",
                "departure": {"port": "稚内港", "lat": 45.4094, "lon": 141.6739},
                "arrival": {"port": "香深港", "lat": 45.3456, "lon": 141.0311}
            }
        }
    
    def _initialize_csv(self):
        """CSVファイル初期化"""
        if not self.csv_file.exists():
            headers = [
                "日付", "出航予定時刻", "出航場所", "着予定時刻", "着場所",
                "運航状況", "欠航理由", "便名", "検知時刻", 
                "風速_ms", "波高_m", "視界_km", "気温_c", "備考"
            ]
            
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            
            logger.info(f"CSVファイルを初期化しました: {self.csv_file}")
    
    async def check_ferry_status(self) -> Dict:
        """フェリー運航状況チェック"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.status_url, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"ステータスページ取得失敗: {response.status}")
                        return {}
                    
                    html = await response.text()
                    return self._parse_status_page(html)
                    
        except Exception as e:
            logger.error(f"運航状況チェックでエラー: {e}")
            return {}
    
    def _parse_status_page(self, html: str) -> Dict:
        """運航状況ページ解析"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            status_info = {}
            
            # 利尻・礼文航路の情報を取得
            # ※実際のHTML構造に合わせて調整が必要
            status_elements = soup.find_all(['div', 'p', 'span'], 
                                          text=lambda text: text and ('運航' in text or '欠航' in text))
            
            for element in status_elements:
                text = element.get_text().strip()
                if '平常通りの運航' in text:
                    status_info['status'] = '通常運航'
                    status_info['message'] = text
                elif '欠航' in text:
                    status_info['status'] = '欠航'
                    status_info['message'] = text
                elif '遅延' in text:
                    status_info['status'] = '遅延'
                    status_info['message'] = text
            
            # デフォルト設定
            if not status_info:
                status_info = {
                    'status': '情報なし',
                    'message': 'ステータス情報を取得できませんでした'
                }
            
            return status_info
            
        except Exception as e:
            logger.error(f"ステータスページ解析でエラー: {e}")
            return {'status': 'エラー', 'message': str(e)}
    
    async def get_weather_data(self, lat: float, lon: float) -> Dict:
        """気象データ取得（OpenWeatherMap等のAPI使用）"""
        try:
            # 気象データAPI（実装例）
            # ※実際にはAPIキーと適切なエンドポイントが必要
            if not self.weather_api_key:
                # フォールバック: 模擬データ
                return self._get_mock_weather_data()
            
            # 実装予定: 実際の気象データAPI呼び出し
            return await self._fetch_real_weather_data(lat, lon)
            
        except Exception as e:
            logger.warning(f"気象データ取得でエラー: {e}")
            return self._get_mock_weather_data()
    
    def _get_mock_weather_data(self) -> Dict:
        """模擬気象データ"""
        import random
        
        # 季節を考慮した模擬データ
        current_month = datetime.now().month
        is_winter = current_month in [11, 12, 1, 2, 3]
        
        if is_winter:
            wind_speed = random.uniform(8, 20)
            temperature = random.uniform(-15, 5)
            visibility = random.uniform(1, 15)
        else:
            wind_speed = random.uniform(3, 12)
            temperature = random.uniform(5, 25)
            visibility = random.uniform(5, 20)
        
        # 風速から波高を簡易推定
        wave_height = wind_speed * 0.25
        
        return {
            "wind_speed": round(wind_speed, 1),
            "wave_height": round(wave_height, 1),
            "visibility": round(visibility, 1),
            "temperature": round(temperature, 1)
        }
    
    async def _fetch_real_weather_data(self, lat: float, lon: float) -> Dict:
        """実際の気象データ取得"""
        # ※実装予定: JMA API、OpenWeatherMap等
        return self._get_mock_weather_data()
    
    def _extract_cancellation_details(self, status_message: str) -> Tuple[str, str]:
        """欠航詳細情報抽出"""
        reason = "不明"
        
        # キーワードによる理由判定
        if any(word in status_message for word in ['強風', '風']):
            reason = "強風"
        elif any(word in status_message for word in ['波', '高波']):
            reason = "高波"
        elif any(word in status_message for word in ['霧', '視界']):
            reason = "濃霧"
        elif any(word in status_message for word in ['低温', '凍結']):
            reason = "低温"
        elif any(word in status_message for word in ['流氷', '海氷']):
            reason = "流氷"
        elif any(word in status_message for word in ['雪', '吹雪']):
            reason = "降雪"
        elif any(word in status_message for word in ['気象', '荒天']):
            reason = "荒天"
        
        return reason, status_message
    
    async def record_cancellation(self, route_id: str, status_info: Dict, weather_data: Dict):
        """欠航情報をCSVに記録"""
        try:
            route = self.routes.get(route_id, {})
            current_time = datetime.now()
            
            # 今日の時刻表から該当便を特定（簡易版）
            schedules = self._get_daily_schedule(route_id)
            
            reason, message = self._extract_cancellation_details(status_info.get('message', ''))
            
            for schedule in schedules:
                # CSVに追記
                row_data = [
                    current_time.strftime("%Y-%m-%d"),  # 日付
                    schedule.get("departure_time", "不明"),  # 出航予定時刻
                    route.get("departure", {}).get("port", "不明"),  # 出航場所
                    schedule.get("arrival_time", "不明"),  # 着予定時刻
                    route.get("arrival", {}).get("port", "不明"),  # 着場所
                    status_info.get("status", "不明"),  # 運航状況
                    reason,  # 欠航理由
                    schedule.get("service_name", f"{route_id}_{schedule.get('departure_time', '')}"),  # 便名
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),  # 検知時刻
                    weather_data.get("wind_speed", ""),  # 風速
                    weather_data.get("wave_height", ""),  # 波高
                    weather_data.get("visibility", ""),  # 視界
                    weather_data.get("temperature", ""),  # 気温
                    message  # 備考
                ]
                
                # CSVファイルに追記
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(row_data)
                
                logger.info(f"欠航情報を記録しました: {route_id} - {schedule.get('departure_time')}")
        
        except Exception as e:
            logger.error(f"欠航情報記録でエラー: {e}")
    
    def _get_daily_schedule(self, route_id: str) -> List[Dict]:
        """当日の運航スケジュール取得（簡易版）"""
        # ※実際にはハートランドフェリーの時刻表APIまたはスクレイピングが必要
        
        # デフォルトスケジュール（冬季想定）
        default_schedules = {
            "wakkanai_oshidomari": [
                {"departure_time": "08:00", "arrival_time": "09:40", "service_name": "第1便"},
                {"departure_time": "15:00", "arrival_time": "16:40", "service_name": "第2便"}
            ],
            "wakkanai_kutsugata": [
                {"departure_time": "09:00", "arrival_time": "10:40", "service_name": "第1便"},
                {"departure_time": "14:30", "arrival_time": "16:10", "service_name": "第2便"}
            ],
            "wakkanai_kafuka": [
                {"departure_time": "08:30", "arrival_time": "09:25", "service_name": "第1便"},
                {"departure_time": "12:00", "arrival_time": "12:55", "service_name": "第2便"},
                {"departure_time": "15:30", "arrival_time": "16:25", "service_name": "第3便"}
            ]
        }
        
        return default_schedules.get(route_id, [{"departure_time": "不明", "arrival_time": "不明"}])
    
    def check_data_limit(self) -> bool:
        """データ収集上限チェック"""
        try:
            if not self.auto_stop_enabled:
                return False
            
            if not self.csv_file.exists():
                return False
            
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            current_count = len(df)
            
            if current_count >= self.max_data_count:
                logger.info(f"データ収集上限に達しました: {current_count}/{self.max_data_count}件")
                logger.info("監視を自動終了します。十分なデータが蓄積されました。")
                return True
                
            elif current_count >= self.max_data_count * 0.9:  # 90%到達で警告
                remaining = self.max_data_count - current_count
                logger.warning(f"データ収集上限まで残り{remaining}件です")
                
            return False
            
        except Exception as e:
            logger.error(f"データ上限チェックでエラー: {e}")
            return False

    async def monitor_all_routes(self):
        """全航路監視"""
        logger.info("フェリー運航状況監視を開始します")
        
        # データ上限チェック
        if self.check_data_limit():
            logger.info("データ収集完了のため監視を終了します")
            self._create_completion_report()
            return False
        
        try:
            # 運航状況チェック
            status_info = await self.check_ferry_status()
            
            for route_id, route_data in self.routes.items():
                try:
                    # 気象データ取得
                    departure_lat = route_data["departure"]["lat"]
                    departure_lon = route_data["departure"]["lon"]
                    weather_data = await self.get_weather_data(departure_lat, departure_lon)
                    
                    # 状況変化チェック
                    current_status = status_info.get("status", "不明")
                    previous_status = self.previous_status.get(route_id, "不明")
                    
                    # 欠航・遅延の場合、または状況が変化した場合に記録
                    if (current_status in ["欠航", "遅延"] or 
                        current_status != previous_status):
                        
                        await self.record_cancellation(route_id, status_info, weather_data)
                        
                        # Slackやメール通知（オプション）
                        await self._send_notification(route_id, status_info)
                    
                    # 前回状況を更新
                    self.previous_status[route_id] = current_status
                    
                except Exception as e:
                    logger.error(f"航路 {route_id} の監視でエラー: {e}")
                    
        except Exception as e:
            logger.error(f"全体監視でエラー: {e}")
    
    async def _send_notification(self, route_id: str, status_info: Dict):
        """通知送信（Discord通知機能）"""
        route_name = self.routes.get(route_id, {}).get("route_name", route_id)
        message = f"【フェリー運航情報】{route_name}: {status_info.get('message', '')}"
        logger.info(f"通知: {message}")
        
        # Discord通知送信
        if self.discord_enabled and self.discord_system:
            try:
                status = status_info.get("status", "不明")
                
                # 欠航の場合は緊急アラート
                if "欠航" in status:
                    await self.discord_system.send_cancellation_alert(
                        route_name=route_name,
                        departure_time="複数便", 
                        reason=status_info.get("message", "気象条件不良")
                    )
                # 遅延の場合は通常通知
                elif "遅延" in status:
                    embed = {
                        "title": "🟡 フェリー運航遅延",
                        "color": 0xFFFF00,
                        "fields": [
                            {"name": "航路", "value": route_name, "inline": True},
                            {"name": "状況", "value": status, "inline": True}
                        ]
                    }
                    await self.discord_system.send_discord_message(embed=embed)
                
            except Exception as e:
                logger.error(f"Discord通知送信エラー: {e}")
        
        # LINE通知送信
        if self.line_enabled and self.line_system:
            try:
                status = status_info.get("status", "不明")
                
                # 欠航の場合は緊急アラート
                if "欠航" in status:
                    await self.line_system.send_cancellation_alert(
                        route_name=route_name,
                        departure_time="複数便",
                        reason=status_info.get("message", "気象条件不良")
                    )
                # 遅延の場合は通常通知
                elif "遅延" in status:
                    text = f"🟡 フェリー運航遅延\n\n"
                    text += f"🚢 航路: {route_name}\n"
                    text += f"📊 状況: {status}\n"
                    text += f"詳細: {status_info.get('message', '')}"
                    message = self.line_system.create_text_message(text)
                    await self.line_system.broadcast_to_all_targets(message)
                
            except Exception as e:
                logger.error(f"LINE通知送信エラー: {e}")
    
    def _create_completion_report(self):
        """データ収集完了レポート作成"""
        try:
            df = self.generate_summary_report()
            completion_time = datetime.now()
            
            report = {
                "completion_time": completion_time.isoformat(),
                "total_records": len(df),
                "data_collection_period": {
                    "start": df['日付'].min() if not df.empty else None,
                    "end": df['日付'].max() if not df.empty else None
                },
                "statistics": {
                    "cancellation_count": len(df[df['運航状況'] == '欠航']) if not df.empty else 0,
                    "delay_count": len(df[df['運航状況'] == '遅延']) if not df.empty else 0,
                    "normal_count": len(df[df['運航状況'] == '通常運航']) if not df.empty else 0
                },
                "status": "DATA_COLLECTION_COMPLETED",
                "recommendation": "予測システムの高精度運用が可能です。定期的なモデル更新を推奨します。"
            }
            
            # 完了レポートファイル保存
            report_file = self.data_dir / "data_collection_completion_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"データ収集完了レポートを作成しました: {report_file}")
            logger.info(f"総収集データ数: {report['total_records']}件")
            
        except Exception as e:
            logger.error(f"完了レポート作成でエラー: {e}")

    def start_monitoring(self, interval_minutes: int = 30):
        """定期監視開始"""
        logger.info(f"定期監視を開始します（{interval_minutes}分間隔）")
        
        # 初回データ上限チェック
        if self.check_data_limit():
            return
        
        # スケジュール設定
        def scheduled_monitor():
            result = asyncio.run(self.monitor_all_routes())
            # False が返された場合は監視終了
            return result is not False
        
        schedule.every(interval_minutes).minutes.do(scheduled_monitor)
        
        # 初回実行
        if not asyncio.run(self.monitor_all_routes()):
            return
        
        # 定期実行
        logger.info("定期監視を開始しました。データ上限に達すると自動終了します。")
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1分毎にスケジュールチェック
            
            # データ上限チェック（定期確認）
            if self.check_data_limit():
                logger.info("定期監視を終了します")
                break
    
    def generate_summary_report(self) -> pd.DataFrame:
        """蓄積データのサマリーレポート生成"""
        try:
            if not self.csv_file.exists():
                logger.warning("CSVファイルが存在しません")
                return pd.DataFrame()
            
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            
            if df.empty:
                logger.info("記録されたデータがありません")
                return df
            
            # 基本統計
            total_records = len(df)
            cancellation_count = len(df[df['運航状況'] == '欠航'])
            cancellation_rate = (cancellation_count / total_records * 100) if total_records > 0 else 0
            
            logger.info(f"蓄積データサマリー:")
            logger.info(f"  総記録数: {total_records}")
            logger.info(f"  欠航記録数: {cancellation_count}")
            logger.info(f"  欠航率: {cancellation_rate:.1f}%")
            
            return df
            
        except Exception as e:
            logger.error(f"サマリーレポート生成でエラー: {e}")
            return pd.DataFrame()

def main():
    """メイン実行関数"""
    print("=== ハートランドフェリー欠航監視システム ===")
    
    monitor = FerryMonitoringSystem()
    
    try:
        # 手動実行（テスト用）
        print("手動監視を実行します...")
        asyncio.run(monitor.monitor_all_routes())
        
        # サマリーレポート表示
        print("\n現在の蓄積データ:")
        summary_df = monitor.generate_summary_report()
        if not summary_df.empty:
            print(summary_df.tail())
        
        # 定期監視開始の選択
        choice = input("\n定期監視を開始しますか？ (y/n): ")
        if choice.lower() == 'y':
            interval = int(input("監視間隔（分）を入力してください [30]: ") or "30")
            
            # データ上限設定確認
            print(f"データ収集上限: {monitor.max_data_count}件")
            print("上限に達すると自動的に監視を終了します")
            
            # 上限変更オプション
            change_limit = input("上限を変更しますか？ (y/n) [n]: ")
            if change_limit.lower() == 'y':
                new_limit = int(input(f"新しい上限を入力してください [{monitor.max_data_count}]: ") or str(monitor.max_data_count))
                monitor.max_data_count = new_limit
                print(f"データ収集上限を{new_limit}件に設定しました")
            
            monitor.start_monitoring(interval)
        
    except KeyboardInterrupt:
        print("\n監視を停止しました")
    except Exception as e:
        logger.error(f"メイン実行でエラー: {e}")

if __name__ == "__main__":
    main()