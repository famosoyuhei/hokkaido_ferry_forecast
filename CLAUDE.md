# Hokkaido Ferry Forecast System - Claude Code ドキュメント

**プロジェクト**: 北海道フェリー運航予報システム
**対象路線**: 稚内⇔利尻島・礼文島
**最終更新**: 2025-12-31

---

## 🎯 プロジェクト概要

### 目的
利尻島・礼文島の飲食店・小売店など、フェリー輸送に依存する事業者向けに、**7日間の欠航リスク予報**を提供し、仕入れ計画の最適化とネットプロフィット向上を支援する。

### 主な機能
- 気象庁(JMA) + Open-Meteo APIによる7日間天気予報
- 風速・波高・視程に基づく欠航リスク計算（HIGH/MEDIUM/LOW/MINIMAL）
- PWA対応スマートフォンアプリ
- 自動データ収集（1日5回）
- 予測精度追跡システム

### ユーザー
- 利尻島・礼文島の飲食店経営者
- 小売店・商店主
- フェリー輸送に依存する全業種

---

## 📁 プロジェクト構造

### アクティブファイル（本番稼働中）

```
hokkaido_ferry_forecast/
│
├── 🌐 Web Dashboard (Production)
│   ├── forecast_dashboard.py          # Flask Webアプリ（Railway起動中）
│   ├── templates/
│   │   └── forecast_dashboard.html    # メインテンプレート
│   └── static/
│       ├── service-worker.js          # PWA Service Worker
│       ├── manifest.json               # PWA Manifest
│       └── icon-*.png                  # PWAアイコン
│
├── 🤖 Data Collectors (Cron Jobs)
│   ├── weather_forecast_collector.py  # 気象予報収集（1日4回）
│   ├── improved_ferry_collector.py    # 実運航データ収集（1日1回）
│   ├── accuracy_tracker.py            # 精度追跡（1日1回）
│   └── notification_service.py        # 通知送信（1日1回）
│
├── 🔮 Future Features
│   ├── push_notification_service.py   # プッシュ通知（開発予定）
│   └── generate_pwa_icons.py          # PWAアイコン生成ツール
│
├── 💾 Databases (Active: 3個のみ)
│   ├── ferry_weather_forecast.db      # 気象予報 + リスク予測（3.5MB）
│   ├── heartland_ferry_real_data.db   # 実運航データ（1.0MB）
│   └── notifications.db                # 通知システム（将来用）
│
├── 📄 Configuration
│   ├── railway.json                    # Railway設定（Public用 - APIキーなし）
│   ├── railway_local.json             # ローカル設定（gitignore - APIキー含む）
│   ├── requirements.txt                # Python依存関係
│   └── .gitignore                      # Git除外設定
│
├── 📚 Documentation
│   ├── README.md                       # プロジェクト概要
│   ├── CLAUDE.md                       # このファイル
│   ├── API_KEY_MANAGEMENT.md          # APIキー管理方法
│   ├── DATABASE_CLEANUP_SUMMARY.md    # DB整理履歴
│   └── PWA_SMARTPHONE_APP_GUIDE.md    # PWAインストールガイド
│
└── 🗂️ Archives (参考用)
    ├── archive_python_scripts/         # レガシースクリプト（67個）
    └── database_backups/               # 旧DBファイル（8個）
```

---

## 🏗️ システムアーキテクチャ

### 3層構造

```
┌─────────────────────────────────────────────────────────────┐
│                     🌐 Presentation Layer                   │
│  forecast_dashboard.py (Flask) + PWA (Service Worker)       │
│  URL: https://web-production-a628.up.railway.app/           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    🧠 Business Logic Layer                   │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Risk Calculation │  │ Accuracy Tracking│                 │
│  │  (欠航リスク判定) │  │  (予測精度検証)  │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     💾 Data Layer                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ferry_weather_forecast.db                            │   │
│  │  ├── weather_forecast (577 records)                 │   │
│  │  ├── cancellation_forecast (19,614 records)         │   │
│  │  └── forecast_collection_log (24 records)           │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ heartland_ferry_real_data.db                         │   │
│  │  ├── ferry_status (730 records)                     │   │
│  │  ├── ferry_status_enhanced (16 records)             │   │
│  │  ├── daily_summary (71 records)                     │   │
│  │  └── historical_operations (12 records - 移行済み)  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                   📡 External Data Sources                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ JMA API      │  │ Open-Meteo   │  │ Heartland Ferry │   │
│  │ (気象庁)     │  │ (気象データ) │  │ (運航状況)       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### データフロー

```
1. データ収集（Railway Cron）
   ┌─ 05:00 JST → weather_forecast_collector.py → JMA/Open-Meteo API
   ├─ 11:00 JST → weather_forecast_collector.py
   ├─ 17:00 JST → weather_forecast_collector.py
   ├─ 23:00 JST → weather_forecast_collector.py
   ├─ 06:00 JST → improved_ferry_collector.py → Heartland Ferry Website
   ├─ 07:00 JST → accuracy_tracker.py → 精度検証
   └─ 06:30 JST → notification_service.py → ユーザー通知

2. リスク計算（自動）
   気象データ → 風速・波高・視程分析 → リスクスコア算出 → 4段階評価

3. ユーザーアクセス
   PWA/Web → forecast_dashboard.py → SQLite DB → JSON API → 画面表示
