# 利尻空港欠航予測システム設計書
**Rishiri Airport Flight Cancellation Prediction System**

## 🎯 システム概要

### 目的
利尻空港（RIS/RJER）発着便の欠航リスクを、地形気象学的要因を考慮して高精度予測するシステム

### 対象路線
- **新千歳空港（CTS）⇔ 利尻空港（RIS）**
- **札幌丘珠空港（OKD）⇔ 利尻空港（RIS）**

### 運航会社
- **ANAウイングス**: 新千歳便（夏季のみ）
- **北海道エアシステム（HAC）**: 丘珠便（通年）

## 🏔️ 利尻島特有の気象要因

### 1. 利尻山による地形効果

#### カルマン渦（Kármán Vortex）
```
利尻山（1,721m）による気流の影響:

       ↓ 北西風
    ◆◆◆◆◆ 利尻山
   🌪️    🌪️  カルマン渦
      空港 ✈️

- 風向: 北西〜西風時に顕著
- 影響高度: 地上〜3,000ft
- 空港への影響: 着陸進入時の乱気流
```

#### 地形性上昇気流・下降気流
- **風上側**: 強制上昇による雲形成
- **風下側**: 下降気流による気温上昇
- **山岳波**: 高度別風向・風速の急変

#### 局地風系
- **海陸風**: 日中の海風、夜間の陸風
- **山谷風**: 利尻山周辺の局地循環
- **収束・発散**: 島嶼効果による風系変化

### 2. 海洋性気象特性

#### 霧の発生メカニズム
```
移流霧（最多）:
暖湿気流 + 冷たい海面 → 霧発生

輻射霧:
夜間放射冷却 + 高湿度 → 早朝霧

蒸発霧:
冷気流 + 暖海面 → 瞬間的濃霧
```

#### 視界不良要因
- **春季**: 融雪 + 移流霧
- **夏季**: 海霧の内陸侵入
- **秋季**: 輻射霧 + 降水霧
- **冬季**: 吹雪・地吹雪

### 3. 航空機運航への影響

#### 離着陸制限要因
```
気象最低値（推定）:
- 視界: 1,600m以上
- 雲高: 200ft以上
- 横風成分: 25kt以下
- 降水強度: 中程度まで
```

## 📊 予測システム設計

### システム構成

```
┌─────────────────────────────────────┐
│        統合予測システム                    │
├─────────────────────────────────────┤
│  ✈️ 航空便予測    │  🚢 フェリー予測      │
│  - 利尻空港      │  - 稚内港発着        │
│  - 地形気象      │  - 海上気象          │
│  - 高層気象      │  - 波浪予測          │
└─────────────────────────────────────┘
           │
    ┌─────┴─────┐
    │ 共通基盤モジュール │
    │ - 気象データ統合  │
    │ - 機械学習エンジン │ 
    │ - 通知システム    │
    └─────────────┘
```

### 気象データソース

#### 1. 基本気象データ
- **気象庁**: 利尻空港METAR/TAF
- **航空局**: 航空気象情報
- **JMA MSM**: 高解像度数値予報
- **Open-Meteo**: 補完データ

#### 2. 高層気象データ
```python
高層観測要素:
- 気温・湿度プロファイル
- 風向・風速の高度分布  
- 安定度指数
- 対流有効位置エネルギー (CAPE)
- 風シア強度
```

#### 3. 地形気象モデル
```python
WRF-LES（Large Eddy Simulation）:
- 水平解像度: 100m
- 鉛直解像度: 10m
- 利尻山周辺の詳細気流解析
- カルマン渦の時空間変化
```

#### 4. 衛星・レーダーデータ
- **ひまわり**: 雲画像・霧検出
- **気象レーダー**: 降水強度
- **ドップラーライダー**: 風プロファイル

### 予測アルゴリズム

#### 1. 地形気象解析モジュール
```python
class TerrainMeteorology:
    def __init__(self):
        self.mountain_height = 1721  # 利尻山標高
        self.airport_location = (45.2421, 141.1864)
        
    def calculate_karman_vortex(self, wind_data):
        """カルマン渦強度計算"""
        # Strouhal数による渦周期計算
        strouhal_number = 0.21
        vortex_frequency = strouhal_number * wind_speed / mountain_width
        
        # 空港位置での乱気流強度推定
        turbulence_intensity = self._estimate_turbulence(
            vortex_frequency, distance_from_mountain
        )
        
        return turbulence_intensity
    
    def mountain_wave_analysis(self, sounding_data):
        """山岳波解析"""
        # Scorer parameter計算
        scorer_param = self._calculate_scorer_parameter(sounding_data)
        
        # 波の伝播・反射特性
        wave_amplitude = self._mountain_wave_model(scorer_param)
        
        return wave_amplitude
```

#### 2. 視界予測モジュール
```python
class VisibilityPredictor:
    def predict_fog_formation(self, meteo_data):
        """霧発生予測"""
        
        # 移流霧判定
        advection_fog_risk = self._advection_fog_model(
            temperature_diff, humidity, wind_speed
        )
        
        # 輻射霧判定
        radiation_fog_risk = self._radiation_fog_model(
            night_cooling, humidity, wind_speed
        )
        
        # 蒸発霧判定
        evaporation_fog_risk = self._evaporation_fog_model(
            air_sea_temp_diff, wind_speed
        )
        
        return max(advection_fog_risk, radiation_fog_risk, evaporation_fog_risk)
```

