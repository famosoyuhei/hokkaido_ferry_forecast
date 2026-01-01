# 🚨 URGENT: セキュリティ問題 - 即座に対応が必要

**発見日**: 2025-12-31
**重大度**: 🔴 HIGH

---

## 問題

### 1. APIキーがGitHub公開リポジトリに漏洩

**場所**: `railway.json` 41行目

```json
"variables": {
  "FLIGHTAWARE_API_KEY": "QEgHk9GkswfERfjg2ujDosuP2Ss60sXs"
}
```

**リスク**:
- ✅ リポジトリがPUBLICで全世界に公開されている
- ❌ FlightAware APIキーが平文で公開
- ❌ 第三者がこのAPIキーを使用可能
- ❌ APIの不正使用で課金される可能性

**確認URL**:
https://github.com/famosoyuhei/hokkaido_ferry_forecast/blob/main/railway.json

---

## 🔧 即座に実行すべきアクション

### ステップ1: FlightAware APIキーを無効化（最優先）

1. **FlightAwareにログイン**
   ```
   https://flightaware.com/commercial/aeroapi/
   ```

2. **APIキー管理画面**
   - 既存のAPIキー `QEgHk9GkswfERfjg2ujDosuP2Ss60sXs` を探す
   - **即座に削除または無効化**

3. **課金履歴を確認**
   - 不正使用がないかチェック
   - 不審なアクセスがあれば報告

---

### ステップ2: railway.jsonからAPIキーを削除

**ローカルで以下を実行**:

#### A. railway.jsonを編集

```json
{
  "build": {
    "commands": [
      "pip install -r requirements.txt"
    ]
  },
  "deploy": {
    "startCommand": "gunicorn --bind 0.0.0.0:$PORT forecast_dashboard:app"
  },
  "cron": {
    ... (cronジョブはそのまま)
  },
  "variables": {}  ← 空にする
}
```

#### B. Gitコミット

```bash
git add railway.json
git commit -m "Remove exposed API key from repository"
git push
```

⚠️ **注意**: これだけでは不十分！Gitの履歴にキーが残っています。

---

### ステップ3: Git履歴からキーを完全に削除（推奨）

**オプションA: BFG Repo-Cleaner使用**

```bash
# BFGをダウンロード
# https://rtyley.github.io/bfg-repo-cleaner/

# APIキーを含む文字列を削除
bfg --replace-text passwords.txt

# 履歴を書き換え
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 強制プッシュ（警告: 他の開発者がいる場合は注意）
git push --force
```

**オプションB: 新しいリポジトリを作成**（最も確実）

1. GitHubで新しいリポジトリ作成
2. ローカルで履歴をクリーンにしてpush
3. 古いリポジトリを削除

---

### ステップ4: Railway環境変数を設定（APIキーが必要な場合のみ）

**現在、FlightAware APIは使用していません**が、将来的に必要な場合:

1. **Railway管理画面**
   - Webサービス → Variables タブ

2. **環境変数を追加**
   ```
   FLIGHTAWARE_API_KEY = (新しいAPIキー)
   ```

3. **コードで参照**
   ```python
   import os
   api_key = os.environ.get('FLIGHTAWARE_API_KEY')
   ```

---

## 📋 その他のセキュリティチェック

### 確認事項

```bash
# 他の秘密情報が含まれていないかチェック
grep -r "password" .
grep -r "secret" .
grep -r "token" .
grep -r "api_key" .
```

### 見つかった場合

- `.gitignore`に追加
- 環境変数に移動
- Git履歴から削除

---

## ✅ 完了チェックリスト

```
□ FlightAware APIキーを無効化した
□ railway.jsonからAPIキーを削除した
□ 変更をGitにコミット・プッシュした
□ Git履歴からキーを削除した（推奨）
□ 他の秘密情報がないか確認した
□ .gitignoreが適切に設定されている
```

---

## 🔒 今後のベストプラクティス

### 秘密情報の管理方法

1. **環境変数を使用**
   - Railway: Variables タブで設定
   - ローカル: `.env`ファイル（`.gitignore`に追加）

2. **絶対にコミットしない**
   ```gitignore
   # .gitignore
   .env
   *.key
   *_secret.json
   railway_config.json  # もし秘密情報を含む場合
   ```

3. **サンプルファイルを提供**
   ```bash
   # .env.example (秘密情報なし)
   FLIGHTAWARE_API_KEY=your_api_key_here
   DATABASE_URL=postgresql://...
   ```

---

## 📞 サポート

もし不正使用が疑われる場合:
- FlightAwareサポート: https://flightaware.com/about/contact
- GitHubセキュリティ: https://github.com/security

---

**優先度**: 🔴 HIGH - 今すぐ対応してください
**推定所要時間**: 15分

**次のステップ**: この問題を解決したら、CLAUDE.md作成に進みます。
