# 🔧 データコレクター実行の代替方法

## 📋 現状

"New Deployment" オプションが見つからない場合の代替手順です。

---

## 方法1: Cron Job を手動トリガー（最も簡単）

### 手順

1. **Railway Dashboard を開く**
   ```
   https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104
   ```

2. **左側メニューまたは画面内で "Cron" または "Observability" を探す**

3. **Cron Jobs のリストを確認**
   - `forecast_collection_morning`
   - `forecast_collection_midday`
   - `forecast_collection_evening`
   - `forecast_collection_night`

4. **いずれかの横にある "Run Now" または "▶️" ボタンをクリック**

5. **実行完了を待つ（1-2分）**

6. **アプリをリロード**
   ```
   https://web-production-27f768.up.railway.app/
   ```

---

## 方法2: 次回のCron実行を待つ

### スケジュール（日本時間）

```
- 05:00 JST (深夜5時)
- 11:00 JST (午前11時)
- 17:00 JST (午後5時)
- 23:00 JST (午後11時)
```

**現在時刻から最も近い時刻まで待つ**

### 自動実行後

- データベースが自動的に初期化される
- 500エラーが自動的に解消される
- アプリが正常に動作開始

**待ち時間:** 最大6時間

---

## 方法3: Railway CLI を使用

### CLI インストール（まだの場合）

#### Windows (PowerShell)

```powershell
iwr https://cli.railway.app/install.ps1 | iex
```

#### Mac/Linux

```bash
curl -fsSL https://cli.railway.app/install.sh | sh
```

### CLI でコマンド実行

```bash
# プロジェクトにリンク
railway link 7c0afe06-afda-4433-bd88-e94a9556e104

# サービスを選択（対話形式）
railway service

# コマンド実行
railway run python weather_forecast_collector.py
```

または

```bash
# 直接実行
railway run --service ad724015-e917-4c35-9fdf-a5b50330c29b python weather_forecast_collector.py
```

### 期待される出力

```
============================================================
WEATHER FORECAST COLLECTOR
============================================================

📅 Forecast date: 2025-10-22
🌐 Collecting from JMA and Open-Meteo APIs...

[JMA] ✅ Successfully collected 7 days of forecasts
[Open-Meteo] ✅ Collected 168 hours × 3 locations

💾 Saving to database...
✅ Saved 499 weather forecast records
✅ Calculated risks for 6 routes × 7 days

✅ Collection completed successfully
```

---

## 方法4: ローカルでデータベースを作成してアップロード

### 手順

#### A. ローカルでコレクター実行

```bash
cd C:\Users\ichry\OneDrive\Desktop\hokkaido_ferry_forecast

python weather_forecast_collector.py
```

これで `ferry_weather_forecast.db` が作成されます。

#### B. データベースをRailwayにアップロード

**注意:** Railwayの無料プラン・Hobbyプランでは、ファイルアップロードが難しい場合があります。

**代替:** Railway Volumes を使用

1. **Settings → Volumes**
2. **"Add Volume" をクリック**
3. **Mount Path:** `/app/ferry_weather_forecast.db`
4. データベースファイルを手動アップロード

**ただし、この方法は複雑なので、方法1または2を推奨します。**

---

## 方法5: forecast_dashboard.py を修正（暫定対処）

### データベースエラーを回避

データベースが空でもエラーを出さないように修正：

#### 修正案

```python
# forecast_dashboard.py の各メソッドに try-except を追加

def get_7day_forecast(self):
    """Get 7-day forecast summary"""
    try:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        # ... existing code ...
        conn.close()
        return forecast_list
    except sqlite3.OperationalError:
        # データベースがまだ初期化されていない
        return []

def get_today_detail(self):
    """Get detailed forecast for today"""
    try:
        # ... existing code ...
        return hourly
    except sqlite3.OperationalError:
        return []

def get_routes_forecast(self, date=None):
    """Get forecast by route"""
    try:
        # ... existing code ...
        return routes
    except sqlite3.OperationalError:
        return []

def get_statistics(self):
    """Get collection statistics"""
    try:
        # ... existing code ...
        return {
            'weather_records': weather_count,
            'weather_days': weather_days,
            'forecast_days': cancel_days,
            'high_risk_days': high_risk_days,
            'last_updated': last_collection
        }
    except sqlite3.OperationalError:
        return {
            'weather_records': 0,
            'weather_days': 0,
            'forecast_days': 0,
            'high_risk_days': 0,
            'last_updated': 'データ収集待ち'
        }
```