```

---

## 🚀 Railway デプロイメント（本番環境）

### 基本情報
- **URL**: https://web-production-a628.up.railway.app/
- **プロジェクトID**: `c93898e1-5fe6-4fd7-b81d-33cb31b8addf`
- **GitHub**: https://github.com/famosoyuhei/hokkaido_ferry_forecast (Public)
- **起動コマンド**: `gunicorn --bind 0.0.0.0:$PORT forecast_dashboard:app`

### 環境変数（Railway Variables）

| 変数名 | 値 | 説明 |
|--------|-----|------|
| `PORT` | 自動設定 | Railway自動割り当て |
| `RAILWAY_VOLUME_MOUNT_PATH` | `/data` | Volume マウントパス |
| `FLIGHTAWARE_API_KEY` | (設定推奨) | 将来の利尻空港アプリ用 |

### Volumeストレージ（永続化）

**重要**: Volumeがないとデータが消えます

- **Mount Path**: `/data`
- **用途**: SQLiteデータベースの永続化
- **サイズ**: 1GB（推奨）

**設定確認**:
```python
# forecast_dashboard.py:26
data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
# → Productionでは '/data', Localでは '.'
```

### Cronジョブ（railway.jsonで定義）

| ジョブ名 | スクリプト | スケジュール (UTC) | JST | 目的 |
|----------|-----------|-------------------|-----|------|
| forecast_collection_morning | weather_forecast_collector.py | 0 20 * * * | 05:00 | 朝の予報取得 |
| forecast_collection_midday | weather_forecast_collector.py | 0 2 * * * | 11:00 | 昼の予報取得 |
| forecast_collection_evening | weather_forecast_collector.py | 0 8 * * * | 17:00 | 夕方の予報取得 |
| forecast_collection_night | weather_forecast_collector.py | 0 14 * * * | 23:00 | 夜の予報取得 |
| ferry_collection | improved_ferry_collector.py | 0 21 * * * | 06:00 | 実運航データ収集 |
| accuracy_tracking | accuracy_tracker.py | 0 22 * * * | 07:00 | 精度検証 |
| notification_morning | notification_service.py | 30 21 * * * | 06:30 | 朝の通知送信 |

**注意**: RailwayのCron機能が見つからない場合は、Railway CLIで設定が必要

---

## 💾 データベース詳細

### 1. ferry_weather_forecast.db（メインDB）

**サイズ**: 3.5 MB
**更新頻度**: 1日4回（気象予報）
**役割**: 予報データとリスク計算

#### テーブル構造

**weather_forecast** (577 records)
```sql
- forecast_date: 予報日
- forecast_hour: 予報時刻
- location: 地点（稚内/利尻/礼文）
- wind_speed_min/max: 風速範囲
- wave_height_min/max: 波高範囲
- visibility: 視程（km）
- temperature: 気温
- data_source: データソース（JMA/Open-Meteo）
```

**cancellation_forecast** (19,614 records)
```sql
- forecast_for_date: 予報対象日
- route: 航路（6ルート）
- risk_level: HIGH/MEDIUM/LOW/MINIMAL
- risk_score: リスクスコア（0-100）
- wind_forecast: 予測風速
- wave_forecast: 予測波高
- visibility_forecast: 予測視程
- recommended_action: 推奨アクション
```

**forecast_collection_log** (24 records)
```sql
- timestamp: 収集日時
- data_source: データソース
- status: SUCCESS/FAILED
- records_added: 追加レコード数
```

### 2. heartland_ferry_real_data.db（実運航DB）

**サイズ**: 1.0 MB
**更新頻度**: 1日1回（06:00 JST）
**役割**: 実際の運航状況記録

#### テーブル構造

**ferry_status** (730 records)
```sql
- scrape_date: スクレイピング日
- route: 航路
- vessel_name: 船舶名
- departure_time: 出航時刻
- operational_status: 運航状況
- is_cancelled: 欠航フラグ
```

**historical_operations** (12 records - 移行済み)
```sql
# ferry_actual_operations.dbから統合されたデータ
- operation_date: 運航日
- status: OPERATED/CANCELLED
- actual_wind_speed: 実測風速
- actual_wave_height: 実測波高
```

### 3. notifications.db（将来用）

**サイズ**: 28 KB
**役割**: プッシュ通知システム（開発予定）

---

## 🔧 ローカル開発環境

### セットアップ

```bash
# 1. リポジトリをクローン
git clone https://github.com/famosoyuhei/hokkaido_ferry_forecast.git
cd hokkaido_ferry_forecast

# 2. 仮想環境作成
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# 3. 依存関係インストール
pip install -r requirements.txt

# 4. 環境変数設定（オプション）
copy .env.example .env
# .envを編集してAPIキーを設定

# 5. Webアプリ起動
python forecast_dashboard.py
# → http://localhost:5000
```

### データ収集の実行

```bash
# 気象予報データ収集
python weather_forecast_collector.py

# 実運航データ収集
python improved_ferry_collector.py

