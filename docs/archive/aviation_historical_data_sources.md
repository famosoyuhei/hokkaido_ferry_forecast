# 航空便過去データ取得可能性調査結果
**Aviation Historical Data Sources Analysis**

## 🔍 調査結果サマリー

**結論**: 航空便の過去データは**部分的に取得可能**だが、フェリーより制約がある

### ✅ 取得可能なデータ

| データソース | 取得期間 | 利尻空港対応 | 費用 | 制約事項 |
|-------------|----------|-------------|------|----------|
| **FlightAware** | 90日間 | ✅ | 月$5まで無料 | API制限あり |
| **HAC公式サイト** | 不明 | ✅ | 無料 | 手動取得のみ |
| **OAG/Cirium** | 数年間 | ❓ | 有償 | 高コスト |
| **NAVITIME API** | 不明 | ❓ | 有償 | 契約必要 |

## 📊 データソース詳細分析

### 1. FlightAware（最有力候補）

#### ✅ メリット
- **90日間の過去データ**を無料で取得可能
- **API提供**で自動化対応
- **利尻空港（RIS/RJER）**に対応
- **遅延・欠航データ**含む

#### 📋 提供データ
```json
{
  "flight_number": "HAC362",
  "departure_airport": "OKD",
  "arrival_airport": "RIS", 
  "scheduled_departure": "08:30",
  "actual_departure": "08:45",
  "status": "Delayed/Cancelled/On-time",
  "delay_minutes": 15,
  "cancellation_reason": "Weather"
}
```

#### 💰 料金体系
- **Personal Plan**: 月$5まで無料
- **超過料金**: リクエスト量に応じて従量課金
- **制約**: 月の無料枠を超過すると課金

#### 🔧 API実装例
```python
import requests

def get_flightaware_history(airport_code, start_date, end_date):
    url = "https://aeroapi.flightaware.com/aeroapi/airports/{}/flights/departures"
    headers = {"x-apikey": "YOUR_API_KEY"}
    params = {
        "start": start_date,
        "end": end_date,
        "max_pages": 10
    }
    return requests.get(url.format(airport_code), headers=headers, params=params)
```

### 2. HAC（北海道エアシステム）

#### 📊 運航実績データ
- **公式サイト**: www.info.hac-air.co.jp/company/operate/
- **データ期間**: 2018年頃まで確認
- **形式**: HTML表形式

#### 🤖 スクレイピング実装可能性
```python
def scrape_hac_data():
    """HAC運航実績をスクレイピング"""
    # 実装例:
    # 1. 運航実績ページにアクセス
    # 2. 表データを解析
    # 3. CSV形式で保存
    pass
```

#### ⚠️ 制約事項
- **手動アクセスが必要**
- **最新データのみ**公開の可能性
- **利尻路線特化データは限定的**

### 3. 商用航空データプロバイダー

#### OAG（Official Airline Guide）
- **世界最大の航空スケジュールDB**
- **数年分の過去データ**提供
- **費用**: 年間数十万円〜

#### Cirium
- **包括的な航空データ**
- **リアルタイム + 履歴**
- **費用**: 高額（企業向け）

## 🎯 推奨アプローチ

### Phase 1: FlightAware活用（短期）
```python
# 90日分のデータを迅速取得
from datetime import datetime, timedelta

def collect_90_days_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    # 利尻空港の全便履歴取得
    rishiri_flights = get_flightaware_history("RIS", start_date, end_date)
    okadama_flights = get_flightaware_history("OKD", start_date, end_date)
    
    return process_flight_data(rishiri_flights, okadama_flights)
```

### Phase 2: HAC公式データ補完（中期）
```python
# HAC公式サイトからの補完データ取得
def supplement_with_hac_data():
    # 運航実績ページのスクレイピング
    # FlightAwareでカバーできない期間の補完
    pass
```

### Phase 3: 継続収集システム（長期）
```python
# フェリーシステムと同様の日次収集
def daily_flight_collection():
    # 毎日の運航状況を記録
    # 蓄積データによる予測精度向上
    pass
```

## 🔄 フェリーシステムとの比較

| 要素 | フェリー | 航空便 |
|------|----------|--------|
| **過去データ** | ❌ 不可 | ✅ 90日分可能 |
| **データ形式** | CSV生成 | JSON/API |
| **自動化** | ✅ 完全対応 | ✅ API対応 |
| **費用** | 無料 | 月$5まで無料 |
| **開発速度** | 遅（日次蓄積） | 早（即座に学習開始） |

## 💡 開発戦略提案

### 即座開始可能な要素
1. **FlightAware API統合**
2. **90日分履歴データ取得**
3. **基本予測モデル構築**

### 段階的強化
1. **HAC公式データ補完**
2. **気象データとの相関分析**
3. **地形効果モデル統合**

## 🎉 航空システムの優位性

### フェリーに対する優位点
- **即座に過去データ利用可能**
- **予測精度の早期向上**
- **学習モデルの迅速検証**

### システム統合効果
```
🚢 フェリー予測（日次蓄積）+ ✈️ 航空予測（過去データ利用）
= 📊 相互補完による高精度予測システム
```

---

**結論**: 航空便システムはFlightAware APIを活用することで、**即座に90日分の過去データから学習開始**が可能。フェリーシステムよりも迅速な精度向上が期待できる。