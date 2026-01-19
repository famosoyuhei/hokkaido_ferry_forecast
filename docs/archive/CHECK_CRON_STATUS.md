# 🔍 Cron Job 実行状況の確認

## 🚨 現状

まだ500エラーが出ている：
```
Internal Server Error
The server encountered an internal error...
```

**原因:** Cron Jobがまだ実行されていない、または失敗した可能性

---

## 📊 確認手順

### ステップ1: 現在時刻の確認

**現在の日本時間は何時ですか？**

- 05:00 JST より前 → まだ実行されていない（正常）
- 05:00 JST より後 → 実行されたはずなのでログ確認が必要

### ステップ2: Railway Logs で確認

#### A. Deploy Logs を確認

1. **Railway Dashboard を開く**
   ```
   https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104/service/ad724015-e917-4c35-9fdf-a5b50330c29b
   ```

2. **"Deploy Logs" タブをクリック**

3. **時刻フィルターを設定**
   - 左上の時刻範囲を選択
   - "Last 6 hours" または "Last 12 hours" を選択

4. **05:00前後のログを探す**

**期待されるログ（成功の場合）:**
```
[2025-10-23 05:00:XX] Starting cron job: forecast_collection_morning
[2025-10-23 05:00:XX] WEATHER FORECAST COLLECTOR
[2025-10-23 05:00:XX] Collecting from JMA and Open-Meteo...
[2025-10-23 05:01:XX] ✅ Collection completed successfully
[2025-10-23 05:01:XX] ✅ Saved 499 weather forecast records
```

**エラーがある場合:**
```
[2025-10-23 05:00:XX] ❌ Error: ...
```

---

## 🔧 ケース別の対処法

### ケースA: まだ05:00 JSTになっていない

**対処:** 05:00 JSTまで待つ

**次回実行:**
- 11:00 JST
- 17:00 JST
- 23:00 JST

### ケースB: 05:00 JSTを過ぎたがログに実行記録がない

**原因:** Cron Jobが実行されていない

**可能性:**
1. railway.json の cron 設定が読み込まれていない
2. Hobby プランの Cron Jobs 機能が有効になっていない
3. タイムゾーンの問題（UTCとJSTの違い）

**対処:** 手動でデータコレクターを実行

### ケースC: ログにエラーがある

**確認:** エラーメッセージの内容

**よくあるエラー:**
- API接続エラー → 再実行で解決する可能性
- タイムアウト → 再実行で解決する可能性
- データベースエラー → 要調査

---

## 🛠️ 手動でデータコレクターを実行

### 方法1: Railway CLI（最も確実）

#### CLIインストール

**Windows PowerShell:**
```powershell
iwr https://cli.railway.app/install.ps1 | iex
```

**Mac/Linux:**
```bash
curl -fsSL https://cli.railway.app/install.sh | sh
```

#### コレクター実行

```bash
# プロジェクトにリンク
railway link 7c0afe06-afda-4433-bd88-e94a9556e104

# コレクター実行
railway run python weather_forecast_collector.py
```

**実行時間:** 1-2分

**期待される出力:**
```
============================================================
WEATHER FORECAST COLLECTOR
============================================================

📅 Forecast date: 2025-10-23
🌐 Collecting from JMA and Open-Meteo APIs...

[JMA] ✅ Successfully collected 7 days of forecasts
[Open-Meteo] ✅ Wakkanai: 168 hours
[Open-Meteo] ✅ Rishiri: 168 hours
[Open-Meteo] ✅ Rebun: 168 hours

💾 Saving to database...
✅ Created table: weather_forecast
✅ Created table: cancellation_forecast
✅ Saved 499 weather forecast records
✅ Calculated risks for 6 routes × 7 days

✅ Collection completed successfully
```

#### アプリ確認

```
https://web-production-27f768.up.railway.app/
```

500エラーが解消され、ダッシュボードが表示される ✅

---

### 方法2: ローカルで実行してデータベースをアップロード

#### A. ローカルで実行

```bash
cd C:\Users\ichry\OneDrive\Desktop\hokkaido_ferry_forecast

python weather_forecast_collector.py
```

これで `ferry_weather_forecast.db` が作成される

#### B. Railway にデプロイ

**注意:** この方法は複雑なので、方法1（Railway CLI）を推奨

---

## 🕐 Cron スケジュールの確認

### railway.json の設定

```json
{
  "cron": {
    "forecast_collection_morning": {
      "command": "python weather_forecast_collector.py",
      "schedule": "0 5 * * *"
    }
  }
}
```

### スケジュール形式

