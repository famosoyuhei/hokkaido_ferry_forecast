# GitHub Actions セットアップガイド

**作成日**: 2026-01-09
**最終更新**: 2026-01-20
**目的**: Railway Cronジョブの代替として、確実なデータ収集を実現

---

## 🆕 最新アップデート (2026-01-20)

**精度追跡の自動化を強化**:
- `unified-accuracy-tracking.yml` を追加
- Railway CLI を使って直接 Railway 上でスクリプト実行
- エンドポイント経由よりも確実で高速

詳細は後半の「精度追跡の自動化 (最新版)」セクションを参照。

---

## 背景

Railway の `railway.json` に定義した Cron ジョブが実行されず、データが 2025-12-31 以降更新されていなかった。

**原因**: Railwayの Cron 機能が自動的に動作しない

**解決策**: GitHub Actions + Railway 管理エンドポイント

---

## システム構成

### Railway 管理エンドポイント

| エンドポイント | 機能 | 実行スクリプト |
|---------------|------|--------------|
| `/admin/collect-data` | 気象予報収集 | `weather_forecast_collector.py` |
| `/admin/collect-ferry-data` | 実運航データ収集 | `improved_ferry_collector.py` |
| `/admin/run-accuracy-tracking` | 精度追跡 | `operation_accuracy_calculator.py`<br>`dual_accuracy_tracker.py`<br>`auto_threshold_adjuster.py` |
| `/admin/init-accuracy-tables` | テーブル初期化 | （各スクリプトのinit処理） |

### GitHub Actions ワークフロー

#### 1. `data-collection.yml` - 気象予報収集
**実行頻度**: 1日4回
- 05:00 JST (20:00 UTC)
- 11:00 JST (02:00 UTC)
- 17:00 JST (08:00 UTC)
- 23:00 JST (14:00 UTC)

**処理**:
```bash
curl https://web-production-a628.up.railway.app/admin/collect-data
```

#### 2. `ferry-collection.yml` - 実運航データ収集
**実行頻度**: 1日1回
- 06:00 JST (21:00 UTC)

**処理**:
```bash
curl https://web-production-a628.up.railway.app/admin/collect-ferry-data
```

#### 3. `accuracy-tracking.yml` - 精度追跡
**実行頻度**: 1日1回
- 07:00 JST (22:00 UTC)

**処理**:
```bash
curl https://web-production-a628.up.railway.app/admin/run-accuracy-tracking
```

---

## セットアップ手順

### 1. GitHub Actions の有効化

リポジトリで GitHub Actions が有効になっていることを確認：

1. GitHub リポジトリ → **Settings** タブ
2. 左メニュー → **Actions** → **General**
3. **Actions permissions**: "Allow all actions and reusable workflows" を選択
4. **Save** をクリック

### 2. ワークフローの確認

1. GitHub リポジトリ → **Actions** タブ
2. 以下の3つのワークフローが表示されていることを確認：
   - Scheduled Data Collection
   - Ferry Operations Collection
   - Accuracy Tracking

### 3. 手動テスト実行

各ワークフローを手動で実行してテスト：

1. **Actions** タブを開く
2. 左側のワークフロー一覧から "Scheduled Data Collection" を選択
3. **Run workflow** ボタンをクリック
4. ブランチを選択（main）
5. **Run workflow** をクリック

同様に他の2つのワークフローもテスト実行。

### 4. 実行結果の確認

1. ワークフロー実行後、緑のチェックマーク ✓ が表示されれば成功
2. 赤い × が表示された場合はログを確認：
   - 該当のワークフロー実行をクリック
   - ジョブ名（例: "Collect Weather Forecast Data"）をクリック
   - エラーログを確認

### 5. データ更新の確認

```bash
curl https://web-production-a628.up.railway.app/api/stats
```

`last_updated` が最新の日時になっていることを確認。

---

## トラブルシューティング

### ワークフローが実行されない

**症状**: スケジュール時刻になってもワークフローが実行されない

**原因**:
- リポジトリが非アクティブ（60日間以上プッシュなし）
- GitHub Actions が無効化されている

**解決策**:
1. 何か小さな変更をコミット＆プッシュしてリポジトリをアクティブ化
2. Settings → Actions で有効化されているか確認

### ワークフローは実行されるがエラーになる

**症状**: ワークフロー実行は成功するが、Railway エンドポイントが 500 エラー

**確認手順**:
1. Railway ログを確認:
   ```bash
   railway logs -s hokkaido-ferry-forecast
   ```

2. 手動でエンドポイントを実行:
   ```bash
   curl https://web-production-a628.up.railway.app/admin/collect-data
   ```

3. エラーメッセージから原因を特定

### データが更新されているか確認したい

**毎日の更新確認**:
```bash
# 統計情報を確認
curl -s https://web-production-a628.up.railway.app/api/stats | python -m json.tool

# last_updated が最新の日時か確認
```

**手動でデータ収集を実行**:
```bash
# 気象予報
curl https://web-production-a628.up.railway.app/admin/collect-data

# 実運航データ
curl https://web-production-a628.up.railway.app/admin/collect-ferry-data

# 精度追跡
curl https://web-production-a628.up.railway.app/admin/run-accuracy-tracking
```

---

## GitHub Actions の制限

### 無料プランの制限
- **実行時間**: 月2,000分まで（Public リポジトリは無制限）
- **ストレージ**: 500MB
- **同時実行**: 20ジョブまで

