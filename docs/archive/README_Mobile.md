# 📱 スマホ対応モバイルWebアプリ

北海道フェリー予測システムのスマートフォン対応Webアプリケーションです。

## 🚀 クイックスタート

### 簡単起動（Windows）
```bash
# バッチファイルをダブルクリック
start_mobile_app.bat
```

### 手動起動
```bash
# 必要パッケージインストール
pip install flask

# Webアプリ起動
python mobile_web_app.py
```

## 📱 スマホでアクセス

### 1. 同一WiFi接続
1. パソコンとスマホを**同じWiFi**に接続
2. パソコンのIPアドレスを確認:
   ```bash
   # Windows
   ipconfig
   
   # Mac/Linux  
   ifconfig
   ```
3. スマホブラウザで以下にアクセス:
   ```
   http://[IPアドレス]:5000
   例: http://192.168.1.100:5000
   ```

### 2. ローカルアクセス（パソコンのみ）
```
http://localhost:5000
```

## 📋 機能一覧

### 🏠 ホーム画面
- システム概要表示
- 現在のデータ蓄積状況
- 予測精度レベル
- ナビゲーションメニュー

### 📅 7日間予報画面
- **3日間/5日間/7日間**の予報期間選択
- 各航路・各便の詳細予報:
  - 🟢🟡🟠🔴 リスクレベル表示
  - 気象条件（風速・波高・視界・気温）
  - 具体的な推奨事項
  - 信頼度表示

### 📊 システム状況画面
- データ収集進捗バー
- 予測システムの成熟度
- 適応調整履歴
- 自動更新（30秒間隔）

### ℹ️ システム情報画面
- 対象航路一覧
- 予測精度の進化段階説明
- 分析要素の詳細

## 📱 モバイル最適化

### レスポンシブデザイン
- スマートフォン画面サイズに最適化
- タブレット対応
- タッチ操作対応

### PWA（Progressive Web App）対応
- ホーム画面への追加可能
- アプリライクな操作感
- オフライン対応（予定）

### パフォーマンス
- 軽量設計
- 高速読み込み
- リアルタイム更新

## 🎨 画面構成

### ナビゲーション
```
🚢 フェリー予報
├── 🏠 ホーム
├── 📅 予報  
├── 📊 システム状況
└── ℹ️ について
```

### 予報表示例
```
📅 08月30日(金)

🛳️ 稚内 ⇔ 鴛泊
┌─────────────────────────────┐
│ 🟠 08:00 → 09:40 (第1便)    │
│ High 75% | 信頼度 85%        │
│ 💨 18.5m/s 🌊 3.2m          │
│ 👁️ 2.0km 🌡️ -5.0°C         │
│ 💡 運航に注意が必要         │
└─────────────────────────────┘
```

### システム状況表示
```
📈 データ収集状況
████████████░░░░ 75% (375/500件)

🤖 予測システム状況  
段階: 成熟段階
手法: ハイブリッド予測
信頼度: 85%
```

## 🔧 カスタマイズ

### ポート変更
```python
# mobile_web_app.py の最終行
app.run(host='0.0.0.0', port=8080, debug=True)  # ポート8080に変更
```

### 予報期間変更
```python
# デフォルト予報日数変更
days = int(request.args.get('days', 5))  # デフォルト5日間
```

### 更新間隔変更
```javascript
// status.html内
setInterval(loadStatus, 60000);  // 60秒間隔に変更
```

## 🌐 外部アクセス設定

### ファイアウォール設定（Windows）
```bash
# Windows Defender ファイアウォール
# 受信規則で TCP ポート 5000 を許可
```

### ルーター設定（外部アクセス用）
1. ポートフォワーディング設定
2. 外部ポート: 5000
3. 内部IP: パソコンのローカルIP
4. 内部ポート: 5000

## 📊 API エンドポイント

### 予報データ API
```
GET /api/forecast?days=3
レスポンス: JSON形式の予報データ
```

### システム状況 API  
```
GET /api/status
レスポンス: データ収集・予測システム状況
```

### 航路情報 API
```
GET /api/routes  
レスポンス: 航路・スケジュール情報
```

## 🔍 トラブルシューティング

### よくある問題

**❌ スマホからアクセスできない**
```bash
# 1. 同一WiFi接続確認
# 2. ファイアウォール確認
# 3. IPアドレス再確認
ipconfig | findstr IPv4
```

**❌ 予報データが表示されない**
```bash
# ログ確認
python mobile_web_app.py
# ブラウザの開発者ツールでエラー確認
```

**❌ システム状況が更新されない**
```bash
# データ収集システム起動確認
python ferry_monitoring_system.py
```

### デバッグモード

```python
# mobile_web_app.py
app.run(host='0.0.0.0', port=5000, debug=True)  # debug=True
```

## 🚀 高度な使用方法

### リバースプロキシ設定（Nginx）
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL対応（HTTPS）
```python
# SSL証明書使用
app.run(host='0.0.0.0', port=5000, 
        ssl_context=('cert.pem', 'key.pem'))
```

### Docker化
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "mobile_web_app.py"]
```

## 📱 スマホアプリ化

### PWAインストール手順
1. スマホブラウザでWebアプリを開く
2. ブラウザメニューから「ホーム画面に追加」
3. アプリ名を確認して「追加」をタップ
4. ホーム画面にアイコンが追加される

### アプリライクな操作
- スプラッシュスクリーン表示
- フルスクリーンモード  
- ネイティブアプリのような操作感

---

**📱 これでスマートフォンで快適にフェリー予報を確認できます！**

WiFi設定して `start_mobile_app.bat` を実行するだけで、スマホからリアルタイムの運航予報にアクセスできるようになります。