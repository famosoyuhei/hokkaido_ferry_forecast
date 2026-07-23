# AI Employees Agent Guide

AI社員定義と自動化スケジュールを編集する時だけ読む。

## AI Employee Map

| AI社員 | 定義ファイル | 対応スクリプト |
|---|---|---|
| 海上気象予報取得 | `marine_forecast_employee.md` | `weather_forecast_collector.py` |
| 海上気象実測取得 | `actual_weather_employee.md` | `actual_weather_collector.py` |
| フェリー運航記録取得 | `ferry_operation_collector_employee.md` | `improved_ferry_collector.py` |
| 予報精度監査 | `accuracy_auditor_employee.md` | `unified_accuracy_tracker.py` |
| スプレッドシート全面監査 | `spreadsheet_auditor_employee.md` | `spreadsheet_auditor.py`（データ源は `accuracy_sheet_exporter.py`） |
| 永久保存DB・Sheets充填監査 | `accuracy_fill_auditor_employee.md` | `accuracy_fill_auditor.py` |
| 問題点整理・修正依頼 | `issue_prompt_composer_employee.md` | `issue_prompt_composer.py` |
| LINE監査 | `line_audit_employee.md` | `line_audit.py` |
| UI監視 | `ui_monitor_employee.md` | `ui_monitor.py` |

## Automation Schedule (JST)

| 時刻 | スクリプト | 目的 |
|---|---|---|
| 05:00 | `weather_forecast_collector.py` | 朝の予報更新 |
| 06:00 | `improved_ferry_collector.py` | 当日運航状況取得 |
| 06:30 | `actual_weather_collector.py` | 前日実測気象取得 |
| 07:00 | `unified_accuracy_tracker.py` | 精度監査 |
| 07:05 | `accuracy_sheet_exporter.py` | スプレッドシート全面監査用データ出力・整合性確認 |
| 07:20 | `issue_prompt_composer.py` | 問題点整理（異常時のみ出力） |
| 09:20 | `accuracy_fill_auditor.py` | 永久保存DB・Google Sheetsへの精度検証データ充填確認 |
| 09:25 | `spreadsheet_auditor.py` | スプレッドシート全面監査（12ルール、DB/Sheets両方） |
| 11:00 | `weather_forecast_collector.py` | 昼の予報更新 |
| 17:00 | `weather_forecast_collector.py` | 夕の予報更新 |
| 23:00 | `weather_forecast_collector.py` | 夜の予報更新 |

詳細な実行順は `automation_blueprint.md` を参照する。

## Editing Notes

- 対応スクリプト名を変えたら、ルート `AGENTS.md` の Main Scripts も確認する。
- 監査系AI社員では、予報値と実測値の混同禁止を必ず維持する。
- Sheets確認用APIキー未設定は監査不能ではなく重大異常として扱う。
- `issue_prompt_composer.py` の使い方:

```bash
python issue_prompt_composer.py
python issue_prompt_composer.py --days 30
python issue_prompt_composer.py --output issue_prompt.md
```
