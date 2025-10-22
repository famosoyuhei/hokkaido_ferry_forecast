# 🔧 Railway リポジトリ接続の修正

## 🚨 問題

Railwayが間違ったリポジトリに接続されています：

```
❌ 現在: famosoyuhei/rishiri-kelp-forecast-system
✅ 正しい: famosoyuhei/hokkaido_ferry_forecast
```

---

## 📋 正しいリポジトリ情報

**リポジトリURL:**
```
https://github.com/famosoyuhei/hokkaido_ferry_forecast.git
```

**ブランチ:**
```
main
```

**最新コミット:**
```
01683fe - Fix Railway deployment: Update startCommand to use forecast_dashboard
```

---

## 🔄 Railway設定の修正手順

### ステップ1: Railway Dashboardを開く

```
https://railway.app/project/c1f7df8d-2f7e-4b54-a0e2-d114e331637d
```

### ステップ2: サービス設定を開く

1. **Service** (comfortable-courtesy) をクリック
2. **Settings** タブを選択

### ステップ3: リポジトリ接続を変更

#### オプションA: リポジトリを再接続（推奨）

1. **Source Repo** セクションを見つける
2. **「Disconnect」** をクリック（現在のrishiri-kelp-forecast-systemを切断）
3. **「Connect Repo」** をクリック
4. **GitHub** を選択
5. **リポジトリを検索**: `hokkaido_ferry_forecast`
6. **「famosoyuhei/hokkaido_ferry_forecast」** を選択
7. **ブランチ**: `main` を選択
8. **「Connect」** をクリック

#### オプションB: 新しいサービスを作成

もしオプションAが複雑な場合：

1. Railway Dashboard のトップへ戻る
2. **「+ New」** → **「GitHub Repo」** を選択
3. **「famosoyuhei/hokkaido_ferry_forecast」** を選択
4. 自動的にデプロイが開始される
5. 古いサービス（rishiri-kelp-forecast-system）を削除

---

## ⚙️ デプロイ設定の確認

リポジトリ接続後、以下を確認：

### 1. Build Settings

**Settings → Build**

```
Build Command: (空欄 - railway.jsonが自動使用される)
```

**railway.json の内容が使用される:**
```json
{
  "build": {
    "commands": [
      "pip install -r requirements.txt"
    ]
  },
  "deploy": {
    "startCommand": "gunicorn --bind 0.0.0.0:$PORT forecast_dashboard:app"
  }
}
```

### 2. Environment Variables

**Settings → Variables**

必須変数（既に設定済みのはず）:
```
PORT: (Railwayが自動設定)
```

オプション変数（通知機能用）:
```
DISCORD_WEBHOOK_URL: (オプション)
LINE_NOTIFY_TOKEN: (オプション)
SLACK_WEBHOOK_URL: (オプション)
```

### 3. Root Directory

**Settings → Service**

```
Root Directory: / (デフォルト)
```

全ファイルがルートにあるので変更不要

---

## 🚀 再デプロイ

### 自動デプロイ

リポジトリ接続後、Railwayが自動的に：
1. 最新のコミット（01683fe）を検出
2. ビルドを開始
3. デプロイを実行

**所要時間:** 3-5分

### 手動デプロイ（必要に応じて）

もし自動デプロイが開始されない場合：

1. **Deployments** タブを開く
2. **「Deploy」** ボタンをクリック
3. または **「Redeploy」** を既存のデプロイからクリック

---

## ✅ 確認チェックリスト

再デプロイ後、以下を確認：

### Railway Dashboard

- [ ] **Source Repo**: `famosoyuhei/hokkaido_ferry_forecast` になっている
- [ ] **Branch**: `main` になっている
- [ ] **Latest Commit**: `01683fe` (Fix Railway deployment...) が表示される
- [ ] **Deploy Status**: Building → Deploying → **Active**

### デプロイログ

```
Deployments → 最新デプロイ → View Logs
```

**期待されるログ:**
```
✅ Cloning famosoyuhei/hokkaido_ferry_forecast...
✅ Checking out main branch...
✅ Found railway.json
✅ Running: pip install -r requirements.txt
✅ Installing Flask>=2.3.3
✅ Installing gunicorn>=21.2.0
✅ Installing Pillow>=10.0.0
✅ Build completed
✅ Starting: gunicorn --bind 0.0.0.0:$PORT forecast_dashboard:app
✅ Listening on 0.0.0.0:XXXX
```

