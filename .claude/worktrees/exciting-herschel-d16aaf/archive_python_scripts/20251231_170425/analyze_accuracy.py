#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フェリー欠航予報システム精度分析
Ferry Cancellation Prediction System Accuracy Analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

def analyze_ferry_prediction_accuracy():
    """フェリー予測精度分析"""
    
    print("=== Ferry Cancellation Prediction Accuracy Analysis ===")
    
    # データファイル確認
    data_file = "data/ferry_cancellation_log.csv"
    old_data_file = "data/ferry_cancellation_log_old.csv"
    
    if not os.path.exists(data_file):
        print("Error: Current data file not found")
        return
    
    # 現在のデータ読み込み
    try:
        df = pd.read_csv(data_file, encoding='utf-8')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"Current data records: {len(df)}")
    except Exception as e:
        print(f"Error reading current data: {e}")
        return
    
    # 旧データ読み込み（比較用）
    old_df = None
    if os.path.exists(old_data_file):
        try:
            old_df = pd.read_csv(old_data_file, encoding='utf-8')
            if 'timestamp' in old_df.columns:
                old_df['timestamp'] = pd.to_datetime(old_df['timestamp'])
            print(f"Historical data records: {len(old_df)}")
        except Exception as e:
            print(f"Warning: Could not read historical data: {e}")
    
    # === 基本統計 ===
    print("\n=== Basic Statistics ===")
    
    # 運航状況統計
    if '運航状況' in df.columns:
        status_counts = df['運航状況'].value_counts()
        print("Operation Status:")
        for status, count in status_counts.items():
            print(f"  {status}: {count} ({count/len(df)*100:.1f}%)")
    
    # boolean形式の欠航フラグ統計
    if 'cancelled' in df.columns:
        total_routes = len(df)
        cancellations = df['cancelled'].sum()
        normal_operations = total_routes - cancellations
        print(f"\nCancellation Statistics:")
        print(f"  Total routes: {total_routes}")
        print(f"  Cancelled: {cancellations} ({cancellations/total_routes*100:.1f}%)")
        print(f"  Normal operation: {normal_operations} ({normal_operations/total_routes*100:.1f}%)")
    
    # === 時系列分析 ===
    print("\n=== Time Series Analysis ===")
    
    # 日別欠航率
    if 'timestamp' in df.columns and 'cancelled' in df.columns:
        df['date'] = df['timestamp'].dt.date
        daily_stats = df.groupby('date').agg({
            'cancelled': ['sum', 'count']
        })
        daily_stats.columns = ['cancellations', 'total']
        daily_stats['cancellation_rate'] = (daily_stats['cancellations'] / daily_stats['total'] * 100).round(2)
        
        print("Daily Cancellation Rate (Last 10 days):")
        for date, row in daily_stats.tail(10).iterrows():
            print(f"  {date}: {row['cancellation_rate']:.1f}% ({row['cancellations']}/{row['total']})")
    
    # === 気象条件分析 ===
    print("\n=== Weather Condition Analysis ===")
    
    if all(col in df.columns for col in ['cancelled', 'wind_speed', 'wave_height', 'visibility', 'temperature']):
        cancelled_data = df[df['cancelled'] == True]
        normal_data = df[df['cancelled'] == False]
        
        if len(cancelled_data) > 0:
            print("Weather conditions during cancellations:")
            print(f"  Wind speed: {cancelled_data['wind_speed'].mean():.1f} m/s (avg)")
            print(f"  Wave height: {cancelled_data['wave_height'].mean():.1f} m (avg)")
            print(f"  Visibility: {cancelled_data['visibility'].mean():.1f} km (avg)")
            print(f"  Temperature: {cancelled_data['temperature'].mean():.1f} °C (avg)")
        
        if len(normal_data) > 0:
            print("Weather conditions during normal operations:")
            print(f"  Wind speed: {normal_data['wind_speed'].mean():.1f} m/s (avg)")
            print(f"  Wave height: {normal_data['wave_height'].mean():.1f} m (avg)")
            print(f"  Visibility: {normal_data['visibility'].mean():.1f} km (avg)")
            print(f"  Temperature: {normal_data['temperature'].mean():.1f} °C (avg)")
    
    # === 欠航理由分析 ===
    print("\n=== Cancellation Reason Analysis ===")
    
    if '欠航理由' in df.columns:
        reasons = df[df['cancelled'] == True]['欠航理由'].value_counts()
        print("Cancellation reasons:")
        for reason, count in reasons.items():
            if pd.notna(reason):
                print(f"  {reason}: {count}")
    
    # === 航路別分析 ===
    print("\n=== Route-wise Analysis ===")
    
    if 'route' in df.columns and 'cancelled' in df.columns:
        route_stats = df.groupby('route').agg({
            'cancelled': ['sum', 'count']
        })
        route_stats.columns = ['cancellations', 'total']
        route_stats['cancellation_rate'] = (route_stats['cancellations'] / route_stats['total'] * 100).round(2)
        
        print("Cancellation rate by route:")
        for route, row in route_stats.iterrows():
            print(f"  {route}: {row['cancellation_rate']:.1f}% ({row['cancellations']}/{row['total']})")
    
    # === 精度改善分析 ===
    print("\n=== Accuracy Improvement Analysis ===")
    
    # データ期間
    if 'timestamp' in df.columns:
        start_date = df['timestamp'].min()
        end_date = df['timestamp'].max()
        print(f"Analysis period: {start_date.date()} to {end_date.date()}")
        
        # 週別改善トレンド
        df['week'] = df['timestamp'].dt.isocalendar().week
        weekly_stats = df.groupby('week').agg({
            'cancelled': ['sum', 'count']
        })
        weekly_stats.columns = ['cancellations', 'total']
        weekly_stats['cancellation_rate'] = (weekly_stats['cancellations'] / weekly_stats['total'] * 100).round(2)
        
        # トレンド分析
        if len(weekly_stats) >= 2:
            first_week_rate = weekly_stats['cancellation_rate'].iloc[0]
            last_week_rate = weekly_stats['cancellation_rate'].iloc[-1]
            trend = last_week_rate - first_week_rate
            
            print(f"Cancellation rate trend:")
            print(f"  First week: {first_week_rate:.1f}%")
            print(f"  Latest week: {last_week_rate:.1f}%")
            print(f"  Trend: {trend:+.1f}% {'(improving)' if trend < 0 else '(needs attention)' if trend > 0 else '(stable)'}")
    
    # === 予測精度メトリクス ===
    print("\n=== Prediction Accuracy Metrics ===")
    
    # 実際の予測精度を評価するにはground truthとの比較が必要
    # 現在のデータは運航実績のため、ここでは基本的な統計のみ提供
    
    if 'cancelled' in df.columns:
        # 基準値との比較（風速15m/s以上での欠航率など）
        high_wind_data = df[df['wind_speed'] >= 15.0] if 'wind_speed' in df.columns else pd.DataFrame()
        high_wave_data = df[df['wave_height'] >= 3.0] if 'wave_height' in df.columns else pd.DataFrame()
        
        if len(high_wind_data) > 0:
            high_wind_cancellation_rate = (high_wind_data['cancelled'].sum() / len(high_wind_data) * 100)
            print(f"Cancellation rate in high wind conditions (>=15 m/s): {high_wind_cancellation_rate:.1f}%")
        
        if len(high_wave_data) > 0:
            high_wave_cancellation_rate = (high_wave_data['cancelled'].sum() / len(high_wave_data) * 100)
            print(f"Cancellation rate in high wave conditions (>=3.0 m): {high_wave_cancellation_rate:.1f}%")
    
    # === 改善提案 ===
    print("\n=== Improvement Recommendations ===")
    
    recommendations = []
    
    # データ量チェック
    if len(df) < 100:
        recommendations.append("More historical data needed for robust analysis")
    
    # 欠航率チェック
    if 'cancelled' in df.columns:
        overall_cancellation_rate = df['cancelled'].sum() / len(df) * 100
        if overall_cancellation_rate > 20:
            recommendations.append("High cancellation rate - consider adjusting thresholds")
        elif overall_cancellation_rate < 5:
            recommendations.append("Low cancellation rate - system may be too conservative")
    
    # 気象条件閾値の見直し
    if len(cancelled_data) > 0 and 'wind_speed' in cancelled_data.columns:
        avg_wind_at_cancellation = cancelled_data['wind_speed'].mean()
        if avg_wind_at_cancellation < 12:
            recommendations.append("Consider lowering wind speed thresholds")
        elif avg_wind_at_cancellation > 18:
            recommendations.append("Consider raising wind speed thresholds")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
    else:
        print("  System performance appears to be within acceptable parameters")
    
    print("\n=== Analysis Complete ===")

if __name__ == "__main__":
    analyze_ferry_prediction_accuracy()