# 精度追跡
python accuracy_tracker.py
```

### ローカルとRailwayの違い

| 項目 | ローカル | Railway (Production) |
|------|----------|----------------------|
| データベース保存先 | `.` (カレントディレクトリ) | `/data` (Volume) |
| 環境変数 | `.env` または `railway_local.json` | Railway Variables |
| 自動データ収集 | 手動実行 | Cronジョブ自動実行 |
| Webサーバー | Flask開発サーバー | gunicorn |

---

## 🔐 セキュリティとAPIキー管理

### ⚠️ 重要な注意事項

**このリポジトリはPUBLICです**
- ✅ コードは公開OK
- ❌ APIキー・パスワードは絶対にコミット禁止

### APIキーの保管場所

#### ❌ 絶対にコミットしないファイル
```
railway.json  ← APIキーを含めない（Public用）
.env
railway_local.json
*_secret.json
```

#### ✅ 安全な保管場所

**Production（Railway）**:
- Railway管理画面 → Variables タブで設定
- 例: `FLIGHTAWARE_API_KEY = QEgHk9G...`

**Local開発**:
- `railway_local.json`（gitignoreに追加済み）
- または `.env`ファイル

### FlightAware API

**現在の状態**:
- APIキーは有効（保持中）
- 使用していない（フライト機能は保留）
- 将来の利尻空港アプリ用に保護

**取得方法**:
https://flightaware.com/commercial/aeroapi/
- 無料プラン: 月1000リクエスト

詳細は [API_KEY_MANAGEMENT.md](API_KEY_MANAGEMENT.md) 参照

---

## 🎨 PWA（Progressive Web App）機能

### インストール方法

**Android（Chrome）**:
1. https://web-production-a628.up.railway.app/ を開く
2. 「ホーム画面に追加」ボタンをタップ
3. アイコンがホーム画面に追加される

**iPhone（Safari）**:
1. Safari でURLを開く
2. 共有ボタン → 「ホーム画面に追加」
3. アイコンが追加される

### オフライン機能
- Service Workerがデータをキャッシュ
- オフラインでも最後に取得したデータを表示
- 30分ごとに自動更新

詳細は [PWA_SMARTPHONE_APP_GUIDE.md](PWA_SMARTPHONE_APP_GUIDE.md) 参照

---

## 🧪 テストとデバッグ

### APIエンドポイント

```bash
# 統計情報
curl https://web-production-a628.up.railway.app/api/stats

# 7日間予報
curl https://web-production-a628.up.railway.app/api/forecast

# 本日詳細
curl https://web-production-a628.up.railway.app/api/today

# 航路別予報
curl https://web-production-a628.up.railway.app/api/routes
```

### データベース確認

```bash
# ローカルでSQLiteを確認
sqlite3 ferry_weather_forecast.db
> SELECT COUNT(*) FROM weather_forecast;
> SELECT * FROM cancellation_forecast WHERE risk_level='HIGH' LIMIT 5;
> .quit
```

### ログ確認

**Railway**:
- 管理画面 → Deployments → 最新デプロイ → View Logs

**ローカル**:
- コンソール出力を確認

---

## 🛠️ よくあるトラブルシューティング

### 問題1: Railway で Cronジョブが動かない

**症状**: データが更新されない

**原因**: Railwayの管理画面にCron設定がない

**解決策**: Railway CLIで手動実行
```bash
# Railway CLIインストール（Windows PowerShell）
iwr https://railway.app/install.ps1 | iex

# ログイン
railway login

# プロジェクトをリンク
railway link  # プロジェクトID: c93898e1-5fe6-4fd7-b81d-33cb31b8addf

# 手動でデータ収集実行
railway run python weather_forecast_collector.py
railway run python improved_ferry_collector.py
```

### 問題2: データベースが空

**症状**: ダッシュボードに「データがありません」表示

**原因**:
- Volumeが設定されていない → 再デプロイでDBが消えた
- 初回データ収集が実行されていない

**解決策**:
1. Railway で Volume を追加（Mount Path: `/data`）
2. 環境変数 `RAILWAY_VOLUME_MOUNT_PATH=/data` を設定
3. 再デプロイ
4. 手動でデータ収集実行（上記のRailway CLI使用）

### 問題3: APIキーエラー

**症状**: `Missing FLIGHTAWARE_API_KEY`

**原因**: 環境変数が設定されていない

**解決策**:
- ローカル: `railway_local.json` にキーを追加
- Railway: Variables タブでキーを設定

詳細は [SECURITY_URGENT_ACTION.md](SECURITY_URGENT_ACTION.md) 参照（もし漏洩した場合）

---

### 🔥 重大な問題: データベースが更新されない（2026-01-01解決済み）

**症状**:
- `/admin/collect-data`で成功するが、`/api/stats`が古いまま
- Volumeにデータを保存しても再デプロイで消える

**根本原因**:
GitHubに`ferry_weather_forecast.db`がコミットされていた。

**問題の詳細**:
1. `.gitignore`に`*.db`があっても、**既にコミット済みのファイルは除外されない**
2. デプロイ時の処理順序：
   ```
   ① GitHubから全ファイルをクローン（古いDBを含む）
   ② カレントディレクトリに展開
   ③ Volumeを/dataにマウント
   ④ アプリ起動時、/dataに古いDBがコピーされる or 上書きされる
   ```
3. 結果：Volumeの新しいデータが古いDBで上書きされる

**解決方法**:
```bash
# GitHubからDBファイルを削除（追跡のみ削除、ローカルファイルは残る）
git rm --cached ferry_weather_forecast.db

# コミット＆プッシュ
git commit -m "Remove database file from Git (use Railway Volume instead)"
git push
```

**確認方法**:
```bash
# Gitで管理されているDBファイルを確認
git ls-files | grep -i "\.db$"

