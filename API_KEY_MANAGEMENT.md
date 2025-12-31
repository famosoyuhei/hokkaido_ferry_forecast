# API Key Management Guide

## 🔒 セキュリティ方針

このプロジェクトはGitHub Publicリポジトリです。
**APIキーやシークレットは絶対にコミットしません。**

---

## 📋 APIキーの保管場所

### Production (Railway)

**場所**: Railway管理画面 → Service → Variables

**設定方法**:
1. Railway管理画面を開く
2. Webサービスをクリック
3. 「Variables」タブ
4. 環境変数を追加:
   ```
   FLIGHTAWARE_API_KEY = QEgHk9GkswfERfjg2ujDosuP2Ss60sXs
   ```

### Local Development

**場所**: `railway_local.json` (gitignoreに追加済み)

**ファイル内容**:
```json
{
  "variables": {
    "FLIGHTAWARE_API_KEY": "your_actual_api_key_here"
  }
}
```

**使い方**:
```bash
# ローカルでRailway CLIを使う場合
railway run python collect_flight_data.py
```

---

## 🔑 FlightAware API Key

**用途**: 利尻空港フライトデータ収集（将来の機能）

**現在の状態**:
- ✅ APIキーは有効
- ⚠️ 現在は使用していない（フライト機能は保留中）
- 📌 将来の利尻空港アプリ用に保持

**取得方法**:
1. https://flightaware.com/commercial/aeroapi/
2. アカウント作成
3. API Keyを発行
4. 無料プラン: 月1000リクエストまで

**セキュリティ**:
- ❌ `railway.json`には含めない（Public）
- ✅ `railway_local.json`に保存（gitignore）
- ✅ Railway環境変数で管理

---

## 📦 その他のシークレット

### 今後追加する可能性があるもの

**Discord Webhook** (通知機能):
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

**LINE Notify** (通知機能):
```
LINE_NOTIFY_TOKEN=your_line_token
```

**PostgreSQL** (将来のDB移行):
```
DATABASE_URL=postgresql://user:pass@host:port/db
```

### 管理方法

**全て同じルール**:
1. ❌ `railway.json`に書かない
2. ✅ `railway_local.json`に保存（Local）
3. ✅ Railway Variables に設定（Production）
4. ✅ `.env.example`にテンプレート追加

---

## 🚨 もし漏洩してしまったら

### 即座に実行すること

1. **APIキーを無効化**
   - FlightAware管理画面でキーを削除
   - 新しいキーを発行

2. **Gitから削除**
   ```bash
   # railway.jsonからキーを削除
   git add railway.json
   git commit -m "Remove exposed API key"
   git push
   ```

3. **Git履歴をクリーン化**（任意）
   - BFG Repo-Cleanerを使用
   - または新しいリポジトリを作成

4. **Railway環境変数を更新**
   - 新しいAPIキーに変更

---

## ✅ チェックリスト

コミット前に必ず確認:

```
□ railway.jsonに秘密情報が含まれていない
□ .envファイルをコミットしていない
□ railway_local.jsonをコミットしていない
□ ハードコードされたAPIキーがない
□ パスワードが含まれていない
```

---

## 📚 参考

- Railway環境変数: https://docs.railway.app/develop/variables
- FlightAware API: https://flightaware.com/commercial/aeroapi/
- GitHub Secrets: https://docs.github.com/en/actions/security-guides/encrypted-secrets

---

**最終更新**: 2025-12-31
**管理者**: 利尻島フェリー予報プロジェクト
