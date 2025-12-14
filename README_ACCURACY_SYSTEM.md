# 予測精度改善システム

フェリー運航予報の精度を継続的に監視・改善するための自動化システムです。

## 🎯 システム概要

予測データと実際の運航データを照合し、予測精度を測定・改善する完全自動化システムです。

### 主要機能

1. **予測-実績マッチング**: 予測データと実運航データを自動的に照合
2. **精度評価**: 正解率、適合率、再現率、F1スコアなどを計算
3. **自動閾値調整**: 予測精度に基づいてリスク閾値を自動調整
4. **可視化ダッシュボード**: Webベースで精度トレンドを監視
5. **継続的改善**: 毎日自動実行で精度を向上

## 📊 システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                 予測精度改善システム                          │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼───────┐  ┌───────▼────────┐
│ データ収集層    │  │  分析・改善層  │  │  可視化層       │
├────────────────┤  ├──────────────┤  ├────────────────┤
│・予測データ     │  │・精度評価      │  │・ダッシュボード  │
│・実運航データ   │  │・マッチング    │  │・トレンド表示   │
│・気象データ     │  │・閾値調整      │  │・レポート生成   │
└────────────────┘  └──────────────┘  └────────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                ┌───────────▼───────────┐
                │  prediction_accuracy.db │
                │  ・予測マッチング       │
                │  ・パフォーマンス履歴   │
                │  ・閾値調整履歴         │
                └───────────────────────┘
```

## 🚀 クイックスタート

### 1. 初回セットアップ

```bash
# 必要なパッケージがインストール済みか確認
pip install -r requirements.txt

# テスト用の予測データ生成（開発環境のみ）
python generate_test_predictions.py

# システムテスト実行
python prediction_accuracy_system.py
```

### 2. ダッシュボード起動

```bash
# Webダッシュボードを起動
python accuracy_dashboard.py

# ブラウザでアクセス
# http://localhost:5001
```

### 3. 自動化システム起動

```bash
# 日次自動実行スクリプト
python automated_improvement_runner.py
```

## 📁 ファイル構成

### コアシステム

- **prediction_accuracy_system.py**: メインの精度改善システム
  - 予測と実績のマッチング
  - 精度評価とメトリクス計算
  - 自動閾値調整

- **automated_improvement_runner.py**: 自動実行スクリプト
  - 実運航データ収集
  - 予測マッチング
  - 精度評価
  - レポート生成

- **accuracy_dashboard.py**: Web可視化ダッシュボード
  - リアルタイム精度監視
  - トレンド可視化
  - 航路別パフォーマンス

### サポートスクリプト

- **generate_test_predictions.py**: テストデータ生成（開発用）
- **accuracy_tracker.py**: 実運航データ収集
- **check_accuracy_db.py**: データベース確認ツール

## 💾 データベース構造

### prediction_accuracy.db

#### 1. prediction_matches テーブル
予測と実績のマッチングデータ

```sql
- match_date: 日付
- route: 航路
- predicted_risk_level: 予測リスクレベル
- predicted_risk_score: 予測リスクスコア
- actual_status: 実際の運航状況
- prediction_correct: 予測が正しかったか
- false_positive: 偽陽性
- false_negative: 偽陰性
```

#### 2. model_performance テーブル
モデルのパフォーマンス履歴

```sql
- evaluation_date: 評価日
- accuracy_rate: 正解率
- precision_score: 適合率
- recall_score: 再現率
- f1_score: F1スコア
- mean_absolute_error: 平均絶対誤差
```

#### 3. threshold_adjustments テーブル
リスク閾値の調整履歴

```sql
- parameter_name: パラメータ名（wind_speed, wave_height等）
- old_value: 変更前の値
- new_value: 変更後の値
- reason: 調整理由
```

## 📈 精度メトリクス

### 主要指標

1. **正解率 (Accuracy)**
   - 全予測のうち、正しく予測できた割合
   - 目標: 80%以上

2. **適合率 (Precision)**
   - 欠航予測のうち、実際に欠航した割合
   - 目標: 75%以上（偽陽性を抑える）

3. **再現率 (Recall)**
   - 実際の欠航のうち、予測できた割合
   - 目標: 85%以上（見逃しを防ぐ）

4. **F1スコア**
   - 適合率と再現率の調和平均
   - 目標: 0.80以上

5. **キャリブレーション**
   - 予測確率と実際の発生率の一致度
   - 目標: 0.85以上

## 🔧 自動調整メカニズム

### 閾値調整アルゴリズム

システムは以下の条件で自動的に閾値を調整します:

```python
# 偽陽性が多い場合
if false_positive_rate > 0.25:
    # 閾値を引き上げる（より厳しく）
    threshold_increase()

