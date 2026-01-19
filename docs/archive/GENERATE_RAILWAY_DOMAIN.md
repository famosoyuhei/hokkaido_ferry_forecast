# 🌐 Railway ドメイン生成手順

## 📋 あなたのサービス情報

**Service URL:**
```
https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104/service/ad724015-e917-4c35-9fdf-a5b50330c29b
```

**プロジェクトID:** `7c0afe06-afda-4433-bd88-e94a9556e104`
**サービスID:** `ad724015-e917-4c35-9fdf-a5b50330c29b`
**環境ID:** `bb061a64-00c3-4c79-a1d3-35c10f724bc0`

---

## 🚨 現状

デフォルトドメインがまだ生成されていないようです。手動で生成する必要があります。

---

## 🔧 ドメイン生成手順

### ステップ1: Service ページを開く

すでに開いているこのページ：
```
https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104/service/ad724015-e917-4c35-9fdf-a5b50330c29b
```

### ステップ2: Settings タブをクリック

左側または上部のメニューから **Settings** を選択

### ステップ3: Networking セクションを探す

Settings 内で以下のいずれかを探す：
- **Networking**
- **Public Networking**
- **Domains**
- **Expose**

### ステップ4: ドメインを生成

#### オプションA: Generate Domain ボタン

1. **"Generate Domain"** または **"Create Domain"** ボタンを見つける
2. **クリック**
3. 自動的に `.up.railway.app` ドメインが生成される
4. 数秒で有効になる

#### オプションB: Public Networking を有効化

1. **"Enable Public Networking"** または類似のトグルを見つける
2. **有効にする**
3. 自動的にドメインが生成される

### ステップ5: 生成されたURLを確認

生成後、以下のような形式のURLが表示されます：
```
https://ad724015-e917-4c35-9fdf-a5b50330c29b.up.railway.app/

または

https://web-production-XXXX.up.railway.app/
```

このURLをコピーしてください！

---

## 📸 UI の例

### 新しい Railway UI (2024-2025)

```
Settings
├── General
├── Variables
├── Networking  ← ここをクリック
│   ├── Public Networking: [ON/OFF トグル]
│   └── Domains:
│       ├── https://XXXXX.up.railway.app  ← 自動生成
│       └── [+ Add Domain] ← カスタムドメイン用
├── Deploy
└── ...
```

### Settings → Networking の詳細

```
┌─────────────────────────────────────────┐
│ Networking                              │
├─────────────────────────────────────────┤
│                                         │
│ Public Networking                       │
│ [●] Enable  [ ] Disable                 │
│                                         │
│ Railway Domain:                         │
│ ┌─────────────────────────────────────┐ │
│ │ https://ad724015-e917...           │ │
│ │      .up.railway.app                │ │
│ │                           [Copy]    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [+ Generate Domain]                     │
│                                         │
└─────────────────────────────────────────┘
```

---

## 🔍 もし Networking が見つからない場合

### 別の場所を確認

#### 1. Overview タブ

- Service の **Overview** タブを開く
- 画面上部に **URL** が表示されている場合があります
- またはカードの中に **"Open"** ボタンがあります

#### 2. Deployments タブ

- **Deployments** タブを開く
- 最新のデプロイ（Status: Active）をクリック
- 右上に **"Open"** ボタンまたは **URL** が表示される

#### 3. Service カードの詳細

Project のメイン画面で：
- Service のカード（ボックス）を見る
- カードをクリックすると詳細が表示される
- その中に **URL** または **"🔗"** アイコンがあるはず

---

## ⚙️ Railway CLI で生成（オプション）

もし Railway CLI がインストールされている場合：

### CLIでドメイン生成

```bash
# プロジェクトにリンク
railway link 7c0afe06-afda-4433-bd88-e94a9556e104

# ドメイン生成
railway domain

# または直接開く
railway open
```

これで自動的にドメインが生成され、ブラウザで開きます。

---

## 🚀 ドメイン生成後の確認

### URLが生成されたら

1. **ブラウザでアクセス**
   ```
   https://[生成されたURL]
   ```

2. **期待される画面**
   ```
   🚢 北海道フェリー運航予報
   稚内⇔利尻・礼文島　7日間欠航リスク予測
   ```

3. **PWA確認**
   ```
   /manifest.json → JSON表示
   /service-worker.js → JavaScript表示
   /static/icon-192.png → アイコン表示
   ```

---

## 🐛 トラブルシューティング

### 問題1: "Generate Domain" ボタンが見つからない

**対処法A: Public Networking を有効化**
1. Settings → Networking
2. "Enable Public Networking" トグルをONにする
3. 自動的にドメインが生成される

**対処法B: プロジェクトを再デプロイ**
1. Deployments → 最新デプロイ
2. "Redeploy" をクリック
3. デプロイ完了後、自動的にドメインが生成される場合がある

### 問題2: ドメインが生成されたが 404 エラー

**原因:** デプロイがまだ完了していない、または失敗している

**確認:**
```
Deployments → 最新デプロイ → Status
```

- Building → 待機
- Deploying → 待機
- **Active** → 成功！
- Failed → ログ確認

**対処:**
デプロイが Active になるまで待つ（通常3-5分）

### 問題3: ドメインが生成されたが接続できない

**確認事項:**

1. **デプロイログを確認**
   ```
   Deployments → View Logs
   → gunicorn 起動メッセージがあるか
   ```

2. **正しいポートでリッスンしているか**
   ```
   ログに "Listening at: http://0.0.0.0:XXXX" が表示される
   ```

3. **railway.json の startCommand が正しいか**
   ```json
   "startCommand": "gunicorn --bind 0.0.0.0:$PORT forecast_dashboard:app"
   ```

---

## 📋 確認チェックリスト

ドメイン生成プロセス：

- [ ] Railway Service ページを開いた
- [ ] Settings タブを開いた
- [ ] Networking セクションを見つけた
- [ ] "Generate Domain" または "Enable Public Networking" を実行
- [ ] ドメインURLが表示された
- [ ] URLをコピーした

アプリ動作確認：

- [ ] ブラウザでURLにアクセス
- [ ] ダッシュボードが表示される
- [ ] Status: Active を確認
- [ ] PWAファイルが配信される

---

## 🎯 次のアクション

### 1. ドメイン生成

上記の手順に従って：
```
Settings → Networking → Generate Domain
```

### 2. URLを教えてください

生成されたURLを教えていただければ：
- 動作確認をサポート
- PWA機能の確認
- データ収集の実行

### 3. アプリをテスト

URLが動作したら：
- スマホでインストールテスト
- オフライン動作確認
- データ収集実行

---

## 📞 サポート

ドメイン生成でお困りの場合：

1. **Settings タブのスクリーンショットを共有**
   - どのようなセクションが表示されているか
   - "Networking" や "Domains" が見つかるか

2. **エラーメッセージを共有**
   - ドメイン生成時のエラー
   - アクセス時のエラー

3. **Deployments ステータスを確認**
   - デプロイが Active になっているか
   - ログにエラーがないか

---

**作成日:** 2025-10-22
**サービスID:** ad724015-e917-4c35-9fdf-a5b50330c29b
**次のアクション:** Settings → Networking → Generate Domain

🌐 ドメインを生成してアプリにアクセスしましょう！
