# 精度追跡システム 設計仕様書

**最終更新**: 2026-05-03（v1.3）  
**バージョン**: 1.0  
**目的**: 役割分担・現状の問題点・改善ロードマップを一元管理する

---

## システム全体の役割分担

```
【役割1】 フェリー実運航データ収集
  improved_ferry_collector.py
  → heartland_ferry_real_data.db / ferry_status_enhanced

【役割2】 各港の実測気象データ収集
  actual_weather_collector.py
  → ferry_weather_forecast.db / actual_weather

【役割3】 予報リスクの計算・保存
  weather_forecast_collector.py
  → ferry_weather_forecast.db / cancellation_forecast

【役割4】 実測気象 × 実運航データの照合（Hindcast精度）
  unified_accuracy_tracker.py
  → ferry_weather_forecast.db / unified_operation_accuracy, unified_daily_summary
```

---

## 現状の実装と問題点

### 役割1：フェリー実運航データ収集 ✅ 正常稼働

| 項目 | 内容 |
|------|------|
| スクリプト | `improved_ferry_collector.py` |
| 実行 | GitHub Actions `ferry-collection.yml`（毎日06:00 JST） |
| 取得内容 | 便ごとの出発時刻・運航/欠航フラグ |
| 対象ルート | 6ルート（稚内-鴛泊、稚内-香深、稚内-沓形、鴛泊-香深 往復） |
| 信頼できる開始日 | **2026-04-05以降**（それ以前はスクレイパーのバグにより全便欠航と誤記録） |

---

### 役割2：実測気象データ収集 ✅ **2026-05-03 修正済み**

| 項目 | 内容 |
|------|------|
| スクリプト | `actual_weather_collector.py` |
| 実行 | GitHub Actions `actual-weather-collection.yml`（毎日07:30 JST） |
| 取得地点 | **4港（稚内・鴛泊・沓形・香深）** |
| 取得頻度 | 1時間ごと（ERA5再解析） |
| 波高取得 | 各港沖（Marine Archive API） |
| DBスキーマ | `UNIQUE(date, hour, location)` — 既存データは自動移行 |

**問題の詳細**：

```python
# actual_weather_collector.py:23 現状
WAKKANAI = {'lat': 45.415, 'lon': 141.673}
# 稚内のみ。鴛泊・沓形・香深の気象が未収集。
```

4港の座標（あるべき姿）：

| 港 | 緯度 | 経度 | 備考 |
|----|------|------|------|
| 稚内港 | 45.415 | 141.673 | ✅ 現在収集中 |
| 鴛泊港（利尻島東） | 45.200 | 141.216 | ❌ 未収集 |
| 沓形港（利尻島西） | 45.393 | 141.107 | ❌ 未収集 |
| 香深港（礼文島） | 45.298 | 141.036 | ❌ 未収集 |

**影響**：稚内の気象だけでは利尻島・礼文島側の局所的な強風・高波を捉えられない。
特に西風時は稚内が穏やかでも鴛泊・沓形・香深が荒れる状況が発生しうる。

---

### 役割3：予報リスクの計算・保存 ✅ 正常稼働

| 項目 | 内容 |
|------|------|
| スクリプト | `weather_forecast_collector.py` |
| 実行 | GitHub Actions `data-collection.yml`（毎日05:00/11:00/17:00/23:00 JST） |
| 予報地点 | 稚内・利尻・礼文（3地点の最大値でリスク算出） |
| 保存先 | `cancellation_forecast` テーブル（6ルート × 7日間） |

---

### 役割4：Hindcast精度照合 ✅ **2026-05-03 修正済み（v2）**

| 項目 | 内容 |
|------|------|
| スクリプト | `unified_accuracy_tracker.py` |
| 実行 | `accuracy-tracking.yml`（役割2から分離済み）07:30 JST |
| 気象データ | **便ごとに出発港×出発時刻（±1h）の実測値** |
| ルート別気象 | ✅ `ROUTE_DEPARTURE_PORT` マッピングで出発港を特定 |
| 礼文ルート強化 | ✅ `ROUTE_DESTINATION_PORT` + MAX(出発港, 香深) で最悪値を使用 |
| 精度単位 | **便単位**（旧：1日1ルートの多数決 → 新：1便1レコード） |
| 整備ドック検出 | ✅ `is_likely_maintenance` フラグ。4/5〜15 + 全便欠航 + 風速<15m/s → フラグ |
| Precision/Recall | 整備フラグ付き日は P/R/F1 の計算から除外（Accuracy は全便対象） |