# 偽陰性が多い場合（見逃しが多い）
if false_negative_rate > 0.15:
    # 閾値を引き下げる（より敏感に）
    threshold_decrease()

# 最適値の計算
optimal_threshold = (avg_fp_weather + avg_fn_weather) / 2
```

### 調整パラメータ

- **風速閾値**: デフォルト 15.0 m/s
- **波高閾値**: デフォルト 3.0 m
- **視界閾値**: デフォルト 1.0 km
- **気温閾値**: デフォルト -10.0 °C

## 📅 自動実行スケジュール

Railway環境での実行スケジュール（UTC時間）:

```json
{
  "accuracy_tracking": {
    "command": "python accuracy_tracker.py",
    "schedule": "0 22 * * *"  // 毎日 7:00 JST - 実運航データ収集
  },
  "accuracy_improvement": {
    "command": "python automated_improvement_runner.py",
    "schedule": "30 22 * * *"  // 毎日 7:30 JST - 精度改善サイクル
  }
}
```

### 実行フロー

```
6:00 JST  → 予測データ生成（weather_forecast_collector.py）
7:00 JST  → 実運航データ収集（accuracy_tracker.py）
7:30 JST  → 精度改善サイクル（automated_improvement_runner.py）
           ├─ 予測と実績のマッチング
           ├─ 精度評価
           ├─ 閾値調整（必要時）
           └─ レポート生成
```

## 📊 ダッシュボード機能

### Webダッシュボード (http://localhost:5001)

#### 1. メトリクスカード
- 現在の精度、適合率、再現率、F1スコア
- ステータスバッジ（優秀/良好/要改善/改善必要）

#### 2. トレンドチャート
- 時系列での精度推移
- 適合率・再現率の変化

#### 3. 混同行列
- 真陽性、真陰性、偽陽性、偽陰性の分布

#### 4. 航路別パフォーマンス
- 各航路の精度比較

#### 5. 予測マッチング履歴
- 最近の予測結果と実績の対照表

#### 6. 閾値調整履歴
- パラメータの変更履歴と理由

### APIエンドポイント

```
GET /api/performance/current     - 現在のパフォーマンス
GET /api/performance/trend       - トレンドデータ
GET /api/matches/recent          - 最近のマッチング
GET /api/confusion_matrix        - 混同行列
GET /api/route_performance       - 航路別精度
GET /api/thresholds/current      - 現在の閾値
GET /api/thresholds/history      - 閾値変更履歴
```

## 🔍 トラブルシューティング

### よくある問題

**Q: マッチングデータが0件**
```bash
# 実運航データが収集されているか確認
python check_accuracy_db.py

# 手動でデータ収集
python accuracy_tracker.py

# 予測データの日付範囲確認
python -c "import sqlite3; conn = sqlite3.connect('ferry_weather_forecast.db');
cur = conn.cursor(); cur.execute('SELECT MIN(forecast_for_date), MAX(forecast_for_date) FROM cancellation_forecast');
print(cur.fetchone())"
```

**Q: ダッシュボードにデータが表示されない**
```bash
# データベースの確認
python check_accuracy_db.py

# 最低1回は改善サイクルを実行
python automated_improvement_runner.py
```

**Q: 精度が低い**
```bash
# 自動調整を実行
python prediction_accuracy_system.py

# データ量を確認（最低30日分推奨）
```

## 📈 精度改善のベストプラクティス

### 1. データ収集
- 最低30日分の予測-実績ペアを蓄積
- 毎日定時に実運航データを収集

### 2. 評価サイクル
- 週1回は詳細レビュー
- 月1回は閾値の妥当性確認

### 3. 季節調整
- 冬季と夏季で別々の閾値を検討
- 季節ごとの精度トレンドを監視

### 4. 航路別最適化
- 航路ごとに異なる特性を考慮
- 航路別の閾値設定も検討

## 🚀 今後の拡張

### 計画中の機能

1. **機械学習モデルの統合**
   - ランダムフォレストやXGBoostの導入
   - 自動的なハイパーパラメータ調整

2. **リアルタイム調整**
   - 運航状況をリアルタイムで取得
   - 即座に精度評価と調整

3. **予測説明機能**
   - なぜその予測になったかを説明
   - SHAP値によるフィーチャー重要度

4. **アラート機能**
   - 精度が閾値を下回ったら通知
   - 異常な予測パターンを検出

## 📞 サポート

### 問題報告
GitHubのIssuesで報告してください

### ログ確認
```bash
# 実行ログ
tail -f ferry_monitoring.log

# エラーログ
grep ERROR ferry_monitoring.log
```

---

**🎯 このシステムにより、フェリー運航予報は継続的に精度が向上し、より信頼性の高い予測を提供できます。**
