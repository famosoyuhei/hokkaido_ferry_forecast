# 🔍 Railway アプリURL の見つけ方

## 方法1: Deployments タブから確認（最も簡単）

### 手順

1. **Railway Dashboard を開く**
   ```
   https://railway.app/
   ```

2. **プロジェクト "handsome-wonder" を選択**

3. **Deployments タブをクリック**

4. **最新のデプロイ（Status: Active）をクリック**

5. **右上に "View Logs" と "Open" ボタンがあります**
   - **"Open" ボタンをクリック** → 新しいタブでアプリが開きます
   - または URL が表示されている場合はそれをコピー

---

## 方法2: Service の概要から確認

### 手順

1. **Railway Dashboard を開く**

2. **Service (comfortable-courtesy または deployment名) をクリック**

3. **画面上部に URL が表示されています**
   ```
   例: https://comfortable-courtesy-production-XXXX.up.railway.app
   ```

4. **URLをクリック** → アプリが開きます

---

## 方法3: Settings タブで生成

### 手順

1. **Railway Dashboard → Service を選択**

2. **Settings タブをクリック**

3. **左側メニューを確認**
   - "Networking" または
   - "Public Networking" または
   - "Environment" セクション

4. **"Generate Domain" ボタンを探す**
   - ボタンがあれば **クリックして生成**
   - 既にURLがあれば **表示されています**

---

## 方法4: URL パターンから推測

Railway のURL形式は通常以下のパターンです：

### パターンA: プロジェクト名ベース
```
https://handsome-wonder-production.up.railway.app/
```

### パターンB: サービス名ベース
```
https://comfortable-courtesy-production.up.railway.app/
```

### パターンC: ランダムID
```
https://web-production-XXXX.up.railway.app/
```

### 試してみる

1. **まずパターンAを試す**
   ```
   https://handsome-wonder-production.up.railway.app/
   ```

2. **次にパターンBを試す**
   ```
   https://comfortable-courtesy-production.up.railway.app/
   ```

3. **どちらかが動作するはずです！**

---

## 方法5: Railway CLI で確認

### 手順

Railwayのコマンドラインツールを使用（既にインストールしている場合）：

```bash
railway status
```

または

```bash
railway open
```

これで自動的にブラウザでアプリが開きます。

---

## 方法6: Railwayの新しいUI (2024年版)

### 最新のRailway UIの場合

1. **Project View を開く**
   ```
   https://railway.app/project/7c0afe06-afda-4433-bd88-e94a9556e104
   ```

2. **Service カードを確認**
   - サービスのカード（ボックス）が表示されている
   - カードの上部または下部に **URL が表示されている**
   - または **"🔗" アイコン** が表示されている

3. **URL またはアイコンをクリック**
   → アプリが新しいタブで開きます

---

## 📱 URL が見つかったら

### 確認すること

1. **ブラウザでアクセス**
   ```
   https://[見つけたURL]
   ```

2. **期待される画面**
   ```
   🚢 北海道フェリー運航予報
   稚内⇔利尻・礼文島　7日間欠航リスク予測
   ```

3. **PWAファイル確認**
   ```
   https://[URL]/manifest.json
   https://[URL]/service-worker.js
   https://[URL]/static/icon-192.png
   ```

---

## 🚨 どうしても見つからない場合

### オプション: カスタムドメインを生成

1. **Railway Dashboard → Project**

2. **Service を選択**

3. **Settings タブ**

4. **"Networking" または "Public Networking" セクション**

5. **"Generate Domain" ボタンをクリック**
   - 新しい `.railway.app` ドメインが生成されます
   - 数秒で有効になります

6. **生成されたURLが表示されます**

---

## 📸 Railway UI の例

### 新しいUI (2024年版)

```
┌─────────────────────────────────────────┐
│ Project: handsome-wonder                │
│                                         │
│ ┌────────────────────────────────────┐ │
│ │ Service: comfortable-courtesy      │ │
│ │                                    │ │
│ │ Status: Active                     │ │
│ │ URL: https://comfortable-...      │ │ ← ここ！
│ │      .up.railway.app               │ │
│ │                                    │ │
│ │ [View Logs] [Settings]             │ │
│ └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 旧UI

```
┌─────────────────────────────────────────┐
│ Settings                                │
│ ┌─────────────────────────────────────┐ │
│ │ General                             │ │
│ │ Networking                          │ │ ← ここをクリック
│ │ Environment                         │ │
│ │ ...                                 │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Domains:                                │
│ https://your-app.up.railway.app        │ ← ここ！
│ [Generate Domain]                       │
└─────────────────────────────────────────┘
```

---

## 🎯 推奨アクション

### 最も確実な方法

1. **Deployments タブを開く**
2. **最新の Active デプロイをクリック**
3. **"Open" ボタンを探す**
4. **クリックしてアプリを開く**

これが最も簡単で確実です！

---

## 💡 URL 形式のヒント

Railway の URL は必ず以下の形式です：
```
https://XXXXXXXX.up.railway.app/
```

- `XXXXXXXX` の部分が変わります
- プロジェクト名、サービス名、またはランダムIDが入ります
- 必ず `.up.railway.app` で終わります

---

## 🔍 URLを教えてください

上記の方法でURLが見つかったら、教えてください！
一緒に動作確認しましょう 🚀

**または、以下を試してみてください：**

1. **パターンAを試す**
   ```
   https://handsome-wonder-production.up.railway.app/
   ```
   → ブラウザでアクセスしてみる

2. **パターンBを試す**
   ```
   https://comfortable-courtesy-production.up.railway.app/
   ```
   → ブラウザでアクセスしてみる

どちらかが動作する可能性が高いです！

---

**作成日:** 2025-10-22
**対応:** Railway 最新UI + 旧UI