### ファイル確認

正しいファイルがデプロイされているか確認：

```
Deployments → File Browser
```

**必須ファイル:**
- [ ] `forecast_dashboard.py` ← **これが重要！**
- [ ] `weather_forecast_collector.py`
- [ ] `notification_service.py`
- [ ] `improved_ferry_collector.py`
- [ ] `templates/forecast_dashboard.html`
- [ ] `static/manifest.json`
- [ ] `static/service-worker.js`
- [ ] `static/icon-192.png`
- [ ] `static/icon-512.png`
- [ ] `railway.json`
- [ ] `requirements.txt`

**間違ったリポジトリの場合、これらのファイルが存在しません！**

---

## 🌐 アプリ動作確認

再デプロイ成功後：

### 1. アプリURLにアクセス

```
https://[あなたのドメイン].up.railway.app/
```

**期待される表示:**
```
🚢 北海道フェリー運航予報
稚内⇔利尻・礼文島　7日間欠航リスク予測
```

### 2. PWAファイル確認

```
/manifest.json
/service-worker.js
/static/icon-192.png
```

すべて正常に表示される ✅

---

## 🔍 トラブルシューティング

### 問題1: リポジトリが切り替わらない

**対処法:**

1. **古いサービスを削除**
   ```
   Service Settings → Delete Service
   ```

2. **新しいサービスを作成**
   ```
   Railway Dashboard → + New → GitHub Repo
   → hokkaido_ferry_forecast を選択
   ```

### 問題2: ファイルが見つからない

**確認:**
```
Deployments → File Browser → forecast_dashboard.py が存在するか
```

**存在しない場合:**
- 間違ったリポジトリに接続されている
- リポジトリ接続をやり直す

### 問題3: デプロイは成功するが動作しない

**ログ確認:**
```
Deployments → View Logs
```

**エラー例:**
```
ModuleNotFoundError: No module named 'forecast_dashboard'
```

**原因:** 間違ったリポジトリ（rishiri-kelp-forecast-system）がデプロイされている

**対処:** リポジトリ接続を修正

---

## 📊 2つのリポジトリの違い

### rishiri-kelp-forecast-system（間違い）

```
目的: 昆布干場の天気予報
ファイル: kelp_drying_forecast.py など
対象: 利尻島の昆布漁業者向け
```

### hokkaido_ferry_forecast（正しい）

```
目的: フェリー欠航リスク予測
ファイル: forecast_dashboard.py
        weather_forecast_collector.py
        notification_service.py
対象: フェリー利用者向け
機能: PWAスマホアプリ対応
```

**完全に別のプロジェクトです！**

---

## 🎯 修正完了の確認

すべて完了したら：

### Railway Dashboard
- [ ] Source Repo: `hokkaido_ferry_forecast` ✅
- [ ] Status: Active ✅
- [ ] Logs: gunicorn が forecast_dashboard:app を起動 ✅

### アプリ動作
- [ ] ダッシュボードが表示される ✅
- [ ] PWAファイルが配信される ✅
- [ ] スマホでインストール可能 ✅

---

## 📝 まとめ

### やるべきこと

1. **Railway Dashboard を開く**
   ```
   https://railway.app/project/c1f7df8d-2f7e-4b54-a0e2-d114e331637d
   ```

2. **Service Settings → Source Repo**
   - Disconnect: `rishiri-kelp-forecast-system`
   - Connect: `hokkaido_ferry_forecast`

3. **自動デプロイを待つ（3-5分）**

4. **アプリURLで確認**
   ```
   フェリー予報ダッシュボードが表示される ✅
   ```

### 重要ポイント

**間違ったリポジトリ:**
- 昆布干場予報システム
- forecast_dashboard.py が存在しない
- フェリー予報機能なし

**正しいリポジトリ:**
- フェリー欠航予測システム
- PWAスマホアプリ対応
- 7日間予報 + 航路別リスク表示

---

**修正日:** 2025-10-22
**正しいリポジトリ:** famosoyuhei/hokkaido_ferry_forecast
**ブランチ:** main
**最新コミット:** 01683fe

🔧 この手順に従ってリポジトリ接続を修正してください！
