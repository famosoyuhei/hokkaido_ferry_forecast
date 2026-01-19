# VS Code GitHub Actions 拡張機能ガイド

**作成日**: 2026-01-09
**対象**: VS Code GitHub Actions Extension

---

## 拡張機能の機能

VS Code の GitHub Actions 拡張機能を使うと、エディタ内で以下が可能になります：

### 1. ワークフローの表示と管理

**サイドバーの GitHub Actions アイコン**をクリック:
- リポジトリのすべてのワークフローが表示される
- 各ワークフローの最新の実行状態が確認できる
- 実行履歴をツリー表示で確認

### 2. ワークフローの手動実行

右クリックメニューから直接実行：
1. サイドバーでワークフロー名を右クリック
2. **"Trigger workflow"** を選択
3. ブランチを選択（main）
4. 実行開始

### 3. 実行ログのリアルタイム確認

ワークフロー実行中：
1. 実行中のワークフローをクリック
2. ジョブ名をクリック
3. 各ステップのログがVS Code内で表示される

### 4. ワークフローファイルの編集支援

`.github/workflows/*.yml` ファイル編集時：
- **構文ハイライト**
- **自動補完** (actions, inputs, etc.)
- **構文エラー検出**
- **YAML スキーマ検証**

---

## 現在のワークフロー一覧

### 1. Scheduled Data Collection
**ファイル**: `.github/workflows/data-collection.yml`
**スケジュール**: 1日4回（05:00, 11:00, 17:00, 23:00 JST）
**機能**: 気象予報データ収集

**手動実行方法**:
1. VS Code サイドバー → GitHub Actions
2. "Scheduled Data Collection" を右クリック
3. "Trigger workflow" → "main" ブランチ選択
4. 実行確認

### 2. Ferry Operations Collection
**ファイル**: `.github/workflows/ferry-collection.yml`
**スケジュール**: 1日1回（06:00 JST）
**機能**: 実運航データ収集

### 3. Accuracy Tracking
**ファイル**: `.github/workflows/accuracy-tracking.yml`
**スケジュール**: 1日1回（07:00 JST）
**機能**: 予測精度追跡とML最適化

---

## よく使う操作

### ワークフローを今すぐ実行したい

**方法1: VS Code サイドバーから**
1. GitHub Actions アイコンをクリック
2. ワークフロー名を右クリック → "Trigger workflow"

**方法2: コマンドパレットから**
1. `Ctrl+Shift+P` (Windows) / `Cmd+Shift+P` (Mac)
2. "GitHub Actions: Trigger workflow" を検索
3. ワークフローとブランチを選択

### 実行結果を確認したい

**リアルタイムで確認**:
1. サイドバーの GitHub Actions
2. 実行中のワークフローを展開
3. ジョブをクリック → ログ表示

**成功/失敗を確認**:
- ✓ 緑チェック = 成功
- ✗ 赤バツ = 失敗
- ● 黄色点 = 実行中

### ワークフローファイルを編集したい

1. エクスプローラーで `.github/workflows/` を開く
2. 編集したい `.yml` ファイルをクリック
3. 編集後、保存 → コミット → プッシュ

**注意**: プッシュ後、次回のスケジュール実行時に新しい設定が適用される

---

## トラブルシューティング

### ワークフローが表示されない

**原因**: GitHub認証が必要
**解決策**:
1. VS Code 下部のアカウントアイコンをクリック
2. "Sign in with GitHub" を選択
3. ブラウザで認証を完了

### ワークフローの実行が失敗する

**確認手順**:
1. サイドバーで失敗したワークフローをクリック
2. 赤い ✗ マークのジョブをクリック
3. エラーログを確認

**よくあるエラー**:

#### エラー1: HTTP 500
```
❌ Weather forecast collection failed
HTTP Status: 500
```

**原因**: Railway サーバーエラー
**解決策**:
```bash
# Railway ログを確認
railway logs -s hokkaido-ferry-forecast

# または Railway ダッシュボードで確認
```

