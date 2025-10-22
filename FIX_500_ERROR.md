# 🔧 500 エラーの修正

## 🚨 現状

**アプリURL:**
```
https://web-production-27f768.up.railway.app/
```

**ステータス:** 500 Internal Server Error

**原因（推測）:** データベースが初期化されていない

---

## 🔍 エラー確認手順

### ステップ1: Railway Logs を確認

1. **Railway Dashboard を開く**
   ```
   https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104/service/ad724015-e917-4c35-9fdf-a5b50330c29b
   ```

2. **Deployments タブをクリック**

3. **最新のデプロイをクリック**

4. **"View Logs" をクリック**

5. **エラーメッセージを探す**

### 期待されるエラー

最も可能性が高いエラー：

```
sqlite3.OperationalError: no such table: weather_forecast
```

または

```
sqlite3.OperationalError: no such table: cancellation_forecast
```

これは**データベースがまだ初期化されていない**ことを意味します。

---

## ✅ 修正方法: データコレクター実行

### オプションA: 手動でコレクター実行（推奨）

#### 手順

1. **Railway Dashboard でサービスを開く**

2. **右上の「…」メニュー（3点ドット）をクリック**

3. **"New Deployment" を選択**

4. **"Run Command" を選択**

5. **コマンド入力:**
   ```
   python weather_forecast_collector.py
   ```

6. **"Deploy" をクリック**

7. **実行ログを確認**
   - "Collecting weather forecasts..." が表示される
   - "Collection completed successfully" が表示される
   - 所要時間: 1-2分

8. **アプリをリロード**
   ```
   https://web-production-27f768.up.railway.app/
   ```
   → ダッシュボードが正常に表示される ✅

---

### オプションB: Cron実行を待つ

次回の自動実行時刻（日本時間）:
```
- 05:00 JST (天気予報)
- 11:00 JST (天気予報)
- 17:00 JST (天気予報)
- 23:00 JST (天気予報)
- 06:00 JST (フェリー情報)
```

**現在時刻から次回実行まで最大6時間**

自動実行後、500エラーは自動的に解消されます。

---

### オプションC: forecast_dashboard.py を修正（将来の改善）

データベースが空の場合でもエラーを出さないように修正可能ですが、
現時点では**オプションA（手動実行）が最も早い解決方法**です。

---

## 🔍 その他の可能性のあるエラー

### エラー2: ModuleNotFoundError

```
ModuleNotFoundError: No module named 'forecast_dashboard'
```

**原因:** 間違ったリポジトリがデプロイされている

**確認:**
```
Deployments → File Browser
→ forecast_dashboard.py が存在するか
```

**対処:** リポジトリ接続を修正（FIX_RAILWAY_REPOSITORY.md 参照）

### エラー3: Import Error

```
ImportError: cannot import name 'app'
```

**原因:** forecast_dashboard.py の構文エラー

**対処:**
- 最新コミット（01683fe）がデプロイされているか確認
- リポジトリの main ブランチと一致しているか確認

---

## 📊 データコレクター実行後の期待される結果

### データベースに作成されるテーブル

```sql
weather_forecast
- forecast_date
- forecast_hour
- location
- wind_speed_min, wind_speed_max
- wave_height_min, wave_height_max
- visibility
- temperature
- weather_text
- pop (precipitation probability)
- data_source

cancellation_forecast
- forecast_for_date
- route
- risk_level (HIGH/MEDIUM/LOW/MINIMAL)
- risk_score
- wind_forecast
- wave_forecast
- visibility_forecast
- recommended_action

forecast_collection_log
- timestamp
- status
- records_collected
```

### ダッシュボードの表示

```
🚢 北海道フェリー運航予報
稚内⇔利尻・礼文島　7日間欠航リスク予測
⚠️ X日間 高リスク

📊 統計情報
予報日数: 7
高リスク日: X
気象データ: 400-500
データ期間: 7日

📅 7日間予報
[7日分のカード表示]
- 日付
- リスクレベル (HIGH/MEDIUM/LOW/MINIMAL)
- 風速、波高、視界

🛳️ 航路別予報（本日）
[6航路のリスト表示]
- 稚内 → 鴛泊（利尻）
- 稚内 → 香深（礼文）
- 鴛泊（利尻）→ 稚内
- 香深（礼文）→ 稚内
- 鴛泊（利尻）→ 香深（礼文）
- 香深（礼文）→ 鴛泊（利尻）
```

