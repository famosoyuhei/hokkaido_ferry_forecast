# n8n 精度分析連携ガイド

フェリー・飛行機の予報ロジックや既存スケジュールを変更せず、監査済みデータを
Google Sheets に同期して可視化するための追加構成です。

## 安全性

- `/admin/export-accuracy-data` は SQLite を `mode=ro` / `query_only` で開き、書き込みません。
- n8n は既存収集・監査の完了後、毎日 07:40 JST に1回だけ実行します。
- 予報閾値は変更しません。見逃しはアラート化し、元データ確認後の判断材料にします。
- フェリーの整備運休、飛行機の実績 `unknown`・予報欠損・明らかな非気象理由は精度母数から除外します。
- 飛行機は便時刻以前に生成された最新予報だけを使い、出発後の予報が混ざる評価リークを防ぎます。
- Google Sheets は `key` 列で upsert するため、再実行しても重複しません。

## 導入手順

1. 作成済みのネイティブGoogleスプレッドシートを使用します。
   - `https://docs.google.com/spreadsheets/d/1C2kvlDZxo0XBagaZfZw3muShhm2Z3XGu9wMIK90kmUM/edit`
   - ExcelアプリやMicrosoft 365は不要です。
2. n8n に `n8n/ferry-flight-accuracy-to-sheets.json` をインポートします。
3. n8n の環境変数を設定します。
   - `FORECAST_ADMIN_TOKEN`: Railway の `ADMIN_TOKEN` と同じ値
   - Google Sheets IDは同梱ワークフローへ設定済みです。別シートへ複製する場合のみ、4つのGoogle SheetsノードでIDを差し替えます。
4. 4つの Google Sheets ノードに同じ Google OAuth2 credential を選択します。
5. `Manual Test` から実行し、4シートへデータが入ることを確認します。
6. `Daily 07:40 JST` ワークフローを Active にします。

n8n Cloud などで `$env` が利用できない場合は、管理トークンをHeader Auth credentialへ移してください。
ワークフローJSONへトークンを直書きしないでください。

## API

```text
GET /admin/export-accuracy-data?days=90
GET /admin/export-accuracy-data?start=2026-06-01&end=2026-06-30
X-Admin-Token: <ADMIN_TOKEN>
```

レスポンスの `datasets` は次の4種類です。

- `daily_metrics`: 日別のAccuracy、Precision、Recall、F1、TP/TN/FP/FN
- `ferry_details`: 便別の予報と実績、気象値、除外理由
- `flight_details`: 便別の横風・視程予報と運航実績、除外理由
- `alerts`: データ未収集、更新遅延、見逃しの要確認項目

## 運用上の見方

- 最優先は `false_negatives`（欠航・目的地変更の見逃し）です。
- `excluded` が増えた日は、API障害や実績 `unknown`、整備運休を確認します。
- 最低30日分の正しい飛行機実績が揃うまでは、横風・視程の閾値を変更しません。
- Dashboardの推移が悪化しても、先に `Ferry Details` / `Flight Details` の元データを確認します。
