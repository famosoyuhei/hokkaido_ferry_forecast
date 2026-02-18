#!/usr/bin/env python3
"""
Improved risk calculation with seasonal adjustment

Current issues:
1. Wind speed thresholds too high for winter
2. No seasonal adjustment (winter is harsher)
3. Fixed thresholds don't account for ferry operator's conservative approach

Proposed improvements:
1. Lower thresholds for winter months (Dec-Mar)
2. Add seasonal multiplier
3. More aggressive risk scoring in winter
"""

from typing import Tuple, List, Optional
from datetime import datetime
import pytz

def calculate_cancellation_risk_improved(wind_speed: float, wave_height: float,
                                visibility: Optional[float] = None,
                                forecast_date: Optional[str] = None) -> Tuple[str, float, List[str]]:
    """
    Calculate cancellation risk with seasonal adjustment

    Args:
        wind_speed: Wind speed in m/s
        wave_height: Wave height in meters
        visibility: Visibility in km (optional)
        forecast_date: Date string 'YYYY-MM-DD' (optional, defaults to today)

    Returns:
        (risk_level, risk_score, risk_factors)
    """

    risk_score = 0
    risk_factors = []

    # Determine if it's winter season (Dec-Mar) for seasonal adjustment
    is_winter = False
    if forecast_date:
        try:
            date_obj = datetime.strptime(forecast_date, '%Y-%m-%d')
            month = date_obj.month
            is_winter = month in [12, 1, 2, 3]
        except:
            pass
    else:
        jst = pytz.timezone('Asia/Tokyo')
        month = datetime.now(jst).month
        is_winter = month in [12, 1, 2, 3]

    # Seasonal multiplier (winter is 1.2x, summer is 1.0x)
    seasonal_multiplier = 1.2 if is_winter else 1.0

    # Wind speed risk (LOWERED thresholds for winter)
    # Winter: Even 12m/s wind is risky
    # Summer: 15m/s wind is acceptable
    winter_wind_thresholds = {
        30: (70, "Extreme wind"),
        25: (60, "Very dangerous wind"),
        20: (50, "Very strong wind"),
        15: (35, "Strong wind"),
        12: (25, "Moderate-strong wind"),  # NEW: Winter specific
        8: (15, "Moderate wind"),  # NEW: Winter specific
    }

    summer_wind_thresholds = {
        35: (70, "Extreme wind"),
        30: (60, "Very dangerous wind"),
        25: (50, "Very strong wind"),
        20: (35, "Strong wind"),
        15: (20, "Moderate wind"),
        10: (10, "Light wind"),
    }

    thresholds = winter_wind_thresholds if is_winter else summer_wind_thresholds

    for threshold in sorted(thresholds.keys(), reverse=True):
        if wind_speed >= threshold:
            score, label = thresholds[threshold]
            risk_score += score
            risk_factors.append(f"{label} ({wind_speed:.1f} m/s)")
            break

    # Wave height risk (also adjusted for season)
    if is_winter:
        # Winter: Even 1.5m waves are risky
        if wave_height >= 4.0:
            risk_score += 45
            risk_factors.append(f"Very high waves ({wave_height:.1f} m)")
        elif wave_height >= 3.0:
            risk_score += 35
            risk_factors.append(f"High waves ({wave_height:.1f} m)")
        elif wave_height >= 2.0:
            risk_score += 20
            risk_factors.append(f"Moderate-high waves ({wave_height:.1f} m)")
        elif wave_height >= 1.5:
            risk_score += 10
            risk_factors.append(f"Moderate waves ({wave_height:.1f} m)")
    else:
        # Summer: Standard thresholds
        if wave_height >= 4.0:
            risk_score += 40
            risk_factors.append(f"Very high waves ({wave_height:.1f} m)")
        elif wave_height >= 3.0:
            risk_score += 30
            risk_factors.append(f"High waves ({wave_height:.1f} m)")
        elif wave_height >= 2.0:
            risk_score += 15
            risk_factors.append(f"Moderate waves ({wave_height:.1f} m)")

    # Visibility risk (same for all seasons)
    if visibility is not None:
        if visibility < 1.0:
            risk_score += 20
            risk_factors.append(f"Very poor visibility ({visibility:.1f} km)")
        elif visibility < 3.0:
            risk_score += 10
            risk_factors.append(f"Poor visibility ({visibility:.1f} km)")

    # Apply seasonal multiplier
    risk_score = risk_score * seasonal_multiplier

    # Determine risk level (LOWERED thresholds)
    # Before: HIGH>=70, MEDIUM>=40, LOW>=20
    # After: HIGH>=60, MEDIUM>=35, LOW>=15 (more conservative)
    if risk_score >= 60:
        risk_level = "HIGH"
    elif risk_score >= 35:
        risk_level = "MEDIUM"
    elif risk_score >= 15:
        risk_level = "LOW"
    else:
        risk_level = "MINIMAL"

    season_tag = "[WINTER]" if is_winter else "[SUMMER]"

    return risk_level, risk_score, [season_tag] + risk_factors


# Test cases
if __name__ == '__main__':
    print("Testing improved risk calculation")
    print("=" * 80)

    # Test case 1: 2026-02-16 scenario (LOW predicted, but actually cancelled)
    # Assume: wind 12m/s, wave 1.8m
    print("\nTest 1: Winter, wind 12m/s, wave 1.8m")
    risk, score, factors = calculate_cancellation_risk_improved(
        wind_speed=12.0,
        wave_height=1.8,
        visibility=15.0,
        forecast_date='2026-02-16'
    )
    print(f"  Risk: {risk}, Score: {score:.1f}")
    print(f"  Factors: {factors}")
    print(f"  Expected: MEDIUM (before would be LOW)")

    # Test case 2: Extreme winter conditions
    print("\nTest 2: Winter, wind 25m/s, wave 3.5m")
    risk, score, factors = calculate_cancellation_risk_improved(
        wind_speed=25.0,
        wave_height=3.5,
        visibility=5.0,
        forecast_date='2026-02-16'
    )
    print(f"  Risk: {risk}, Score: {score:.1f}")
    print(f"  Factors: {factors}")
    print(f"  Expected: HIGH")

    # Test case 3: Summer, same conditions
    print("\nTest 3: Summer, wind 12m/s, wave 1.8m")
    risk, score, factors = calculate_cancellation_risk_improved(
        wind_speed=12.0,
        wave_height=1.8,
        visibility=15.0,
        forecast_date='2026-07-15'
    )
    print(f"  Risk: {risk}, Score: {score:.1f}")
    print(f"  Factors: {factors}")
    print(f"  Expected: LOW or MINIMAL")
