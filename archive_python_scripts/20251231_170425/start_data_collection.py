#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Data Collection Starter
シンプルなデータ収集開始スクリプト
"""

import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

def generate_sample_data():
    """サンプルデータ生成（実際の気象・運航データの代替）"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    csv_file = data_dir / "ferry_cancellation_log.csv"
    
    print("Starting data collection simulation...")
    
    # CSVヘッダー
    if not csv_file.exists():
        df = pd.DataFrame(columns=[
            'timestamp', 'route', 'scheduled_departure', 'actual_departure',
            'cancelled', 'wind_speed', 'wave_height', 'visibility', 'temperature'
        ])
        df.to_csv(csv_file, index=False)
        print("Created CSV file with headers")
    
    # サンプルデータ追加
    routes = ['wakkanai_oshidomari', 'wakkanai_kutsugata', 'wakkanai_kafuka']
    
    for i in range(10):  # 10件のサンプルデータ
        now = datetime.now() - timedelta(hours=i)
        route = random.choice(routes)
        
        # 気象条件をランダム生成
        wind_speed = random.uniform(5, 25)  # 5-25 m/s
        wave_height = random.uniform(1, 5)  # 1-5 m
        visibility = random.uniform(0.5, 10)  # 0.5-10 km
        temperature = random.uniform(-15, 15)  # -15-15°C
        
        # 欠航判定（簡単なルール）
        cancelled = (wind_speed > 20 or wave_height > 4 or visibility < 1 or temperature < -10)
        
        # データ行作成
        new_row = {
            'timestamp': now.isoformat(),
            'route': route,
            'scheduled_departure': (now + timedelta(hours=1)).strftime('%H:%M'),
            'actual_departure': '' if cancelled else (now + timedelta(hours=1, minutes=5)).strftime('%H:%M'),
            'cancelled': cancelled,
            'wind_speed': round(wind_speed, 1),
            'wave_height': round(wave_height, 1),
            'visibility': round(visibility, 1),
            'temperature': round(temperature, 1)
        }
        
        # CSV追加
        df = pd.read_csv(csv_file)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(csv_file, index=False)
        
        status = "CANCELLED" if cancelled else "OPERATED"
        print(f"Added data #{i+1}: {route} - {status} (Wind: {wind_speed:.1f}m/s, Wave: {wave_height:.1f}m)")
        
        time.sleep(0.5)  # 短い間隔でデータ追加
    
    print(f"\nData collection completed! {len(df)} records total.")
    
    # 統計表示
    df = pd.read_csv(csv_file)
    total_records = len(df)
    cancelled_count = df['cancelled'].sum()
    cancellation_rate = (cancelled_count / total_records * 100) if total_records > 0 else 0
    
    print(f"Statistics:")
    print(f"- Total records: {total_records}")
    print(f"- Cancelled operations: {cancelled_count}")
    print(f"- Cancellation rate: {cancellation_rate:.1f}%")
    
    return {
        "total_records": total_records,
        "cancelled_count": int(cancelled_count),
        "cancellation_rate": cancellation_rate
    }

def main():
    """メイン実行"""
    print("=== Ferry Data Collection System ===")
    
    # データ収集実行
    result = generate_sample_data()
    
    print(f"\nData collection successful!")
    print(f"Check data/ferry_cancellation_log.csv for collected data")

if __name__ == "__main__":
    main()