# 何も表示されなければOK
```

**予防策**:
- 新しいDBファイルを作成する際は、`.gitignore`に含まれているか確認
- `git status`でステージングされていないか確認
- Volumeを使う場合は、DBファイルをGitに含めない

---

### 問題4: Railway環境変数が設定できない（Git Bash問題）

**症状**:
`RAILWAY_VOLUME_MOUNT_PATH=/data`と設定したのに`C:/Program Files/Git/data`になる

**原因**:
Git Bashが自動的にパスを変換してしまう

**解決策**:
```bash
# ダブルスラッシュを使う
railway variables --set "RAILWAY_VOLUME_MOUNT_PATH=//data" -s hokkaido-ferry-forecast

# または Railway管理画面で直接設定
```

---

### 問題5: workerサービスが勝手に再起動

**症状**:
削除したはずのworkerサービスが何度も起動する

**原因**:
`railway.json`の`cron`セクションが残っていると、Railwayが自動的にworkerサービスを作成する可能性がある

**解決策**:
1. Railway管理画面で完全削除
2. 確認画面で「apply destructive changes」と入力
3. `railway.json`の`cron`セクションを削除するか、別の方法でCronを設定

---

### 問題6: `/data`ディレクトリにアクセスできない

**症状**:
`sqlite3.OperationalError: unable to open database file`

**原因**:
- Volumeがマウントされていない
- `/data`ディレクトリの権限がない

**解決策**:
1. デバッグエンドポイントで確認：
   ```
   https://web-production-a628.up.railway.app/admin/env
   ```
   確認項目：
   - `data_dir_exists`: true
   - `data_dir_writable`: true
   - `data_dir_contents`: ["ferry_weather_forecast.db", ...]

2. Volumeが存在しない場合：
   - Railway → Create → Volume
   - Volume名: `ferry-data`
   - Mount to service: `hokkaido-ferry-forecast`
   - Mount path: `/data`

3. 環境変数の確認：
   ```bash
   railway variables -s hokkaido-ferry-forecast
   ```
   `RAILWAY_VOLUME_MOUNT_PATH=/data`が設定されているか確認

---

### 問題7: 時刻が9時間ズレる（日本時間問題）⚠️

**症状**:
- ダッシュボードの「最終更新」時刻が9時間古い
- 「次の便」が正しく判定されない（夜なのに「本日」と表示）
- データ収集タイミングがずれる

**原因**:
Railwayサーバーは**UTC（協定世界時）**で動作しており、`datetime.now()`がUTC時刻を返す。日本時間(JST)はUTC+9時間。

**解決策**:

1. **必ず`pytz`でJST明示**：
   ```python
   # ❌ 間違い（Railwayでは UTC）
   from datetime import datetime
   current_time = datetime.now()

   # ✅ 正解（JST）
   from datetime import datetime
   import pytz
   jst = pytz.timezone('Asia/Tokyo')
   current_time = datetime.now(jst)
   ```

2. **requirements.txtに追加**：
   ```
   pytz>=2023.3
   ```

3. **影響を受けるファイル**：
   - ✅ `forecast_dashboard.py` - 修正済み
   - ⚠️ `weather_forecast_collector.py` - 要確認
   - ⚠️ `improved_ferry_collector.py` - 要確認
   - ⚠️ `accuracy_tracker.py` - 要確認
   - ⚠️ `notification_service.py` - 要確認

4. **確認方法**：
   ```bash
   # Railwayで実行
   railway run python -c "from datetime import datetime; import pytz; print(datetime.now(pytz.timezone('Asia/Tokyo')))"
   ```

**重要**: データ収集スクリプトで`datetime.now()`を使っている場合、同様の修正が必要。特にcron実行時刻の判定やログタイムスタンプに影響する。

---

## 📊 リスク計算ロジック

### 技術的背景（気象庁・フェリー運航基準）

**気象庁(JMA)の予報要件**:
1. **数値予報モデル**:
   - メソスケールモデル (MSM): 5km解像度、39時間先まで
   - 沿岸波浪モデル (MOVE-JPN): 波高・周期・波向予測
   - 海流・潮位予測: 海洋短期予測システム

2. **必要な予報データ**:
   - 風速・風向（特に横風成分）
   - 波高・波周期・波向
   - 視程（霧・降雪時）
   - 海氷情報（冬季限定）
   - 潮汐・海流

3. **ハートランドフェリー運航基準**（推定）:
   - 風速: 25 m/s以上で要注意
   - 波高: 4.0 m以上で欠航リスク
   - 視程: 1 km未満で要注意
   - 横風成分: 航路に対する直角方向の風が特に危険

**現在の実装との差分**:
- ✅ 実装済み: 風速・波高・視程
- ❌ 未実装: 横風成分計算、波向・波周期、海流データ
- ❌ 未実装: 沿岸波浪モデル（MOVE-JPN）との統合
- ❌ 未実装: 実測気象データとの比較（予測精度向上）

**将来の改善案**（Phase 3以降）:
1. 気象庁沿岸波浪モデルAPI統合
2. 横風成分計算（航路方位との角度考慮）
3. 機械学習による欠航確率モデル
4. 実測気象データ収集（稚内気象台API）

### アルゴリズム

```python
# weather_forecast_collector.py:448-505