---

## GitHubワークフローの現状

| ワークフロー | 役割 | 実行時刻(JST) | 状態 |
|------------|------|-------------|------|
| `data-collection.yml` | 役割3（予報収集） | 05:00/11:00/17:00/23:00 | ✅ |
| `ferry-collection.yml` | 役割1（実運航収集） | 06:00 | ✅ |
| `actual-weather-collection.yml` | 役割2のみ（実測気象収集） | 07:00 | ✅ 分離済み |
| `accuracy-tracking.yml` | 役割4のみ（精度照合） | 07:30 | ✅ 新設（2026-05-03） |

---

## 改善ロードマップ

### 優先度 高：4港の実測気象収集（役割2の修正）

**修正ファイル**: `actual_weather_collector.py`

```python
# 修正後のあるべき姿
LOCATIONS = {
    'wakkanai':   {'lat': 45.415, 'lon': 141.673},
    'oshidomari': {'lat': 45.200, 'lon': 141.216},
    'kutsugata':  {'lat': 45.393, 'lon': 141.107},
    'kafuka':     {'lat': 45.298, 'lon': 141.036},
}
# → actual_weather テーブルに location カラムを追加
# → 各港ごとに hourly データを収集
```

**DBスキーマ変更**：

```sql
-- 現状
actual_weather (id, date, hour, wind_speed, wave_height, visibility, collected_at)
UNIQUE(date, hour)

-- 修正後
actual_weather (id, date, hour, location, wind_speed, wave_height, visibility, collected_at)
UNIQUE(date, hour, location)
```

---

### 優先度 高：出発時刻ベースの気象マッチング（役割4の修正）

**修正ファイル**: `unified_accuracy_tracker.py`

```python
# 修正後のあるべき姿
# ルートの出発港を使い、出発時刻 ±1時間の気象値を取得する

ROUTE_DEPARTURE_PORT = {
    'wakkanai_oshidomari': 'wakkanai',
    'oshidomari_wakkanai': 'oshidomari',
    'wakkanai_kafuka':     'wakkanai',
    'kafuka_wakkanai':     'kafuka',
    'wakkanai_kutsugata':  'wakkanai',
    'kutsugata_wakkanai':  'kutsugata',
    'oshidomari_kafuka':   'oshidomari',
    'kafuka_oshidomari':   'kafuka',
}

# 出発時刻に合わせた気象値を取得
departure_hour = int(departure_time[:2])   # "06:55" → 6
SELECT wind_speed, wave_height, visibility
FROM actual_weather
WHERE date = ? AND location = ? AND hour = ?
```

---

### 優先度 中：ワークフローの分離

✅ **2026-05-03 完了**

```
actual-weather-collection.yml  → 役割2のみ（実測気象収集）07:00 JST → /admin/run-actual-weather
accuracy-tracking.yml          → 役割4のみ（精度照合）     07:30 JST → /admin/run-accuracy-only
```

---

### 優先度 低：バックフィル対応

✅ **2026-05-04 完了**  
4港すべての実測気象データを 2025-10-01〜2026-05-02 で取得済み（214日 × 4港 × 24時間 = 20,544件）。

---

## 既知のデータバイアス・限界事項（MARITIME_RESEARCH.md 照合結果）

> 詳細は [MARITIME_RESEARCH.md](MARITIME_RESEARCH.md) §8・§11 参照

### ERA5 波高の離島近傍過大推定

| 項目 | 内容 |
|------|------|
| 原因 | ERA5 の水平解像度は 31km。利尻島（直径約20km）・礼文島（幅約8km）は 1〜2 格子以下 |
| 影響 | 島陰効果が表現されず、鴛泊・沓形・香深の波高が実際より**高く**計算される可能性 |
| 方向 | False Positive（欠航予測 → 実際は運航）が増える方向に働く |
| 対応 | 既知バイアスとして記録。実測値との乖離が蓄積されれば補正係数を検討（Phase 3） |

