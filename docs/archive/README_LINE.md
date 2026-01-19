# LINE通知機能

北海道フェリー予測システムのLINE通知機能の設定・利用ガイドです。

## 📋 機能概要

### 通知タイプ

- **🔴 緊急アラート**: 欠航確定・危険レベル85%以上
- **🟠 高リスク通知**: リスクレベル70%以上  
- **🟡 運航遅延通知**: 遅延情報
- **📊 データマイルストーン**: 50, 100, 200, 300, 400, 500件達成時
- **📅 日次サマリー**: 1日の運航状況まとめ

### メッセージ形式

- **📱 Flex Message**: リッチなカード形式メッセージ
- **📝 テキストメッセージ**: シンプルなテキスト形式
- **⚡ Quick Reply**: ワンタップ返信ボタン

### 通知対象

- **👤 個人ユーザー**: 個別のLINEユーザーへプッシュ通知
- **👥 グループ**: LINEグループへの一括通知
- **📢 ブロードキャスト**: 友だち全員への配信

## 🔧 設定方法

### 1. LINE Messaging API設定

#### LINE Developers アカウント作成
1. [LINE Developers](https://developers.line.biz) にアクセス
2. LINEアカウントでログイン
3. 新規プロバイダー作成（例: フェリー予報）

#### Messaging APIチャンネル作成
1. **新規チャンネル作成** → **Messaging API**を選択
2. チャンネル情報入力:
   - **チャンネル名**: フェリー予報Bot
   - **チャンネル説明**: 北海道フェリー運航予報
   - **大業種**: 旅行・交通
   - **小業種**: 海運

#### トークン取得
1. **Basic settings** → **Channel Secret**をコピー
2. **Messaging API** → **Channel access token**を発行・コピー

### 2. Bot設定

#### Messaging API設定
```
- 応答メッセージ: 無効
- あいさつメッセージ: 有効  
- Webhook: 不要（プッシュ通知のみ）
```

### 3. システム設定

```bash
# 対話式設定ツール実行
python line_setup_guide.py
```

または直接コードで設定:

```python
from line_notification_system import LINENotificationSystem
from pathlib import Path

# 初期化
line_system = LINENotificationSystem(Path("data"))

# Channel設定
line_system.setup_line_bot(
    channel_access_token="YOUR_CHANNEL_ACCESS_TOKEN",
    channel_secret="YOUR_CHANNEL_SECRET"
)

# 通知対象追加
line_system.add_notification_target("USER_ID", "user")       # 個人
line_system.add_notification_target("GROUP_ID", "group")     # グループ
```

### 4. ユーザーID・グループID取得

#### 簡易取得方法
```python
# Flask + LINE Bot SDK使用例
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    print(f"User ID: {user_id}")  # これをシステムに登録
    
    # グループの場合
    if hasattr(event.source, 'group_id'):
        group_id = event.source.group_id
        print(f"Group ID: {group_id}")
```

## 📱 通知例

### 高リスクアラート（Flex Message）
```json
{
  "type": "flex",
  "altText": "🟠 フェリー運航予報 High",
  "contents": {
    "type": "bubble",
    "header": {
      "type": "box",
      "contents": [
        {
          "type": "text", 
          "text": "🟠 フェリー運航予報",
          "weight": "bold",
          "color": "#FFFFFF"
        }
      ],
      "backgroundColor": "#FF8000"
    },
    "body": {
      "contents": [
        {
          "type": "text",
          "text": "🚢 稚内 ⇔ 鴛泊"
        },
        {
          "type": "text", 
          "text": "⏰ 08:00便"
        },
        {
          "type": "text",
          "text": "⚠️ High (75%)"
        }
      ]
    }
  }
}
```

### 欠航アラート（テキスト）
```
🔴 フェリー欠航のお知らせ

🚢 航路: 稚内 ⇔ 鴛泊
⏰ 便: 08:00便  
📝 理由: 強風・高波のため

最新の運航情報をご確認ください
```

### データマイルストーン
```
📊 データマイルストーン達成

🎯 200件達成！
📈 総データ数: 200件
🚀 ⚡ ハイブリッド予測開始！高精度予測システム稼働
```

## 🛠️ 開発者向け

### カスタム通知送信

```python
# テキストメッセージ
message = line_system.create_text_message("カスタムメッセージ")
await line_system.broadcast_to_all_targets(message)

# 個別送信
await line_system.send_line_message(message, "USER_ID", "push")

# 予報結果通知
forecast_result = {
    "risk_level": "High",
    "risk_score": 75.0,
    "service": {"route_name": "稚内 ⇔ 鴛泊", "departure_time": "08:00"},
    "weather_conditions": {"wind_speed": 18.5},
    "recommendation": "注意が必要です"
}
await line_system.send_risk_alert(forecast_result)
```

### Flex Message カスタマイズ

```python
# カスタムFlex Message
custom_flex = {
    "type": "flex",
    "altText": "カスタム通知",
    "contents": {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "カスタム内容",
                    "weight": "bold"
                }
            ]
        }
    }
}

await line_system.send_line_message(custom_flex)
```

### 設定カスタマイズ

```python
# 設定変更
line_system.config["notification_settings"]["use_flex_messages"] = True
line_system.config["notification_settings"]["use_quick_reply"] = True
line_system.config["message_format"]["brand_color"] = "#FF6B35"
line_system._save_config(line_system.config)
```

## 🔍 トラブルシューティング

### よくある問題

**❌ 通知が送信されない**
```bash
# 設定確認
python line_setup_guide.py
# → 選択: 3 (現在の設定確認)

# ログ確認
tail -f ferry_monitoring.log
```

**❌ Channel Access Token エラー**
- トークンの有効期限確認
- Channel typeがMessaging APIか確認
- トークンが正しくコピーされているか確認

**❌ ユーザーIDが取得できない**
- WebhookのURL設定確認
- SSL証明書の有効性確認
- ngrokなどのトンネルツール使用を検討

### デバッグモード

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 詳細ログでデバッグ
line_system = LINENotificationSystem(data_dir)
```

### 通知制限

- **Push API制限**: 月間1000通まで（開発者プラン）
- **メッセージ長**: テキスト5000文字まで
- **Flex Message**: JSON 10KB まで

## 🚀 システム統合

### 監視システムとの連携

LINE通知は以下のタイミングで自動送信されます:

1. **運航状況変化時**: 欠航・遅延発生
2. **高リスク検出時**: リスクスコア70%以上  
3. **データマイルストーン**: 50, 100, 200, 300, 400, 500件達成
4. **日次サマリー**: 毎日の運航統計

### 予報システムとの連携

```python
from ferry_forecast_ui import FerryForecastUI

ui_system = FerryForecastUI()

# 7日間予報生成時に高リスク便を自動通知
forecasts = await ui_system.generate_7day_forecasts()
for forecast in forecasts:
    if forecast.risk_score >= 70:
        if hasattr(ui_system.monitoring_system, 'line_system'):
            await ui_system.monitoring_system.line_system.send_risk_alert(forecast)
```

### Discord・LINE同時通知

```python
# 両方の通知システムが有効な場合、同時送信
async def send_dual_notification(forecast_result):
    tasks = []
    
    if discord_system:
        tasks.append(discord_system.send_risk_alert(forecast_result))
    
    if line_system:  
        tasks.append(line_system.send_risk_alert(forecast_result))
    
    await asyncio.gather(*tasks)
```

## 📞 サポート

### 必要パッケージ

```bash
pip install aiohttp line-bot-sdk flask qrcode pillow
```

### 参考リンク

- [LINE Messaging API ドキュメント](https://developers.line.biz/ja/docs/messaging-api/)
- [Flex Message Simulator](https://developers.line.biz/flex-simulator/)
- [LINE Bot SDK for Python](https://github.com/line/line-bot-sdk-python)

---

**📞 サポート**: システム統合や設定でご不明な点がございましたら、開発チームまでお問い合わせください。