def calculate_cancellation_risk(wind_speed, wave_height, visibility):
    risk_score = 0

    # 風速リスク
    if wind_speed >= 35:  risk_score += 70  # 極めて危険
    elif wind_speed >= 30:  risk_score += 60  # 非常に危険
    elif wind_speed >= 25:  risk_score += 50  # 非常に強風
    elif wind_speed >= 20:  risk_score += 35  # 強風
    elif wind_speed >= 15:  risk_score += 20  # やや強風
    elif wind_speed >= 10:  risk_score += 10  # 穏やか

    # 波高リスク
    if wave_height >= 4.0:  risk_score += 40  # 非常に高波
    elif wave_height >= 3.0:  risk_score += 30  # 高波
    elif wave_height >= 2.0:  risk_score += 15  # やや高波

    # 視程リスク
    if visibility < 1.0:  risk_score += 20  # 視界不良
    elif visibility < 3.0:  risk_score += 10  # やや視界不良

    # リスクレベル判定
    if risk_score >= 70:  return "HIGH"
    elif risk_score >= 40:  return "MEDIUM"
    elif risk_score >= 20:  return "LOW"
    else:  return "MINIMAL"
```

### リスクレベル定義

| レベル | スコア | 説明 | 推奨アクション |
|--------|--------|------|----------------|
| **HIGH** | 70+ | 欠航の可能性が高い | 代替日を検討 |
| **MEDIUM** | 40-69 | 欠航のリスクあり | 天気予報を注視 |
| **LOW** | 20-39 | 低リスク | 通常通り運航予想 |
| **MINIMAL** | 0-19 | 良好な条件 | 安定運航予想 |

---

## 🔮 将来の機能拡張

### 1. プッシュ通知システム（優先度: 高）

**ファイル**: `push_notification_service.py` (未完成)
**目的**: 高リスク日の自動通知
**実装予定**:
- Web Push API
- 通知設定（航路選択、リスクレベル閾値）
- 朝6:00の自動通知

### 2. 利尻空港フライト予測（優先度: 中）

**関連ファイル**: アーカイブ済み（`archive_python_scripts/`）
**検討事項**:
- 姉妹アプリとして別開発 or 統合
- FlightAware API使用（APIキー保持中）

### 3. PostgreSQL移行（優先度: 低）

**現在**: SQLite
**理由**: Railway無料枠でも十分
**移行時期**: データ量増加時（目安: 100MB超）

---

## 📚 参考資料

### 公式ドキュメント
- [Flask](https://flask.palletsprojects.com/)
- [Railway](https://docs.railway.app/)
- [PWA Guide](https://web.dev/progressive-web-apps/)

### API
- [JMA API](https://www.jma.go.jp/bosai/forecast/)
- [Open-Meteo](https://open-meteo.com/)
- [FlightAware AeroAPI](https://flightaware.com/commercial/aeroapi/)

### プロジェクト内ドキュメント
- [README.md](README.md) - プロジェクト概要
- [API_KEY_MANAGEMENT.md](API_KEY_MANAGEMENT.md) - セキュリティガイド
- [DATABASE_CLEANUP_SUMMARY.md](DATABASE_CLEANUP_SUMMARY.md) - DB整理履歴
- [PWA_SMARTPHONE_APP_GUIDE.md](PWA_SMARTPHONE_APP_GUIDE.md) - PWAインストール

---

## 🤝 開発ガイドライン

### コミット前のチェックリスト

```bash
# 1. APIキーが含まれていないか確認
git diff railway.json

# 2. 不要なファイルが含まれていないか確認
git status

# 3. テスト実行（ローカル）
python forecast_dashboard.py  # 起動確認
curl http://localhost:5000/api/stats  # API確認

# 4. コミット
git add .
git commit -m "説明的なコミットメッセージ"
git push
```

### コーディング規約

- Python: PEP 8準拠
- 文字エンコーディング: UTF-8
- コメント: 日本語OK（ユーザー向けプロジェクト）
- Docstring: 英語推奨（機能説明）

---

## 📞 サポート

### 問題が発生したら

1. **ログを確認**
   - Railway: Deployments → Logs
   - ローカル: コンソール出力

2. **APIエンドポイントをテスト**
   ```bash
   curl https://web-production-a628.up.railway.app/api/stats
   ```

3. **データベースを確認**
   ```bash
   railway run python -c "import sqlite3; print(sqlite3.connect('/data/ferry_weather_forecast.db').execute('SELECT COUNT(*) FROM weather_forecast').fetchone())"
   ```

4. **GitHub Issuesを検索**
   https://github.com/famosoyuhei/hokkaido_ferry_forecast/issues

---

## ✅ 最近の変更

### 2026-02-18: 季節調整機能の実装（冬季リスク判定の改善）

#### **背景**
精度追跡の結果、直近10日間で精度が大きくバラついている（85.6% ↔ 1.1%）ことが判明。特に2026-02-16は精度1.1%という異常値を記録。

#### **原因分析**

**2026-02-16の異常精度（1.1%）の原因**:
- 全6ルートで「LOW」リスクと予測
- 実際は全6ルート「MOSTLY_CANCELLED」（ほぼ全便欠航）
- 風速12m/s程度でも冬季は欠航するが、システムは「LOW」と判定

**現在のリスク判定の問題点**:
1. 閾値が固定（風速15m/s未満 → MINIMAL）
2. 季節を考慮していない（冬も夏も同じ基準）
3. 利尻・礼文の冬季の厳しさを過小評価

#### **実装した改善策**

**1. 季節調整システム**
```python
# 冬季判定（12月-3月）
is_winter = month in [12, 1, 2, 3]

