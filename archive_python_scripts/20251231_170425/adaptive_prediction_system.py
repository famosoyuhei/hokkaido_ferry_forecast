#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
適応的予測システム
Adaptive Prediction System

データ蓄積量に応じて予報基準を自動調整し、
初期ルールベースから学習ベース予測へ段階的に移行する
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
import pandas as pd

# 既存システムインポート
from data_collection_manager import DataCollectionManager
from prediction_data_integration import PredictionDataIntegration

logger = logging.getLogger(__name__)

class AdaptivePredictionSystem:
    """適応的予測システム"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_manager = DataCollectionManager(data_dir)
        self.prediction_integration = PredictionDataIntegration()
        
        # 適応パラメータファイル
        self.adaptation_config_file = data_dir / "adaptation_config.json"
        
        # 段階別設定
        self.adaptation_stages = {
            "stage_0": {  # 0-49件: 初期ルールのみ
                "name": "初期段階",
                "min_data": 0,
                "max_data": 49,
                "prediction_method": "initial_rules_only",
                "confidence_base": 0.60,
                "threshold_adjustment": 1.0  # 調整なし
            },
            "stage_1": {  # 50-199件: 初期ルール + 基本ML
                "name": "学習段階",
                "min_data": 50,
                "max_data": 199,
                "prediction_method": "rules_with_ml",
                "confidence_base": 0.70,
                "threshold_adjustment": 0.95  # やや厳格化
            },
            "stage_2": {  # 200-499件: ハイブリッド予測
                "name": "成熟段階", 
                "min_data": 200,
                "max_data": 499,
                "prediction_method": "hybrid_prediction",
                "confidence_base": 0.85,
                "threshold_adjustment": 0.90  # 実績ベース調整
            },
            "stage_3": {  # 500+件: 完全学習ベース
                "name": "完成段階",
                "min_data": 500,
                "max_data": float('inf'),
                "prediction_method": "ml_dominant",
                "confidence_base": 0.90,
                "threshold_adjustment": 0.85  # 最適化された閾値
            }
        }
        
        # 初期閾値（ベースライン）
        self.base_thresholds = {
            "wind_speed": {
                "low": 10.0,
                "medium": 15.0,
                "high": 20.0,
                "critical": 25.0
            },
            "wave_height": {
                "low": 2.0,
                "medium": 3.0,
                "high": 4.0,
                "critical": 5.0
            },
            "visibility": {
                "critical": 0.5,
                "high": 1.0,
                "medium": 2.0,
                "low": 5.0
            },
            "temperature": {
                "critical": -15.0,
                "high": -10.0,
                "medium": -5.0,
                "low": 0.0
            }
        }
        
        # 現在の適応設定
        self.current_config = self._load_adaptation_config()
        
    def _load_adaptation_config(self) -> Dict:
        """適応設定読み込み"""
        try:
            if self.adaptation_config_file.exists():
                with open(self.adaptation_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 初期設定
                return self._create_initial_config()
        except Exception as e:
            logger.error(f"適応設定読み込みエラー: {e}")
            return self._create_initial_config()
    
    def _create_initial_config(self) -> Dict:
        """初期適応設定作成"""
        config = {
            "created_at": datetime.now().isoformat(),
            "current_stage": "stage_0",
            "adapted_thresholds": self.base_thresholds.copy(),
            "adaptation_history": [],
            "last_adaptation": None,
            "auto_adaptation_enabled": True
        }
        
        self._save_adaptation_config(config)
        return config
    
    def _save_adaptation_config(self, config: Dict):
        """適応設定保存"""
        try:
            config["updated_at"] = datetime.now().isoformat()
            with open(self.adaptation_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("適応設定を保存しました")
        except Exception as e:
            logger.error(f"適応設定保存エラー: {e}")
    
    def determine_current_stage(self) -> Dict:
        """現在の適応段階判定"""
        data_status = self.data_manager.get_current_status()
        data_count = data_status.get("current_count", 0)
        
        for stage_id, stage_config in self.adaptation_stages.items():
            if stage_config["min_data"] <= data_count <= stage_config["max_data"]:
                return {
                    "stage_id": stage_id,
                    "stage_config": stage_config,
                    "data_count": data_count,
                    "progress": min(1.0, (data_count - stage_config["min_data"]) / 
                                  max(1, stage_config["max_data"] - stage_config["min_data"]))
                }
        
        # フォールバック（最終段階）
        final_stage = "stage_3"
        return {
            "stage_id": final_stage,
            "stage_config": self.adaptation_stages[final_stage],
            "data_count": data_count,
            "progress": 1.0
        }
    
    def analyze_prediction_accuracy(self) -> Dict:
        """予測精度分析"""
        try:
            csv_file = self.data_dir / "ferry_cancellation_log.csv"
            if not csv_file.exists() or csv_file.stat().st_size == 0:
                return {"error": "分析用データが不足しています"}
            
            df = pd.read_csv(csv_file, encoding='utf-8')
            
            if len(df) < 10:
                return {"error": "分析には最低10件のデータが必要です"}
            
            # 直近1ヶ月のデータで分析
            df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
            recent_date = datetime.now() - timedelta(days=30)
            recent_df = df[df['日付'] >= recent_date]
            
            if len(recent_df) == 0:
                recent_df = df.tail(min(50, len(df)))  # 直近50件
            
            # 欠航データの気象条件分析
            cancellation_data = recent_df[recent_df['運航状況'] == '欠航']
            
            analysis = {
                "total_records": len(recent_df),
                "cancellation_count": len(cancellation_data),
                "cancellation_rate": len(cancellation_data) / len(recent_df) * 100,
                "weather_analysis": {}
            }
            
            if len(cancellation_data) > 0:
                # 欠航時の気象条件統計
                for condition in ['風速_ms', '波高_m', '視界_km', '気温_c']:
                    if condition in cancellation_data.columns:
                        values = pd.to_numeric(cancellation_data[condition], errors='coerce')
                        valid_values = values.dropna()
                        
                        if len(valid_values) > 0:
                            analysis["weather_analysis"][condition] = {
                                "mean": float(valid_values.mean()),
                                "min": float(valid_values.min()),
                                "max": float(valid_values.max()),
                                "percentile_75": float(valid_values.quantile(0.75))
                            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"予測精度分析エラー: {e}")
            return {"error": str(e)}
    
    def calculate_threshold_adjustments(self, accuracy_analysis: Dict) -> Dict:
        """閾値調整計算"""
        if "error" in accuracy_analysis:
            return {}
        
        adjustments = {}
        weather_stats = accuracy_analysis.get("weather_analysis", {})
        
        # 風速閾値調整
        if "風速_ms" in weather_stats:
            wind_stats = weather_stats["風速_ms"]
            avg_wind_at_cancellation = wind_stats["mean"]
            
            # 現在の中程度閾値と比較
            current_medium_threshold = self.current_config["adapted_thresholds"]["wind_speed"]["medium"]
            
            if avg_wind_at_cancellation < current_medium_threshold * 0.9:
                # 実際の欠航風速が閾値より低い場合、閾値を下げる
                adjustment_factor = max(0.8, avg_wind_at_cancellation / current_medium_threshold)
                adjustments["wind_speed"] = {
                    "factor": adjustment_factor,
                    "reason": f"実欠航風速平均 {avg_wind_at_cancellation:.1f}m/s < 閾値 {current_medium_threshold:.1f}m/s"
                }
        
        # 波高閾値調整
        if "波高_m" in weather_stats:
            wave_stats = weather_stats["波高_m"]
            avg_wave_at_cancellation = wave_stats["mean"]
            
            current_medium_threshold = self.current_config["adapted_thresholds"]["wave_height"]["medium"]
            
            if avg_wave_at_cancellation < current_medium_threshold * 0.9:
                adjustment_factor = max(0.8, avg_wave_at_cancellation / current_medium_threshold)
                adjustments["wave_height"] = {
                    "factor": adjustment_factor,
                    "reason": f"実欠航波高平均 {avg_wave_at_cancellation:.1f}m < 閾値 {current_medium_threshold:.1f}m"
                }
        
        # 視界閾値調整
        if "視界_km" in weather_stats:
            visibility_stats = weather_stats["視界_km"]
            avg_visibility_at_cancellation = visibility_stats["mean"]
            
            current_medium_threshold = self.current_config["adapted_thresholds"]["visibility"]["medium"]
            
            if avg_visibility_at_cancellation > current_medium_threshold * 1.2:
                adjustment_factor = min(1.5, avg_visibility_at_cancellation / current_medium_threshold)
                adjustments["visibility"] = {
                    "factor": adjustment_factor,
                    "reason": f"実欠航視界平均 {avg_visibility_at_cancellation:.1f}km > 閾値 {current_medium_threshold:.1f}km"
                }
        
        return adjustments
    
    def apply_adaptive_adjustments(self) -> Dict:
        """適応的調整適用"""
        try:
            # 現在の段階確認
            current_stage = self.determine_current_stage()
            stage_id = current_stage["stage_id"]
            stage_config = current_stage["stage_config"]
            
            logger.info(f"適応調整開始: {stage_config['name']} (データ{current_stage['data_count']}件)")
            
            # 段階が変わった場合の処理
            if self.current_config["current_stage"] != stage_id:
                logger.info(f"段階移行: {self.current_config['current_stage']} → {stage_id}")
                self.current_config["current_stage"] = stage_id
                
                # 段階移行履歴記録
                transition_record = {
                    "timestamp": datetime.now().isoformat(),
                    "from_stage": self.current_config["current_stage"],
                    "to_stage": stage_id,
                    "data_count": current_stage["data_count"],
                    "transition_type": "stage_progression"
                }
                self.current_config["adaptation_history"].append(transition_record)
            
            result = {
                "stage": stage_config["name"],
                "data_count": current_stage["data_count"],
                "adjustments_applied": [],
                "confidence_updated": stage_config["confidence_base"]
            }
            
            # 学習段階以上の場合、実績ベース調整
            if current_stage["data_count"] >= 50:
                # 予測精度分析
                accuracy_analysis = self.analyze_prediction_accuracy()
                
                if "error" not in accuracy_analysis:
                    # 閾値調整計算
                    adjustments = self.calculate_threshold_adjustments(accuracy_analysis)
                    
                    # 調整適用
                    for condition_type, adjustment in adjustments.items():
                        factor = adjustment["factor"]
                        
                        # 閾値更新
                        for level in self.current_config["adapted_thresholds"][condition_type]:
                            old_value = self.current_config["adapted_thresholds"][condition_type][level]
                            new_value = old_value * factor
                            self.current_config["adapted_thresholds"][condition_type][level] = new_value
                        
                        adjustment_record = {
                            "condition": condition_type,
                            "factor": factor,
                            "reason": adjustment["reason"],
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        result["adjustments_applied"].append(adjustment_record)
                        self.current_config["adaptation_history"].append(adjustment_record)
                        
                        logger.info(f"{condition_type} 閾値調整: factor={factor:.3f}")
            
            # 設定保存
            self.current_config["last_adaptation"] = datetime.now().isoformat()
            self._save_adaptation_config(self.current_config)
            
            return result
            
        except Exception as e:
            logger.error(f"適応的調整エラー: {e}")
            return {"error": str(e)}
    
    def get_current_prediction_parameters(self) -> Dict:
        """現在の予測パラメータ取得"""
        current_stage = self.determine_current_stage()
        
        return {
            "stage": current_stage["stage_config"]["name"],
            "stage_id": current_stage["stage_id"],
            "data_count": current_stage["data_count"],
            "progress": current_stage["progress"],
            "prediction_method": current_stage["stage_config"]["prediction_method"],
            "confidence_base": current_stage["stage_config"]["confidence_base"],
            "adapted_thresholds": self.current_config["adapted_thresholds"],
            "last_adaptation": self.current_config.get("last_adaptation"),
            "adaptation_count": len(self.current_config["adaptation_history"])
        }
    
    def should_trigger_adaptation(self) -> bool:
        """適応調整トリガー判定"""
        if not self.current_config.get("auto_adaptation_enabled", True):
            return False
        
        last_adaptation = self.current_config.get("last_adaptation")
        
        # 初回適応
        if last_adaptation is None:
            return True
        
        # 前回適応から24時間経過
        try:
            last_time = datetime.fromisoformat(last_adaptation)
            if datetime.now() - last_time > timedelta(hours=24):
                return True
        except:
            return True
        
        # 段階変更チェック
        current_stage = self.determine_current_stage()
        if self.current_config["current_stage"] != current_stage["stage_id"]:
            return True
        
        return False
    
    def generate_adaptation_report(self) -> Dict:
        """適応レポート生成"""
        try:
            current_params = self.get_current_prediction_parameters()
            
            # 閾値変更履歴
            threshold_changes = []
            base_thresholds = self.base_thresholds
            current_thresholds = current_params["adapted_thresholds"]
            
            for condition_type in base_thresholds:
                for level in base_thresholds[condition_type]:
                    base_value = base_thresholds[condition_type][level]
                    current_value = current_thresholds[condition_type][level]
                    
                    if abs(current_value - base_value) > 0.01:
                        change_percent = ((current_value - base_value) / base_value) * 100
                        threshold_changes.append({
                            "condition": condition_type,
                            "level": level,
                            "base_value": base_value,
                            "current_value": current_value,
                            "change_percent": change_percent
                        })
            
            report = {
                "generated_at": datetime.now().isoformat(),
                "current_stage": current_params["stage"],
                "data_count": current_params["data_count"],
                "stage_progress": f"{current_params['progress']:.1%}",
                "prediction_method": current_params["prediction_method"],
                "confidence_level": f"{current_params['confidence_base']:.0%}",
                "threshold_changes": threshold_changes,
                "adaptation_history_count": current_params["adaptation_count"],
                "system_maturity": self._assess_system_maturity(current_params),
                "recommendations": self._generate_adaptation_recommendations(current_params)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"適応レポート生成エラー: {e}")
            return {"error": str(e)}
    
    def _assess_system_maturity(self, params: Dict) -> str:
        """システム成熟度評価"""
        data_count = params["data_count"]
        
        if data_count >= 500:
            return "完全成熟: 高精度予測システム"
        elif data_count >= 200:
            return "成熟: 実用的予測システム"
        elif data_count >= 50:
            return "学習中: 改善継続中"
        else:
            return "初期: データ蓄積中"
    
    def _generate_adaptation_recommendations(self, params: Dict) -> List[str]:
        """適応推奨事項生成"""
        recommendations = []
        data_count = params["data_count"]
        stage = params["stage_id"]
        
        if stage == "stage_0":
            recommendations.append("🔄 データ収集を継続してください（目標50件）")
            recommendations.append("📊 気象条件と運航状況の相関分析準備")
        elif stage == "stage_1":
            recommendations.append("🤖 機械学習モデルの訓練を開始しました")
            recommendations.append("📈 予測精度向上のため継続的データ収集推奨")
        elif stage == "stage_2":
            recommendations.append("⚙️ ハイブリッド予測システムが稼働中")
            recommendations.append("🎯 閾値の実績ベース最適化実行中")
        elif stage == "stage_3":
            recommendations.append("✅ 高精度予測システム完成")
            recommendations.append("🔧 定期的なモデル再訓練とメンテナンス推奨")
        
        # 適応頻度チェック
        adaptation_count = params["adaptation_count"]
        if adaptation_count > 10:
            recommendations.append("⚠️ 適応回数が多いため、データ品質を確認してください")
        
        return recommendations

def main():
    """テスト実行"""
    from pathlib import Path
    
    data_dir = Path(__file__).parent / "data"
    adaptive_system = AdaptivePredictionSystem(data_dir)
    
    print("=== 適応的予測システム ===")
    
    # 現在の予測パラメータ表示
    current_params = adaptive_system.get_current_prediction_parameters()
    print("現在のシステム状況:")
    print(f"段階: {current_params['stage']} (データ{current_params['data_count']}件)")
    print(f"予測手法: {current_params['prediction_method']}")
    print(f"信頼度: {current_params['confidence_base']:.0%}")
    
    # 適応調整判定
    if adaptive_system.should_trigger_adaptation():
        print("\n適応調整を実行中...")
        adjustment_result = adaptive_system.apply_adaptive_adjustments()
        print(f"調整結果: {adjustment_result}")
    else:
        print("\n適応調整は不要です")
    
    # 適応レポート
    print("\n適応レポート:")
    report = adaptive_system.generate_adaptation_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()