#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE通知設定ガイド
LINE Notification Setup Guide

LINE Messaging APIを使用した通知機能の設定手順と設定確認ツール
"""

import asyncio
import json
import qrcode
from pathlib import Path
from line_notification_system import LINENotificationSystem
from PIL import Image
from io import BytesIO

def display_setup_guide():
    """LINE設定ガイド表示"""
    print("=" * 80)
    print("🔧 LINE通知システム設定ガイド")
    print("=" * 80)
    
    print("""
📋 設定手順:

1️⃣ LINE Developers アカウント作成
   ┌─────────────────────────────────────────┐
   │ 1. https://developers.line.biz にアクセス │
   │ 2. 「ログイン」→ LINEアカウントでログイン    │
   │ 3. 「新規プロバイダー作成」をクリック        │
   │ 4. プロバイダー名を入力（例: フェリー予報）   │
   └─────────────────────────────────────────┘

2️⃣ Messaging APIチャンネル作成
   ┌─────────────────────────────────────────┐
   │ 1. 「新規チャンネル作成」をクリック          │
   │ 2. 「Messaging API」を選択               │
   │ 3. チャンネル情報を入力:                  │
   │    - チャンネル名: フェリー予報Bot         │
   │    - チャンネル説明: 北海道フェリー運航予報  │
   │    - 大業種: 旅行・交通                  │
   │    - 小業種: 海運                       │
   │ 4. 利用規約に同意して作成                 │
   └─────────────────────────────────────────┘

3️⃣ Channel Access Token取得
   ┌─────────────────────────────────────────┐
   │ 1. 作成したチャンネルの「Basic settings」  │
   │ 2. 「Channel Secret」をコピー             │
   │ 3. 「Messaging API」タブをクリック        │
   │ 4. 「Channel access token」を発行        │
   │ 5. トークンをコピー                      │
   └─────────────────────────────────────────┘

4️⃣ Bot設定
   ┌─────────────────────────────────────────┐
   │ 1. 「Messaging API設定」で以下を設定:     │
   │    - 応答メッセージ: 無効                │
   │    - あいさつメッセージ: 有効             │
   │    - Webhook: 不要（Push通知のみ使用）    │
   │ 2. 友だち追加QRコードを取得               │
   └─────────────────────────────────────────┘

5️⃣ システム設定
   ┌─────────────────────────────────────────┐
   │ python line_setup_guide.py              │
   │ → 対話形式でトークンを設定                │
   │ → ユーザーID・グループIDを登録            │
   └─────────────────────────────────────────┘
