#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合予測システム実行スクリプト
Integrated Prediction System Runner
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

# 既存システムのインポート
from ferry_monitoring_system import FerryMonitoringSystem
from prediction_data_integration import PredictionDataIntegration
from core.ferry_prediction_engine import FerryPredictionEngine

class IntegratedPredictionRunner:
    """統合予測システム実行管理"""
    
    def __init__(self):
        self.monitoring_system = FerryMonitoringSystem()
        self.prediction_integration = PredictionDataIntegration()
        self.ferry_engine = FerryPredictionEngine()
        
    async def run_full_prediction_cycle(self, route_id: str = "wakkanai_oshidomari"):
        """完全な予測サイクル実行"""
        print(f"=== 統合予測システム実行: {route_id} ===")
        
        # 1. 現在の運航状況監視
        print("1. 現在の運航状況を確認中...")
        status_info = await self.monitoring_system.check_ferry_status()
        print(f"運航状況: {status_info}")
        
        # 2. 蓄積データによる学習更新
        print("\n2. 蓄積データによるモデル更新中...")
        update_result = self.prediction_integration.update_model_with_new_data()
        print(f"モデル更新結果: {update_result}")
        
        # 3. 実績フィードバック適用
        print("\n3. 実績フィードバックを適用中...")
        feedback_result = self.ferry_engine.apply_feedback_learning(route_id)
        print(f"フィードバック結果: {feedback_result}")
        
        # 4. ハイブリッド予測実行
        print("\n4. ハイブリッド予測を実行中...")
        
        # テスト用気象条件
        test_weather = {
            "wind_speed": 16.0,
            "wave_height": 3.2,
            "visibility": 1.8,
            "temperature": -3.0
        }
        
        hybrid_prediction = self.prediction_integration.create_hybrid_prediction(
            route_id, "08:00", test_weather
        )
        
        print("ハイブリッド予測結果:")
        print(json.dumps(hybrid_prediction, ensure_ascii=False, indent=2))
        
        # 5. 予測精度メトリクス表示
        print("\n5. 予測精度メトリクス:")
        accuracy_metrics = self.ferry_engine.get_prediction_accuracy_metrics()
        print(json.dumps(accuracy_metrics, ensure_ascii=False, indent=2))
        
        # 6. 通常の予測エンジンとの比較
        print("\n6. 通常予測エンジンとの比較:")
        try:
            traditional_predictions = await self.ferry_engine.predict_cancellation_risk(route_id, 24)
            if traditional_predictions:
                current_risk = traditional_predictions[0]
                print(f"従来予測: {current_risk.risk_level} (スコア: {current_risk.risk_score:.1f})")
                
                # ハイブリッド予測との比較
                if "hybrid" in hybrid_prediction.get("predictions", {}):
                    hybrid_risk = hybrid_prediction["predictions"]["hybrid"]["risk_score"]
                    print(f"ハイブリッド予測: {hybrid_prediction['predictions']['hybrid']['risk_level']} (スコア: {hybrid_risk:.1f})")
                    print(f"予測差異: {abs(current_risk.risk_score - hybrid_risk):.1f}ポイント")
        except Exception as e:
            print(f"従来予測でエラー: {e}")
        
        return {
            "status": status_info,
            "model_update": update_result,
            "feedback": feedback_result,
            "hybrid_prediction": hybrid_prediction,
            "accuracy_metrics": accuracy_metrics
        }
    
    def demonstrate_learning_progression(self):
        """学習進行状況のデモンストレーション"""
        print("=== 学習進行状況デモンストレーション ===")
        
        # データ蓄積状況
        df = self.prediction_integration.load_cancellation_data()
        data_count = len(df)
        max_target = 500
        
        print(f"現在の蓄積データ数: {data_count}件 / 目標: {max_target}件")
        
        # 進捗バー表示
        if data_count > 0:
            progress = min(100, (data_count / max_target) * 100)
            bar_length = 30
            filled_length = int(bar_length * progress // 100)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            print(f"収集進捗: |{bar}| {progress:.1f}%")
        
        # データ収集完了チェック
        if data_count >= max_target:
            print("🎉 データ収集が完了しています！高精度予測システムが利用可能です。")
            
            # 完了レポート確認
            completion_report_file = self.monitoring_system.data_dir / "data_collection_completion_report.json"
            if completion_report_file.exists():
                print("✅ データ収集完了レポートが作成されています")
            else:
                print("ℹ️ 完了レポートを作成することをお勧めします")
        
        if data_count == 0:
            print("データが蓄積されていません。監視システムを実行してデータを収集してください。")
            return
        
        # 学習段階判定
        if data_count < 50:
            stage = "初期段階"
            description = "基本的な気象条件による予測のみ"
        elif data_count < 200:
            stage = "学習段階"
            description = "実績データによる予測精度向上開始"
        elif data_count < 500:
            stage = "成熟段階"
            description = "高精度な季節・航路別予測"
        else:
            stage = "完成段階"
            description = "最適化された予測システム"
        
        print(f"学習段階: {stage}")
        print(f"予測能力: {description}")
        
        # 精度向上予測
        if data_count >= 50:
            accuracy_report = self.prediction_integration.generate_accuracy_report()
            print("\n精度レポート:")
            print(json.dumps(accuracy_report, ensure_ascii=False, indent=2))
        
        # 推奨アクション
        print(f"\n推奨アクション:")
        if data_count < 50:
            print("- 監視システムを継続実行してデータを蓄積")
            print("- 最低50件のデータ蓄積で機械学習開始可能")
        elif data_count < 200:
            print("- 機械学習モデルの訓練と評価")
            print("- 予測精度の定期確認")
        else:
            print("- 定期的なモデル再訓練")
            print("- 季節変動に応じた調整")

def main():
    """メイン実行"""
    runner = IntegratedPredictionRunner()
    
    print("統合予測システムを開始します...\n")
    
    # 学習進行状況確認
    runner.demonstrate_learning_progression()
    
    print("\n" + "="*50)
    
    # 選択メニュー
    print("実行オプションを選択してください:")
    print("1. 完全予測サイクル実行（推奨）")
    print("2. 監視システムのみ実行")
    print("3. 学習システムのみ実行")
    print("4. 精度レポートのみ表示")
    
    try:
        choice = input("選択 (1-4): ").strip()
        
        if choice == "1":
            # 完全予測サイクル
            route = input("航路を選択 (wakkanai_oshidomari/wakkanai_kutsugata/wakkanai_kafuka) [wakkanai_oshidomari]: ").strip()
            if not route:
                route = "wakkanai_oshidomari"
            
            result = asyncio.run(runner.run_full_prediction_cycle(route))
            print(f"\n実行完了: {datetime.now()}")
            
        elif choice == "2":
            # 監視システムのみ
            print("監視システムを開始します...")
            asyncio.run(runner.monitoring_system.monitor_all_routes())
            
        elif choice == "3":
            # 学習システムのみ
            print("学習システムを実行します...")
            runner.prediction_integration.update_model_with_new_data()
            
        elif choice == "4":
            # 精度レポートのみ
            print("精度レポートを表示します...")
            metrics = runner.ferry_engine.get_prediction_accuracy_metrics()
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
            
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n実行を中断しました")
    except Exception as e:
        print(f"実行中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()