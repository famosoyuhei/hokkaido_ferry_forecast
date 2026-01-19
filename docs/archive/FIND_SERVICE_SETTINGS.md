# 🎯 サービス設定で Cron Jobs を見つける

## 📋 現状確認

確認できたメニュー（これは**プロジェクト設定**です）：
```
Project Settings
├── General
├── Usage
├── Environments
├── Shared Variables
├── Webhooks
├── Members
├── Tokens
├── Integrations
└── Danger
```

**Cron Jobs はここにはありません！**

Cron Jobs は **サービス設定** にあります。

---

## 🔄 サービス設定へ移動

### ステップ1: サービスに戻る

#### 方法A: 左上のプロジェクト名をクリック

画面左上の：
```
endearing-gentleness ▼
```
をクリックして、プロジェクト全体に戻る

#### 方法B: ブラウザの戻るボタン

戻るボタンを何度か押して、サービス画面に戻る

#### 方法C: 直接URLにアクセス

```
https://railway.com/project/7c0afe06-afda-4433-bd88-e94a9556e104/service/ad724015-e917-4c35-9fdf-a5b50330c29b
```

### ステップ2: サービスの "web" カードを確認

プロジェクト画面に戻ったら：

```
┌─────────────────────────────────┐
│ ○ web                           │
│ web-production-27f768.up.r...   │
│                                 │
│ Status: Active                  │
│ 50 minutes ago via GitHub       │
└─────────────────────────────────┘
```

このカードを**クリック**してサービス詳細を開く

### ステップ3: サービスの Settings タブを開く

サービス画面で（プロジェクト画面ではなく）：

```
上部タブ:
[Details] [Build Logs] [Deploy Logs] [HTTP Logs] [Settings]
                                                      ↑
                                                  ここをクリック
```

**これはサービス設定です**（プロジェクト設定とは別）

### ステップ4: 左側メニューで Cron を探す

サービス設定の左側メニューに以下があるはずです：

```
Service Settings
├── General
├── Variables
├── Networking
├── Deploy
├── Cron Jobs  ← ここ！
├── Health Check
└── ...
```

**"Cron Jobs" をクリック**

---

## 🎯 Cron Jobs ページの構成

### 期待される表示

```
┌─────────────────────────────────────────┐
│ Cron Jobs                               │
├─────────────────────────────────────────┤
│                                         │
│ ✓ forecast_collection_morning           │
│   Schedule: 0 5 * * *                   │
│   Command: python weather_forecast...   │
│   Last Run: Never                       │
│   Next Run: Oct 23, 2025 05:00 JST     │
│   [▶️ Run Now] [Edit] [Delete]          │
│                                         │
│ ✓ forecast_collection_midday            │
│   Schedule: 0 11 * * *                  │
│   [▶️ Run Now] [Edit] [Delete]          │
│                                         │
│ ✓ forecast_collection_evening           │
│   Schedule: 0 17 * * *                  │
│   [▶️ Run Now] [Edit] [Delete]          │
│                                         │
│ ✓ forecast_collection_night             │
│   Schedule: 0 23 * * *                  │
│   [▶️ Run Now] [Edit] [Delete]          │
│                                         │
│ ✓ ferry_collection                      │
│   Schedule: 0 6 * * *                   │
│   [▶️ Run Now] [Edit] [Delete]          │
│                                         │
│ ✓ notification_morning                  │
│   Schedule: 30 6 * * *                  │
│   [▶️ Run Now] [Edit] [Delete]          │
└─────────────────────────────────────────┘
```

### 実行方法

**"▶️ Run Now"** ボタンをクリック！

`forecast_collection_morning` または他のどのforecast_collection_XXXでもOKです。

---

## 📍 現在地の確認方法

### プロジェクト設定 vs サービス設定

#### あなたが今見ているのは: **プロジェクト設定** ❌

```
URL: .../project/XXXX/settings
メニュー: General, Usage, Environments, Webhooks...
```

#### 必要なのは: **サービス設定** ✅

```
URL: .../service/XXXX/settings
メニュー: General, Variables, Networking, Cron Jobs...
```

### 違いの見分け方

**プロジェクト設定:**
- プロジェクト全体に関する設定
- Environments, Members, Tokens など

**サービス設定:**
- 個別のサービス（webアプリ）の設定
- Cron Jobs, Networking, Deploy など

---

## 🔧 手順まとめ

### クイックガイド

1. **左上のプロジェクト名をクリック**
   ```
   endearing-gentleness ▼
   ```

2. **"web" サービスカードをクリック**
   ```
   ┌─ web ─┐
   │ Active│
   └───────┘
   ```

3. **サービス画面の "Settings" タブをクリック**
   ```
   [Details] [Build Logs] [Deploy Logs] [HTTP Logs] [Settings]
                                                        ↑
   ```

4. **左側メニューで "Cron Jobs" をクリック**
   ```
   ├── Cron Jobs  ← ここ
   ```

5. **"▶️ Run Now" をクリック**
   ```
   forecast_collection_morning
   [▶️ Run Now]
   ```

---

## ⏰ 代替案: 自動実行を待つ

もしCron Jobsが見つからない場合、最も簡単な方法：

### 何もせず待つ

**現在時刻:** 2025-10-23 02:00 JST

**次回自動実行:**
- **05:00 JST（あと約3時間）**

3時間後に自動的に：
1. データコレクターが実行される
2. データベースが初期化される
3. 500エラーが解消される
4. アプリが正常に動作開始

**これが最も簡単で確実な方法です！**

---

## 🎯 次のアクション

### オプションA: サービス設定を探す（推奨）

1. プロジェクト画面に戻る
2. "web" サービスをクリック
3. Settings タブを開く
4. Cron Jobs を探す

### オプションB: 自動実行を待つ（最も簡単）

1. 何もしない
2. 3時間待つ
3. 05:00 JST に自動実行
4. アプリ動作確認

### オプションC: スクリーンショット共有

もし迷った場合は：
- サービス画面のスクリーンショット
- または現在表示されている画面

を共有していただければ、正確な場所をお伝えします！

---

## 💡 ヒント

### 画面上部を確認

**プロジェクト設定の場合:**
```
[Project Name] > Settings
```

**サービス設定の場合:**
```
[Project Name] > [Service Name] > Settings
```

サービス名（"web"）が含まれていることを確認してください。

---

**次のステップ:**
1. プロジェクト画面に戻る
2. "web" サービスをクリック
3. Settings → Cron Jobs

または

**3時間待つ** → 自動実行 → 完了 ✅

---

**作成日:** 2025-10-23 02:00 JST
**目標:** Cron Jobs を見つけて実行
**代替:** 05:00 JST の自動実行を待つ