#### エラー2: HTTP 404
```
❌ Ferry data collection failed
HTTP Status: 404
```

**原因**: エンドポイントが存在しない、またはデプロイ中
**解決策**: Railway デプロイ完了を待つ

#### エラー3: Timeout
```
Error: The operation was canceled.
```

**原因**: スクリプト実行に時間がかかりすぎた
**解決策**: `forecast_dashboard.py` のタイムアウト値を増やす

---

## 便利なショートカット

### VS Code GitHub Actions 拡張機能

| 操作 | ショートカット |
|------|---------------|
| コマンドパレット | `Ctrl+Shift+P` (Win) / `Cmd+Shift+P` (Mac) |
| ファイル検索 | `Ctrl+P` (Win) / `Cmd+P` (Mac) |
| ワークフロー実行 | サイドバーから右クリック |
| ログ表示 | ジョブ名をクリック |

### よく使うコマンド

```bash
# 現在のデータ状況を確認
curl -s https://web-production-a628.up.railway.app/api/stats | python -m json.tool

# 気象予報を手動収集
curl https://web-production-a628.up.railway.app/admin/collect-data

# 実運航データを手動収集
curl https://web-production-a628.up.railway.app/admin/collect-ferry-data

# 精度追跡を手動実行
curl https://web-production-a628.up.railway.app/admin/run-accuracy-tracking
```

---

## ワークフローのカスタマイズ

### 実行頻度を変更する

例: 気象予報収集を6時間ごとに変更

**編集ファイル**: `.github/workflows/data-collection.yml`

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # 6時間ごと
```

**Cron記法**:
```
分 時 日 月 曜日 (すべてUTC)

例:
0 */6 * * *   = 6時間ごと
0 0 * * *     = 毎日 00:00 UTC (09:00 JST)
*/30 * * * *  = 30分ごと
0 0 * * 0     = 毎週日曜 00:00 UTC
```

### タイムアウト時間を変更する

例: 気象予報収集のタイムアウトを5分→10分に変更

**編集ファイル**: `forecast_dashboard.py`

```python
result = subprocess.run(
    ['python', 'weather_forecast_collector.py'],
    capture_output=True,
    text=True,
    timeout=600  # 300→600に変更 (10分)
)
```

### 通知を追加する

失敗時にSlackに通知したい場合：

```yaml
# .github/workflows/data-collection.yml の最後に追加
- name: Notify Slack on failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

**注意**: `secrets.SLACK_WEBHOOK` はリポジトリの Settings → Secrets で設定

---

## モニタリングのベストプラクティス

### 毎日チェックすべきこと

1. **VS Code GitHub Actions サイドバー**
   - 直近3つのワークフロー実行が成功しているか確認

2. **データ更新確認**
   ```bash
   curl -s https://web-production-a628.up.railway.app/api/stats | grep last_updated
   ```
   - `last_updated` が今日の日付か確認

3. **失敗アラートの確認**
   - GitHub からのメール通知をチェック
   - 失敗があればログを確認

### 週次チェック

1. **データ蓄積量の確認**
   ```bash
   curl -s https://web-production-a628.up.railway.app/api/stats
   ```
   - `weather_records` が増えているか確認

2. **精度追跡の確認**
   - 30日後: ML threshold optimization が動作しているか確認

---

## まとめ

✅ **VS Code 内でワークフローを完全管理**
- サイドバーから実行状態を確認
- 右クリックで手動実行
- ログをリアルタイム表示

✅ **効率的な開発フロー**
- ワークフローファイルの編集支援
- 構文エラーを即座に検出
- コミット→プッシュで即座に反映

✅ **確実なモニタリング**
- 失敗を即座に検知
- ログから原因を特定
- 手動実行で即座にリカバリ

---

**最終更新**: 2026-01-09
**VS Code 拡張機能**: GitHub Actions v0.26.2+
