#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord通知設定ガイド
Discord Notification Setup Guide

Discord通知機能の設定手順と設定確認ツール
"""

import asyncio
import json
from pathlib import Path
from discord_notification_system import DiscordNotificationSystem

def display_setup_guide():
    """Discord設定ガイド表示"""
    print("=" * 80)
    print("🔧 Discord通知システム設定ガイド")
    print("=" * 80)
    
    print("""
📋 設定手順:

1️⃣ Discord Webhookの作成
   ┌─────────────────────────────────────────┐
   │ 1. Discordサーバーにて                    │
   │ 2. サーバー設定 → 連携サービス → ウェブフック │
   │ 3. 「新しいウェブフック」をクリック          │
   │ 4. 名前を設定 (例: フェリー予報Bot)        │
   │ 5. チャンネルを選択                       │
   │ 6. 「ウェブフックURLをコピー」をクリック     │
   └─────────────────────────────────────────┘

2️⃣ 複数チャンネル設定（推奨）
   ┌─────────────────────────────────────────┐
   │ • #ferry-alerts (緊急通知用)             │
   │ • #ferry-reports (日次レポート用)         │
   │ • #ferry-general (一般通知用)            │
   └─────────────────────────────────────────┘

3️⃣ システム設定
   ┌─────────────────────────────────────────┐
   │ python discord_setup_guide.py           │
   │ → 対話形式でWebhook URLを設定             │
   └─────────────────────────────────────────┘
