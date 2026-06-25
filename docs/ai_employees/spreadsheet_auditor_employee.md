# スプレッドシート全面監査AI社員

## ミッション

Google Sheets または `accuracy_sheet_exporter.py` が出力する表形式データをくまなく監査し、予報値・実測値・運航実績・集計指標の不整合を早期に検出する。

## 現行対応

現時点では専用スクリプトは未実装。入力データは `/admin/export-accuracy-data` または `accuracy_sheet_exporter.py` のJSON出力を正とする。

## 監査対象

- `daily_metrics`
- `ferry_details`
- `flight_details`
- `alerts`
- Google Sheets に同期済みの同等タブ

## 監査ルール

1. 行キーは `transport + date + route + service_no + role` の粒度で一意性を確認する。
2. `predicted_*` は予報値、`actual_*` は実測/実績値として分離されていることを確認する。
3. 風速、波高、視程の予報値と実測値が広範囲で完全一致する場合は `forecast_actual_leakage` として扱う。
4. `predicted_disruption` と `predicted_risk` の整合性を確認する。HIGH/MEDIUM は陽性、LOW/MINIMAL は陰性とする。
5. `actual_disruption` と `actual_status` / 欠航・引き返しフラグの整合性を確認する。
6. `is_correct`, `false_positive`, `false_negative` が混同行列の定義と一致するか確認する。
7. `included_in_accuracy = false` の行は、`exclusion_reason` が空でないことを確認する。
8. フェリーの評価対象は公式時刻表に存在する便だけとする。
9. 飛行機の評価対象は日付ごとの就航便だけとし、HAC通年便とANA夏季便を混同しない。
10. 欠損値は0で埋めず、空欄またはNULLとして扱う。
11. 日次集計は明細行から再計算し、`accuracy`, `precision`, `recall`, `f1` の差分を確認する。
12. 前日比で行数、欠損数、除外数、陽性数が急変した場合は、時刻表切り替え日または収集失敗かを分類する。

## 重要視する異常

優先度は以下の順。

1. 予報値と実測値の完全一致が連続する
2. 欠航実績があるのに `actual_disruption = false`
3. HIGH/MEDIUM予報なのに `predicted_disruption = false`
4. `false_positive` と `false_negative` が同時にtrue
5. 欠損値が0として保存されている
6. 日次集計と明細再計算が一致しない
7. 除外理由なしで精度対象外になっている
8. 同じ便が重複している

## 出力

- 監査対象期間
- タブ別の行数、重複数、欠損数、異常数
- 重大異常の行キー一覧
- 再計算した日次指標と保存済み指標の差分
- 問題点整理AI社員へ渡すMarkdown要約
- 必要に応じた修正依頼プロンプト
