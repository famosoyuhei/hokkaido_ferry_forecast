# データ蓄積失敗の原因と解決策

**作成日**: 2026-01-08
**対象期間**: プロジェクト開始〜2026-01-08

---

## 概要

過去にデータ蓄積が何度も失敗していた根本原因を調査・特定し、すべて解決しました。

---

## 問題1: GitHubにDBファイルがコミットされていた（最も重大）

### 症状
- データ収集は成功するが、再デプロイ後に古いデータに戻る
- Volumeに保存しても消える
- `/admin/collect-data`で成功するが、`/api/stats`が古いまま

### 根本原因
`ferry_weather_forecast.db`がGitリポジトリに含まれていた。

デプロイ時の処理順序：
1. GitHubから全ファイルをクローン（**古いDBを含む**）
2. カレントディレクトリに展開
3. Volumeを`/data`にマウント
4. アプリ起動時、`/data`に古いDBがコピーされる or 上書きされる

結果：**Volumeの新しいデータが古いDBで上書きされる**

### 解決方法（2026-01-01実施済み）
```bash
git rm --cached ferry_weather_forecast.db
git commit -m "Remove database file from Git (use Railway Volume instead)"
git push
```

### 予防策
- 新しいDBファイルを作成する際は、`.gitignore`に含まれているか確認
- `git status`でステージングされていないか確認
- Volumeを使う場合は、DBファイルをGitに含めない

---

## 問題2: Railway Volume設定の不備

### 症状
- データベースが再デプロイで消える
- `sqlite3.OperationalError: unable to open database file`

### 原因
- Volumeが設定されていない
- `/data`ディレクトリへのマウントが失敗

### 解決方法
1. Railway管理画面でVolume作成
   - Volume名: `ferry-data`
   - Mount to service: `hokkaido-ferry-forecast`
   - Mount path: `/data`

2. 環境変数設定
   ```bash
   RAILWAY_VOLUME_MOUNT_PATH=/data
   ```

### 確認方法
```bash
# Webブラウザで確認
https://web-production-a628.up.railway.app/admin/env

# 確認項目
- data_dir_exists: true
- data_dir_writable: true
- data_dir_contents: ["ferry_weather_forecast.db", ...]
```

---

## 問題3: Railway環境変数のパス変換問題（Git Bash）

### 症状
`/data`と設定したのに`C:/Program Files/Git/data`になる

### 原因
Git Bashが自動的にパスをWindows形式に変換

### 解決方法
```bash
# ダブルスラッシュを使う
railway variables --set "RAILWAY_VOLUME_MOUNT_PATH=//data" -s hokkaido-ferry-forecast

# または Railway管理画面で直接設定（推奨）
```

---

## 問題4: Cronジョブが実行されない

### 症状
- `railway.json`にCron設定があるのに実行されない
- データが自動更新されない

### 原因
RailwayのCron機能が管理画面に表示されない場合がある

### 解決方法

**手動実行（Railway CLI）**:
```bash
railway run --service hokkaido-ferry-forecast python weather_forecast_collector.py
```

**Webエンドポイント経由（推奨）**:
```bash
# データ収集
curl https://web-production-a628.up.railway.app/admin/collect-data

# テーブル初期化
curl https://web-production-a628.up.railway.app/admin/init-accuracy-tables
```

---

## 問題5: Accuracy Trackingテーブルが作成されない（2026-01-08発見・解決）

### 症状
- `sailing_forecast`テーブルにはデータが蓄積される
- accuracy tracking用のテーブルが存在しない
- 4つのテーブルがすべて missing:
  - `weather_accuracy`
  - `operation_accuracy`
  - `daily_accuracy_summary`
  - `threshold_adjustment_history`

### 根本原因
新しいスクリプト（Phase 1で作成）が**一度も実行されていなかった**。

