# 「no jobs were run」メール 即時対応ランブック

**メール差出人**: GitHub (famosoyuhei リポジトリの通知)  
**受信先**: ichryo1@gmail.com  
**意味**: GitHubがスケジュールワークフローを自動無効化した  
**影響**: フェリー運航データ・気象データの自動収集がすべて停止している

---

## なぜこのメールが来るのか

GitHub は **リポジトリへのコミット・アクティビティが60日間ない場合**、スケジュール実行（cron）ワークフローを自動的に無効化します。

無効化されると：
- 気象予報収集（1日4回）→ 停止
- フェリー運航データ収集（毎朝6時）→ 停止
- 実測気象収集（毎朝7時半）→ 停止
- ヘルスチェック（30分ごと）→ 停止

---

## ステップ1：停止しているワークフローを再有効化（3分）

1. https://github.com/famosoyuhei/hokkaido_ferry_forecast/actions を開く
2. 左側のワークフロー一覧を確認
3. グレーアウトまたは「disabled」となっているワークフローをクリック
4. 黄色いバナー **「This workflow is disabled」** が出たら **「Enable workflow」** ボタンをクリック
5. 以下の全ワークフローに対して繰り返す：
   - `Scheduled Data Collection`
   - `Ferry Status Collection`
   - `Actual Weather Collection`
   - `Railway Health Check`

---

## ステップ2：手動で全ワークフローを即時実行（5分）

再有効化直後はデータが溜まっていないため、手動で実行して補完します。

各ワークフローを開き **「Run workflow」→「Run workflow」** をクリック：

| ワークフロー | 用途 |
|------------|------|
| `Scheduled Data Collection` | 気象予報データ収集 |
| `Ferry Status Collection` | 実際の運航状況収集 |
| `Actual Weather Collection` | 実測気象＋精度照合 |

実行後、数分待って緑チェックになれば復旧完了。

---

## ステップ3：データ復旧を確認

```bash
curl -s "https://web-production-a628.up.railway.app/api/stats" | python -m json.tool
```

`last_updated` が今日の日時になっていれば正常。

---

## ステップ4：停止期間のデータを補完（必要な場合）

停止期間が長かった場合（1週間以上）は、実測気象データのバックフィルが必要です。

```bash
# Railway上で実行（ローカル環境がある場合）
railway run python backfill_actual_weather.py 2026-XX-XX  # 停止開始日
```

または Railway管理画面 → エンドポイントを直接叩く：
```
https://web-production-a628.up.railway.app/admin/run-backfill?start=YYYY-MM-DD
```

---

## 自動予防策（keep-alive）

このリポジトリには **`keep-alive.yml`** ワークフローが設定されており、**毎週月曜 09:00 JST** に自動でタイムスタンプを更新します。

これにより60日間のアクティビティゼロ状態を防ぎ、「no jobs were run」メールを原則受信しないようにしています。

`keep-alive.yml` 自体も止まっていた場合は上記の手順で再有効化してください。

---

## 再発防止チェック

- [ ] `keep-alive.yml` が有効になっているか確認
- [ ] GitHub Actions → 全ワークフローが緑またはアクティブ状態
- [ ] `/api/stats` の `last_updated` が今日以内

---

## 関連ドキュメント

- [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) — Railway デプロイ失敗時の対応
- [ACCURACY_SYSTEM_DESIGN.md](ACCURACY_SYSTEM_DESIGN.md) — データ収集の役割分担
