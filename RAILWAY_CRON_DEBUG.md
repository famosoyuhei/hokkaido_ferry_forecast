# Railway Cron デバッグガイド

**作成日**: 2026-01-09
**問題**: railway.json の cron が実行されていない
**参考**: ChatGPT分析 - Railway Cron troubleshooting

---

## 現状

### ✅ 確認済み
- `railway.json` に9個のCronジョブを定義
- 各スクリプトは手動実行で正常動作
- GitHub Actionsで代替システム構築済み

### ❌ 問題
- 最終更新: 2025-12-31（9日間更新なし）
- Railway CronログをまだRailway Dashboardで確認していない

---

## Railway Cron ログ確認手順

### 1. Railway Dashboardにアクセス

```
https://railway.app/project/c93898e1-5fe6-4fd7-b81d-33cb31b8addf
```

または:
```bash
railway open
```

### 2. サービスを選択

- プロジェクト画面で `hokkaido-ferry-forecast` サービスをクリック

### 3. Cron タブを探す

Railway Dashboardの構成（バージョンにより異なる）:

**パターン1**: サービス詳細画面に "Cron" タブがある
- クリックして各Cronジョブの実行履歴を確認

**パターン2**: "Deployments" タブの中にCronログがある
- Deploymentsを開く → Cron Jobs セクションを探す

**パターン3**: Cronタブがない
- Railway CLIでログを確認:
  ```bash
  railway logs --deployment <deployment-id>
  ```

### 4. 確認すべきポイント

#### ケース1: Cronジョブが表示されている
✅ `railway.json` の cron セクションが認識されている

**チェック項目**:
- [ ] 各ジョブの最終実行日時
- [ ] 実行ステータス（Success / Failed / Running）
- [ ] エラーログ

#### ケース2: Cronジョブが表示されない
❌ Railway が `railway.json` の cron を読み込んでいない

**原因の可能性**:
1. Railway が cron 機能を新しい UI で廃止した
2. プロジェクトが cron をサポートしていない
3. `railway.json` の構文エラー

---

## 環境変数の確認

Cronジョブが実行されているが失敗している場合、環境変数を確認：

### デバッグ用スクリプト作成

**ファイル**: `debug_cron_env.py`

```python
#!/usr/bin/env python3
import os
import sys
from datetime import datetime

print("=" * 80)
print(f"CRON DEBUG - {datetime.now()}")
print("=" * 80)

# 環境変数を確認
print("\n[ENV VARIABLES]")
print(f"RAILWAY_VOLUME_MOUNT_PATH: {os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')}")
print(f"RAILWAY_VOLUME_MOUNT: {os.environ.get('RAILWAY_VOLUME_MOUNT')}")
print(f"PORT: {os.environ.get('PORT')}")
print(f"PWD: {os.getcwd()}")

# ファイルシステムを確認
print("\n[FILESYSTEM]")
data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
print(f"Data directory: {data_dir}")
print(f"Exists: {os.path.exists(data_dir)}")

if os.path.exists(data_dir):
    print(f"Contents: {os.listdir(data_dir)}")

# データベースを確認
import sqlite3
db_path = os.path.join(data_dir, "ferry_weather_forecast.db")
print(f"\n[DATABASE]")
print(f"DB path: {db_path}")
print(f"DB exists: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM weather_forecast")
    count = cursor.fetchone()[0]
    print(f"Weather forecast records: {count}")
    conn.close()

print("\n" + "=" * 80)
print("[SUCCESS] Debug completed")
sys.exit(0)
```

### railway.json に追加

```json
"debug_env": {
  "command": "python debug_cron_env.py",
  "schedule": "*/5 * * * *"
}
```

5分ごとに実行して、Railway Dashboardでログをチェック。

---

## よくある失敗パターンと対策

### パターン1: 環境変数が渡っていない

**症状**:
```
sqlite3.OperationalError: unable to open database file
```

**原因**: `RAILWAY_VOLUME_MOUNT_PATH` がCron環境で設定されていない

**対策**:
```python
# 各スクリプトの先頭で確認
data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
if not data_dir:
    print("[ERROR] RAILWAY_VOLUME_MOUNT_PATH not set")
    sys.exit(1)
```

### パターン2: Volumeがマウントされていない

**症状**: ファイルが見つからない

**原因**: Cron実行時にVolumeがマウントされない

**対策**: Railway設定で Volume を Service に確実にマウント

### パターン3: タイムアウト

**症状**: ジョブが途中で停止

**対策**: スクリプト実行時間を短縮、または分割実行

### パターン4: 依存関係のインストール失敗

**症状**: `ModuleNotFoundError`

**対策**:
```json
"command": "pip install -r requirements.txt && python script.py"
```

---

## Railway Cron が使えない場合の代替案

### ✅ 既に実装済み: GitHub Actions

現在のプロジェクトでは、以下を実装済み：

1. **GitHub Actions ワークフロー**（3個）
   - `data-collection.yml` - 1日4回
   - `ferry-collection.yml` - 1日1回
   - `accuracy-tracking.yml` - 1日1回

2. **Railway 管理エンドポイント**（3個）
   - `/admin/collect-data`
   - `/admin/collect-ferry-data`
   - `/admin/run-accuracy-tracking`

**結論**: Railway Cron が動かなくても、GitHub Actions で完全に代替可能。

---

## 次のアクション

### 優先度1: Railway Dashboard確認（今すぐ）
1. Railway Dashboard → Cron タブ
2. ログを確認
3. 実行されているか/エラーがあるか確認

### 優先度2: デバッグスクリプト追加（必要なら）
1. `debug_cron_env.py` を作成
2. `railway.json` に追加
3. プッシュ＆デプロイ
4. 5分後にログ確認

### 優先度3: GitHub Actions 依存に切り替え（推奨）
- Railway Cron が動かない場合は完全に無視
- GitHub Actions のみに依存
- `railway.json` の `cron` セクションはドキュメント目的で残す

---

## Railway Dashboard 確認結果（2026-01-09）

### 発見事項

✅ Settings タブに **"Cron Schedule"** セクションを発見

❌ **Cronスケジュールが1つも設定されていない**

### 重要な仕様

**`railway.json` の `cron` セクションは自動適用されない**

Railway では:
1. `railway.json` に cron を定義しても
2. Dashboard で手動設定しない限り実行されない
3. 9個のジョブを手動設定するのは非現実的

### ChatGPT 分析の的中

> Railway は OS レベルの cron は基本的に動きません
> Railway の Cron は「別プロセス」として実行される

→ `railway.json` は設定ファイルではなく、**ドキュメント**扱い

---

## まとめ

| 項目 | ステータス |
|------|-----------|
| Railway Cron 設定 | ❌ 未設定（Dashboard で手動設定が必要） |
| Railway Cron 動作確認 | ✅ **確認完了 - 動作していない** |
| GitHub Actions 代替 | ✅ 完了・稼働中 |
| 推奨アプローチ | **GitHub Actions のみ** |

**結論**: Railway Cron は Dashboard で手動設定が必要。GitHub Actions で完全に代替可能。

---

**最終更新**: 2026-01-09
**ステータス**: GitHub Actions で運用中（Railway Cron 不使用）
