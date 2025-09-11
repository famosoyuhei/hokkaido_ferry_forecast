# FlightAware API キー取得ガイド

## 📋 **ステップバイステップ手順**

### Step 1: アカウント作成
1. **公式サイトにアクセス**
   - URL: https://www.flightaware.com/commercial/aeroapi/
   - 「Get Started」または「Sign Up」をクリック

2. **アカウント情報入力**
   ```
   必要情報:
   - 名前（First Name / Last Name）
   - メールアドレス
   - パスワード
   - 会社名（個人の場合は「Individual」でOK）
   - 用途（Research/Personal Project等）
   ```

3. **プラン選択**
   - **Personal Plan**を選択（これが月$5のプラン）
   - 「Start Free Trial」をクリック

### Step 2: 支払い情報設定
1. **クレジットカード情報入力**
   ```
   必要情報:
   - カード番号
   - 有効期限
   - セキュリティコード
   - 請求先住所
   ```

2. **プラン詳細確認**
   ```
   Personal Plan 特典:
   - 月額 $5 まで無料
   - 90日間の過去データアクセス
   - リアルタイムフライトトラッキング
   - API制限: 月額$5分のクエリ
   ```

### Step 3: APIキー生成
1. **アカウント作成完了後**
   - メール認証を完了
   - FlightAwareアカウントにログイン

2. **APIキー作成**
   - 「My FlightAware」→「AeroAPI」セクション
   - 「Create API Key」をクリック
   - キー名を入力（例: "Hokkaido Transport Prediction"）
   - APIキーが生成される（長い英数字の文字列）

3. **APIキーのコピー**
   ```
   生成例: fa1234567890abcdef1234567890abcdef12345678
   
   ⚠️ 重要: このキーは安全に保管してください
   - 他人と共有しない
   - コードにハードコーディングしない
   - 環境変数として設定推奨
   ```

## 💳 **料金体系詳細**

### Personal Plan 料金
```
基本: 無料（月$5まで）
超過: 従量課金

API呼び出し単価:
- Airport Info: $0.0025/回
- Flight Search: $0.005/回
- Flight Details: $0.01/回
- Historical Data: $0.01/回
```

### 月$5で何ができるか？
```
概算使用量:
- 空港情報取得: 2,000回
- フライト検索: 1,000回
- 詳細データ: 500回
- 過去データ: 500回

我々の使用想定:
- 1日あたり利尻空港データ取得: 数十回
- 月間総使用量: $3-4程度
- 月$5以内で十分運用可能
```

## 🔧 **APIキー設定方法**

### 方法1: 環境変数設定（推奨）
```bash
# Windows（コマンドプロンプト）
setx FLIGHTAWARE_API_KEY "your_api_key_here"

# Windows（PowerShell）
$env:FLIGHTAWARE_API_KEY="your_api_key_here"

# プログラムで読み込み
import os
api_key = os.getenv('FLIGHTAWARE_API_KEY')
```

### 方法2: 設定ファイル使用
```python
# config.json作成
{
  "flightaware_api_key": "your_api_key_here"
}

# Pythonで読み込み
import json
with open('config.json') as f:
    config = json.load(f)
api_key = config['flightaware_api_key']
```

### 方法3: 我々のセットアップスクリプト使用
```bash
# セットアップガイドスクリプト実行
python flightaware_setup_guide.py

# 対話的にAPIキーを入力・保存
# 自動でテスト実行
# 設定完了確認
```

## 🧪 **APIキー動作テスト**

取得後、必ず動作テストを実行：

```python
# テストスクリプト実行
python test_flightaware_api.py

# 期待される結果:
✅ API Key Valid - Connected to Rishiri Airport
✅ Successfully retrieved airport data
✅ Historical data access confirmed
```

## ⚠️ **注意事項**

### セキュリティ
- APIキーを直接コードに書かない
- GitHubなど公開リポジトリにコミットしない
- `.gitignore`で設定ファイルを除外

### 使用制限
- 月$5の上限に注意
- 過度なAPI呼び出しを避ける
- キャッシュ機能を活用

### 課金管理
- FlightAwareダッシュボードで使用量監視
- 月末近くに使用量確認
- アラート設定でオーバーチャージ防止

## 📞 **サポート・トラブルシューティング**

### よくある問題
1. **APIキーが認識されない**
   - キーのコピペミスを確認
   - 環境変数の設定確認
   - ブラウザキャッシュクリア

2. **課金が発生した**
   - 使用量ダッシュボード確認
   - APIクエリ効率化検討
   - 不要な呼び出し削減

3. **データが取得できない**
   - 利尻空港コード確認（RIS/RJER）
   - 日付形式確認
   - API制限確認

### サポート連絡先
- FlightAware Support: support@flightaware.com
- API Documentation: https://www.flightaware.com/commercial/aeroapi/documentation/

## 🎯 **取得完了後の次ステップ**

1. **システム統合**
   ```bash
   # 我々のシステムに統合
   python flightaware_integration.py
   ```

2. **データ収集開始**
   ```bash
   # 90日分の過去データ取得
   python run_flight_collection.py
   ```

3. **予測システム更新**
   - 実データでモデル再訓練
   - 精度向上確認
   - 本格運用開始

---

**推定所要時間**: 15-20分
**必要なもの**: クレジットカード、メールアドレス
**月額コスト**: 実質$3-4（$5以内）