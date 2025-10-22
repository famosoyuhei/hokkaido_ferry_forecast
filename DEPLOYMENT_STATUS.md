# 🚀 Railway デプロイ状況確認

## 📋 プロジェクト情報

**プロジェクト名:** handsome-wonder
**サービス数:** 1 service
**環境:** comfortable-courtesy

---

## ✅ デプロイ確認手順

### 1. Railway ダッシュボードで確認

**URL:**
```
https://railway.app/project/handsome-wonder
```

**確認項目:**

#### A. デプロイステータス
```
Deployments タブを開く
→ 最新のデプロイ（コミット 01683fe）を確認
→ ステータスが "Active" になっているか
```

**期待される表示:**
- ✅ Building... (1-2分)
- ✅ Deploying... (30秒)
- ✅ **Active** (成功)

#### B. ビルドログ
```
最新デプロイをクリック
→ "View Logs" をクリック
```

**期待されるログ:**
```
✅ Cloning repository...
✅ Installing dependencies from requirements.txt
✅ Successfully installed Flask-2.3.3
✅ Successfully installed gunicorn-21.2.0
✅ Successfully installed Pillow-10.0.0
✅ Build completed
✅ Starting gunicorn...
✅ Listening on 0.0.0.0:XXXX
```

#### C. アプリURL取得
```
Settings タブを開く
→ "Domains" セクションを確認
→ "Generate Domain" をクリック（まだの場合）
```

**生成されるURL例:**
```
https://handsome-wonder-production.up.railway.app/
または
https://comfortable-courtesy.up.railway.app/
```

---

## 🌐 アプリ動作確認

### ステップ1: メインページ確認

**URL:**
```
https://[あなたのドメイン].up.railway.app/
```

**期待される表示:**
```
🚢 北海道フェリー運航予報
稚内⇔利尻・礼文島　7日間欠航リスク予測
⚠️ X日間 高リスク

[7日間予報カード表示]
[航路別予報リスト]
```

**確認ポイント:**
- [ ] ページが正常に表示される
- [ ] 紫色のグラデーション背景が表示される
- [ ] 7日間予報カードが表示される
- [ ] 航路別予報が表示される
- [ ] レスポンシブデザインが動作する

---

### ステップ2: PWA ファイル確認

#### A. Manifest.json
```
https://[あなたのドメイン].up.railway.app/manifest.json
```

**期待される内容:**
```json
{
  "name": "北海道フェリー運航予報",
  "short_name": "フェリー予報",
  "display": "standalone",
  "theme_color": "#667eea",
  "icons": [...]
}
```

- [ ] JSONが正しく表示される
- [ ] Content-Type: application/json

#### B. Service Worker
```
https://[あなたのドメイン].up.railway.app/service-worker.js
```

**期待される内容:**
```javascript
// Ferry Forecast PWA Service Worker
const CACHE_NAME = 'ferry-forecast-v1';
...
```

- [ ] JavaScriptコードが表示される
- [ ] Content-Type: application/javascript

#### C. アプリアイコン
```
https://[あなたのドメイン].up.railway.app/static/icon-192.png
https://[あなたのドメイン].up.railway.app/static/icon-512.png
```

**期待される表示:**
- [ ] フェリーアイコン（紫背景に白い船）が表示される
- [ ] 画像が正常にロードされる

---

### ステップ3: API エンドポイント確認

#### A. 7日間予報API
```
https://[あなたのドメイン].up.railway.app/api/forecast
```

**期待される内容:**
```json
[
  {
    "date": "2025-10-22",
    "max_risk": "HIGH",
    "max_score": 80,
    "risks": [...]
  },
  ...
]
```

- [ ] JSON配列が返される
- [ ] 7日分のデータが含まれる

#### B. 本日詳細API
```
https://[あなたのドメイン].up.railway.app/api/today
```

- [ ] 本日の時間別予報が返される

#### C. 航路別API
```
https://[あなたのドメイン].up.railway.app/api/routes
```

- [ ] 6航路の予報が返される

#### D. 統計API
```
https://[あなたのドメイン].up.railway.app/api/stats
```

**期待される内容:**
```json
{
  "weather_records": XXX,
  "weather_days": X,
  "forecast_days": X,
  "high_risk_days": X,
  "last_updated": "2025-10-22 XX:XX:XX"
}
```

---

## 🔍 Chrome DevTools 確認

### PWA インストール可能性チェック

1. **ChromeでアプリURLを開く**

2. **DevToolsを開く（F12）**

3. **Application タブを選択**

4. **Manifest セクション確認**
   ```
   Manifest の内容が表示される:
   - Name: 北海道フェリー運航予報
   - Short name: フェリー予報
   - Start URL: /
   - Theme color: #667eea
   - Display: standalone
   - Icons: 2個表示される
   ```

5. **Service Workers セクション確認**
   ```
   service-worker.js が登録されている:
   - Status: activated and is running
   - Source: /service-worker.js
   - Scope: https://[domain]/
   ```

6. **Cache Storage セクション確認**
   ```
   キャッシュが作成されている:
   - ferry-forecast-v1
   - ferry-forecast-runtime
   ```

---

## 📱 スマホインストール確認

### Android（Chrome）

1. **Chromeでアプリを開く**
   ```
   https://[あなたのドメイン].up.railway.app/
   ```

2. **インストールプロンプト確認**
   - [ ] アドレスバーに「＋」アイコンが表示される
   - [ ] ページ右下に「📱 ホーム画面に追加」ボタンが表示される（数秒後）

