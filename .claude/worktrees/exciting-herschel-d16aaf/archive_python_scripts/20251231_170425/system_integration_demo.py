#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北海道フェリー予測システム統合デモ
Hokkaido Ferry Prediction System Integration Demo

全システムの連携動作を確認するデモンストレーション
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from ferry_forecast_ui import FerryForecastUI
from adaptive_prediction_system import AdaptivePredictionSystem
from data_collection_manager import DataCollectionManager

def main():
    """統合デモ実行"""
    print("=" * 80)
    print("🚢 北海道フェリー予測システム 統合デモ")
    print("=" * 80)
    
    # システム初期化
    ui_system = FerryForecastUI()
    
    print("\n🔄 システム初期化完了")
    print("📊 利用可能な機能:")
    print("  - 7日間運航予報表示")
    print("  - データ蓄積量に応じた適応的予測")
    print("  - 初期ルール → 機械学習への段階的移行")
    print("  - 実績データによる自動閾値調整")
    print("  - 500件上限での自動データ収集停止")
    
    # システム状況表示
    print("\n" + "-" * 40)
    print("📈 現在のシステム状況")
    print("-" * 40)
    
    prediction_params = ui_system.adaptive_system.get_current_prediction_parameters()
    data_count = prediction_params["data_count"]
    
    print(f"予測段階: {prediction_params['stage']}")
    print(f"データ数: {data_count}件")
    print(f"進捗: {prediction_params['progress']:.1%}")
    print(f"予測手法: {prediction_params['prediction_method']}")
    print(f"信頼度: {prediction_params['confidence_base']:.0%}")
    
    # 段階別説明
    stage_descriptions = {
        "stage_0": "初期段階（0-49件）: 気象条件ルールベース予測",
        "stage_1": "学習段階（50-199件）: ルールベース + 基本機械学習", 
        "stage_2": "成熟段階（200-499件）: ハイブリッド予測システム",
        "stage_3": "完成段階（500+件）: 高精度機械学習予測"
    }
    
    current_stage = prediction_params["stage_id"]
    print(f"段階詳細: {stage_descriptions.get(current_stage, '未定義')}")
    
    # 次のステップ案内
    if data_count < 50:
        next_goal = 50
        print(f"\n🎯 次の目標: {next_goal}件のデータ収集で機械学習開始")
    elif data_count < 200:
        next_goal = 200
        print(f"\n🎯 次の目標: {next_goal}件のデータ収集でハイブリッド予測開始")
    elif data_count < 500:
        next_goal = 500
        print(f"\n🎯 次の目標: {next_goal}件のデータ収集でシステム完成")
    else:
        print("\n🎉 システム完成！高精度予測が利用可能です")
    
    # 適応レポート表示
    print("\n" + "-" * 40)
    print("⚙️ 適応システムレポート")
    print("-" * 40)
    
    adaptation_report = ui_system.adaptive_system.generate_adaptation_report()
    if "error" not in adaptation_report:
        print(f"システム成熟度: {adaptation_report['system_maturity']}")
        print(f"適応調整回数: {adaptation_report['adaptation_history_count']}回")
        
        if adaptation_report.get('threshold_changes'):
            print("閾値調整状況:")
            for change in adaptation_report['threshold_changes'][:3]:  # 上位3件表示
                print(f"  - {change['condition']}:{change['level']}: {change['change_percent']:+.1f}%")
        
        print("推奨事項:")
        for recommendation in adaptation_report.get('recommendations', [])[:3]:
            print(f"  {recommendation}")
    
    # メニュー選択
    print("\n" + "=" * 80)
    print("実行オプション:")
    print("1. 7日間運航予報表示 🚢")
    print("2. システム詳細状況確認 📊") 
    print("3. 適応調整実行 ⚙️")
    print("4. 予報データJSON出力 💾")
    print("5. 全機能デモンストレーション 🎬")
    
    try:
        choice = input("選択 (1-5): ").strip()
        
        if choice == "1":
            print("\n7日間運航予報を表示します...")
            ui_system.display_7day_forecast()
            
        elif choice == "2":
            print("\nシステム詳細状況:")
            print(json.dumps(prediction_params, ensure_ascii=False, indent=2))
            
            print("\nデータ収集状況:")
            data_status = ui_system.data_manager.get_current_status()
            print(json.dumps(data_status, ensure_ascii=False, indent=2))
            
        elif choice == "3":
            print("\n適応調整を実行中...")
            if ui_system.adaptive_system.should_trigger_adaptation():
                result = ui_system.adaptive_system.apply_adaptive_adjustments()
                print("適応調整結果:")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("現在は適応調整不要です")
                
        elif choice == "4":
            print("\n予報データをJSON出力中...")
            ui_system.display_7day_forecast()
            ui_system.export_forecast_to_json()
            
        elif choice == "5":
            print("\n🎬 全機能デモンストレーション開始")
            demo_all_features(ui_system)
            
        else:
            print("無効な選択です")
            
    except KeyboardInterrupt:
        print("\n実行を中断しました")
    except Exception as e:
        print(f"実行エラー: {e}")

