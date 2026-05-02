<div align="center">
  <img src="app_icon.png" alt="Hokkaido Ferry Forecast" width="150" height="150">
  <h1>北海道フェリー運航予報システム</h1>
  <p>稚内⇔利尻島・礼文島の欠航リスクを7日間予報するWebアプリ</p>
</div>

**本番URL**: https://web-production-a628.up.railway.app/

---

## 概要

フェリー輸送に依存する利尻島・礼文島の事業者向けに、**7日間の欠航リスク予報**（HIGH / MEDIUM / LOW / MINIMAL）を提供するシステムです。気象庁(JMA) + Open-Meteo APIの気象データをもとにリスクを算出し、PWA対応でスマートフォンからも利用できます。

## 機能

- 7日間の欠航リスク予報（全6ルート）
- 風速・波高・視程に基づくリスク計算
- PWA対応スマートフォンアプリ（iOS/Android）
- 自動データ収集（1日4回気象、1日1回実運航）
- Hindcast精度追跡（実測気象 vs 実際の運航結果）

## 対象航路

- 稚内 ↔ 鴛泊（利尻島）
- 稚内 ↔ 香深（礼文島）
- 鴛泊 ↔ 香深

## 技術スタック

| 項目 | 内容 |
|------|------|
| バックエンド | Python 3.11 / Flask / gunicorn |
| データベース | SQLite（Railway Volume で永続化） |
| ホスティング | Railway |
| 自動化 | GitHub Actions（データ収集・精度追跡） |

## データソース

- **気象予報**: 気象庁(JMA) API + Open-Meteo Forecast/Marine API
- **実測気象**: Open-Meteo Archive API（ERA5再解析）
- **実運航データ**: [ハートランドフェリー公式サイト](https://heartlandferry.jp/status/)

## データベース（3個）

| ファイル | 用途 |
|---------|------|
| `ferry_weather_forecast.db` | 気象予報・欠航リスク予測・実測気象 |
| `heartland_ferry_real_data.db` | 実運航データ |
| `notifications.db` | プッシュ通知（開発予定） |

## 自動化スケジュール（GitHub Actions）

| ワークフロー | 実行時刻(JST) | 内容 |
|-------------|-------------|------|
| data-collection.yml | 05:00 / 11:00 / 17:00 / 23:00 | 気象予報収集 |
| ferry-collection.yml | 06:00 | 実運航データ収集 |
| actual-weather-collection.yml | 07:30 | 実測気象収集（前日分） |
| unified-accuracy-tracking.yml | 07:00 | 精度追跡 |

## ローカル開発

```bash
git clone https://github.com/famosoyuhei/hokkaido_ferry_forecast.git
cd hokkaido_ferry_forecast
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python forecast_dashboard.py   # → http://localhost:5000
```

## APIエンドポイント

```bash
curl https://web-production-a628.up.railway.app/api/stats     # 統計情報
curl https://web-production-a628.up.railway.app/api/forecast  # 7日間予報
curl https://web-production-a628.up.railway.app/api/today     # 本日詳細
```

## ドキュメント

- [CLAUDE.md](CLAUDE.md) - システム全体の詳細仕様（開発者向け）
- [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) - 自動化の設定方法
- [PWA_SMARTPHONE_APP_GUIDE.md](PWA_SMARTPHONE_APP_GUIDE.md) - スマホアプリのインストール方法
- [API_KEY_MANAGEMENT.md](API_KEY_MANAGEMENT.md) - APIキーの管理方法

## セキュリティ

このリポジトリは**Public**です。APIキー・シークレットは Railway Variables に保存し、コードにハードコードしません。詳細は [API_KEY_MANAGEMENT.md](API_KEY_MANAGEMENT.md) を参照。

---

**ライセンス**: Private（商用利用）
