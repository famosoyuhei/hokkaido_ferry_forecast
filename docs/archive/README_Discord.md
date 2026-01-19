# Discord通知機能

北海道フェリー予測システムのDiscord通知機能の設定・利用ガイドです。

## 📋 機能概要

### 通知タイプ

- **🔴 緊急アラート**: 欠航確定・危険レベル85%以上
- **🟠 高リスク通知**: リスクレベル70%以上  
- **🟡 運航遅延通知**: 遅延情報
- **📊 データマイルストーン**: 50, 100, 200, 300, 400, 500件達成時
- **📅 日次サマリー**: 1日の運航状況まとめ
- **📈 週次レポート**: 週間統計とトレンド分析

### 通知チャンネル分離

- **main**: 一般的な運航情報・リスク通知
- **alerts**: 緊急欠航アラート・高リスク警告
- **reports**: 日次・週次レポート・統計情報

## 🔧 設定方法

### 1. Discord Webhook作成

1. Discordサーバーの**サーバー設定**を開く
2. **連携サービス** → **ウェブフック**をクリック
3. **新しいウェブフック**を作成
4. 名前を設定（例: フェリー予報Bot）
5. 通知したいチャンネルを選択
6. **ウェブフックURLをコピー**

### 2. システム設定

```bash
# 対話式設定ツール実行
python discord_setup_guide.py
```

または直接コードで設定:

```python
from discord_notification_system import DiscordNotificationSystem
from pathlib import Path

# 初期化
discord_system = DiscordNotificationSystem(Path("data"))

# Webhook URL設定
webhook_url = "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
discord_system.setup_discord_webhook(webhook_url, "main")

# 複数チャンネル設定
discord_system.setup_discord_webhook(alerts_webhook, "alerts")
discord_system.setup_discord_webhook(reports_webhook, "reports")
```

### 3. 通知設定カスタマイズ

```python
# 設定ファイル編集: data/discord_config.json
{
  "notification_settings": {
    "enabled": true,
    "risk_notifications": true,     # リスク通知
    "cancellation_alerts": true,    # 欠航アラート  
    "data_milestones": true,        # データマイルストーン
    "daily_summary": true,          # 日次サマリー
    "weekly_report": false          # 週次レポート
  },
  "message_format": {
    "use_mentions": false,          # メンション使用
    "mention_role_id": "ROLE_ID"    # メンション対象ロールID
  }
}
```

## 📤 通知例

### 高リスクアラート
```
🟠 フェリー運航予報

🚢 航路: 稚内 ⇔ 鴛泊
⏰ 出発時刻: 08:00
⚠️ リスクレベル: High (75%)

🌤️ 気象条件
💨 風速: 18.5m/s
🌊 波高: 3.2m
👁️ 視界: 2.0km
🌡️ 気温: -5.0°C

💡 推奨事項
⚠️ 運航に注意が必要です。08:00便は遅延・欠航の可能性があります。

信頼度: 85% | hybrid
```

### 欠航アラート
```
🔴 フェリー欠航アラート

🚢 航路: 稚内 ⇔ 鴛泊  
⏰ 便: 08:00便
📝 理由: 強風・高波のため

最新の運航情報をご確認ください
```

### データマイルストーン
```
📊 データ収集マイルストーン達成

🎯 達成マイルストーン: 200件
📈 総データ数: 200件  
🚀 システム状況: ⚡ ハイブリッド予測開始！高精度予測システム稼働
```

## 🛠️ 開発者向け

### カスタム通知送信

```python
# 基本メッセージ送信
await discord_system.send_discord_message(
    content="テストメッセージ",
    channel_type="main"
)

# Embed形式送信
embed = {
    "title": "カスタム通知",
    "color": 0x00FF00,
    "fields": [
        {"name": "項目", "value": "内容", "inline": True}
    ]
}
await discord_system.send_discord_message(embed=embed)

# 予報結果通知
forecast_result = {
    "risk_level": "High",
    "risk_score": 75.0,
    "service": {"route_name": "稚内 ⇔ 鴛泊", "departure_time": "08:00"},
    "weather_conditions": {"wind_speed": 18.5},
    "recommendation": "注意が必要です"
}
await discord_system.send_risk_alert(forecast_result)
```

### 通知頻度制限

- 同一リスクレベル: 1時間に1回まで
- 緊急アラート: 制限なし
- データマイルストーン: 各マイルストーンで1回のみ

## 🔍 トラブルシューティング

### よくある問題

**❌ 通知が送信されない**
```bash
# 設定確認
python discord_setup_guide.py
# → 選択: 3 (現在の設定確認)

# ログ確認  
tail -f ferry_monitoring.log
```

**❌ Webhook URLが無効**
- URLが `https://discord.com/api/webhooks/` で始まっているか確認
- Webhook設定でチャンネル権限を確認

**❌ メッセージが文字化けする**
- 設定ファイルの文字エンコーディング確認
- `ensure_ascii=False` が設定されているか確認

### デバッグモード

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 詳細ログでデバッグ
discord_system = DiscordNotificationSystem(data_dir)
```

## 🚀 システム統合

### 監視システムとの連携

Discord通知は以下のタイミングで自動送信されます:

1. **運航状況変化時**: 欠航・遅延発生
2. **高リスク検出時**: リスクスコア70%以上
3. **データマイルストーン**: 50, 100, 200, 300, 400, 500件達成
4. **日次サマリー**: 毎日の運航統計
5. **システム完成時**: 500件データ収集完了

### 予報システムとの連携

```python
from ferry_forecast_ui import FerryForecastUI

ui_system = FerryForecastUI()

# 7日間予報生成時に高リスク便を自動通知
forecasts = await ui_system.generate_7day_forecasts()
for forecast in forecasts:
    if forecast.risk_score >= 70:
        await ui_system.monitoring_system.discord_system.send_risk_alert(forecast)
```

---

**📞 サポート**: システム統合や設定でご不明な点がございましたら、開発チームまでお問い合わせください。