---

## 🎯 実行手順まとめ

### すぐに実行（推奨）

1. **Railway Dashboard を開く**
   ```
   https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104
   ```

2. **Service を選択**

3. **右上「…」→ New Deployment → Run Command**

4. **コマンド:**
   ```
   python weather_forecast_collector.py
   ```

5. **Deploy をクリック**

6. **1-2分待つ**

7. **アプリをリロード:**
   ```
   https://web-production-27f768.up.railway.app/
   ```

8. **ダッシュボードが表示される** ✅

---

## 🔄 コレクター実行のログ例

### 正常なログ

```
============================================================
WEATHER FORECAST COLLECTOR
============================================================

📅 Forecast date: 2025-10-22
🌐 Collecting from JMA and Open-Meteo APIs...

[JMA] Fetching forecast for Wakkanai/Soya region...
[JMA] ✅ Successfully collected 7 days of forecasts

[Open-Meteo] Fetching detailed forecasts...
[Open-Meteo] ✅ Wakkanai: 168 hours collected
[Open-Meteo] ✅ Rishiri: 168 hours collected
[Open-Meteo] ✅ Rebun: 168 hours collected

💾 Saving to database...
✅ Saved 499 weather forecast records
✅ Calculated cancellation risks for 6 routes × 7 days

📊 Summary:
- Weather forecasts: 499 records
- Cancellation forecasts: 42 records (6 routes × 7 days)
- High risk days: X
- Collection time: X seconds

✅ Collection completed successfully
```

### エラーがある場合のログ

```
❌ Error: Unable to connect to JMA API
❌ Error: Database connection failed
```

エラーがあれば、詳細を共有してください。

---

## ✅ 成功確認

データコレクター実行後、以下を確認：

### アプリアクセス
- [ ] `https://web-production-27f768.up.railway.app/` が表示される
- [ ] 500エラーが出ない
- [ ] ダッシュボードが表示される

### データ表示
- [ ] 予報日数が 7 になっている
- [ ] 7日間予報カードが表示される
- [ ] 航路別予報が6航路表示される
- [ ] 気象データ数が 400-500 になっている

### PWA機能
- [ ] `/manifest.json` が表示される
- [ ] `/service-worker.js` が表示される
- [ ] `/static/icon-192.png` が表示される

---

## 📱 PWA確認（エラー修正後）

500エラーが解消したら、PWA機能を確認：

### 1. Manifest.json
```
https://web-production-27f768.up.railway.app/manifest.json
```
→ JSON が表示される ✅

### 2. Service Worker
```
https://web-production-27f768.up.railway.app/service-worker.js
```
→ JavaScript コードが表示される ✅

### 3. アイコン
```
https://web-production-27f768.up.railway.app/static/icon-192.png
```
→ フェリーアイコンが表示される ✅

### 4. Chrome DevTools
```
F12 → Application → Manifest
```
→ PWA情報が表示される ✅

### 5. スマホインストール
- Android Chrome: 「ホーム画面に追加」ボタン表示
- iPhone Safari: 共有→「ホーム画面に追加」選択可能

---

## 🎉 完全成功の状態

すべて完了したら：

```
✅ アプリURL: https://web-production-27f768.up.railway.app/
✅ ダッシュボード表示: 正常
✅ データ収集: 完了（499レコード）
✅ 7日間予報: 表示
✅ 航路別予報: 6航路表示
✅ PWAファイル: すべて配信
✅ スマホインストール: 可能
✅ オフライン動作: 確認済み

🎊 フェリー予報PWAスマホアプリ完成！
```

---

## 📞 サポート

問題が解決しない場合：

1. **Railway Logs の全文を共有**
   - エラーメッセージ
   - スタックトレース

2. **実行したコマンド**
   ```
   python weather_forecast_collector.py
   ```
   の結果

3. **ブラウザのエラー**
   - F12 → Console のエラー

---

**作成日:** 2025-10-22
**アプリURL:** https://web-production-27f768.up.railway.app/
**現状:** 500 Error（データベース未初期化）
**対処:** データコレクター実行

🔧 今すぐデータコレクターを実行して、アプリを動作させましょう！
