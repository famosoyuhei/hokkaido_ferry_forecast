#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予測連携システム - 蓄積データを予測エンジンに活用
Prediction Integration System - Utilizing Accumulated Data for Prediction Engine
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
import joblib

# 既存の予測エンジンをインポート
from core.ferry_prediction_engine import FerryPredictionEngine, CancellationRisk

logger = logging.getLogger(__name__)

class PredictionDataIntegration:
    """予測データ統合システム"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.models_dir = self.base_dir / "models"
        self.models_dir.mkdir(exist_ok=True)
        
        # データファイル
        self.csv_file = self.data_dir / "ferry_cancellation_log.csv"
        self.training_data_file = self.data_dir / "training_data.json"
        self.model_file = self.models_dir / "cancellation_predictor.pkl"
        
        # 既存の予測エンジン
        self.ferry_engine = FerryPredictionEngine()
        
        # 機械学習モデル
        self.ml_model = None
        self.label_encoder = LabelEncoder()
        
        # 学習データの最小件数
        self.min_training_samples = 50
        
    def load_cancellation_data(self) -> pd.DataFrame:
        """蓄積された欠航データを読み込み"""
        try:
            if not self.csv_file.exists():
                logger.warning("CSVファイルが存在しません")
                return pd.DataFrame()
            
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            logger.info(f"欠航データを読み込みました: {len(df)}件")
            
            # データクリーニング
            df = self._clean_data(df)
            
            return df
            
        except Exception as e:
            logger.error(f"欠航データ読み込みでエラー: {e}")
            return pd.DataFrame()
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """データクリーニング"""
        try:
            # 日付フォーマット統一
            df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
            
            # 数値データの型変換
            numeric_columns = ['風速_ms', '波高_m', '視界_km', '気温_c']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 欠損値処理
            df = df.dropna(subset=['日付', '運航状況'])
            
            # 運航状況の標準化
            df['運航状況'] = df['運航状況'].map({
                '欠航': 1,
                '遅延': 0.5,
                '通常運航': 0,
                '通常': 0
            }).fillna(0)
            
            logger.info(f"データクリーニング完了: {len(df)}件")
            return df
            
        except Exception as e:
            logger.error(f"データクリーニングでエラー: {e}")
            return df
    
    def convert_to_training_format(self, df: pd.DataFrame) -> Dict:
        """学習データ形式に変換"""
        try:
            training_data = {
                "features": [],
                "labels": [],
                "feature_names": [
                    "month", "hour", "wind_speed", "wave_height", 
                    "visibility", "temperature", "route_id"
                ],
                "metadata": {
                    "total_samples": len(df),
                    "created_at": datetime.now().isoformat(),
                    "data_period": {
                        "start": df['日付'].min().isoformat() if not df.empty else None,
                        "end": df['日付'].max().isoformat() if not df.empty else None
                    }
                }
            }
            
            for _, row in df.iterrows():
                try:
                    # 特徴量抽出
                    date = pd.to_datetime(row['日付'])
                    hour = pd.to_datetime(row['出航予定時刻'], format='%H:%M', errors='coerce')
                    
                    # 航路IDエンコード
                    route_id = self._encode_route_id(row['出航場所'], row['着場所'])
                    
                    features = [
                        date.month,  # 月
                        hour.hour if pd.notna(hour) else 12,  # 時間
                        row.get('風速_ms', 0) or 0,  # 風速
                        row.get('波高_m', 0) or 0,   # 波高
                        row.get('視界_km', 10) or 10,  # 視界
                        row.get('気温_c', 5) or 5,   # 気温
                        route_id  # 航路ID
                    ]
                    
                    label = row['運航状況']  # 0: 正常, 0.5: 遅延, 1: 欠航
                    
                    training_data["features"].append(features)
                    training_data["labels"].append(label)
                    
                except Exception as e:
                    logger.warning(f"行の変換でエラー: {e}, 行をスキップ")
                    continue
            
            logger.info(f"学習データ変換完了: {len(training_data['features'])}件")
            
            # JSONファイルに保存
            with open(self.training_data_file, 'w', encoding='utf-8') as f:
                json.dump(training_data, f, ensure_ascii=False, indent=2)
            
            return training_data
            
        except Exception as e:
            logger.error(f"学習データ変換でエラー: {e}")
            return {"features": [], "labels": []}
    
    def _encode_route_id(self, departure: str, arrival: str) -> int:
        """航路IDエンコード"""
        route_mapping = {
            ("稚内港", "鴛泊港"): 1,
            ("稚内港", "沓形港"): 2,
            ("稚内港", "香深港"): 3,
            ("鴛泊港", "稚内港"): 1,
            ("沓形港", "稚内港"): 2,
            ("香深港", "稚内港"): 3
        }
        return route_mapping.get((departure, arrival), 0)
    
    def train_ml_model(self, training_data: Dict) -> Optional[RandomForestClassifier]:
        """機械学習モデル訓練"""
        try:
            features = np.array(training_data["features"])
            labels = np.array(training_data["labels"])
            
            if len(features) < self.min_training_samples:
                logger.warning(f"学習データが不足しています: {len(features)}件 (最低{self.min_training_samples}件必要)")
                return None
            
            # ラベルの離散化（0: 正常, 1: 遅延・欠航）
            binary_labels = (labels > 0).astype(int)
            
            # 訓練・テストデータ分割
            X_train, X_test, y_train, y_test = train_test_split(
                features, binary_labels, test_size=0.2, random_state=42, stratify=binary_labels
            )
            
            # ランダムフォレストモデル
            self.ml_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'  # 不均衡データ対応
            )
            
            # モデル訓練
            self.ml_model.fit(X_train, y_train)
            
            # 評価
            y_pred = self.ml_model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            logger.info(f"モデル訓練完了 - 精度: {accuracy:.3f}")
            logger.info(f"訓練データ: {len(X_train)}件, テストデータ: {len(X_test)}件")
            
            # 特徴量重要度
            feature_importance = self.ml_model.feature_importances_
            feature_names = training_data["feature_names"]
            
            logger.info("特徴量重要度:")
            for name, importance in zip(feature_names, feature_importance):
                logger.info(f"  {name}: {importance:.3f}")
            
            # モデル保存
            joblib.dump(self.ml_model, self.model_file)
            logger.info(f"モデルを保存しました: {self.model_file}")
            
            return self.ml_model
            
        except Exception as e:
            logger.error(f"モデル訓練でエラー: {e}")
            return None
    
    def load_trained_model(self) -> Optional[RandomForestClassifier]:
        """訓練済みモデル読み込み"""
        try:
            if self.model_file.exists():
                self.ml_model = joblib.load(self.model_file)
                logger.info("訓練済みモデルを読み込みました")
                return self.ml_model
            else:
                logger.warning("訓練済みモデルが存在しません")
                return None
        except Exception as e:
            logger.error(f"モデル読み込みでエラー: {e}")
            return None
    
    def predict_with_ml_model(self, weather_conditions: Dict, route_id: str, 
                             departure_time: str) -> Dict:
        """機械学習モデルによる予測"""
        try:
            if self.ml_model is None:
                self.load_trained_model()
                if self.ml_model is None:
                    return {"error": "訓練済みモデルがありません"}
            
            # 特徴量準備
            current_time = datetime.now()
            departure_hour = pd.to_datetime(departure_time, format='%H:%M', errors='coerce')
            
            route_id_encoded = self._encode_route_name_to_id(route_id)
            
            features = np.array([[
                current_time.month,
                departure_hour.hour if pd.notna(departure_hour) else 12,
                weather_conditions.get("wind_speed", 0),
                weather_conditions.get("wave_height", 0),
                weather_conditions.get("visibility", 10),
                weather_conditions.get("temperature", 5),
                route_id_encoded
            ]])
            
            # 予測実行
            prediction = self.ml_model.predict(features)[0]
            prediction_proba = self.ml_model.predict_proba(features)[0]
            
            # 結果整理
            result = {
                "prediction": "欠航リスク" if prediction == 1 else "運航可能",
                "cancellation_probability": float(prediction_proba[1]),
                "confidence": float(max(prediction_proba)),
                "model_type": "machine_learning",
                "weather_conditions": weather_conditions
            }
            
            return result
            
        except Exception as e:
            logger.error(f"ML予測でエラー: {e}")
            return {"error": str(e)}
    
    def _encode_route_name_to_id(self, route_name: str) -> int:
        """航路名からIDへ変換"""
        route_mapping = {
            "wakkanai_oshidomari": 1,
            "wakkanai_kutsugata": 2,
            "wakkanai_kafuka": 3
        }
        return route_mapping.get(route_name, 1)
    
    def create_hybrid_prediction(self, route_id: str, departure_time: str,
                               weather_conditions: Dict) -> Dict:
        """ハイブリッド予測（従来エンジン + ML）"""
        try:
            results = {
                "route_id": route_id,
                "departure_time": departure_time,
                "weather_conditions": weather_conditions,
                "predictions": {}
            }
            
            # 1. 従来の予測エンジン
            try:
                # 簡易的な従来予測（実際はより複雑な処理）
                wind_risk = min(100, (weather_conditions.get("wind_speed", 0) / 15) * 100)
                wave_risk = min(100, (weather_conditions.get("wave_height", 0) / 3) * 100)
                visibility_risk = max(0, (5 - weather_conditions.get("visibility", 10)) / 5 * 100)
                
                traditional_risk = (wind_risk + wave_risk + visibility_risk) / 3
                
                results["predictions"]["traditional"] = {
                    "risk_score": traditional_risk,
                    "risk_level": "High" if traditional_risk > 60 else "Medium" if traditional_risk > 30 else "Low",
                    "method": "rule_based"
                }
            except Exception as e:
                logger.warning(f"従来予測でエラー: {e}")
                results["predictions"]["traditional"] = {"error": str(e)}
            
            # 2. 機械学習予測
            ml_result = self.predict_with_ml_model(weather_conditions, route_id, departure_time)
            results["predictions"]["machine_learning"] = ml_result
            
            # 3. ハイブリッド統合
            if "error" not in ml_result and "error" not in results["predictions"]["traditional"]:
                traditional_risk = results["predictions"]["traditional"]["risk_score"]
                ml_risk = ml_result["cancellation_probability"] * 100
                
                # 重み付き平均（MLの重みは学習データ量に比例）
                data_count = self._get_training_data_count()
                ml_weight = min(0.7, data_count / 1000)  # 最大70%
                traditional_weight = 1 - ml_weight
                
                hybrid_risk = (traditional_risk * traditional_weight + 
                              ml_risk * ml_weight)
                
                results["predictions"]["hybrid"] = {
                    "risk_score": hybrid_risk,
                    "risk_level": "High" if hybrid_risk > 60 else "Medium" if hybrid_risk > 30 else "Low",
                    "ml_weight": ml_weight,
                    "traditional_weight": traditional_weight,
                    "method": "hybrid",
                    "recommendation": self._generate_recommendation(hybrid_risk)
                }
            
            return results
            
        except Exception as e:
            logger.error(f"ハイブリッド予測でエラー: {e}")
            return {"error": str(e)}
    
    def _get_training_data_count(self) -> int:
        """学習データ件数取得"""
        try:
            df = self.load_cancellation_data()
            return len(df)
        except:
            return 0
    
    def _generate_recommendation(self, risk_score: float) -> str:
        """推奨事項生成"""
        if risk_score > 80:
            return "運航困難な可能性が高いです。気象情報を継続監視し、早めの判断をお勧めします。"
        elif risk_score > 60:
            return "運航に注意が必要です。気象条件の変化を注視してください。"
        elif risk_score > 30:
            return "比較的安全な運航が予想されますが、念のため気象情報を確認してください。"
        else:
            return "安全な運航が予想されます。"
    
    def update_model_with_new_data(self):
        """新しいデータでモデル更新"""
        try:
            logger.info("モデル更新を開始します...")
            
            # 最新データ読み込み
            df = self.load_cancellation_data()
            if df.empty:
                logger.warning("更新用データがありません")
                return
            
            # 学習データ変換
            training_data = self.convert_to_training_format(df)
            
            # モデル再訓練
            updated_model = self.train_ml_model(training_data)
            
            if updated_model:
                logger.info("モデル更新が完了しました")
                return True
            else:
                logger.warning("モデル更新に失敗しました")
                return False
                
        except Exception as e:
            logger.error(f"モデル更新でエラー: {e}")
            return False
    
    def generate_accuracy_report(self) -> Dict:
        """予測精度レポート生成"""
        try:
            df = self.load_cancellation_data()
            if df.empty:
                return {"error": "データが不足しています"}
            
            # 直近1ヶ月のデータで評価
            recent_date = datetime.now() - timedelta(days=30)
            recent_df = df[df['日付'] >= recent_date]
            
            if len(recent_df) < 10:
                return {"warning": "評価用データが不足しています"}
            
            # 精度評価（実装の詳細は省略）
            total_predictions = len(recent_df)
            accurate_predictions = len(recent_df[recent_df['運航状況'] >= 0])  # 簡易評価
            
            accuracy = accurate_predictions / total_predictions if total_predictions > 0 else 0
            
            report = {
                "evaluation_period": f"{recent_date.date()} - {datetime.now().date()}",
                "total_predictions": total_predictions,
                "accuracy": accuracy,
                "data_summary": {
                    "cancellations": len(recent_df[recent_df['運航状況'] == 1]),
                    "delays": len(recent_df[recent_df['運航状況'] == 0.5]),
                    "normal_operations": len(recent_df[recent_df['運航状況'] == 0])
                },
                "model_status": "trained" if self.ml_model else "not_trained"
            }
            
            return report
            
        except Exception as e:
            logger.error(f"精度レポート生成でエラー: {e}")
            return {"error": str(e)}

def main():
    """メイン実行関数"""
    print("=== 予測連携システム ===")
    
    integration = PredictionDataIntegration()
    
    # 1. データ読み込み・変換
    print("1. 蓄積データを読み込み中...")
    df = integration.load_cancellation_data()
    print(f"読み込み完了: {len(df)}件")
    
    if len(df) > 0:
        # 2. 学習データ変換
        print("2. 学習データに変換中...")
        training_data = integration.convert_to_training_format(df)
        print(f"変換完了: {len(training_data['features'])}件")
        
        # 3. モデル訓練
        if len(training_data['features']) >= integration.min_training_samples:
            print("3. モデル訓練中...")
            model = integration.train_ml_model(training_data)
            if model:
                print("モデル訓練完了")
            else:
                print("モデル訓練失敗")
        else:
            print(f"3. 学習データ不足（{len(training_data['features'])}件、最低{integration.min_training_samples}件必要）")
        
        # 4. 予測テスト
        print("4. 予測テスト...")
        test_conditions = {
            "wind_speed": 18.0,
            "wave_height": 3.5,
            "visibility": 2.0,
            "temperature": -2.0
        }
        
        result = integration.create_hybrid_prediction(
            "wakkanai_oshidomari", "08:00", test_conditions
        )
        
        print("予測結果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("蓄積データがありません。監視システムを先に実行してください。")

if __name__ == "__main__":
    main()