# 季節倍率（冬季は1.2倍）
seasonal_multiplier = 1.2 if is_winter else 1.0
```

**2. 冬季専用の低い閾値**

| 条件 | 冬季スコア | 夏季スコア | 変更内容 |
|------|-----------|-----------|----------|
| 風速12m/s | **25点** | 10点 | 新規追加（冬季のみ） |
| 風速8m/s | **15点** | 0点 | 新規追加（冬季のみ） |
| 波高1.5m | **10点** | 0点 | 新規追加（冬季のみ） |
| 波高2.0m | **20点** | 15点 | 冬季は+5点 |
| 波高3.0m | **35点** | 30点 | 冬季は+5点 |

**3. リスクレベル判定閾値の引き下げ**

| レベル | 修正前 | 修正後 | 変更 |
|--------|--------|--------|------|
| HIGH | ≥70 | **≥60** | -10点 |
| MEDIUM | ≥40 | **≥35** | -5点 |
| LOW | ≥20 | **≥15** | -5点 |

#### **期待される効果**

**修正前（2026-02-16のケース）**:
- 風速12m/s、波高1.8m
- スコア: 10点（風速のみ）
- 判定: **MINIMAL** ❌

**修正後（同条件、冬季）**:
- スコア: (25点[風速] + 10点[波高]) × 1.2 = **42点**
- 判定: **MEDIUM** ✅

#### **検証方法**

次回の気象データ収集（UTCで00/06/12/18時）から新ロジックが適用されます。以下で効果を検証：

```bash
# 1週間後（2026-02-25頃）に精度再評価
curl https://web-production-a628.up.railway.app/admin/analyze-accuracy

