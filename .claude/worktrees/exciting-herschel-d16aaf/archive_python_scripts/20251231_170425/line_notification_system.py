#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE通知システム
LINE Notification System

フェリー運航状況とリスク情報をLINEに自動通知
LINE Messaging APIを使用してメッセージ・Flex Message・リッチメニューに対応
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from pathlib import Path
import logging
import base64
import hmac
import hashlib

logger = logging.getLogger(__name__)

class LINENotificationSystem:
    """LINE通知システム"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config_file = data_dir / "line_config.json"
        self.notification_log_file = data_dir / "line_notifications.log"
        
        # 通知設定
        self.config = self._load_config()
        
        # LINE API エンドポイント
        self.line_api_base = "https://api.line.me/v2/bot"
        
        # 通知閾値
        self.notification_thresholds = {
            "high_risk": 70.0,      # 高リスク通知
            "critical_risk": 85.0,   # 緊急通知
            "cancellation": True,    # 欠航確定通知
            "data_milestone": [50, 100, 200, 300, 400, 500]  # データマイルストーン通知
        }
        
        # 絵文字・アイコン
        self.emoji_map = {
            "Low": "🟢",
            "Medium": "🟡", 
            "High": "🟠",
            "Critical": "🔴",
            "ferry": "🚢",
            "alert": "⚠️",
            "time": "⏰",
            "weather": "🌤️",
            "wind": "💨",
            "wave": "🌊",
            "visibility": "👁️",
            "temperature": "🌡️",
            "recommendation": "💡",
            "cancel": "❌",
            "check": "✅"
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
            logger.error(f"LINE設定読み込みエラー: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        """デフォルト設定作成"""
        config = {
            "channel_access_token": None,
            "channel_secret": None,
            "user_ids": [],              # 個人ユーザーID（push用）
            "group_ids": [],             # グループID（push用）
            "notification_settings": {
                "enabled": False,
                "risk_notifications": True,
                "cancellation_alerts": True,
                "data_milestones": True,
                "daily_summary": True,
                "use_flex_messages": True,    # Flex Message使用
                "use_quick_reply": True       # Quick Reply使用
            },
            "message_format": {
                "max_text_length": 5000,     # テキストメッセージ最大長
                "use_rich_menu": False,      # リッチメニュー使用
                "brand_color": "#FF6B35"     # ブランドカラー
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
            logger.error(f"LINE設定保存エラー: {e}")
    
    def setup_line_bot(self, channel_access_token: str, channel_secret: str):
        """LINE Bot設定"""
        if not channel_access_token or not channel_secret:
            raise ValueError("Channel Access TokenとChannel Secretが必要です")
        
        self.config["channel_access_token"] = channel_access_token
        self.config["channel_secret"] = channel_secret
        self.config["notification_settings"]["enabled"] = True
        self._save_config(self.config)
        
        logger.info("LINE Bot設定完了")
    
    def add_notification_target(self, target_id: str, target_type: str = "user"):
        """通知対象追加"""
        if target_type == "user":
            if target_id not in self.config["user_ids"]:
                self.config["user_ids"].append(target_id)
        elif target_type == "group":
            if target_id not in self.config["group_ids"]:
                self.config["group_ids"].append(target_id)
        else:
            raise ValueError("target_typeは'user'または'group'である必要があります")
        
        self._save_config(self.config)
        logger.info(f"通知対象追加: {target_type} {target_id}")
    
    def _get_headers(self) -> Dict[str, str]:
        """API リクエストヘッダー取得"""
        return {
            "Authorization": f"Bearer {self.config['channel_access_token']}",
            "Content-Type": "application/json"
        }
    
    async def send_line_message(self, message: Union[Dict, List[Dict]], 
                               target_id: str = None, target_type: str = "broadcast") -> bool:
        """LINEメッセージ送信"""
        try:
            if not self.config["notification_settings"]["enabled"]:
                logger.info("LINE通知が無効化されています")
                return False
            
            if not self.config["channel_access_token"]:
                logger.warning("LINE Channel Access Token未設定")
                return False
            
            headers = self._get_headers()
            
            # メッセージペイロード作成
            if target_type == "broadcast":
                # ブロードキャスト（全友だち）
                endpoint = f"{self.line_api_base}/message/broadcast"
                payload = {"messages": message if isinstance(message, list) else [message]}
            else:
                # 個別送信
                if not target_id:
                    logger.error("個別送信にはtarget_idが必要です")
                    return False
                
                endpoint = f"{self.line_api_base}/message/push"
                payload = {
                    "to": target_id,
                    "messages": message if isinstance(message, list) else [message]
                }
            
            # LINE API送信
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=payload, headers=headers) as response:
                    if response.status == 200:
                        logger.info(f"LINE通知送信成功: {target_type}")
                        self._log_notification(payload, target_type)
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"LINE通知送信失敗: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"LINE通知送信エラー: {e}")
            return False
    
    async def broadcast_to_all_targets(self, message: Union[Dict, List[Dict]]) -> bool:
        """全通知対象に送信"""
        success_count = 0
        total_count = 0
        
        # 登録ユーザーに送信
        for user_id in self.config["user_ids"]:
            total_count += 1
            if await self.send_line_message(message, user_id, "push"):
                success_count += 1
        
        # 登録グループに送信
        for group_id in self.config["group_ids"]:
            total_count += 1
            if await self.send_line_message(message, group_id, "push"):
                success_count += 1
        
        logger.info(f"LINE通知結果: {success_count}/{total_count} 成功")
        return success_count > 0
    
    def _log_notification(self, payload: Dict, target_type: str):
        """通知ログ記録"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "target_type": target_type,
                "message_count": len(payload.get("messages", [])),
                "target_id": payload.get("to", "broadcast")
            }
            
            with open(self.notification_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"通知ログ記録エラー: {e}")
    
    def create_text_message(self, text: str) -> Dict:
        """テキストメッセージ作成"""
        # 長さ制限チェック
        max_length = self.config["message_format"]["max_text_length"]
        if len(text) > max_length:
            text = text[:max_length-10] + "...(続く)"
        
        return {
            "type": "text",
            "text": text
        }
    
    def create_forecast_flex_message(self, forecast_result: Dict) -> Dict:
        """予報結果のFlex Message作成"""
        try:
            risk_level = forecast_result.get("risk_level", "Unknown")
            risk_score = forecast_result.get("risk_score", 0)
            service = forecast_result.get("service", {})
            weather = forecast_result.get("weather_conditions", {})
            
            # 色設定
            risk_colors = {
                "Low": "#00FF00",
                "Medium": "#FFFF00", 
                "High": "#FF8000",
                "Critical": "#FF0000",
                "Unknown": "#808080"
            }
            color = risk_colors.get(risk_level, "#808080")
            
            # アイコン
            icon = self.emoji_map.get(risk_level, "❓")
            
            # Flex Message構造
            flex_message = {
                "type": "flex",
                "altText": f"{icon} フェリー運航予報 {risk_level}",
                "contents": {
                    "type": "bubble",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{icon} フェリー運航予報",
                                "weight": "bold",
                                "size": "lg",
                                "color": "#FFFFFF"
                            }
                        ],
                        "backgroundColor": color
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            # 航路情報
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": f"{self.emoji_map['ferry']} 航路",
                                        "flex": 0,
                                        "size": "sm",
                                        "color": "#666666"
                                    },
                                    {
                                        "type": "text",
                                        "text": service.get("route_name", "不明"),
                                        "flex": 0,
                                        "size": "sm",
                                        "weight": "bold",
                                        "align": "end"
                                    }
                                ]
                            },
                            # 出発時刻
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": f"{self.emoji_map['time']} 出発",
                                        "flex": 0,
                                        "size": "sm",
                                        "color": "#666666"
                                    },
                                    {
                                        "type": "text",
                                        "text": service.get("departure_time", "不明"),
                                        "flex": 0,
                                        "size": "sm",
                                        "weight": "bold",
                                        "align": "end"
                                    }
                                ]
                            },
                            # リスクレベル
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": f"{self.emoji_map['alert']} リスク",
                                        "flex": 0,
                                        "size": "sm",
                                        "color": "#666666"
                                    },
                                    {
                                        "type": "text",
                                        "text": f"{risk_level} ({risk_score:.0f}%)",
                                        "flex": 0,
                                        "size": "sm",
                                        "weight": "bold",
                                        "align": "end",
                                        "color": color
                                    }
                                ]
                            },
                            # セパレーター
                            {
                                "type": "separator",
                                "margin": "md"
                            },
                            # 気象条件
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['weather']} 気象条件",
                                "weight": "bold",
                                "size": "sm",
                                "margin": "md"
                            }
                        ]
                    }
                }
            }
            
            # 気象条件詳細追加
            if weather:
                weather_contents = [
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['wind']} 風速",
                                "flex": 0,
                                "size": "xs",
                                "color": "#666666"
                            },
                            {
                                "type": "text",
                                "text": f"{weather.get('wind_speed', 0):.1f}m/s",
                                "flex": 0,
                                "size": "xs",
                                "align": "end"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['wave']} 波高",
                                "flex": 0,
                                "size": "xs",
                                "color": "#666666"
                            },
                            {
                                "type": "text",
                                "text": f"{weather.get('wave_height', 0):.1f}m",
                                "flex": 0,
                                "size": "xs",
                                "align": "end"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['visibility']} 視界",
                                "flex": 0,
                                "size": "xs",
                                "color": "#666666"
                            },
                            {
                                "type": "text",
                                "text": f"{weather.get('visibility', 0):.1f}km",
                                "flex": 0,
                                "size": "xs",
                                "align": "end"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['temperature']} 気温",
                                "flex": 0,
                                "size": "xs",
                                "color": "#666666"
                            },
                            {
                                "type": "text",
                                "text": f"{weather.get('temperature', 0):.1f}°C",
                                "flex": 0,
                                "size": "xs",
                                "align": "end"
                            }
                        ]
                    }
                ]
                
                flex_message["contents"]["body"]["contents"].extend(weather_contents)
            
            # 推奨事項追加
            recommendation = forecast_result.get("recommendation", "")
            if recommendation:
                flex_message["contents"]["body"]["contents"].extend([
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": f"{self.emoji_map['recommendation']} {recommendation}",
                        "size": "sm",
                        "wrap": True,
                        "margin": "md"
                    }
                ])
            
            # フッター追加
            confidence = forecast_result.get("confidence", 0)
            method = forecast_result.get("prediction_method", "unknown")
            
            flex_message["contents"]["footer"] = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"信頼度: {confidence:.0%} | 予測手法: {method}",
                        "size": "xs",
                        "color": "#AAAAAA",
                        "align": "center"
                    }
                ]
            }
            
            return flex_message
            
        except Exception as e:
            logger.error(f"Flex Message作成エラー: {e}")
            # フォールバック: テキストメッセージ
            text = f"{self.emoji_map.get(risk_level, '❓')} フェリー運航予報\n"
            text += f"{self.emoji_map['ferry']} {service.get('route_name', '不明')}\n"
            text += f"{self.emoji_map['time']} {service.get('departure_time', '不明')}\n"
            text += f"{self.emoji_map['alert']} {risk_level} ({risk_score:.0f}%)"
            return self.create_text_message(text)
    
    async def send_risk_alert(self, forecast_result: Dict) -> bool:
        """リスクアラート通知"""
        risk_score = forecast_result.get("risk_score", 0)
        
        # 通知判定
        should_notify = (
            risk_score >= self.notification_thresholds["high_risk"] and
            self.config["notification_settings"]["risk_notifications"]
        )
        
        if not should_notify:
            return False
        
        # メッセージ作成
        if self.config["notification_settings"]["use_flex_messages"]:
            message = self.create_forecast_flex_message(forecast_result)
        else:
            # テキストメッセージフォールバック
            risk_level = forecast_result.get("risk_level", "Unknown")
            service = forecast_result.get("service", {})
            text = f"{self.emoji_map.get(risk_level, '❓')} フェリー運航アラート\n\n"
            text += f"{self.emoji_map['ferry']} {service.get('route_name', '不明')}\n"
            text += f"{self.emoji_map['time']} {service.get('departure_time', '不明')}\n"
            text += f"{self.emoji_map['alert']} リスクレベル: {risk_level} ({risk_score:.0f}%)\n\n"
            text += f"{forecast_result.get('recommendation', '気象情報をご確認ください')}"
            message = self.create_text_message(text)
        
        return await self.broadcast_to_all_targets(message)
    
    async def send_cancellation_alert(self, route_name: str, departure_time: str, reason: str = "") -> bool:
        """欠航アラート通知"""
        if not self.config["notification_settings"]["cancellation_alerts"]:
            return False
        
        if self.config["notification_settings"]["use_flex_messages"]:
            # Flex Message形式
            flex_message = {
                "type": "flex",
                "altText": f"{self.emoji_map['cancel']} フェリー欠航のお知らせ",
                "contents": {
                    "type": "bubble",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['cancel']} 欠航のお知らせ",
                                "weight": "bold",
                                "size": "lg",
                                "color": "#FFFFFF"
                            }
                        ],
                        "backgroundColor": "#FF0000"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['ferry']} {route_name}",
                                "weight": "bold",
                                "size": "md"
                            },
                            {
                                "type": "text",
                                "text": f"{self.emoji_map['time']} {departure_time}",
                                "size": "sm",
                                "color": "#666666",
                                "margin": "sm"
                            },
                            {
                                "type": "separator",
                                "margin": "md"
                            },
                            {
                                "type": "text",
                                "text": f"理由: {reason if reason else '気象条件不良'}",
                                "size": "sm",
                                "wrap": True,
                                "margin": "md"
                            },
                            {
                                "type": "text",
                                "text": "最新の運航情報をご確認ください",
                                "size": "sm",
                                "color": "#AAAAAA",
                                "margin": "lg"
                            }
                        ]
                    }
                }
            }
            message = flex_message
        else:
            # テキストメッセージ
            text = f"{self.emoji_map['cancel']} フェリー欠航のお知らせ\n\n"
            text += f"{self.emoji_map['ferry']} 航路: {route_name}\n"
            text += f"{self.emoji_map['time']} 便: {departure_time}\n"
            text += f"理由: {reason if reason else '気象条件不良'}\n\n"
            text += "最新の運航情報をご確認ください"
            message = self.create_text_message(text)
        
        return await self.broadcast_to_all_targets(message)
    
    async def send_data_milestone_notification(self, milestone: int, total_data: int) -> bool:
        """データマイルストーン通知"""
        if not self.config["notification_settings"]["data_milestones"]:
            return False
        
        if milestone not in self.notification_thresholds["data_milestone"]:
            return False
        
        # マイルストーン別メッセージ
        milestone_messages = {
            50: "🤖 機械学習予測開始！",
            100: "📈 予測精度向上中！",
            200: "⚡ ハイブリッド予測開始！",
            300: "🎯 予測システム成熟中！",
            400: "🚀 システム完成間近！",
            500: "🎉 予測システム完成！"
        }
        
        message_text = milestone_messages.get(milestone, f"データ{milestone}件達成！")
        
        if self.config["notification_settings"]["use_flex_messages"]:
            # Flex Message形式
            flex_message = {
                "type": "flex",
                "altText": f"📊 データマイルストーン {milestone}件達成",
                "contents": {
                    "type": "bubble",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "📊 マイルストーン達成",
                                "weight": "bold",
                                "size": "lg",
                                "color": "#FFFFFF"
                            }
                        ],
                        "backgroundColor": "#00FF00"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"🎯 {milestone}件達成！",
                                "weight": "bold",
                                "size": "xl"
                            },
                            {
                                "type": "text",
                                "text": f"総データ数: {total_data}件",
                                "size": "md",
                                "color": "#666666",
                                "margin": "sm"
                            },
                            {
                                "type": "separator",
                                "margin": "md"
                            },
                            {
                                "type": "text",
                                "text": message_text,
                                "size": "md",
                                "wrap": True,
                                "margin": "md"
                            }
                        ]
                    }
                }
            }
            message = flex_message
        else:
            # テキストメッセージ
            text = f"📊 データマイルストーン達成\n\n"
            text += f"🎯 {milestone}件達成！\n"
            text += f"📈 総データ数: {total_data}件\n\n"
            text += message_text
            message = self.create_text_message(text)
        
        return await self.broadcast_to_all_targets(message)
    
    async def send_daily_summary(self, summary_data: Dict) -> bool:
        """日次サマリー通知"""
        if not self.config["notification_settings"]["daily_summary"]:
            return False
        
        # サマリーテキスト作成
        text = f"📅 本日のフェリー運航サマリー\n\n"
        text += f"📊 運航状況\n"
        text += f"  {self.emoji_map['check']} 正常: {summary_data.get('normal_count', 0)}便\n"
        text += f"  🟡 遅延: {summary_data.get('delay_count', 0)}便\n"
        text += f"  {self.emoji_map['cancel']} 欠航: {summary_data.get('cancellation_count', 0)}便\n\n"
        text += f"{self.emoji_map['alert']} 平均リスク: {summary_data.get('average_risk_level', 'Low')}\n"
        text += f"{self.emoji_map['weather']} 主要要因: {summary_data.get('primary_factors', ['良好な条件'])[0]}\n\n"
        text += f"📈 データ更新: {summary_data.get('data_count', 0)}件蓄積済み"
        
        message = self.create_text_message(text)
        return await self.broadcast_to_all_targets(message)
    
    def create_quick_reply_buttons(self, forecast_results: List[Dict] = None) -> Dict:
        """Quick Reply ボタン作成"""
        quick_reply = {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "今日の予報",
                        "text": "今日の運航予報を教えて"
                    }
                },
                {
                    "type": "action", 
                    "action": {
                        "type": "message",
                        "label": "明日の予報",
                        "text": "明日の運航予報を教えて"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "高リスク便",
                        "text": "高リスクの便を教えて"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "運航状況",
                        "text": "現在の運航状況は？"
                    }
                }
            ]
        }
        
        return quick_reply

def main():
    """テスト実行"""
    from pathlib import Path
    
    data_dir = Path(__file__).parent / "data"
    line_system = LINENotificationSystem(data_dir)
    
    print("=== LINE通知システム ===")
    
    # 設定確認
    if line_system.config["notification_settings"]["enabled"]:
        print("✅ LINE通知が有効です")
        print(f"   登録ユーザー: {len(line_system.config['user_ids'])}人")
        print(f"   登録グループ: {len(line_system.config['group_ids'])}個")
    else:
        print("❌ LINE通知が無効です（Channel Access Token未設定）")
        print("設定方法:")
        print('line_system.setup_line_bot("YOUR_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_SECRET")')
        print('line_system.add_notification_target("USER_ID", "user")')

if __name__ == "__main__":
    main()