```
0 5 * * *
│ │ │ │ │
│ │ │ │ └─ 曜日 (0-7, 0と7は日曜)
│ │ │ └─── 月 (1-12)
│ │ └───── 日 (1-31)
│ └─────── 時 (0-23)
└───────── 分 (0-59)

0 5 * * * = 毎日05:00 UTC
```

**重要な注意:**
Railway の Cron スケジュールは **UTC** です！

### UTC vs JST

```
UTC 05:00 = JST 14:00 (午後2時)
UTC 20:00 = JST 05:00 (午前5時) ← これが正しい！
```

**問題発見！**

railway.json の設定が間違っています：
```json
"schedule": "0 5 * * *"  ← これは UTC 05:00 = JST 14:00
```

正しくは：
```json
"schedule": "0 20 * * *"  ← UTC 20:00 = JST 05:00
```

---

## 🔧 railway.json を修正

### 修正内容

すべての Cron スケジュールを UTC に変換：

```json
{
  "cron": {
    "forecast_collection_morning": {
      "command": "python weather_forecast_collector.py",
      "schedule": "0 20 * * *"  // JST 05:00 = UTC 20:00
    },
    "forecast_collection_midday": {
      "command": "python weather_forecast_collector.py",
      "schedule": "0 2 * * *"   // JST 11:00 = UTC 02:00
    },
    "forecast_collection_evening": {
      "command": "python weather_forecast_collector.py",
      "schedule": "0 8 * * *"   // JST 17:00 = UTC 08:00
    },
    "forecast_collection_night": {
      "command": "python weather_forecast_collector.py",
      "schedule": "0 14 * * *"  // JST 23:00 = UTC 14:00
    },
    "ferry_collection": {
      "command": "python improved_ferry_collector.py",
      "schedule": "0 21 * * *"  // JST 06:00 = UTC 21:00
    },
    "notification_morning": {
      "command": "python notification_service.py",
      "schedule": "30 21 * * *" // JST 06:30 = UTC 21:30
    }
  }
}
```

### 実際の実行時刻（修正後）

```
UTC 20:00 → JST 05:00 (forecast_collection_morning)
UTC 02:00 → JST 11:00 (forecast_collection_midday)
UTC 08:00 → JST 17:00 (forecast_collection_evening)
UTC 14:00 → JST 23:00 (forecast_collection_night)
UTC 21:00 → JST 06:00 (ferry_collection)
UTC 21:30 → JST 06:30 (notification_morning)
```

---

## 🚀 即座の解決策

### オプションA: 今すぐ手動実行（推奨）

```bash
# Railway CLI インストール
iwr https://cli.railway.app/install.ps1 | iex

# コレクター実行
railway link 7c0afe06-afda-4433-bd88-e94a9556e104
railway run python weather_forecast_collector.py
```

**1-2分で完了** → アプリが動作開始

### オプションB: railway.json を修正して次回実行を待つ

1. `railway.json` のタイムゾーンを修正
2. Git commit & push
3. 次回の実行を待つ（修正後の正しい時刻）

### オプションC: 現在のスケジュールで実行を待つ

**現在の設定（間違っているが動作する）:**
```
"schedule": "0 5 * * *" = UTC 05:00 = JST 14:00 (午後2時)
```

**次回実行:** 本日 14:00 JST（午後2時）

---

## 🎯 推奨アクション（優先順）

### 1位: Railway CLI で今すぐ実行

最も早く、確実に解決：
```bash
railway run python weather_forecast_collector.py
```

### 2位: 午後2時まで待つ

現在のスケジュールでの次回実行：
```
本日 14:00 JST（UTC 05:00）
```

### 3位: railway.json を修正

正しいタイムゾーンに修正してから待つ

---

## 📞 次のステップ

### すぐに動作させたい場合

**Railway CLI を使用:**
1. PowerShell を開く
2. CLI をインストール
3. コレクターを実行
4. アプリ確認

### 午後まで待てる場合

**何もせず待つ:**
1. 14:00 JST を待つ
2. 自動実行
3. アプリ確認

### 正しく修正したい場合

**railway.json を修正:**
1. タイムゾーンを UTC に修正
2. Git push
3. 次回の正しい時刻に実行

---

**どの方法を選びますか？**

おすすめは **Railway CLI で今すぐ実行** です！
最も早く（1-2分）アプリが動作します 🚀

---

**作成日:** 2025-10-23
**現状:** 500 Error（データベース未初期化）
**原因:** Cron Job のタイムゾーン設定ミス
**解決:** Railway CLI で手動実行、または 14:00 JST まで待つ
