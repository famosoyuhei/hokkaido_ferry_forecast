# デプロイ失敗時 即時対応ランブック

**更新日**: 2026-05-03  
**対象**: Railway デプロイ失敗 / アプリ無応答  
**本番URL**: https://web-production-a628.up.railway.app/

---

## ステップ1：状態確認（1分）

```bash
# アプリが応答するか確認
curl -s -o /dev/null -w "%{http_code}" https://web-production-a628.up.railway.app/api/stats

# 200 → 正常稼働（デプロイは成功している）
# 502/503/000 → アプリダウン → ステップ2へ
```

---

## ステップ2：Railway ログを確認（3分）

Railway管理画面でログを確認する：

1. https://railway.app にログイン
2. プロジェクト `hokkaido-ferry-forecast` を開く
3. 左メニュー → **Deployments** → 最新デプロイをクリック
4. **View Logs** をクリック

### よく出るエラーと対処

| エラーメッセージ | 原因 | 対処 |
|----------------|------|------|
| `ModuleNotFoundError: No module named 'xxx'` | requirements.txt に未記載 | requirements.txt に追加してpush |
| `sqlite3.OperationalError: unable to open database file` | Volume未マウント or /data に権限なし | ステップ3-A |
| `UnicodeDecodeError` | ファイルのエンコーディング問題 | ファイル先頭に `# -*- coding: utf-8 -*-` があるか確認 |
| `SyntaxError` | Pythonコードのバグ | ローカルで `python -m py_compile ファイル名.py` で確認 |
| `gunicorn: error: unrecognized arguments` | gunicorn起動コマンドのオプションミス | railway.jsonの`startCommand`を確認 |
| `Address already in use` | 前のプロセスが残っている | Railway側の問題 → ステップ3-B |

---

## ステップ3-A：Volume問題の対処

**症状**: DBファイルが見つからない、/data に書き込めない

```bash
# デバッグエンドポイントで確認
curl https://web-production-a628.up.railway.app/admin/env

# 期待する結果:
# "data_dir_exists": true
# "data_dir_writable": true
# "data_dir_contents": ["ferry_weather_forecast.db", ...]
```

**修正手順**:
1. Railway管理画面 → サービス `hokkaido-ferry-forecast` → **Variables**
2. `RAILWAY_VOLUME_MOUNT_PATH` = `/data` が設定されているか確認
3. なければ追加してデプロイ
4. Volume自体がなければ: **New** → **Volume** → Mount Path `/data`

---

## ステップ3-B：ロールバック（原因不明 or 緊急）

**前のコミットに戻す手順**:

```bash
# 1. 直前の正常なコミットを探す
git log --oneline -10

# 2. ロールバック（例：9fbbdb7 が正常な最後のコミット）
git revert HEAD --no-edit
git push origin main

# または特定のコミット以降をすべて元に戻す場合:
# git revert HEAD~3..HEAD --no-edit  # 直近3コミットを戻す
# git push origin main
```

Railwayはpushを検知して自動再デプロイします。

---

## ステップ4：デプロイ確認（2分）

```bash
# 30秒おきに3回試行
for i in 1 2 3; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 https://web-production-a628.up.railway.app/api/stats)
  echo "試行$i: HTTP $code"
  sleep 30
done
```

**注意**: Railway のコールドスタートには通常1〜3分かかります。502が出ても30〜60秒待ってから再確認してください。

---

## ステップ5：データ整合性確認

デプロイ後、データが正常か確認：

```bash
# 予報データが存在するか
curl -s https://web-production-a628.up.railway.app/api/stats | python -m json.tool

# 今日の予報が取れるか
curl -s https://web-production-a628.up.railway.app/api/today | python -m json.tool | head -20
```

**正常な`/api/stats`の戻り値**:
```json
{
  "forecast_days": 100以上,
  "high_risk_days": 数値,
  "last_updated": "2026-XX-XXTXX:XX:XX...",
  "weather_records": 1000以上
}
```

---

## ステップ6：GitHub Actionsのデータ収集が止まっていないか確認

デプロイ失敗が長引いた場合、Cronジョブがエラーになっている可能性があります。

1. GitHub → Actions タブ を開く
2. 以下のワークフローのステータスを確認:
   - `Scheduled Data Collection`（予報収集）
   - `Ferry Status Collection`（運航データ収集）
   - `Actual Weather Collection`（実測気象収集）
3. 失敗していたら **Re-run all jobs** で手動再実行

---

## 予防的チェックリスト（push前）

```bash
# ローカルで構文チェック
python -m py_compile forecast_dashboard.py
python -m py_compile actual_weather_collector.py
python -m py_compile unified_accuracy_tracker.py
python -m py_compile improved_ferry_collector.py
python -m py_compile weather_forecast_collector.py

# ローカルで起動確認（オプション）
python forecast_dashboard.py &
curl http://localhost:5000/api/stats
kill %1
```

---

## 自動モニタリング

`health-check.yml`（GitHub Actions）が **30分ごと** に自動でアプリの死活確認を行います。

- 失敗した場合 → GitHub Issue が自動作成されます
- Issue タイトル: `[ALERT] Railway app is down - YYYY-MM-DD HH:MM`
- 通知は登録メールアドレス（ichryo1@gmail.com）に届きます

手動でヘルスチェックを実行したい場合：  
GitHub → Actions → **Railway Health Check** → **Run workflow**