このプロジェクトの使用量：
- 1日あたり: 4回（気象）+ 1回（フェリー）+ 1回（精度）= 6回
- 1回あたり: 約30秒
- 月間合計: 6回 × 30日 × 30秒 = **90分/月**

→ **無料枠内で十分に運用可能**

---

## メンテナンス

### ワークフローのスケジュール変更

`.github/workflows/*.yml` ファイルの `cron` 設定を編集：

```yaml
on:
  schedule:
    - cron: '0 20 * * *'  # 時刻を変更
```

**Cron 形式**: `分 時 日 月 曜日` (UTC)

例：
- `0 20 * * *` = 毎日 20:00 UTC (05:00 JST)
- `*/30 * * * *` = 30分ごと
- `0 */6 * * *` = 6時間ごと

### ワークフローの無効化

不要なワークフローを無効化：

1. GitHub リポジトリ → **Actions** タブ
2. 左側のワークフロー一覧から該当ワークフローを選択
3. 右上の **...** メニュー → **Disable workflow**

### ワークフローの削除

`.github/workflows/` からファイルを削除してコミット。

---

## モニタリング

### GitHub Actions の実行履歴

1. **Actions** タブ → ワークフロー選択
2. 過去の実行履歴を確認
3. 失敗した実行をクリックしてログを確認

### メール通知設定

GitHub はデフォルトでワークフロー失敗時にメール通知を送信。

通知設定の変更：
1. GitHub プロフィール → **Settings**
2. **Notifications** → **Actions**
3. "Send notifications for failed workflows only" など設定

---

## まとめ

✅ **GitHub Actions で確実なデータ収集を実現**
- Railway Cron の問題を回避
- 無料で信頼性の高いスケジュール実行
- ワークフロー実行履歴で監視可能

✅ **Railway 管理エンドポイントで柔軟な実行**
- 手動でのデータ収集も可能
- 他のサービスからの呼び出しも可能

✅ **長期運用可能**
- GitHub Actions 無料枠内で運用
- メンテナンス性が高い

---

## 🚀 精度追跡の自動化（最新版 - 2026-01-20）

### 概要

**新しい方式**: Railway CLI を使って直接 Railway 上でスクリプト実行

**メリット**:
- ✅ エンドポイント経由より確実
- ✅ タイムアウトの心配なし
- ✅ Railway環境変数とVolumeに直接アクセス
- ✅ 実行ログが詳細

### ワークフロー: `unified-accuracy-tracking.yml`

**実行頻度**: 毎日 07:00 JST (22:00 UTC)

**処理**:
```bash
# Railway CLI で直接スクリプト実行
railway link hokkaido-ferry-forecast --environment production
railway run python unified_accuracy_tracker.py
```

### セットアップ手順（初回のみ）

#### ステップ1: Railway CLIトークンを取得

**方法A: Railway Webダッシュボード（推奨）**

1. Railway Dashboard にアクセス
   ```
   https://railway.app/
   ```

2. Account Settings → Tokens
   - 右上のアカウントアイコン → Account Settings
   - 左メニュー → Tokens

3. 新しいトークンを作成
   - 「Create New Token」ボタンをクリック
   - Token name: `GitHub Actions - Accuracy Tracking`
   - 「Create Token」をクリック

4. トークンをコピー
   - ⚠️ 表示されたトークンを今すぐコピー（再表示不可）
   - 形式: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

#### ステップ2: GitHub Secretsにトークンを設定

1. GitHubリポジトリを開く
   ```
   https://github.com/famosoyuhei/hokkaido_ferry_forecast
   ```

2. Settings タブ → Secrets and variables → Actions

3. New repository secret
   ```
   Name: RAILWAY_TOKEN
   Secret: [ステップ1でコピーしたトークン]
   ```

4. Add secret をクリック

5. ✅ 確認: `RAILWAY_TOKEN` が一覧に表示される

#### ステップ3: 変更をプッシュ

```bash
git push
```

これで自動化が有効になります！

### テスト実行

**手動トリガー**:
1. GitHub → Actions → Unified Accuracy Tracking
2. Run workflow ボタンをクリック
3. Branch: main を選択
4. Target date: 空欄（昨日のデータ）
5. Run workflow をクリック

**成功の確認**:
- ✅ 緑色のチェックマーク
- Summary に `Unified Accuracy Tracking Completed ✅`
- Artifacts に `accuracy-report-XXX` がダウンロード可能

### トラブルシューティング

**エラー: `RAILWAY_TOKEN not found`**
- GitHub Secrets にトークンを設定してください

**エラー: `railway link failed`**
- サービス名を確認: `hokkaido-ferry-forecast`
- ローカルで確認: `railway status`

**エラー: `No data found for date`**
- 正常な動作です（該当日のデータがまだない）
- 気象予報と実運航データが収集されているか確認

### 関連ファイル

- [unified_accuracy_tracker.py](unified_accuracy_tracker.py) - 精度追跡スクリプト
- [ACCURACY_IMPROVEMENT_STRATEGY.md](ACCURACY_IMPROVEMENT_STRATEGY.md) - 精度向上戦略
- [.github/workflows/unified-accuracy-tracking.yml](.github/workflows/unified-accuracy-tracking.yml) - ワークフロー定義

---

**最終更新**: 2026-01-20
**ステータス**: ✅ 稼働中（精度追跡も自動化完了）
