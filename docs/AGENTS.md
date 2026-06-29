# Docs Agent Guide

このディレクトリは運用ドキュメント、監査説明、アーカイブ資料を扱う。
コード変更時のハードルールはルート `AGENTS.md` を優先する。

## Documentation Rules

- 仕様説明ではJST日付を明示する。
- DB・Sheets・APIのどれを根拠にしているかを分けて書く。
- `.db`、APIキー、トークン、個人情報をドキュメントに貼らない。
- フェリー便別データは `ferry_status_enhanced` を正とし、旧 `ferry_status` を新規説明の正テーブルにしない。
- 2026-04-05以前の精度データは、スクレイパーバグ期間として注記する。

## Cross References

- AI社員・自動化仕様は `docs/ai_employees/AGENTS.md`。
- 欠航リサーチや時刻表JSONの機械処理仕様は `skills/ferry-cancellation-research/AGENTS.md`。
