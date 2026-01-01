# Railway CLI セットアップガイド

**日付**: 2025-12-31
**目的**: Railwayの本番環境でコマンドを実行し、データ収集を開始する

---

## 📥 Railway CLIのインストール

### 方法1: npm（推奨）

**前提条件**: Node.js 16以上がインストール済み

```bash
npm i -g @railway/cli
```

**インストール確認**:
```bash
railway --version
```

---

### 方法2: Scoop（Windows）

**前提条件**: Scoopがインストール済み

```bash
scoop install railway
```

---

### 方法3: 手動ダウンロード

1. GitHubから最新版をダウンロード:
   https://github.com/railwayapp/cli/releases

2. `railway.exe`をPATHに追加

---

## 🔐 Railway CLIの認証

### ステップ1: ログイン

```bash
railway login
```

- ブラウザが自動的に開きます
- Railwayアカウントでログイン
- CLIに認証情報が保存されます

---

## 🔗 プロジェクトをリンク

### ステップ2: プロジェクトをリンク

```bash
railway link
```

**プロジェクト情報**:
- **Project ID**: `c93898e1-5fe6-4fd7-b81d-33cb31b8addf`
- **Project Name**: hokkaido_ferry_forecast
- **Environment**: production

**選択肢が表示されたら**:
- プロジェクトを選択: `hokkaido_ferry_forecast`
- 環境を選択: `production`

---

## 🚀 データ収集の実行

### ステップ3: 気象予報データを収集

```bash
railway run python weather_forecast_collector.py
```

**期待される出力**:
```
======================================================================
WEATHER FORECAST COLLECTION - JMA + OPEN-METEO INTEGRATION
Collection time: 2025-12-31 XX:XX:XX
======================================================================

[INFO] Collecting JMA forecast for area 011000
[OK] Forecast from: 稚内地方気象台
[OK] Collected XXX JMA forecast records

[INFO] Collecting Open-Meteo forecast for 稚内
[OK] Collected XXX Open-Meteo forecast records

[INFO] Generating cancellation risk forecasts
[OK] Generated XXX cancellation risk forecasts

======================================================================
[SUCCESS] Collection completed
  Weather forecasts saved: XXX
  Cancellation forecasts generated: XXX
  Database: /data/ferry_weather_forecast.db
======================================================================
```

---

### ステップ4: 実運航データを収集

```bash
railway run python improved_ferry_collector.py
```

**期待される出力**:
```
======================================================================
IMPROVED FERRY DATA COLLECTION WITH WEATHER INTEGRATION
Time: 2025-12-31 XX:XX:XX
======================================================================

[INFO] Scraping ferry schedules from https://heartlandferry.jp/status/
[OK] 稚内-利尻 06:00-08:10 アマポーラ宗谷 - 運航

[OK] Collected X ferry schedule records
[OK] Saved X records to database

======================================================================
[SUCCESS] Ferry data collection completed
======================================================================
```

---

## ✅ 動作確認

### ステップ5: データ更新を確認

```bash
curl https://web-production-a628.up.railway.app/api/stats
```

**確認ポイント**:
```json
{
  "last_updated": "2025-12-31 XX:XX:XX",  ← 最新日時になっているか
  "weather_records": XXX,  ← 数値が増えているか
  "forecast_days": 7  ← 7日分あるか
}
```

---

## 🔄 定期的なデータ収集（オプション）

### 手動で定期実行する場合

**Windows タスクスケジューラー**:

1. タスクスケジューラーを開く
2. 新しいタスクを作成
3. トリガー: 毎日 05:00（JST）
4. アクション:
   ```
   Program: cmd.exe
   Arguments: /c railway run python weather_forecast_collector.py
   Working directory: C:\Users\ichry\OneDrive\Desktop\hokkaido_ferry_forecast
   ```

**注意**: Railway Cronジョブが正常に動作すれば、手動実行は不要です。

---

## 🧪 その他の便利なコマンド

### Railwayのログを表示

```bash
railway logs
```

リアルタイムでログを確認できます。

---

### Railwayの環境変数を確認

```bash
railway variables
```

現在設定されている環境変数を表示します。

---

### Railwayのシェルに入る

```bash
railway shell
```

本番環境のコンテナ内でコマンドを実行できます。

---

### Railway環境でPythonスクリプトを実行

```bash
railway run python <スクリプト名>
```

任意のスクリプトを本番環境で実行できます。

---

## 🚨 トラブルシューティング

### エラー: "No project linked"

**原因**: プロジェクトがリンクされていない

**解決策**:
```bash
railway link
```
プロジェクトを選択し直す

---

### エラー: "Authentication required"

**原因**: ログインしていない

**解決策**:
```bash
railway login
```

---

### エラー: "Database file not found"

**原因**: Volumeが設定されていない、またはパスが間違っている

**解決策**:
1. Railway管理画面でVolumeを確認（Mount Path: `/data`）
2. 環境変数 `RAILWAY_VOLUME_MOUNT_PATH=/data` を確認

---

## 📋 チェックリスト

実行前に確認:

```
□ Railway CLIがインストール済み（railway --version）
□ Railwayにログイン済み（railway whoami）
□ プロジェクトがリンク済み
□ Volumeが設定済み（/data）
□ 環境変数 RAILWAY_VOLUME_MOUNT_PATH=/data が設定済み
```

実行後に確認:

```
□ 気象予報データ収集が成功した
□ 実運航データ収集が成功した
□ /api/stats でlast_updatedが最新になっている
□ ダッシュボードで7日間予報が表示される
```

---

## 🎯 推奨スケジュール

**データ収集頻度**（本番環境）:

| 時刻（JST） | スクリプト | 目的 |
|-------------|-----------|------|
| 05:00 | weather_forecast_collector.py | 朝の予報更新 |
| 06:00 | improved_ferry_collector.py | 実運航状況確認 |
| 11:00 | weather_forecast_collector.py | 昼の予報更新 |
| 17:00 | weather_forecast_collector.py | 夕方の予報更新 |
| 23:00 | weather_forecast_collector.py | 夜の予報更新 |

**注意**: Railway Cronジョブが動作していれば、手動実行は不要です。

---

## 📞 サポート

Railway CLIのヘルプ:
```bash
railway help
```

公式ドキュメント:
https://docs.railway.com/guides/cli

---

**作成日**: 2025-12-31
**対象**: 北海道フェリー予報システム
