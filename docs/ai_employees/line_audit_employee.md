# LINE連携監査AI社員

## ミッション

LINE Messaging API ボットの設定、ユーザー登録状況、朝通知の送信実績を毎日確認し、通知が必要なユーザーへ確実に届く状態を維持する。

## 現行対応

`line_audit.py` が次のチェックを実行し、コンソール出力とオプションのJSONレポートを出力する。
`line_bot_service.py` の `send_morning_notifications()` が `notification_log` テーブルへ実行結果を記録する。

## 監査ルール

1. 評価の基準時刻はJSTとする。
2. SDK チェックは `linebot.v3` のインポート可否で判断する。
3. 環境変数 `LINE_CHANNEL_ACCESS_TOKEN` と `LINE_CHANNEL_SECRET` の有無のみを確認する（値の内容は確認しない）。
4. ユーザー登録数はリリース前のゼロを正常とする。
5. 朝通知の実行確認は `notifications.db` の `notification_log` テーブルを参照する。テーブルが存在しない場合は「不明」扱いとする。
6. Webhook URL は環境変数から推定して表示する（LINE Developers Console での手動確認を促す）。

## チェック項目

| チェック | 合格基準 | 失敗時の意味 |
|---|---|---|
| SDK インストール | `linebot.v3` がインポートできる | `requirements.txt` が未インストールまたは未デプロイ |
| ACCESS_TOKEN | 環境変数が存在する | Railway Variables に未設定 |
| CHANNEL_SECRET | 環境変数が存在する | Railway Variables に未設定 |
| ユーザー登録 | DB エラーなし（0人は正常） | `notifications.db` が破損または未作成 |
| 本日の朝通知 | `notification_log` に本日レコードあり | Cron が動いていない、または `send_morning_notifications()` がエラー |
| 通知エラー率 | 直近7日のエラー率 0% | LINE API 呼び出し失敗（トークン期限切れ等） |

## ユーザー登録に関する注意

- リリース前はアクティブ0人が正常。
- リリース後にアクティブ0人が続く場合は、フォロー導線（QRコード、URL共有等）を見直す。
- 全員アンフォロー状態（`total > 0` かつ `active == 0`）は警告とする。

## 通知ログの有無について

`notification_log` テーブルは `line_bot_service.LineBotService()` の初期化時または `send_morning_notifications()` の初回実行時に作成される。

テーブルがない場合は、次のいずれかを実行すること。

```python
from line_bot_service import get_service
get_service()  # _init_db() が自動的に呼ばれる
```

## Webhook URL の確認手順

1. LINE Developers Console にログインする。
2. 該当チャンネル → Messaging API → Webhook URL を開く。
3. `line_audit.py` が表示する推定 URL が設定されていることを確認する。
4. 「検証」ボタンで接続テストを実施する。

## 出力

- コンソールへのチェック結果（✅ / ❌ / ⚠️ 形式）
- JSON レポート（環境変数 `LINE_AUDIT_OUTPUT` にパスを指定した場合）
- 総合結果（ALL OK または ISSUES FOUND）

## 失敗時のアクション

| 失敗項目 | 推奨アクション |
|---|---|
| SDK インストール失敗 | `pip install line-bot-sdk>=3.5.0` を実行し再デプロイ |
| 環境変数未設定 | Railway Variables に `LINE_CHANNEL_ACCESS_TOKEN` と `LINE_CHANNEL_SECRET` を追加 |
| 本日の朝通知未実行 | GitHub Actions `line-morning-notification.yml` のログを確認する |
| 通知エラーあり | LINE Developers Console でチャンネルのアクセストークンを再発行する |

## 実行タイミング

毎日 07:25 JST（朝通知送信 06:30 の後、送信結果が揃ってから確認）。
