# 永久保存DB・Sheets充填監査AI社員

## ミッション

毎日の精度検証に必要なデータが、永久保存DBとGoogle Sheetsの両方に同じ対象日まで充填されているかを監査する。

## 対応スクリプト

`accuracy_fill_auditor.py`

## 入力

- `/admin/export-accuracy-data?days=90` のJSON
- Google Sheets:
  - `Daily Metrics`
  - `Ferry Details`
  - `Flight Details`
  - `Alerts`

## 監査対象日

原則としてJSTの前日。例: 2026-06-28 07:50 JST に実行する場合、対象日は `2026-06-27`。

## 監査ルール

1. 永久保存DBのエクスポート期間末尾が対象日以上であること。
2. `daily_metrics` にフェリー・飛行機それぞれ対象日の行があること。
3. `ferry_details` と `flight_details` の最新日付が対象日であること。
4. 対象日のフェリー明細に `actual_wind` と `actual_wave` が入っていること。
5. 実測視程 `actual_visibility` はソース側で欠損しうるため、空欄だけでは異常にしない。
6. 対象日の予報風速・予報波高と実測風速・実測波高が広範囲で完全一致する場合は、`forecast_actual_leakage` 疑いとして扱う。
7. Google Sheetsの各タブが、永久保存DBエクスポートに存在する対象日キーをすべて持っていること。
8. Sheets認証が未設定でSheets確認ができない場合は、監査不能ではなく重大異常として扱う。

## 異常分類

| コード | 意味 | 優先度 |
|---|---|---|
| `DB_EXPORT_STALE` | 永久保存DBエクスポートが対象日まで進んでいない | HIGH |
| `DB_DAILY_MISSING` | 日次精度行が欠けている | HIGH |
| `DB_DETAIL_MISSING` | 便別明細が欠けている | HIGH |
| `DB_ACTUAL_WEATHER_MISSING` | フェリー明細の実測風・波が欠けている | HIGH |
| `FORECAST_ACTUAL_LEAKAGE_SUSPECTED` | 予報値と実測値が不自然に一致している | HIGH |
| `SHEET_DATE_MISMATCH` | Sheetsの最新日付が対象日ではない | HIGH |
| `SHEET_KEYS_MISSING` | DBにある対象日キーがSheetsにない | HIGH |
| `SHEET_ACTUAL_WEATHER_MISSING` | Sheets上の実測風・波が欠けている | HIGH |
| `AUDITOR_RUNTIME_ERROR` | 監査スクリプト自体が実行不能 | HIGH |

## 実行タイミング

07:50 JST。精度監査、Sheets同期、実測収集の後に実行する。

## 必要な環境変数

- `ADMIN_TOKEN`: Railway admin endpoint用
- `GOOGLE_SHEETS_ID`: 省略時は本番Sheets IDを使用
- `GOOGLE_SHEETS_API_KEY` または `GOOGLE_SHEETS_BEARER_TOKEN`: Sheets読み取り用

## 出力

- `status`: `success` または `fail`
- `expected_date`
- DB/Sheets別の行数
- 重大異常件数
- 異常コード、説明、サンプルキー

異常が1件でもHIGHならGitHub Actionsを失敗させ、問題点整理AI社員の入力にする。
