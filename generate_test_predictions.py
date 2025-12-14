#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Test Prediction Data
Creates realistic prediction data for testing the accuracy improvement system
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import numpy as np
from datetime import datetime, timedelta
import random

def generate_test_predictions(days_back=30):
    """Generate test prediction data for the last N days"""

    print("="*80)
    print("GENERATING TEST PREDICTION DATA")
    print("="*80)

    import os
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    forecast_db = os.path.join(data_dir, "ferry_weather_forecast.db")

    conn = sqlite3.connect(forecast_db)
    cursor = conn.cursor()

    routes = [
        'wakkanai_oshidomari',
        'oshidomari_wakkanai',
        'wakkanai_kafuka',
        'kafuka_wakkanai',
        'oshidomari_kafuka',
        'kafuka_oshidomari'
    ]

    # Generate predictions for last N days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)

    generated_count = 0

    for day_offset in range(days_back + 1):
        forecast_date = end_date - timedelta(days=day_offset)

        for route in routes:
            # Generate realistic weather conditions
            # Base conditions with some randomness
            wind_speed = random.uniform(5, 25)
            wave_height = random.uniform(0.5, 4.5)
            visibility = random.uniform(1, 15)
            temperature = random.uniform(-5, 20)

            # Calculate risk based on conditions
            wind_risk = min(100, (wind_speed / 15) * 100)
            wave_risk = min(100, (wave_height / 3) * 100)
            vis_risk = max(0, (1 - visibility / 10) * 100)

            risk_score = (wind_risk * 0.4 + wave_risk * 0.35 + vis_risk * 0.15 + 10)

            # Determine risk level
            if risk_score >= 70:
                risk_level = 'HIGH'
            elif risk_score >= 40:
                risk_level = 'MEDIUM'
            elif risk_score >= 20:
                risk_level = 'LOW'
            else:
                risk_level = 'MINIMAL'

            # Recommendation
            if risk_level == 'HIGH':
                recommendation = "欠航の可能性が高い。運航状況を確認してください。"
            elif risk_level == 'MEDIUM':
                recommendation = "運航に注意が必要。遅延の可能性があります。"
            elif risk_level == 'LOW':
                recommendation = "通常運航が見込まれますが、気象状況に注意してください。"
            else:
                recommendation = "安全な運航が見込まれます。"

            confidence = random.uniform(0.75, 0.95)

            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO cancellation_forecast (
                        forecast_for_date, forecast_hour, route,
                        risk_level, risk_score, risk_factors,
                        wind_forecast, wave_forecast, visibility_forecast, temperature_forecast,
                        recommended_action, confidence, generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    forecast_date.isoformat(), 8, route,
                    risk_level, risk_score,
                    f"風速: {wind_speed:.1f}m/s, 波高: {wave_height:.1f}m, 視界: {visibility:.1f}km",
                    wind_speed, wave_height, visibility, temperature,
                    recommendation, confidence, datetime.now().isoformat()
                ))
                generated_count += 1
            except Exception as e:
                print(f"Error inserting {forecast_date} {route}: {e}")

    conn.commit()
    conn.close()

    print(f"✓ Generated {generated_count} test predictions for {days_back} days")
    print(f"  Date range: {start_date} to {end_date}")
    print("="*80)

if __name__ == '__main__':
    generate_test_predictions(days_back=30)
