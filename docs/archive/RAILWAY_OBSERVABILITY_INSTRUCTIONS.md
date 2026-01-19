# 🎯 Railway でデータコレクターを実行する手順

## ✅ 確認されたエラー

スクリーンショットから確認されたエラー：

```
sqlite3.OperationalError: no such table: cancellation_forecast
```

**これは予想通りです！** データベーステーブルがまだ作成されていません。

---

## 🔧 解決手順

### ステップ1: Observability タブをクリック

画面上部のメニューで **"Observability"** をクリックしてください。

```
[Architecture] [Observability] [Logs] [Settings] [Share]
                      ↑
                  ここをクリック
```

### ステップ2: Cron Jobs を探す

Observability ページで以下を探してください：

- **"Cron Jobs"** セクション
- または **"Scheduled Tasks"**
- または左側メニューに **"Cron"** タブ

### ステップ3: Cron Job を手動実行

以下のいずれかのジョブを見つけてください：

```
✓ forecast_collection_morning
  Schedule: 0 5 * * *
  Command: python weather_forecast_collector.py
  [▶️ Run Now] または [Trigger] ボタン

✓ forecast_collection_midday
  Schedule: 0 11 * * *
  [▶️ Run Now]

✓ forecast_collection_evening
  Schedule: 0 17 * * *
  [▶️ Run Now]

✓ forecast_collection_night
  Schedule: 0 23 * * *
  [▶️ Run Now]
```

**いずれか1つの "Run Now" ボタンをクリック**

### ステップ4: 実行完了を確認

#### Logs タブで確認

1. 上部メニューの **"Logs"** をクリック
2. 実行ログを確認：

**期待されるログ:**
```
============================================================
WEATHER FORECAST COLLECTOR
============================================================

📅 Forecast date: 2025-10-22
🌐 Collecting from JMA and Open-Meteo APIs...

[JMA] ✅ Successfully collected 7 days of forecasts
[Open-Meteo] ✅ Collected 168 hours × 3 locations

💾 Saving to database...
✅ Created table: weather_forecast
✅ Created table: cancellation_forecast
✅ Created table: forecast_collection_log
✅ Saved 499 weather forecast records
✅ Calculated risks for 6 routes × 7 days

✅ Collection completed successfully
```

**所要時間:** 1-2分

### ステップ5: アプリをリロード

```
https://web-production-27f768.up.railway.app/
```

ブラウザでリロードしてください。

**期待される画面:**
```
🚢 北海道フェリー運航予報
稚内⇔利尻・礼文島　7日間欠航リスク予測
⚠️ X日間 高リスク

📊 予報日数: 7
⚠️ 高リスク日: X
🌊 気象データ: 499
🗓️ データ期間: 7日

[7日間の予報カード × 7]
[航路別予報 × 6]
```

---

## 📸 Observability ページの探し方

### 画面構成

スクリーンショットから見える上部メニュー：

```
[Architecture] [Observability] [Logs] [Settings] [Share]
```

**"Observability" をクリック** → Cron Jobs が表示されるはず

### Observability ページの構成（予想）

```
┌─────────────────────────────────────────┐
│ Observability                           │
├─────────────────────────────────────────┤
│                                         │
│ Metrics                                 │
│ [グラフ表示]                            │
│                                         │
│ Cron Jobs                               │
│ ┌─────────────────────────────────────┐ │
│ │ forecast_collection_morning         │ │
│ │ Schedule: 0 5 * * *                 │ │
│ │ Last Run: Never                     │ │
│ │ Status: Pending                     │ │
│ │ [▶️ Run Now] [Edit]                 │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ forecast_collection_midday          │ │
│ │ ... (同様)                          │ │
│ └─────────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

**"▶️ Run Now" ボタンを探してクリック**

---

## 🔄 代替方法（もし Observability に Cron Jobs がない場合）

### 方法A: Settings から確認

1. **Settings タブをクリック**
2. 左側メニューで **"Cron"** または **"Scheduled Tasks"** を探す
3. Cron Jobs のリストが表示される
4. "Run Now" をクリック

### 方法B: 左サイドバーから確認

スクリーンショットの左側に見える縦のアイコンバー：

```
[:::] ← グリッドアイコン
[+]
[-]
[⛶]
[↶]
[↷]
```

1. **グリッドアイコン [:::]** をクリック
2. メニューが展開される
3. **"Cron Jobs"** を探す

### 方法C: 検索機能を使用

1. **Ctrl + K** または **Cmd + K** を押す
2. Railway のコマンドパレットが開く
3. **"cron"** と入力
4. Cron Jobs ページに移動

---

## ⏰ 自動実行を待つ場合

もし手動実行が見つからない場合、次回の自動実行を待つこともできます：

### 日本時間でのスケジュール

```
現在時刻: 2025-10-23 01:54 (JST)

次回実行:
- 05:00 JST (あと約3時間)  ← 最も近い
- 11:00 JST
- 17:00 JST
- 23:00 JST
```

**あと約3時間待てば自動的に実行され、エラーが解消されます。**

---

## 🎯 推奨アクション（優先順）

### 1. Observability タブを開く
```
上部メニュー → Observability
→ Cron Jobs セクションを探す
→ Run Now をクリック
```

### 2. Settings タブを確認
```
上部メニュー → Settings
→ 左メニューで Cron を探す
→ Run Now をクリック
```

### 3. 自動実行を待つ（最も簡単）
```
何もせず約3時間待つ
→ 05:00 JST に自動実行
→ エラー自動解消
```

---

## 📊 実行後の確認

### A. Logs で確認

```
Logs タブ → 最新のログを確認
```

**成功メッセージ:**
```
✅ Collection completed successfully
✅ Saved 499 weather forecast records
```

### B. アプリで確認

```
https://web-production-27f768.up.railway.app/
```

**表示されるべき内容:**
- 7日間予報カード
- 航路別予報リスト
- 統計情報（予報日数: 7、気象データ: 499）

### C. PWA確認

```
https://web-production-27f768.up.railway.app/manifest.json
https://web-production-27f768.up.railway.app/service-worker.js
https://web-production-27f768.up.railway.app/static/icon-192.png
```

すべて正常に表示される ✅

---

## 💡 次のステップ

### Observability を開いて確認してください

1. **"Observability" タブをクリック**
2. **Cron Jobs を探す**
3. **スクリーンショットを共有**（もし見つからない場合）

Observability ページの画面を見せていただければ、
具体的な手順をお伝えできます！

---

**現在時刻:** 2025-10-23 01:54 JST
**次回自動実行:** 05:00 JST（約3時間後）
**推奨:** Observability → Cron Jobs → Run Now

🚀 Observability タブを開いてみてください！