""")

def interactive_setup():
    """対話式設定"""
    print("\n🛠️ 対話式LINE設定を開始します")
    
    data_dir = Path(__file__).parent / "data"
    line_system = LINENotificationSystem(data_dir)
    
    print("\n現在の設定状況:")
    current_config = line_system.config
    
    if current_config["notification_settings"]["enabled"]:
        print("✅ LINE通知: 有効")
        print(f"   登録ユーザー: {len(current_config['user_ids'])}人")
        print(f"   登録グループ: {len(current_config['group_ids'])}個")
        print(f"   Flex Message: {'有効' if current_config['notification_settings']['use_flex_messages'] else '無効'}")
    else:
        print("❌ LINE通知: 無効")
    
    print("\n設定項目を選択してください:")
    print("1. Channel Access Token・Channel Secret設定")
    print("2. ユーザーID追加")
    print("3. グループID追加")
    print("4. 通知設定変更")
    print("5. テスト通知送信")
    print("6. 設定確認のみ")
    
    try:
        choice = input("\n選択 (1-6): ").strip()
        
        if choice == "1":
            setup_channel_tokens(line_system)
        elif choice == "2":
            setup_user_id(line_system)
        elif choice == "3":
            setup_group_id(line_system)
        elif choice == "4":
            setup_notification_settings(line_system)
        elif choice == "5":
            asyncio.run(send_test_notification(line_system))
        elif choice == "6":
            display_current_settings(line_system)
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n設定を中断しました")

def setup_channel_tokens(line_system: LINENotificationSystem):
    """Channel Token設定"""
    print("\n🔑 LINE Channel設定")
    
    print("LINE Developersコンソールから以下の情報を取得してください:")
    print("1. Basic settings → Channel Secret")
    print("2. Messaging API → Channel access token")
    
    channel_secret = input("\nChannel Secret: ").strip()
    channel_access_token = input("Channel Access Token: ").strip()
    
    if not channel_secret or not channel_access_token:
        print("❌ 両方の値が必要です")
        return
    
    try:
        line_system.setup_line_bot(channel_access_token, channel_secret)
        print("✅ Channel設定完了")
        
        print("\n次のステップ:")
        print("1. LINE公式アカウントを友だち追加")
        print("2. ユーザーIDを取得して登録")
        
        # QRコード生成（Bot URL）
        generate_friend_qr_code(line_system)
        
    except Exception as e:
        print(f"❌ 設定エラー: {e}")

def setup_user_id(line_system: LINENotificationSystem):
    """ユーザーID設定"""
    print("\n👤 ユーザーID追加")
    
    if not line_system.config["notification_settings"]["enabled"]:
        print("❌ 先にChannel Access Tokenを設定してください")
        return
    
    print("ユーザーIDの取得方法:")
    print("1. LINE公式アカウントを友だち追加")
    print("2. 何かメッセージを送信")
    print("3. Webhook URLでユーザーIDを確認")
    print("または、LINE Bot SDK を使用してユーザーIDを取得")
    
    print("\nユーザーID例: U4af4980629...")
    user_id = input("ユーザーID: ").strip()
    
    if not user_id.startswith("U"):
        print("❌ ユーザーIDは'U'で始まる必要があります")
        return
    
    try:
        line_system.add_notification_target(user_id, "user")
        print(f"✅ ユーザーID追加完了: {user_id}")
    except Exception as e:
        print(f"❌ 追加エラー: {e}")

def setup_group_id(line_system: LINENotificationSystem):
    """グループID設定"""
    print("\n👥 グループID追加")
    
    if not line_system.config["notification_settings"]["enabled"]:
        print("❌ 先にChannel Access Tokenを設定してください")
        return
    
    print("グループIDの取得方法:")
    print("1. LINE Botをグループに招待")
    print("2. グループで何かメッセージを送信")
    print("3. Webhook URLでグループIDを確認")
    
    print("\nグループID例: C1234567890abcdef...")
    group_id = input("グループID: ").strip()
    
    if not group_id.startswith("C"):
        print("❌ グループIDは'C'で始まる必要があります")
        return
    
    try:
        line_system.add_notification_target(group_id, "group")
        print(f"✅ グループID追加完了: {group_id}")
    except Exception as e:
        print(f"❌ 追加エラー: {e}")

def setup_notification_settings(line_system: LINENotificationSystem):
    """通知設定変更"""
    print("\n⚙️ 通知設定変更")
    
    settings = line_system.config["notification_settings"]
    
    print("現在の設定:")
    for key, value in settings.items():
        if key != "enabled":
            status = "✅ 有効" if value else "❌ 無効"
            print(f"  {key}: {status}")
    
    print("\n変更する設定項目:")
    print("1. リスク通知 (risk_notifications)")
    print("2. 欠航アラート (cancellation_alerts)")
    print("3. データマイルストーン (data_milestones)")
    print("4. 日次サマリー (daily_summary)")
    print("5. Flex Message使用 (use_flex_messages)")
    
    try:
        choice = input("選択 (1-5): ").strip()
        setting_keys = {
            "1": "risk_notifications",
            "2": "cancellation_alerts", 
            "3": "data_milestones",
            "4": "daily_summary",
            "5": "use_flex_messages"
        }
        
        setting_key = setting_keys.get(choice)
        if not setting_key:
            print("無効な選択です")
            return
        
        current_value = settings[setting_key]
        new_value = not current_value
        
        line_system.config["notification_settings"][setting_key] = new_value
        line_system._save_config(line_system.config)
        
        status = "有効" if new_value else "無効"
        print(f"✅ {setting_key}を{status}に変更しました")
        
    except Exception as e:
        print(f"❌ 設定変更エラー: {e}")

async def send_test_notification(line_system: LINENotificationSystem):
    """テスト通知送信"""
    print("\n📤 テスト通知送信")
    
    if not line_system.config["notification_settings"]["enabled"]:
        print("❌ LINE通知が無効です")
        return
    
    if not line_system.config["user_ids"] and not line_system.config["group_ids"]:
        print("❌ 通知対象が登録されていません")
        return
    
    print("送信するテストメッセージタイプ:")
    print("1. テキストメッセージ")
    print("2. 運航予報 Flex Message")
    print("3. 欠航アラート")
    print("4. データマイルストーン通知")
    
    try:
        choice = input("選択 (1-4): ").strip()
        
        if choice == "1":
            message = line_system.create_text_message(
                "🧪 LINE通知システムのテストです。\n"
                "北海道フェリー予測システムからのテスト通知が正常に届きました！"
            )
            success = await line_system.broadcast_to_all_targets(message)
            
        elif choice == "2":
            test_forecast = {
                "risk_level": "High",
                "risk_score": 75.0,
                "service": {
                    "route_name": "稚内 ⇔ 鴛泊 (テスト)",
                    "departure_time": "08:00便"
                },
                "weather_conditions": {
                    "wind_speed": 18.5,
                    "wave_height": 3.2,
                    "visibility": 2.0,
                    "temperature": -5.0
                },
                "recommendation": "システムテスト - 実際のリスクではありません",
                "confidence": 0.85,
                "prediction_method": "test"
            }
            success = await line_system.send_risk_alert(test_forecast)
            
        elif choice == "3":
            success = await line_system.send_cancellation_alert(
                route_name="稚内 ⇔ 鴛泊 (テスト)",
                departure_time="08:00便",
                reason="システムテスト - 実際の欠航ではありません"
            )
            
        elif choice == "4":
            success = await line_system.send_data_milestone_notification(100, 100)
            
        else:
            print("無効な選択です")
            return
        
        if success:
            print("✅ テスト通知送信成功")
        else:
            print("❌ テスト通知送信失敗")
            
    except Exception as e:
        print(f"❌ テスト送信エラー: {e}")

def generate_friend_qr_code(line_system: LINENotificationSystem):
    """友だち追加QRコード生成"""
    try:
        # 仮のBot URL（実際はLINE Developersコンソールから取得）
        bot_url = "https://line.me/R/ti/p/@your-bot-id"
        
        # QRコード生成
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(bot_url)
        qr.make(fit=True)
        
        # QRコード画像作成
        img = qr.make_image(fill_color="black", back_color="white")
        
        # ファイル保存
        qr_file = line_system.data_dir / "line_friend_qr.png"
        img.save(qr_file)
        
        print(f"\n📱 友だち追加QRコードを生成しました: {qr_file}")
        print("注意: 実際のBot URLをLINE Developersコンソールから取得して更新してください")
        
    except ImportError:
        print("❌ QRコード生成にはpillowとqrcodeライブラリが必要です")
        print("pip install pillow qrcode[pil]")
    except Exception as e:
        print(f"❌ QRコード生成エラー: {e}")

def display_current_settings(line_system: LINENotificationSystem):
    """現在の設定表示"""
    print("\n📋 現在のLINE通知設定")
    print("=" * 50)
    
    config = line_system.config
    
    print(f"通知システム: {'✅ 有効' if config['notification_settings']['enabled'] else '❌ 無効'}")
    
    print("\nChannel情報:")
    token_set = "✅ 設定済み" if config.get("channel_access_token") else "❌ 未設定"
    secret_set = "✅ 設定済み" if config.get("channel_secret") else "❌ 未設定"
    print(f"  Channel Access Token: {token_set}")
    print(f"  Channel Secret: {secret_set}")
    
    print("\n通知対象:")
    print(f"  登録ユーザー: {len(config['user_ids'])}人")
    print(f"  登録グループ: {len(config['group_ids'])}個")
    
    print("\n通知種類:")
    settings = config["notification_settings"]
    for setting, enabled in settings.items():
        if setting != "enabled":
            status = "✅ ON" if enabled else "❌ OFF"
            print(f"  {setting:20}: {status}")
    
    print(f"\n設定ファイル: {line_system.config_file}")
    
    # ユーザーID・グループID一覧表示（一部マスク）
    if config['user_ids']:
        print("\n登録ユーザーID:")
        for user_id in config['user_ids']:
            masked_id = user_id[:8] + "..." if len(user_id) > 8 else user_id
            print(f"  {masked_id}")
    
    if config['group_ids']:
        print("\n登録グループID:")
        for group_id in config['group_ids']:
            masked_id = group_id[:8] + "..." if len(group_id) > 8 else group_id
            print(f"  {masked_id}")

def create_webhook_receiver_example():
    """Webhook受信サンプルコード生成"""
    example_code = '''
# LINE Bot Webhook受信サンプル（Flask使用）

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage

app = Flask(__name__)

# 設定
line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')
handler = WebhookHandler('YOUR_CHANNEL_SECRET')

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # ユーザーIDまたはグループIDを取得
    user_id = event.source.user_id
    
    # グループの場合
    if hasattr(event.source, 'group_id'):
        group_id = event.source.group_id
        print(f"Group ID: {group_id}")
    
    print(f"User ID: {user_id}")
    
    # 自動応答（オプション）
    line_bot_api.reply_message(
        event.reply_token,
        TextMessage(text=f"あなたのユーザーIDは {user_id} です")
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)

# 使用方法:
# 1. ngrok等でローカルサーバーを外部公開
# 2. LINE DevelopersでWebhook URLを設定
# 3. ユーザーがメッセージを送信するとIDが表示される
'''
    
    print("\n💻 Webhook受信サンプルコード")
    print("=" * 50)
    print(example_code)

def main():
    """メイン実行"""
    print("🔧 LINE通知システム設定ツール")
    
    print("\n実行モード:")
    print("1. 設定ガイド表示")
    print("2. 対話式設定")
    print("3. 現在の設定確認")
    print("4. Webhook受信サンプルコード表示")
    
    try:
        choice = input("選択 (1-4): ").strip()
        
        if choice == "1":
            display_setup_guide()
        elif choice == "2":
            interactive_setup()
        elif choice == "3":
            data_dir = Path(__file__).parent / "data"
            line_system = LINENotificationSystem(data_dir)
            display_current_settings(line_system)
        elif choice == "4":
            create_webhook_receiver_example()
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n設定を中断しました")

if __name__ == "__main__":
    main()