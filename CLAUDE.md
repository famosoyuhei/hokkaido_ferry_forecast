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

## 📊 リスク計算ロジック

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

## ✅ 最近の変更（2025-12-31）

1. **セキュリティ強化**
   - FlightAware APIキーを`railway.json`から削除
   - `railway_local.json`に移動（gitignore追加）
   - `.env.example`と`API_KEY_MANAGEMENT.md`を作成

2. **コード整理**
   - 67個のレガシースクリプトをアーカイブ
   - 本番ファイルを7個に集約

3. **データベース統合**
   - 11個のDBを3個に統合
   - 8個のレガシーDBをバックアップ

4. **ドキュメント整備**
   - このCLAUDE.mdを作成
   - DATABASE_CLEANUP_SUMMARY.mdを作成

---

**最終更新日**: 2025-12-31
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
