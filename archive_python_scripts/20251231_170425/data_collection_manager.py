#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データ収集管理システム
Data Collection Management System

500件上限での自動停止機能と収集状況管理
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DataCollectionManager:
    """データ収集管理クラス"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.csv_file = data_dir / "ferry_cancellation_log.csv"
        self.status_file = data_dir / "collection_status.json"
        self.completion_report_file = data_dir / "data_collection_completion_report.json"
        
        # デフォルト設定
        self.default_max_count = 500
        self.warning_threshold = 0.9  # 90%で警告
        
    def get_current_status(self) -> dict:
        """現在の収集状況取得"""
        try:
            # 現在のデータ数
            current_count = self._get_current_data_count()
            
            # 設定読み込み
            settings = self._load_settings()
            max_count = settings.get("max_count", self.default_max_count)
            
            # 進捗計算
            progress = (current_count / max_count) * 100 if max_count > 0 else 0
            
            # ステータス判定
            if current_count >= max_count:
                status = "COMPLETED"
                message = "データ収集が完了しています"
            elif current_count >= max_count * self.warning_threshold:
                status = "NEAR_COMPLETION"
                remaining = max_count - current_count
                message = f"まもなく完了（残り{remaining}件）"
            elif current_count >= 50:
                status = "LEARNING_ACTIVE"
                message = "機械学習による予測が利用可能です"
            elif current_count > 0:
                status = "COLLECTING"
                message = "データ収集中"
            else:
                status = "NOT_STARTED"
                message = "データ収集未開始"
            
            return {
                "current_count": current_count,
                "max_count": max_count,
                "progress_percentage": round(progress, 1),
                "status": status,
                "message": message,
                "auto_stop_enabled": settings.get("auto_stop_enabled", True),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"収集状況取得でエラー: {e}")
            return {"error": str(e)}
    
    def _get_current_data_count(self) -> int:
        """現在のデータ件数取得"""
        try:
            if not self.csv_file.exists():
                return 0
            
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            return len(df)
            
        except Exception as e:
            logger.error(f"データ件数取得でエラー: {e}")
            return 0
    
    def _load_settings(self) -> dict:
        """設定読み込み"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # デフォルト設定
                return {
                    "max_count": self.default_max_count,
                    "auto_stop_enabled": True,
                    "created_at": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"設定読み込みでエラー: {e}")
            return {"max_count": self.default_max_count, "auto_stop_enabled": True}
    
    def update_settings(self, max_count: int = None, auto_stop_enabled: bool = None):
        """設定更新"""
        try:
            settings = self._load_settings()
            
            if max_count is not None:
                settings["max_count"] = max_count
                
            if auto_stop_enabled is not None:
                settings["auto_stop_enabled"] = auto_stop_enabled
                
            settings["updated_at"] = datetime.now().isoformat()
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
                
            logger.info(f"設定を更新しました: max_count={settings['max_count']}, auto_stop={settings['auto_stop_enabled']}")
            
        except Exception as e:
            logger.error(f"設定更新でエラー: {e}")
    
    def should_stop_collection(self) -> bool:
        """収集停止判定"""
        try:
            status = self.get_current_status()
            return (status.get("auto_stop_enabled", True) and 
                   status.get("status") == "COMPLETED")
        except:
            return False
    
    def create_final_report(self) -> dict:
        """最終レポート作成"""
        try:
            if not self.csv_file.exists():
                return {"error": "データファイルが存在しません"}
            
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            
            # 統計計算
            total_records = len(df)
            
            # 日付変換
            df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
            
            # 運航状況別集計
            cancellation_count = len(df[df['運航状況'] == '欠航'])
            delay_count = len(df[df['運航状況'] == '遅延'])
            normal_count = len(df[df['運航状況'].isin(['通常運航', '通常'])])
            
            # 期間計算
            start_date = df['日付'].min()
            end_date = df['日付'].max()
            
            # 航路別集計
            route_stats = {}
            for route in ['鴛泊港', '沓形港', '香深港']:
                route_data = df[df['着場所'].str.contains(route, na=False)]
                if len(route_data) > 0:
                    route_stats[route] = {
                        "total": len(route_data),
                        "cancellations": len(route_data[route_data['運航状況'] == '欠航']),
                        "cancellation_rate": len(route_data[route_data['運航状況'] == '欠航']) / len(route_data) * 100
                    }
            
            # 月別集計
            df['月'] = df['日付'].dt.month
            monthly_stats = df.groupby('月').size().to_dict()
            
            # 気象条件統計
            weather_stats = {}
            for col in ['風速_ms', '波高_m', '視界_km', '気温_c']:
                if col in df.columns:
                    weather_stats[col] = {
                        "平均": float(df[col].mean()) if df[col].notna().any() else None,
                        "最大": float(df[col].max()) if df[col].notna().any() else None,
                        "最小": float(df[col].min()) if df[col].notna().any() else None
                    }
            
            report = {
                "completion_time": datetime.now().isoformat(),
                "data_summary": {
                    "total_records": total_records,
                    "data_period": {
                        "start": start_date.isoformat() if pd.notna(start_date) else None,
                        "end": end_date.isoformat() if pd.notna(end_date) else None,
                        "duration_days": (end_date - start_date).days if pd.notna(start_date) and pd.notna(end_date) else None
                    }
                },
                "operation_statistics": {
                    "cancellation_count": cancellation_count,
                    "delay_count": delay_count,
                    "normal_count": normal_count,
                    "cancellation_rate_percent": round((cancellation_count / total_records * 100), 2) if total_records > 0 else 0
                },
                "route_statistics": route_stats,
                "monthly_distribution": monthly_stats,
                "weather_statistics": weather_stats,
                "system_readiness": {
                    "machine_learning_ready": total_records >= 50,
                    "high_accuracy_ready": total_records >= 200,
                    "optimal_system_ready": total_records >= 500,
                    "prediction_confidence_level": "高" if total_records >= 500 else "中" if total_records >= 200 else "低" if total_records >= 50 else "不可"
                },
                "recommendations": self._generate_final_recommendations(total_records, cancellation_count, route_stats)
            }
            
            # レポート保存
            with open(self.completion_report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"最終レポートを作成しました: {self.completion_report_file}")
            
            return report
            
        except Exception as e:
            logger.error(f"最終レポート作成でエラー: {e}")
            return {"error": str(e)}
    
    def _generate_final_recommendations(self, total_records: int, cancellation_count: int, route_stats: dict) -> list:
        """最終推奨事項生成"""
        recommendations = []
        
        if total_records >= 500:
            recommendations.append("✅ 高精度予測システムの運用が可能です")
            recommendations.append("📊 定期的なモデル再訓練（月1回程度）を実施してください")
        elif total_records >= 200:
            recommendations.append("✅ 実用的な予測システムが利用可能です")
            recommendations.append("📈 さらなる精度向上のため継続的なデータ収集を推奨")
        elif total_records >= 50:
            recommendations.append("⚠️ 基本的な予測は可能ですが、精度向上のためより多くのデータが必要です")
        else:
            recommendations.append("❌ 予測システム運用には不十分なデータ量です")
        
        # 欠航率チェック
        if total_records > 0:
            cancellation_rate = (cancellation_count / total_records) * 100
            if cancellation_rate > 20:
                recommendations.append(f"⚠️ 欠航率が高いです（{cancellation_rate:.1f}%）。気象条件の詳細分析を推奨")
            elif cancellation_rate < 5:
                recommendations.append("ℹ️ 比較的安定した運航状況です。予測精度の維持に注力してください")
        
        # 航路別推奨
        if route_stats:
            max_cancellation_route = max(route_stats.items(), key=lambda x: x[1]['cancellation_rate'])
            if max_cancellation_route[1]['cancellation_rate'] > 15:
                recommendations.append(f"🔍 {max_cancellation_route[0]}航路の欠航率が高いため、個別対策を検討してください")
        
        return recommendations
    
    def display_progress_bar(self, current: int, total: int, width: int = 50) -> str:
        """進捗バー表示用文字列生成"""
        if total == 0:
            return "[" + "-" * width + "] 0.0%"
        
        progress = current / total
        filled_width = int(width * progress)
        bar = "█" * filled_width + "-" * (width - filled_width)
        percentage = progress * 100
        
        return f"[{bar}] {percentage:.1f}% ({current}/{total})"

def main():
    """テスト実行"""
    from pathlib import Path
    
    data_dir = Path(__file__).parent / "data"
    manager = DataCollectionManager(data_dir)
    
    print("=== Data Collection Management System ===")
    
    # 現在状況確認
    status = manager.get_current_status()
    print("Current data collection status:")
    print(json.dumps(status, ensure_ascii=True, indent=2))
    
    # 進捗バー表示
    if status.get("current_count", 0) > 0:
        progress_bar = manager.display_progress_bar(
            status["current_count"], 
            status["max_count"]
        )
        print(f"\nProgress: {progress_bar}")
    
    # 完了時の最終レポート作成
    if status.get("status") == "COMPLETED":
        print("\nCreating final report...")
        final_report = manager.create_final_report()
        if "error" not in final_report:
            print("Final report created successfully")
            print("Main statistics:")
            print(f"- Total records: {final_report['data_summary']['total_records']}")
            print(f"- Cancellations: {final_report['operation_statistics']['cancellation_count']}")
            print(f"- Cancellation rate: {final_report['operation_statistics']['cancellation_rate_percent']}%")

if __name__ == "__main__":
    main()