#### 3. 統合リスク評価
```python
class FlightCancellationPredictor:
    def __init__(self):
        self.terrain_module = TerrainMeteorology()
        self.visibility_module = VisibilityPredictor()
        
    def predict_cancellation_risk(self, forecast_hours=48):
        """欠航リスク総合評価"""
        
        risks = {}
        
        # 基本気象リスク
        risks['wind'] = self._wind_risk_assessment()
        risks['visibility'] = self.visibility_module.predict_fog_formation()
        risks['precipitation'] = self._precipitation_risk()
        risks['cloud_ceiling'] = self._ceiling_risk()
        
        # 地形効果リスク
        risks['karman_vortex'] = self.terrain_module.calculate_karman_vortex()
        risks['mountain_wave'] = self.terrain_module.mountain_wave_analysis()
        risks['local_wind'] = self._local_wind_system_risk()
        
        # 重み付け統合
        weights = {
            'wind': 0.20,
            'visibility': 0.25,
            'precipitation': 0.15,
            'cloud_ceiling': 0.15,
            'karman_vortex': 0.10,
            'mountain_wave': 0.10,
            'local_wind': 0.05
        }
        
        integrated_risk = sum(risks[factor] * weights[factor] 
                            for factor in risks.keys())
        
        return self._determine_risk_level(integrated_risk, risks)
```

### 機械学習アプローチ

#### 1. 特徴量設計
```python
航空特化特徴量:
- 高層気象プロファイル（850hPa、700hPa、500hPa）
- 風シア指数（0-3000ft）
- 安定度指数（K-Index、Total Totals）
- 地形パラメータ（フルード数、ロスビー数）
- カルマン渦強度指標
- 霧発生ポテンシャル
- 季節調整係数
```

#### 2. モデル構成
```python
アンサンブル学習:
├─ Random Forest: 基本予測
├─ XGBoost: 非線形関係捕捉  
├─ LSTM: 時系列パターン学習
├─ CNN: 空間パターン認識（衛星画像）
└─ 物理モデル: WRF-LES出力
```

#### 3. 学習データ
```python
訓練データ構成:
- 運航実績: 過去5年分
- 気象観測: METAR/TAF/上層観測
- 数値予報: MSM/GPV
- 衛星画像: ひまわり8号
- 地形数値標高: 10mメッシュDEM
```

## 🔧 システム統合設計

### 既存フェリーシステムとの統合

```python
class IntegratedTransportPredictor:
    def __init__(self):
        self.ferry_system = FerryPredictionEngine()
        self.flight_system = FlightCancellationPredictor()
        
    def comprehensive_forecast(self):
        """総合交通予測"""
        
        # 各交通手段のリスク評価
        ferry_risk = self.ferry_system.predict_cancellation_risk()
        flight_risk = self.flight_system.predict_cancellation_risk()
        
        # 交通手段間の相関分析
        correlation = self._analyze_transport_correlation()
        
        # 代替交通手段の提案
        alternatives = self._suggest_alternatives(ferry_risk, flight_risk)
        
        return {
            'ferry_forecast': ferry_risk,
            'flight_forecast': flight_risk,
            'recommendations': alternatives,
            'correlation_analysis': correlation
        }
```

### データ共有アーキテクチャ

```
共通データレイヤー:
┌─────────────────────────────────┐
│ 気象データベース                    │
│ - 観測データ                       │
│ - 数値予報データ                   │
│ - 衛星・レーダーデータ             │
└─────────────────────────────────┘
           │
    ┌─────┴─────┐
    │             │
┌───▼───┐   ┌───▼───┐
│フェリー  │   │航空便    │
│予測API  │   │予測API   │
└───┬───┘   └───┬───┘
    │             │
    └─────┬─────┘
          │
    ┌─────▼─────┐
    │ 統合UI/API │
    │ - Web App  │
    │ - Mobile   │
    │ - Discord  │
    │ - LINE     │
    └───────────┘
```

## 📱 ユーザーインターフェース

### 統合予報画面

```
┌─────────────────────────────────────┐
│    利尻島アクセス総合予報             │
├─────────────────────────────────────┤
│ 🚢 フェリー予報    │ ✈️ 航空便予報    │
│ 稚内-鴛泊: 安全    │ CTS-RIS: 注意    │
│ 稚内-香深: 注意    │ OKD-RIS: 安全    │
├─────────────────────────────────────┤
│ ⚠️ 気象警戒情報                      │
│ • 15:00頃 カルマン渦による乱気流     │
│ • 夜間 移流霧発生の可能性            │
├─────────────────────────────────────┤
│ 💡 おすすめルート                    │
│ 午前: 丘珠→利尻 (航空便)            │
│ 午後: 稚内→鴛泊 (フェリー)          │
└─────────────────────────────────────┘
```

## 🎯 開発計画

### Phase 1: 基盤構築（1-2ヶ月）
- [ ] 航空気象データAPI統合
- [ ] 基本予測アルゴリズム実装
- [ ] 既存システムとの統合

### Phase 2: 地形気象強化（2-3ヶ月）
- [ ] WRF-LESモデル導入
- [ ] カルマン渦解析実装
- [ ] 山岳波予測機能

### Phase 3: 機械学習高度化（1-2ヶ月）
- [ ] 深層学習モデル開発
- [ ] アンサンブル予測実装
- [ ] 精度検証・調整

### Phase 4: 総合システム（1ヶ月）
- [ ] 統合UI開発
- [ ] 通知システム拡張
- [ ] 運用監視機能

## 📊 期待される効果

### 予測精度目標
- **視界予測**: 80%以上の的中率
- **風況予測**: 85%以上の的中率  
- **総合欠航予測**: 75%以上の的中率

### 社会的インパクト
- **利用者**: 旅行計画の最適化
- **航空会社**: 運航判断支援
- **観光業**: 集客安定化
- **島民**: 生活交通の予見性向上

---

**次のステップ**: 航空気象データAPIの調査と基本システム設計から開始することをお勧めします。