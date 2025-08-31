#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord通知システム
Discord Notification System

フェリー運航状況とリスク情報をDiscordに自動通知
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DiscordNotificationSystem:
    """Discord通知システム"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config_file = data_dir / "discord_config.json"
        self.notification_log_file = data_dir / "discord_notifications.log"
        
        # 通知設定
        self.config = self._load_config()
        
        # 通知閾値
        self.notification_thresholds = {
            "high_risk": 70.0,      # 高リスク通知
            "critical_risk": 85.0,   # 緊急通知
            "cancellation": True,    # 欠航確定通知
            "data_milestone": [50, 100, 200, 300, 400, 500]  # データマイルストーン通知
        }
        
        # 通知制限（スパム防止）
        self.notification_limits = {
            "same_risk_interval": 3600,  # 同じリスクレベルは1時間に1回
            "daily_summary": True,       # 日次サマリー通知
            "weekly_report": True        # 週次レポート通知
        }
        
    def _load_config(self) -> Dict:
        """設定読み込み"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return self._create_default_config()
        except Exception as e:
            logger.error(f"Discord設定読み込みエラー: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        """デフォルト設定作成"""
        config = {
            "webhook_urls": {
                "main": None,           # メイン通知チャンネル
                "alerts": None,         # 緊急アラート用
                "reports": None         # レポート用
            },
            "notification_settings": {
                "enabled": False,
                "risk_notifications": True,
                "cancellation_alerts": True,
                "data_milestones": True,
                "daily_summary": True,
                "weekly_report": False
            },
            "message_format": {
                "use_embeds": True,
                "use_mentions": False,
                "mention_role_id": None,
                "color_scheme": {
                    "low": 0x00FF00,      # 緑
                    "medium": 0xFFFF00,   # 黄
                    "high": 0xFF8000,     # オレンジ  
                    "critical": 0xFF0000  # 赤
                }
            },
            "created_at": datetime.now().isoformat()
        }
        
        self._save_config(config)
        return config
    
    def _save_config(self, config: Dict):
        """設定保存"""
        try:
            config["updated_at"] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Discord設定保存エラー: {e}")
    
    def setup_discord_webhook(self, webhook_url: str, channel_type: str = "main"):
        """Discord Webhook設定"""
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            raise ValueError("無効なWebhook URLです")
        
        self.config["webhook_urls"][channel_type] = webhook_url
        self.config["notification_settings"]["enabled"] = True
        self._save_config(self.config)
        
        logger.info(f"Discord Webhook設定完了: {channel_type}")
    
    async def send_discord_message(self, content: str = None, embed: Dict = None, 
                                 channel_type: str = "main") -> bool:
        """Discordメッセージ送信"""
        try:
            webhook_url = self.config["webhook_urls"].get(channel_type)
            
            if not webhook_url:
                logger.warning(f"Discord Webhook未設定: {channel_type}")
                return False
            
            if not self.config["notification_settings"]["enabled"]:
                logger.info("Discord通知が無効化されています")
                return False
            
            # メッセージペイロード作成
            payload = {}
            
            if content:
                payload["content"] = content
            
            if embed:
                payload["embeds"] = [embed]
            
            # メンション設定
            if (self.config["message_format"]["use_mentions"] and 
                self.config["message_format"]["mention_role_id"]):
                mention = f"<@&{self.config['message_format']['mention_role_id']}>"
                payload["content"] = f"{mention}\n{payload.get('content', '')}"
            
            # Discord API送信
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 204:
                        logger.info(f"Discord通知送信成功: {channel_type}")
                        self._log_notification(payload, channel_type)
                        return True
                    else:
                        logger.error(f"Discord通知送信失敗: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Discord通知送信エラー: {e}")
            return False
    
    def _log_notification(self, payload: Dict, channel_type: str):
        """通知ログ記録"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "channel_type": channel_type,
                "content_length": len(payload.get("content", "")),
                "has_embed": "embeds" in payload
            }
            
            with open(self.notification_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"通知ログ記録エラー: {e}")
    
    def create_forecast_embed(self, forecast_result: Dict) -> Dict:
        """予報結果のEmbed作成"""
        try:
            risk_level = forecast_result.get("risk_level", "Unknown")
            risk_score = forecast_result.get("risk_score", 0)
            service = forecast_result.get("service", {})
            weather = forecast_result.get("weather_conditions", {})
            
            # 色設定
            colors = self.config["message_format"]["color_scheme"]
            color = colors.get(risk_level.lower(), 0x808080)
            
            # リスクアイコン
            risk_icons = {
                "Low": "🟢",
                "Medium": "🟡", 
                "High": "🟠",
                "Critical": "🔴"
            }
            icon = risk_icons.get(risk_level, "❓")
            
            embed = {
                "title": f"{icon} フェリー運航予報",
                "color": color,
                "timestamp": datetime.now().isoformat(),
                "fields": [
                    {
                        "name": "🚢 航路",
                        "value": service.get("route_name", "不明"),
                        "inline": True
                    },
                    {
                        "name": "⏰ 出発時刻",
                        "value": service.get("departure_time", "不明"),
                        "inline": True
                    },
                    {
                        "name": "⚠️ リスクレベル",
                        "value": f"{risk_level} ({risk_score:.0f}%)",
                        "inline": True
                    }
                ]
            }
            
            # 気象条件追加
            if weather:
                weather_text = f"💨 風速: {weather.get('wind_speed', 0):.1f}m/s\n"
                weather_text += f"🌊 波高: {weather.get('wave_height', 0):.1f}m\n"
                weather_text += f"👁️ 視界: {weather.get('visibility', 0):.1f}km\n"
                weather_text += f"🌡️ 気温: {weather.get('temperature', 0):.1f}°C"
                
                embed["fields"].append({
                    "name": "🌤️ 気象条件",
                    "value": weather_text,
                    "inline": False
                })
            
            # 推奨事項追加
            recommendation = forecast_result.get("recommendation", "")
            if recommendation:
                embed["fields"].append({
                    "name": "💡 推奨事項", 
                    "value": recommendation,
                    "inline": False
                })
            
            # フッター追加
            embed["footer"] = {
                "text": f"信頼度: {forecast_result.get('confidence', 0):.0%} | {forecast_result.get('prediction_method', 'unknown')}"
            }
            
            return embed
            
        except Exception as e:
            logger.error(f"Embed作成エラー: {e}")
            return {
                "title": "❌ 予報データ取得エラー",
                "color": 0xFF0000,
                "description": str(e)
            }
    
    async def send_risk_alert(self, forecast_result: Dict):
        """リスクアラート通知"""
        risk_score = forecast_result.get("risk_score", 0)
        risk_level = forecast_result.get("risk_level", "Unknown")
        
        # 通知判定
        should_notify = False
        channel_type = "main"
        
        if risk_score >= self.notification_thresholds["critical_risk"]:
            should_notify = True
            channel_type = "alerts"
        elif risk_score >= self.notification_thresholds["high_risk"]:
            should_notify = True
            channel_type = "main"
        
        if not should_notify:
            return False
        
        # 重複通知チェック
        if not self._should_send_risk_notification(risk_level):
            return False
        
        # Embed作成
        embed = self.create_forecast_embed(forecast_result)
        
        # 緊急アラートの場合はメンション追加
        content = None
        if risk_score >= self.notification_thresholds["critical_risk"]:
            content = "🚨 **緊急フェリー運航アラート** 🚨"
        
        return await self.send_discord_message(content=content, embed=embed, channel_type=channel_type)
    
    async def send_cancellation_alert(self, route_name: str, departure_time: str, reason: str = ""):
        """欠航アラート通知"""
        if not self.config["notification_settings"]["cancellation_alerts"]:
            return False
        
        embed = {
            "title": "🔴 フェリー欠航アラート",
            "color": 0xFF0000,
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "🚢 航路",
                    "value": route_name,
                    "inline": True
                },
                {
                    "name": "⏰ 便",
                    "value": departure_time,
                    "inline": True
                },
                {
                    "name": "📝 理由",
                    "value": reason if reason else "気象条件不良",
                    "inline": False
                }
            ],
            "footer": {
                "text": "最新の運航情報をご確認ください"
            }
        }
        
        content = "⚠️ **フェリー欠航のお知らせ** ⚠️"
        return await self.send_discord_message(content=content, embed=embed, channel_type="alerts")
    
    async def send_data_milestone_notification(self, milestone: int, total_data: int):
        """データマイルストーン通知"""
        if not self.config["notification_settings"]["data_milestones"]:
            return False
        
        if milestone not in self.notification_thresholds["data_milestone"]:
            return False
        
        # マイルストーン別メッセージ
        milestone_messages = {
            50: "🤖 機械学習予測開始！基本的なデータ学習が可能になりました",
            100: "📈 予測精度向上中！さらなるデータ蓄積で精度アップ",
            200: "⚡ ハイブリッド予測開始！高精度予測システム稼働",
            300: "🎯 予測システム成熟中！より信頼性の高い予報が可能",
            400: "🚀 システム完成間近！最終調整段階に入りました",
            500: "🎉 予測システム完成！最高精度の運航予報システム稼働開始"
        }
        
        message = milestone_messages.get(milestone, f"データ{milestone}件達成！")
        
        embed = {
            "title": "📊 データ収集マイルストーン達成",
            "color": 0x00FF00,
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "🎯 達成マイルストーン",
                    "value": f"{milestone}件",
                    "inline": True
                },
                {
                    "name": "📈 総データ数",
                    "value": f"{total_data}件",
                    "inline": True
                },
                {
                    "name": "🚀 システム状況",
                    "value": message,
                    "inline": False
                }
            ]
        }
        
        return await self.send_discord_message(embed=embed, channel_type="main")
    
    async def send_daily_summary(self, summary_data: Dict):
        """日次サマリー通知"""
        if not self.config["notification_settings"]["daily_summary"]:
            return False
        
        embed = {
            "title": "📅 本日のフェリー運航サマリー",
            "color": 0x0099FF,
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "📊 運航状況",
                    "value": f"正常: {summary_data.get('normal_count', 0)}便\n"
                           f"遅延: {summary_data.get('delay_count', 0)}便\n"
                           f"欠航: {summary_data.get('cancellation_count', 0)}便",
                    "inline": True
                },
                {
                    "name": "⚠️ 平均リスクレベル",
                    "value": f"{summary_data.get('average_risk_level', 'Low')} "
                           f"({summary_data.get('average_risk_score', 0):.0f}%)",
                    "inline": True
                },
                {
                    "name": "🌤️ 主要気象要因",
                    "value": summary_data.get('primary_factors', ['良好な条件'])[0],
                    "inline": False
                }
            ],
            "footer": {
                "text": f"データ更新: {summary_data.get('data_count', 0)}件蓄積済み"
            }
        }
        
        return await self.send_discord_message(embed=embed, channel_type="reports")
    
    def _should_send_risk_notification(self, risk_level: str) -> bool:
        """リスク通知の重複チェック"""
        try:
            # 簡易重複チェック（実装では詳細なログベース判定）
            return True  # とりあえずすべて通知
        except:
            return True
    
    def create_setup_guide(self) -> str:
        """Discord設定ガイド生成"""
        guide = """
🔧 Discord通知システム設定ガイド

1️⃣ Discord Webhook URL取得:
   - Discordサーバーの設定 → 連携サービス → ウェブフック
   - 新しいウェブフック作成
   - Webhook URLをコピー

2️⃣ システム設定:
   ```python
   from discord_notification_system import DiscordNotificationSystem
   from pathlib import Path
   
   # 初期化
   discord_system = DiscordNotificationSystem(Path("data"))
   
   # Webhook URL設定
   webhook_url = "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
   discord_system.setup_discord_webhook(webhook_url, "main")
   ```

3️⃣ 通知タイプ:
   - 🟠 高リスクアラート (70%以上)
   - 🔴 緊急アラート (85%以上)  
   - ❌ 欠航確定通知
   - 📊 データマイルストーン通知
   - 📅 日次サマリー

4️⃣ 追加設定:
   - メンション設定 (ロールID指定)
   - 通知チャンネル分離 (main/alerts/reports)
   - 通知頻度制限設定
"""
        return guide

def main():
    """テスト実行"""
    from pathlib import Path
    
    data_dir = Path(__file__).parent / "data"
    discord_system = DiscordNotificationSystem(data_dir)
    
    print("=== Discord通知システム ===")
    print(discord_system.create_setup_guide())
    
    # 設定確認
    if discord_system.config["notification_settings"]["enabled"]:
        print("✅ Discord通知が有効です")
    else:
        print("❌ Discord通知が無効です（Webhook URL未設定）")
        print("設定方法:")
        print('discord_system.setup_discord_webhook("YOUR_WEBHOOK_URL")')

if __name__ == "__main__":
    main()