テーブル初期化メソッドは存在するが、`main()`関数で呼び出されていなかった：
- ✗ `operation_accuracy_calculator.py` - `init_tables()`呼び出しなし
- ✗ `dual_accuracy_tracker.py` - `init_accuracy_tables()`呼び出しなし
- ✓ `auto_threshold_adjuster.py` - `init_threshold_history_table()`呼び出しあり

### 解決方法（2026-01-08実施済み）

**コード修正**:
```python
# operation_accuracy_calculator.py
if __name__ == "__main__":
    calculator = OperationAccuracyCalculator()

    # 追加
    print("\n[INFO] Initializing accuracy tracking tables...")
    calculator.init_tables()

    # 既存コード
    results = calculator.calculate_daily_accuracy(yesterday)
```

**同様に**:
- `dual_accuracy_tracker.py` → `init_accuracy_tables()`追加
- `auto_threshold_adjuster.py` → stdout encoding問題も修正

**Railway本番環境での実行**:
```bash
curl https://web-production-a628.up.railway.app/admin/init-accuracy-tables
```

**結果**:
```json
{
  "status": "success",
  "tables_created": [
    "daily_accuracy_summary",
    "operation_accuracy",
    "threshold_adjustment_history",
    "weather_accuracy"
  ]
}
```

---

## 問題6: `sailing_forecast`テーブルが存在しない

### 症状
`dual_accuracy_tracker.py`実行時にエラー:
```
sqlite3.OperationalError: no such table: sailing_forecast
```

### 原因
`sailing_forecast_system.py`が実行されていない

### 解決方法（2026-01-08実施済み）

`/admin/init-accuracy-tables`エンドポイントに追加:
```python
scripts = [
    'sailing_forecast_system.py',  # 追加（最初に実行）
    'operation_accuracy_calculator.py',
    'dual_accuracy_tracker.py',
    'auto_threshold_adjuster.py'
]
```

---

## 完全な初期化手順（本番環境）

### 1. 環境確認
```bash
curl https://web-production-a628.up.railway.app/admin/env
```

確認項目：
- ✓ `data_dir_exists: true`
- ✓ `data_dir_writable: true`
- ✓ `RAILWAY_VOLUME_MOUNT_PATH: "/data"`

### 2. データ収集
```bash
curl https://web-production-a628.up.railway.app/admin/collect-data
```

### 3. テーブル初期化
```bash
curl https://web-production-a628.up.railway.app/admin/init-accuracy-tables
```

### 4. 確認
```bash
curl https://web-production-a628.up.railway.app/api/stats
```

---

## 現在の状態（2026-01-08時点）

### ✓ 解決済み
1. GitHubからDBファイルを削除
2. Railway Volumeを正しく設定
3. 環境変数`RAILWAY_VOLUME_MOUNT_PATH=/data`設定
4. Accuracy trackingテーブルの初期化処理を追加
5. Webエンドポイント経由でテーブル初期化可能

### 📊 稼働中のテーブル
- `sailing_forecast` (70 records)
- `weather_accuracy` (0 records - AMeDASデータ待ち)
- `operation_accuracy` (0 records - 実運航データ待ち)
- `daily_accuracy_summary` (1 record)
- `threshold_adjustment_history` (0 records)

### 🔄 次のステップ
1. Cronジョブの自動実行を確認（または手動で定期実行）
2. 実運航データ収集（`improved_ferry_collector.py`）
3. AMeDASデータ収集（404エラーが解消されるまで待機）
4. 30日間データ蓄積後、ML threshold optimizationを評価

---

## まとめ

**過去のデータ蓄積失敗の主な原因**:
1. **GitHubにDBファイルがコミットされていた**（最も重大）
2. **Railway Volumeの設定不備**
3. **テーブル初期化処理の未実行**

**すべて解決済み**（2026-01-08現在）

今後は、Webエンドポイント経由でテーブル初期化とデータ収集が可能になり、
Railway環境での直接スクリプト実行の問題を回避できます。

---

**最終更新**: 2026-01-08
**ステータス**: ✅ すべての既知の問題を解決