def demo_all_features(ui_system: FerryForecastUI):
    """全機能デモンストレーション"""
    print("\n" + "=" * 60)
    print("🎬 北海道フェリー予測システム 全機能デモ")
    print("=" * 60)
    
    # 1. システム初期化確認
    print("\n1️⃣ システム初期化状況")
    prediction_params = ui_system.adaptive_system.get_current_prediction_parameters()
    print(f"   予測段階: {prediction_params['stage']}")
    print(f"   データ数: {prediction_params['data_count']}件")
    
    # 2. 適応調整デモ
    print("\n2️⃣ 適応調整システム")
    if ui_system.adaptive_system.should_trigger_adaptation():
        print("   適応調整を実行中...")
        ui_system.adaptive_system.apply_adaptive_adjustments()
        print("   ✅ 適応調整完了")
    else:
        print("   ℹ️ 現在適応調整不要")
    
    # 3. 7日間予報デモ（簡略版）
    print("\n3️⃣ 7日間運航予報システム")
    print("   🚢 稚内 ⇔ 利尻・礼文島 3航路の予報生成")
    
    # 予報を1日分だけ表示（デモ用）
    services = ui_system.generate_7day_schedule()
    today_services = [s for s in services if s.date.date() == datetime.now().date()][:3]  # 本日3便のみ
    
    if today_services:
        print(f"   📅 {datetime.now().strftime('%Y年%m月%d日')} の予報例:")
        
        for service in today_services:
            forecast = asyncio.run(ui_system.generate_forecast_for_service(service))
            risk_icons = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}
            icon = risk_icons.get(forecast.risk_level, "❓")
            
            print(f"     {icon} {service.route_name} {service.departure_time}便: {forecast.risk_level}")
    
    # 4. データ収集管理デモ
    print("\n4️⃣ データ収集管理システム")
    data_status = ui_system.data_manager.get_current_status()
    current_count = data_status.get("current_count", 0)
    max_count = data_status.get("max_count", 500)
    progress = (current_count / max_count) * 100
    
    print(f"   📈 収集進捗: {current_count}/{max_count}件 ({progress:.1f}%)")
    
    if current_count >= max_count:
        print("   🎉 データ収集完了！高精度システム稼働中")
    elif current_count >= 50:
        print("   🤖 機械学習システム稼働中")
    else:
        print("   📊 初期データ収集中")
    
    # 5. 予測精度向上システムデモ
    print("\n5️⃣ 予測精度向上システム")
    adaptation_report = ui_system.adaptive_system.generate_adaptation_report()
    
    if "error" not in adaptation_report:
        print(f"   🎯 現在の精度: {adaptation_report['confidence_level']}")
        print(f"   ⚙️ 調整回数: {adaptation_report['adaptation_history_count']}回")
        
        if adaptation_report.get('threshold_changes'):
            print("   📊 閾値最適化例:")
            for change in adaptation_report['threshold_changes'][:2]:
                print(f"     - {change['condition']}: {change['change_percent']:+.1f}%調整")
    
    # 6. JSON出力デモ
    print("\n6️⃣ データ出力システム")
    print("   💾 JSON形式での予報データ出力")
    output_file = "demo_7day_forecast.json"
    ui_system.export_forecast_to_json(output_file)
    print(f"   ✅ {output_file} に出力完了")
    
    # デモ完了
    print("\n" + "=" * 60)
    print("🎊 全機能デモンストレーション完了")
    print("=" * 60)
    print("システムの主な特徴:")
    print("✅ データ蓄積に応じた自動的な予測精度向上")
    print("✅ 実績データによる自動閾値調整")
    print("✅ 初期ルール → 機械学習への段階的移行")
    print("✅ 7日間詳細運航予報")
    print("✅ 500件上限での自動データ収集停止")
    print("\n🚀 北海道フェリー予測システムの運用準備完了！")

if __name__ == "__main__":
    main()