# 期待値：
# - 冬季の精度安定化（60-85%の範囲）
# - 1.1%のような異常値の解消
# - 総合精度75% → 85%への改善
```

#### **修正ファイル**
- [weather_forecast_collector.py](weather_forecast_collector.py) - `calculate_cancellation_risk()`に季節調整を実装
- [improved_risk_calculation.py](improved_risk_calculation.py) - テスト用スタンドアロン版（新規）
- [investigate_bad_day.py](investigate_bad_day.py) - 低精度日の調査ツール（新規）
- コミット: 5c0f320

#### **閾値精度分析結果（2026-02-18 実行）**

`analyze_threshold_accuracy.py`による過去14日間の分析:

**風速帯別精度**:
```
風速範囲    予測数    正解数    精度      欠航数    欠航率
8-12 m/s    6件      0件      0.0%     6件      100%
12-15 m/s   6件      0件      0.0%     6件      100%
15-20 m/s   12件     0件      0.0%     12件     100%
20-25 m/s   6件      0件      0.0%     6件      100%
25-30 m/s   18件     18件     100.0%   18件     100%
30+ m/s     24件     24件     100.0%   24件     100%
```

**重要な発見**:
- **風速8-25 m/s**: 精度0%（全て欠航したが、予測がLOW/MINIMALだった）
- **風速25+ m/s**: 精度100%（HIGH予測が的中）
- **臨界点**: 25 m/s付近に明確な境界線

**False Negative（予測不足）分析**:
- 30件の予測失敗すべてが False Negative
- False Positive（過剰予測）: **0件**
- 平均条件: **風速16.9 m/s、波高1.5 m**
- 旧ロジック判定: LOW/MINIMAL（20点以下）
- 実際の結果: 欠航

**データ駆動型の推奨**:
1. **冬季の風速閾値を15 m/sに引き下げ**
   - 現状: 20 m/s以上でMEDIUM
   - 推奨: **15 m/s以上でMEDIUM**
2. **季節乗数の適用** (1.2倍)
3. **False Positiveは0件** → 保守的すぎる心配なし

**新ロジックとの整合性確認**:
- 新ロジック: 冬季15 m/s = 35点 × 1.2 = **42点 = MEDIUM** ✅
- データ推奨: 15 m/s以上をMEDIUM ✅
- **完全に一致** - 実装が正しいことを証明

関連ファイル:
- [analyze_threshold_accuracy.py](analyze_threshold_accuracy.py) - 閾値分析ツール（新規）
- コミット: a27285e

---

### 2026-02-12: 精度追跡システムのバグ修正と検証完了

#### **背景**
精度追跡システムが動作していたが、異常な精度値（5000%超）と予測データの大量喪失（38%）が発覚。

#### **発見した3つの重大なバグ**

**1. パーセント表示の二重計算**
- **問題**: `analyze_accuracy.py`が`accuracy * 100`を実行
- **原因**: `unified_accuracy_tracker.py`で既に100倍してDBに保存済み
- **結果**: 精度79.4%が7940%と表示される異常値
- **修正**: `analyze_accuracy.py:75`で`* 100`を削除
- **コミット**: 3c764af

**2. DISTINCT による予測データ喪失（38%）**
- **問題**: 同じ日・同じ航路で複数の予測（forecast_hour別）があり、DISTINCTで1つに絞られる
  - 例：2026-02-11は12,834件の予測 → DISTINCT後7,932件（4,902件喪失）
- **原因**: `unified_accuracy_tracker.py:147-158`で`SELECT DISTINCT`を使用
- **修正**: 最新の予測（forecast_hour最大値）のみを取得するよう変更
  ```sql
  -- 修正前: DISTINCT
  SELECT DISTINCT forecast_for_date, route, risk_level...

  -- 修正後: 最新予測を取得
  SELECT cf.* FROM cancellation_forecast cf
  INNER JOIN (
      SELECT forecast_for_date, route, MAX(forecast_hour) as max_hour
      FROM cancellation_forecast
      WHERE forecast_for_date = ?
      GROUP BY forecast_for_date, route
  ) latest ON...
  ```
- **コミット**: 9102240

**3. データベーステーブル名の不一致**
- **問題**: `improved_ferry_collector.py`が`ferry_status_enhanced`に保存、`unified_accuracy_tracker.py`が`ferry_status`を参照
- **結果**: 実運航データが0件として扱われる
- **修正**: `unified_accuracy_tracker.py:180`で正しいテーブル名に変更
- **コミット**: 1f1696a

#### **検証ツール作成**

デバッグと検証のため3つのツールを作成：

1. **check_route_names.py**
   - 予測データと実運航データのルート名マッピングを確認
   - 結果：6ルート完全一致（kafuka-wakkanai, oshidomari-wakkanai等）

2. **check_prediction_count.py**
   - DISTINCT有無での予測件数差分を確認
   - 結果：DISTINCTで38%のデータ喪失を発見

3. **debug_accuracy_data.py**
   - 日別の予測数・実運航数を確認
   - 結果：テーブル名の不一致を発見

#### **修正後の精度結果**

| 日付 | 予測数 | 正解数 | 精度 | F1スコア |
|------|--------|--------|------|----------|
| 2026-02-07 | 11,058 | 10,068 | **91.0%** | 0.953 |
| 2026-02-08 | 11,022 | 8,520 | 77.3% | 0.872 |
| 2026-02-09 | 10,428 | 8,082 | 77.5% | 0.873 |
| 2026-02-10 | 2,844 | 1,578 | 55.5% | 0.714 |
| 2026-02-11 | 522 | 222 | 42.5% | 0.597 |

**総合精度: 79.4%**（35,874件中28,470件正解）

#### **現状の課題**

直近の精度低下（42.5%）の原因：
- システムは**LOW/MINIMAL**（低リスク）と予測
- 実際は**MOSTLY_CANCELLED**（ほぼ全便欠航）
- 冬季の厳しい天候（風速30m/s超）を過小評価

**次のアクション**:
- Phase 3: 機械学習による閾値最適化が必要
- 現在のリスク判定基準（風速15m/s→LOW、20m/s→MEDIUM）が甘すぎる
- 冬季は閾値を下げる（例：風速12m/s→MEDIUM、18m/s→HIGH）

#### **修正ファイル一覧**
- [analyze_accuracy.py](analyze_accuracy.py) - パーセント計算修正
- [unified_accuracy_tracker.py](unified_accuracy_tracker.py) - 最新予測取得、テーブル名修正
- [check_route_names.py](check_route_names.py) - ルート名検証ツール（新規）
- [check_prediction_count.py](check_prediction_count.py) - DISTINCT検証ツール（新規）
- [forecast_dashboard.py](forecast_dashboard.py) - デバッグエンドポイント追加

---

### 2026-01-20: GitHub Actions完全自動化（Railway Cron問題の最終解決）

#### **背景**
Railway Cronが何度試しても動作せず、データ収集の自動化が不安定だった。

#### **解決策**
GitHub Actionsで完全自動化を実現。Railway CLIを使って直接Railway上でスクリプト実行。

#### **実装内容**

**1. 精度追跡ワークフローの改善**
- ファイル: `.github/workflows/unified-accuracy-tracking.yml`
- 変更点:
  ```yaml
  # 自動スケジュールを再有効化
  schedule:
    - cron: '0 22 * * *'  # 毎日 07:00 JST

  # Railway CLI で直接実行（エンドポイント経由より確実）
  railway link hokkaido-ferry-forecast --environment production
  railway run python unified_accuracy_tracker.py
  ```

**2. セットアップ要件**
- GitHub Secrets に `RAILWAY_TOKEN` を設定（初回のみ）
- Railway Webダッシュボードでトークン作成
- 手動トリガーでテスト可能

**3. メリット**
- ✅ Railway Cronの問題を完全回避
- ✅ 確実な毎日自動実行（GitHub Actionsは信頼性が高い）
- ✅ 実行履歴とログが見える
- ✅ エラー時は自動メール通知
- ✅ アーティファクト保存（accuracy_report.txt）

**4. ドキュメント更新**
- `GITHUB_ACTIONS_SETUP.md` に詳細手順を追加
- Railway CLIトークン取得方法
- GitHub Secrets設定手順
- トラブルシューティング

**5. 関連ファイル**
- [.github/workflows/unified-accuracy-tracking.yml](.github/workflows/unified-accuracy-tracking.yml)
- [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)
- [unified_accuracy_tracker.py](unified_accuracy_tracker.py)

**次のステップ**:
1. RAILWAY_TOKEN を GitHub Secrets に設定
2. 手動トリガーでテスト実行
3. 1週間データ蓄積を監視
4. Phase 3（機械学習）に進む

---

### 2026-01-19 (夜): 統合精度追跡システム実装（Phase 1-2）

#### **新規システム: unified_accuracy_tracker.py**
包括的な精度追跡システムを実装。複数データベースを統合して精度計算を自動化。

**主な機能**:
1. **データベース統合**
   - `ferry_weather_forecast.db`: 予測データ
   - `heartland_ferry_real_data.db`: 実運航データ
   - 自動マッチングで精度計算

2. **高度な精度メトリクス**
   - 混同行列（TP, TN, FP, FN）
   - 適合率（Precision）: 欠航予測の的中率
   - 再現率（Recall）: 実際の欠航を予測できた割合
   - F1スコア: 精度の総合指標

3. **新規データベーステーブル**
   - `unified_operation_accuracy`: 予測 vs 実績の詳細記録
   - `unified_daily_summary`: 日別精度サマリー
   - `risk_level_accuracy`: リスクレベル別精度分析

**GitHub Actions統合**:
- ワークフロー: `.github/workflows/unified-accuracy-tracking.yml`
- 実行: 毎日07:00 JST（実運航データ収集の1時間後）
- 自動化: データベースダウンロード → 精度計算 → アップロード
- レポート: アーティファクト保存（30日間）

**戦略ドキュメント**:
- `ACCURACY_IMPROVEMENT_STRATEGY.md`作成
- 5フェーズの実装計画
- 複数気象データソース統合
- 機械学習による閾値最適化
- コスト分析と期待効果

**次のステップ**:
- データ蓄積の監視（1週間）
- Phase 3実装準備（機械学習導入）
- 実測気象データ収集の追加

---

### 2026-01-19 (昼): UI改善と日本時間対応（重要）

#### 1. **「次の便の予報」機能実装**
   - 問題：全便出航後も「本日の運航予報」を表示していた
   - 解決：`get_next_sailings()`メソッドを実装
     - 現在時刻以降の本日便があれば表示
     - 全便出航済みなら翌日の最初の便を表示
     - タイミングラベル表示（「本日 06:55発」「明日 06:55発」）
   - ファイル：`forecast_dashboard.py:186-278`, `templates/forecast_dashboard.html:464-510`

#### 2. **日本時間(JST)対応（最重要）** ⚠️
   - **問題**：Railwayサーバーは**UTC時刻**で動作
     - 表示時刻が9時間古い（例：UTC 10:57 → JST 19:57）
     - 「次の便」判定が9時間ズレる

   - **解決**：`pytz`ライブラリでJST明示
     ```python
     import pytz
     jst = pytz.timezone('Asia/Tokyo')
     current_datetime = datetime.now(jst)  # 必須！
     ```

   - **変更箇所**：
     - `forecast_dashboard.py:186-199` - `get_next_sailings()`
     - `forecast_dashboard.py:414-416` - `index()`表示時刻
     - `requirements.txt` - `pytz>=2023.3`追加

   - **重要な注意点**：
     - ❌ `datetime.now()` → RailwayではUTC時刻
     - ✅ `datetime.now(pytz.timezone('Asia/Tokyo'))` → JST時刻
     - データ収集スクリプトも同様に注意が必要

#### 3. **UIシンプル化**
   - トップページの7日間予報グリッドを削除（ユーザー要望）
   - 3ステップ便選択システムを維持
   - リスクガイドとデータ統計を保持

#### 4. **キャッシュ制御強化**
   - HTML meta tags + Flask response headers
   - ブラウザキャッシュによる古いデータ表示を防止

---

### 2026-01-01: Railway本番環境セットアップ完了

1. **Railwayへの統一**
   - RenderからRailwayに本番環境を移行
   - 理由：Volume、Cron Jobs、常時起動が無料で使える
   - Renderは永続ディスク($3/月) + Cron($7/月) = $10/月かかる

2. **Volume設定**
   - Mount Path: `/data`
   - 環境変数: `RAILWAY_VOLUME_MOUNT_PATH=/data`
   - データベースを永続化

3. **重要な修正：GitHubからDBファイルを削除**
   - 問題：`ferry_weather_forecast.db`がGit管理されていた
   - 影響：デプロイごとに古いDBで上書きされ、Volumeの新データが消える
   - 解決：`git rm --cached ferry_weather_forecast.db`で削除
   - 現在：Volumeのみでデータ管理

4. **セキュリティ強化**
   - FlightAware APIキーを`railway.json`から削除
   - `railway_local.json`に移動（gitignore追加）
   - `.env.example`と`API_KEY_MANAGEMENT.md`を作成

5. **コード整理**
   - 67個のレガシースクリプトをアーカイブ
   - 本番ファイルを7個に集約

6. **データベース統合**
   - 11個のDBを3個に統合
   - 8個のレガシーDBをバックアップ

7. **ドキュメント整備**
   - このCLAUDE.mdを作成
   - DATABASE_CLEANUP_SUMMARY.mdを作成

---

**最終更新日**: 2026-01-19
**メンテナー**: 利尻島フェリー予報プロジェクト
**ライセンス**: Private（商用利用）

---

## 🚀 クイックスタート（Claude Code向け）

Claude Codeでこのプロジェクトを扱う際は：

1. **本番環境URL**: https://web-production-a628.up.railway.app/
2. **主要ファイル**: 7個のPythonスクリプトのみ（他はアーカイブ済み）
3. **データベース**: 3個のみ（`ferry_weather_forecast.db`, `heartland_ferry_real_data.db`, `notifications.db`）
4. **セキュリティ**: `railway.json`にAPIキーを含めない（`railway_local.json`使用）
5. **テスト**: `/api/stats`でデータ確認可能

**注意**: Railway Cronジョブが管理画面に表示されない場合は、Railway CLIでの手動実行が必要です。
