# 🔧 Railway CLI インストール方法（2025年版）

## 🚨 旧URLが404エラー

```powershell
iwr https://cli.railway.app/install.ps1 | iex
→ Not Found (404)
```

Railway CLIのインストール方法が変更されました。

---

## ✅ 新しいインストール方法

### 方法1: NPM経由（最も確実）

#### 前提条件

Node.js がインストールされている必要があります。

**Node.js インストール確認:**
```powershell
node --version
npm --version
```

もし表示されない場合は、先にNode.jsをインストール：
https://nodejs.org/ から最新版をダウンロード

#### Railway CLI インストール

```powershell
npm install -g @railway/cli
```

#### 確認

```powershell
railway --version
```

---

### 方法2: Scoop経由（Windows）

#### Scoop インストール（まだの場合）

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
```

#### Railway CLI インストール

```powershell
scoop install railway
```

---

### 方法3: 手動ダウンロード

#### ダウンロードページ

https://github.com/railwayapp/cli/releases

#### 手順

1. **最新リリースを開く**
2. **Windows用のバイナリをダウンロード**
   - `railway-windows-amd64.exe`
3. **ダウンロードしたファイルを `railway.exe` にリネーム**
4. **PATHに追加** または **プロジェクトフォルダに配置**

---

## 🚀 Railway CLI 使用方法

### ログイン

```powershell
railway login
```

ブラウザが開き、Railway アカウントでログイン

### プロジェクトにリンク

```powershell
# プロジェクトディレクトリに移動
cd C:\Users\ichry\OneDrive\Desktop\hokkaido_ferry_forecast

# プロジェクトにリンク
railway link 7c0afe06-afda-4433-bd88-e94a9556e104
```

### データコレクター実行

```powershell
railway run python weather_forecast_collector.py
```

---

## ⚡ より簡単な代替方法

### オプションA: ローカルで実行してデータベースを生成

Railway CLIをインストールせずに、ローカルで直接実行：

#### ステップ1: ローカルで実行

```powershell
cd C:\Users\ichry\OneDrive\Desktop\hokkaido_ferry_forecast

python weather_forecast_collector.py
```

**実行時間:** 1-2分

**結果:** `ferry_weather_forecast.db` が作成される

#### ステップ2: データベースファイルの確認

```powershell
ls ferry_weather_forecast.db
```

ファイルサイズが 100KB 以上あれば成功

#### ステップ3: Railway Volume にアップロード（複雑）

**問題:** RailwayのHobbyプランでは、ローカルファイルのアップロードが簡単ではない

**代替案:** 次のCron実行を待つ

---

### オプションB: 次のCron実行を待つ（最も簡単）

**修正後の次回実行時刻:**

```
今日 23:00 JST (UTC 14:00) - forecast_collection_night
明日 05:00 JST (UTC 20:00) - forecast_collection_morning
```

**推奨:** 今夜23時まで待つ（あと約15時間）

---

## 🎯 推奨アクション（優先順）

### 1位: 次のCron実行を待つ（最も簡単）

**何もせず待つ:**
- 今夜 23:00 JST
- または明日朝 05:00 JST

**メリット:**
- インストール不要
- 自動的に実行される
- 確実に動作する

### 2位: Node.js経由でRailway CLIをインストール

**Node.jsがある場合:**
```powershell
npm install -g @railway/cli
railway login
railway link 7c0afe06-afda-4433-bd88-e94a9556e104
railway run python weather_forecast_collector.py
```

### 3位: ローカルで実行（参考用）

**開発・テスト目的:**
```powershell
cd C:\Users\ichry\OneDrive\Desktop\hokkaido_ferry_forecast
python weather_forecast_collector.py
```

データベースがローカルに作成されますが、Railwayにアップロードするのは複雑

---

## 📅 修正後のスケジュール

### 今後の自動実行（毎日）

```
UTC 20:00 = JST 05:00 (朝) - 天気予報
UTC 02:00 = JST 11:00 (昼) - 天気予報
UTC 08:00 = JST 17:00 (夕) - 天気予報
UTC 14:00 = JST 23:00 (夜) - 天気予報
UTC 21:00 = JST 06:00 (朝) - フェリー情報
UTC 21:30 = JST 06:30 (朝) - 通知
```

**次回実行:** 今夜 23:00 JST

---

## ✅ 推奨：今夜23時まで待つ

### 理由

1. **最も簡単** - 何もする必要がない
2. **確実** - 自動的に実行される
3. **短い待ち時間** - あと約15時間

### タイムライン

```
現在 (08:00頃)
  ↓
  ... 通常通り過ごす ...
  ↓
23:00 JST ← 自動実行
  ↓ (1-2分)
23:02 JST ← 完了
  ↓
アプリ確認 → 正常動作 ✅
```

---

## 💡 今夜23時以降にすること

### アプリ確認

```
https://web-production-27f768.up.railway.app/
```

**期待される画面:**
```
🚢 北海道フェリー運航予報
稚内⇔利尻・礼文島　7日間欠航リスク予測

📊 予報日数: 7
🌊 気象データ: 499
[7日間予報]
[6航路予報]
```

### PWA確認

```
/manifest.json ✅
/service-worker.js ✅
/static/icon-192.png ✅
```

### スマホインストール

**Android / iPhone:**
「ホーム画面に追加」でインストール

---

## 🎊 完成まであと少し！

**今夜23時には、すべてが自動的に完成します！**

---

**作成日:** 2025-10-23
**次回実行:** 23:00 JST (UTC 14:00)
**推奨:** 23時まで待つ（最も簡単で確実）

⏰ あと約15時間で自動的に完成します！