### 出発港のみ使用（航路中間点の気象を未反映）

| 項目 | 内容 |
|------|------|
| 現行 | 出発港の実測気象でリスク計算 |
| 実態 | 稚内〜香深（55km）ルートの中間は礼文水道で最も外洋性が高い |
| 影響 | 礼文島行きのルートで欠航リスクを若干過小評価する可能性 |
| 対応 | Phase 3 で航路別バイアス補正を検討 |

### 計画外欠航（定期ドック）の混入

| 項目 | 内容 |
|------|------|
| 現象 | 毎年4月上旬〜中旬にハートランドフェリーが定期整備（ドック入り）を実施 |
| 影響 | この期間の全便欠航が「気象モデルの見逃し（FN）」として精度計算に混入する |
| 2026年実績 | 2026-04-10〜11 が全便欠航（実測風速は穏やか → 気象外欠航と判断） |
| 対応 | 毎年4月5〜15日前後を「計画外欠航候補期間」としてフラグ管理することを Phase 3 で検討 |

### 霧の継続時間を未考慮

| 項目 | 内容 |
|------|------|
| 現行 | 1時間単位の視程値をリスクスコアに加算（単発か継続かを区別しない） |
| 実態 | 夏季（6〜8月）の移流霧は 2〜3 日間継続することがある |
| 対応 | 「連続 N 時間以上の視程不良」への追加スコアを Phase 4 で検討 |

---

## データフロー（あるべき姿）

```
【毎日のデータ収集フロー】

05:00 JST  weather_forecast_collector.py
           → cancellation_forecast（稚内・利尻・礼文の予報リスク）

06:00 JST  improved_ferry_collector.py
           → ferry_status_enhanced（便ごとの運航/欠航実績）

07:00 JST  actual_weather_collector.py（4港対応後）
           → actual_weather（稚内・鴛泊・沓形・香深の hourly 実測値）

07:30 JST  unified_accuracy_tracker.py（出発時刻対応後）
           → 各便の出発港・出発時刻に対応した実測気象を取得
           → hindcast リスク計算
           → 実際の運航結果と照合
           → unified_operation_accuracy に保存
```

---

## 各スクリプトの役割一覧（現時点）

| スクリプト | 役割 | 状態 | 主な問題 |
|-----------|------|------|---------|
| `weather_forecast_collector.py` | 予報収集・リスク計算 | ✅ 稼働中 | なし |
| `improved_ferry_collector.py` | 実運航データ収集 | ✅ 稼働中 | なし |
| `actual_weather_collector.py` | 実測気象収集 | ✅ 稼働中 | 4港対応済み（2026-05-03） |
| `unified_accuracy_tracker.py` | Hindcast精度照合 | ✅ 稼働中 | 礼文MAX気象・整備ドック検出フラグ対応済み（2026-05-03） |
| `backfill_actual_weather.py` | 実測気象の一括取得 | ✅ 利用可能 | 4港対応済み・2026-04-05以降を再実行推奨 |
| `auto_threshold_adjuster.py` | 閾値の自動調整 | 🔴 未稼働 | 精度データ蓄積後に使用予定 |
| `ml_threshold_optimizer.py` | ML閾値最適化 | 🔴 未稼働 | Phase 3（将来） |
| `notification_service.py` | 通知送信 | 🔴 未稼働 | 将来実装 |

---

## 更新履歴

| 日付 | バージョン | 変更内容 |
|------|----------|---------|
| 2026-05-03 | 1.0 | 初版作成。現状の問題点（稚内のみ・日平均値）と改善ロードマップを文書化 |
| 2026-05-03 | 1.1 | 役割2・4の修正を実装・反映。全スクリプトを稼働中に更新 |
| 2026-05-04 | 1.2 | バックフィル完了を記録。MARITIME_RESEARCH.md 照合によるバイアス・限界事項を追加 |
| 2026-05-03 | 1.3 | 礼文ルートMAX気象・整備ドック検出・ワークフロー分離を実装・反映 |