""")

def interactive_setup():
    """対話式設定"""
    print("\n🛠️ 対話式Discord設定を開始します")
    
    data_dir = Path(__file__).parent / "data"
    discord_system = DiscordNotificationSystem(data_dir)
    
    print("\n現在の設定状況:")
    current_config = discord_system.config
    
    if current_config["notification_settings"]["enabled"]:
        print("✅ Discord通知: 有効")
        print(f"   メイン通知: {'設定済み' if current_config['webhook_urls']['main'] else '未設定'}")
        print(f"   緊急アラート: {'設定済み' if current_config['webhook_urls']['alerts'] else '未設定'}")
        print(f"   レポート: {'設定済み' if current_config['webhook_urls']['reports'] else '未設定'}")
    else:
        print("❌ Discord通知: 無効")
    
    print("\n設定するチャンネルタイプを選択してください:")
    print("1. メイン通知チャンネル (一般的な運航状況)")
    print("2. 緊急アラートチャンネル (欠航・高リスク通知)")
    print("3. レポートチャンネル (日次・週次サマリー)")
    print("4. 全チャンネル一括設定")
    print("5. 設定確認のみ")
    
    try:
        choice = input("\n選択 (1-5): ").strip()
        
        if choice == "1":
            setup_single_channel(discord_system, "main", "メイン通知")
        elif choice == "2":
            setup_single_channel(discord_system, "alerts", "緊急アラート")
        elif choice == "3":
            setup_single_channel(discord_system, "reports", "レポート")
        elif choice == "4":
            setup_all_channels(discord_system)
        elif choice == "5":
            display_current_settings(discord_system)
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n設定を中断しました")

def setup_single_channel(discord_system: DiscordNotificationSystem, channel_type: str, channel_name: str):
    """個別チャンネル設定"""
    print(f"\n📡 {channel_name}チャンネルの設定")
    print("Webhook URLを入力してください:")
    print("例: https://discord.com/api/webhooks/123456789/abcdefghijk...")
    
    webhook_url = input("Webhook URL: ").strip()
    
    if not webhook_url:
        print("❌ URLが入力されませんでした")
        return
    
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        print("❌ 無効なWebhook URLです")
        return
    
    try:
        discord_system.setup_discord_webhook(webhook_url, channel_type)
        print(f"✅ {channel_name}チャンネル設定完了")
        
        # テスト送信確認
        test_choice = input("テスト通知を送信しますか? (y/n): ").strip().lower()
        if test_choice == 'y':
            asyncio.run(send_test_notification(discord_system, channel_type, channel_name))
        
    except Exception as e:
        print(f"❌ 設定エラー: {e}")

def setup_all_channels(discord_system: DiscordNotificationSystem):
    """全チャンネル設定"""
    print("\n📡 全チャンネル設定")
    
    channels = [
        ("main", "メイン通知"),
        ("alerts", "緊急アラート"),  
        ("reports", "レポート")
    ]
    
    for channel_type, channel_name in channels:
        print(f"\n--- {channel_name}チャンネル ---")
        
        # 現在の設定確認
        current_url = discord_system.config["webhook_urls"].get(channel_type)
        if current_url:
            print(f"現在の設定: {current_url[:50]}...")
            skip = input("スキップしますか? (y/n): ").strip().lower()
            if skip == 'y':
                continue
        
        webhook_url = input(f"{channel_name} Webhook URL: ").strip()
        
        if webhook_url and webhook_url.startswith("https://discord.com/api/webhooks/"):
            try:
                discord_system.setup_discord_webhook(webhook_url, channel_type)
                print(f"✅ {channel_name}設定完了")
            except Exception as e:
                print(f"❌ {channel_name}設定エラー: {e}")
        else:
            print(f"⏩ {channel_name}をスキップしました")
    
    print("\n🎉 全チャンネル設定完了")

async def send_test_notification(discord_system: DiscordNotificationSystem, channel_type: str, channel_name: str):
    """テスト通知送信"""
    print(f"📤 {channel_name}にテスト通知を送信中...")
    
    if channel_type == "main":
        embed = {
            "title": "🧪 テスト通知",
            "color": 0x00FF00,
            "description": f"Discord通知システムのテストです。\n{channel_name}チャンネルの設定が正常に完了しました！",
            "fields": [
                {"name": "🚢 システム", "value": "北海道フェリー予測システム", "inline": False},
                {"name": "⏰ 送信時刻", "value": "2025-08-30 テスト実行", "inline": False}
            ]
        }
        success = await discord_system.send_discord_message(embed=embed, channel_type=channel_type)
    
    elif channel_type == "alerts":
        success = await discord_system.send_cancellation_alert(
            route_name="稚内 ⇔ 鴛泊 (テスト)",
            departure_time="08:00便",
            reason="システムテスト - 実際の欠航ではありません"
        )
    
    elif channel_type == "reports":
        test_summary = {
            "normal_count": 10,
            "delay_count": 2,
            "cancellation_count": 1,
            "average_risk_level": "Medium",
            "average_risk_score": 45,
            "primary_factors": ["テストデータ"],
            "data_count": 150
        }
        success = await discord_system.send_daily_summary(test_summary)
    
    if success:
        print(f"✅ テスト通知送信成功")
    else:
        print(f"❌ テスト通知送信失敗")

def display_current_settings(discord_system: DiscordNotificationSystem):
    """現在の設定表示"""
    print("\n📋 現在のDiscord通知設定")
    print("=" * 50)
    
    config = discord_system.config
    
    print(f"通知システム: {'✅ 有効' if config['notification_settings']['enabled'] else '❌ 無効'}")
    
    print("\nWebhook設定:")
    for channel_type, url in config["webhook_urls"].items():
        status = "✅ 設定済み" if url else "❌ 未設定"
        print(f"  {channel_type:10}: {status}")
    
    print("\n通知種類:")
    settings = config["notification_settings"]
    for setting, enabled in settings.items():
        if setting != "enabled":
            status = "✅ ON" if enabled else "❌ OFF"
            print(f"  {setting:20}: {status}")
    
    print(f"\n設定ファイル: {discord_system.config_file}")

def create_example_integration():
    """統合例のコード生成"""
    example_code = '''
# フェリー監視システムにDiscord通知を統合する例

from ferry_monitoring_system import FerryMonitoringSystem
from discord_notification_system import DiscordNotificationSystem

async def main():
    # システム初期化
    monitor = FerryMonitoringSystem()
    
    # Discord通知設定
    if monitor.discord_enabled:
        print("Discord通知システム利用可能")
        
        # 高リスク予報の場合の通知例
        forecast_result = {
            "risk_level": "High",
            "risk_score": 75.0,
            "service": {
                "route_name": "稚内 ⇔ 鴛泊",
                "departure_time": "08:00"
            },
            "weather_conditions": {
                "wind_speed": 18.5,
                "wave_height": 3.2,
                "visibility": 2.0,
                "temperature": -5.0
            },
            "recommendation": "運航に注意が必要です",
            "confidence": 0.85,
            "prediction_method": "hybrid"
        }
        
        # Discord通知送信
        await monitor.discord_system.send_risk_alert(forecast_result)
        
        # データマイルストーン通知
        await monitor.discord_system.send_data_milestone_notification(100, 100)
    
    # 通常の監視開始
    await monitor.monitor_all_routes()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''
    
    print("\n💻 統合コード例")
    print("=" * 50)
    print(example_code)

def main():
    """メイン実行"""
    print("🔧 Discord通知システム設定ツール")
    
    print("\n実行モード:")
    print("1. 設定ガイド表示")
    print("2. 対話式設定")
    print("3. 現在の設定確認")
    print("4. 統合コード例表示")
    
    try:
        choice = input("選択 (1-4): ").strip()
        
        if choice == "1":
            display_setup_guide()
        elif choice == "2":
            interactive_setup()
        elif choice == "3":
            data_dir = Path(__file__).parent / "data"
            discord_system = DiscordNotificationSystem(data_dir)
            display_current_settings(discord_system)
        elif choice == "4":
            create_example_integration()
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n設定を中断しました")

if __name__ == "__main__":
    main()