3. **インストール実行**
   - [ ] ボタンをタップ
   - [ ] 「インストール」確認ダイアログが表示される
   - [ ] インストール完了

4. **動作確認**
   - [ ] ホーム画面にアイコンが追加される
   - [ ] アイコンをタップすると全画面で起動
   - [ ] ブラウザUIが表示されない（スタンドアロンモード）

---

### iPhone（Safari）

1. **Safariでアプリを開く**
   ```
   https://[あなたのドメイン].up.railway.app/
   ```

2. **共有メニューから追加**
   - [ ] 共有ボタン（□に↑矢印）をタップ
   - [ ] 「ホーム画面に追加」を選択可能

3. **インストール実行**
   - [ ] 「追加」をタップ
   - [ ] ホーム画面にアイコンが追加される

4. **動作確認**
   - [ ] アイコンをタップすると全画面で起動
   - [ ] SafariのUIが表示されない

---

## 🧪 オフライン動作確認

### テスト手順

1. **オンラインでページを開く**
   - キャッシュを生成

2. **DevToolsでオフライン化**
   ```
   F12 → Network タブ → "Offline" にチェック
   ```

3. **ページをリロード（Ctrl+R）**

4. **確認**
   - [ ] ページが正常に表示される（キャッシュから）
   - [ ] 最後に取得したデータが表示される
   - [ ] 「オフラインです」メッセージが表示されない

---

## 🐛 トラブルシューティング

### 問題1: デプロイが失敗する

**確認:**
```
Railway Logs でエラーメッセージを確認
```

**よくあるエラー:**

#### A. ModuleNotFoundError
```
Error: ModuleNotFoundError: No module named 'forecast_dashboard'
```

**原因:** ファイル名の不一致

**確認コマンド:**
```bash
ls forecast_dashboard.py
```

**対処:** ファイルが存在することを確認

#### B. Import Error
```
Error: cannot import name 'app' from 'forecast_dashboard'
```

**原因:** forecast_dashboard.py内でappオブジェクトが定義されていない

**確認:** forecast_dashboard.py の最後に以下があるか
```python
if __name__ == '__main__':
    app.run(...)
```

#### C. Port Error
```
Error: Address already in use
```

**原因:** PORTの競合

**対処:** railway.jsonで`$PORT`を使用していることを確認

---

### 問題2: ページが表示されない（404）

**確認事項:**

1. **デプロイが完了しているか**
   ```
   Railway Dashboard → Status: Active
   ```

2. **ドメインが正しいか**
   ```
   Settings → Domains で確認
   ```

3. **ルートが定義されているか**
   ```python
   @app.route('/')
   def index():
       ...
   ```

---

### 問題3: データベースエラー

**エラー例:**
```
sqlite3.OperationalError: no such table: weather_forecast
```

**原因:** データベースが初期化されていない

**対処方法:**

#### オプションA: 手動でコレクター実行（推奨）

Railway Dashboard → Service → Manual Run:
```bash
python weather_forecast_collector.py
```

これでデータベーステーブルが作成される

#### オプションB: 初回アクセス時に自動作成

forecast_dashboard.py が初回アクセス時に空のデータベースを処理できるように実装済み

**期待される動作:**
- データがない場合は「データ収集中」メッセージ
- 次回のCron実行（05:00 JST）でデータが取得される

---

### 問題4: PWAインストールボタンが表示されない

**確認事項:**

1. **HTTPSでアクセスしているか**
   ```
   ✅ https://your-app.up.railway.app/
   ❌ http://your-app.up.railway.app/
   ```

2. **manifest.jsonが読み込めるか**
   ```
   ブラウザで直接アクセス:
   https://your-app.up.railway.app/manifest.json
   ```

3. **Service Workerが登録されているか**
   ```
   DevTools → Application → Service Workers
   ```

4. **ブラウザがPWAをサポートしているか**
   - ✅ Chrome/Edge (Android/PC)
   - ✅ Safari (iPhone)
   - ❌ Firefox (制限あり)

---

## ✅ 成功の確認

すべて完了したら、以下がチェック済みになります：

### デプロイ確認
- [ ] Railway Dashboard でステータス "Active"
- [ ] ビルドログに成功メッセージ
- [ ] gunicorn が起動している

### アプリ確認
- [ ] メインページが表示される
- [ ] 7日間予報が表示される
- [ ] 航路別予報が表示される

### PWA確認
- [ ] manifest.json が配信される
- [ ] service-worker.js が配信される
- [ ] アイコンが配信される
- [ ] Chrome DevTools で Manifest 確認
- [ ] Service Worker が登録される

### API確認
- [ ] /api/forecast が動作
- [ ] /api/today が動作
- [ ] /api/routes が動作
- [ ] /api/stats が動作

### インストール確認
- [ ] Android で「ホーム画面に追加」可能
- [ ] iPhone で「ホーム画面に追加」可能
- [ ] 全画面モードで起動

### オフライン確認
- [ ] オフラインでキャッシュから表示

---

## 🎉 完了！

すべてのチェック項目が完了したら、PWAスマホアプリのデプロイは成功です！

ユーザーに以下を共有できます：
```
🚢 北海道フェリー運航予報アプリ

アプリURL:
https://[あなたのドメイン].up.railway.app/

インストール方法:
- Android: Chromeで開いて「ホーム画面に追加」
- iPhone: Safariで開いて共有→「ホーム画面に追加」

詳細: USER_INSTALL_GUIDE.md を参照
```

---

**確認日:** 2025-10-22
**プロジェクト:** handsome-wonder
**サービス:** comfortable-courtesy
**デプロイ:** コミット 01683fe