**ただし、これは暫定対処で、根本的な解決にはなりません。**

---

## 方法6: Deployments から再デプロイ

### 手順

1. **Deployments タブを開く**

2. **最新のデプロイ（Status: Active）を探す**

3. **デプロイの右側にある "⋮" または "..." をクリック**

4. **"Redeploy" を選択**

5. **確認ダイアログで "Redeploy" をクリック**

### 注意

これは単に再デプロイするだけで、データコレクターは実行されません。
データベースは空のままなので、500エラーは解消されません。

---

## 🎯 推奨アクション（優先順）

### 1位: 方法1（Cron Job 手動トリガー）

最も簡単で確実です。
```
Dashboard → Cron Jobs → forecast_collection_morning → Run Now
```

### 2位: 方法2（次回Cron実行を待つ）

何もせずに最大6時間待つだけです。
```
次回実行: 05:00/11:00/17:00/23:00 JST
```

### 3位: 方法3（Railway CLI）

CLIをインストールする必要がありますが、柔軟性が高いです。
```
railway run python weather_forecast_collector.py
```

---

## 🔍 Railway UI の確認ポイント

### 新しいUI (2024-2025)

画面を確認してください：

#### トップバー
```
[Project] [Service] [Deployments] [Settings] [Observability]
```

#### 左サイドバー
```
Overview
Deployments
Metrics
Logs
Variables
Cron Jobs  ← ここを探す
Settings
```

#### Cron Jobs セクション

```
┌─────────────────────────────────────────┐
│ Cron Jobs                               │
├─────────────────────────────────────────┤
│                                         │
│ forecast_collection_morning             │
│ Schedule: 0 5 * * *                     │
│ Command: python weather_forecast_...    │
│ Last Run: -                             │
│ [▶️ Run Now]  [Edit]  [Delete]         │
│                                         │
│ forecast_collection_midday              │
│ Schedule: 0 11 * * *                    │
│ [▶️ Run Now]  [Edit]  [Delete]         │
│                                         │
│ ... (他のCron Jobsも同様)               │
└─────────────────────────────────────────┘
```

**"▶️ Run Now" ボタンを探してクリック**

---

## 🐛 もし Cron Jobs が表示されない場合

### 確認事項

1. **railway.json が正しくデプロイされているか**
   ```
   Deployments → File Browser → railway.json 確認
   ```

2. **Cron Jobs が有効になっているか**
   ```
   Settings → Service Settings → Cron Jobs: Enabled
   ```

3. **Hobby プラン以上にアップグレードされているか**
   ```
   Free プランでは Cron Jobs は使えません
   → すでに Hobby ($5/月) にサブスクライブ済みなのでOK ✅
   ```

---

## 📱 画面のスクリーンショットを共有

もし上記の方法が見つからない場合：

1. **Railway Dashboard の画面**
2. **左側メニューの内容**
3. **上部メニューバーの内容**

を共有していただければ、具体的な手順をご案内できます。

---

## ⏰ 暫定的な対処（今すぐ動作させたい場合）

### 簡易版アプリを表示

データがなくても500エラーを出さないように、
forecast_dashboard.py に暫定的な修正を加えることもできます。

**ただし、次回のCron実行（最大6時間）を待つのが最も簡単です。**

---

## ✅ どの方法を選びますか？

### オプションA: Cron Job を探して手動実行（推奨）
- Dashboard で "Cron" または "Observability" を探す
- "Run Now" ボタンをクリック

### オプションB: 次回実行を待つ（最も簡単）
- 何もせず最大6時間待つ
- 自動的に解消される

### オプションC: Railway CLI を使用
- CLI をインストール
- `railway run python weather_forecast_collector.py` 実行

### オプションD: 画面を共有
- Railway Dashboard のスクリーンショット共有
- 具体的な手順をご案内

---

**次のアクション:**
Railway Dashboard で "Cron" または "Cron Jobs" というメニューを探してみてください。
見つからない場合は、画面の構成を教えていただければサポートします！

---

**作成日:** 2025-10-22
**アプリURL:** https://web-production-27f768.up.railway.app/
**目標:** データコレクター実行 → 500エラー解消
