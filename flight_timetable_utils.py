#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flight_timetable_utils.py — 利尻空港の時刻表ユーティリティ

jst_utils.py のフェリー版に相当する飛行機専用モジュール。
rishiri_flight_{year}_timetable.json を参照し、指定日の就航便リストを返す。

設計原則（AGENTS.md ルール19〜23）:
  - 年ハードコード禁止: year 変数 + glob フォールバック
  - 滑走路は RWY07/25（070°）、南北方向（01/19）と混同しない
  - HAC通年 / ANA夏季（6/1〜9/30）を日付で動的判定
  - flight_routes をハードコードしない
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 利尻空港 RWY07 の方位（度）。変更するときはここだけ変える。
RUNWAY_HEADING_DEG = 70

# 参照ディレクトリ
_REF_DIR = Path(__file__).parent / 'skills' / 'ferry-cancellation-research' / 'references'

# タイムテーブルキャッシュ（年→JSON dict）
_timetable_cache: Dict[int, dict] = {}


# ---------------------------------------------------------------------------
# 時刻表ロード
# ---------------------------------------------------------------------------

def _load_timetable(year: int) -> dict:
    """
    rishiri_flight_{year}_timetable.json を読み込む。
    見つからない場合は最新年のファイルにフォールバックする。
    """
    if year in _timetable_cache:
        return _timetable_cache[year]

    path = _REF_DIR / f'rishiri_flight_{year}_timetable.json'
    if not path.exists():
        candidates = sorted(_REF_DIR.glob('rishiri_flight_????_timetable.json'), reverse=True)
        if not candidates:
            _timetable_cache[year] = {}
            return {}
        path = candidates[0]

    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    _timetable_cache[year] = data
    return data


def _find_schedule(date_str: str) -> Optional[dict]:
    """date_str（YYYY-MM-DD）に該当するスケジュール期間を返す。"""
    year = int(date_str[:4])
    timetable = _load_timetable(year)
    for schedule in timetable.get('schedules', []):
        if schedule['start_date'] <= date_str <= schedule['end_date']:
            return schedule
    return None


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def get_active_flights_on(date_str: str) -> List[Dict]:
    """
    date_str（YYYY-MM-DD）の就航便リストを返す。

    戻り値の各要素:
        {
            'route_key':    str,   # 'okd_ris' など
            'departure':    str,   # '07:50'
            'arrival':      str,   # '08:45'
            'flight_no':    str,   # 'JAL2783'
            'airline':      str,   # 'HAC' or 'ANA'
            'aircraft':     str,   # 'ATR42-600'
            'rishiri_time': str,   # 利尻空港側の時刻（到着 or 出発）
            'rishiri_role': str,   # 'arrival' or 'departure'
        }
    """
    schedule = _find_schedule(date_str)
    if not schedule:
        return []

    result = []
    for route_key, flights in schedule.get('flights', {}).items():
        for flight in flights:
            dep_time, arr_time = flight[0], flight[1]
            meta = flight[2] if len(flight) > 2 else {}

            # 利尻空港（RIS）側が到着か出発かを判定
            if route_key.endswith('_ris'):
                rishiri_time = arr_time
                rishiri_role = 'arrival'
            else:   # ris_*
                rishiri_time = dep_time
                rishiri_role = 'departure'

            result.append({
                'route_key':    route_key,
                'departure':    dep_time,
                'arrival':      arr_time,
                'flight_no':    meta.get('flight_no', ''),
                'airline':      meta.get('airline', ''),
                'aircraft':     meta.get('aircraft', ''),
                'rishiri_time': rishiri_time,
                'rishiri_role': rishiri_role,
            })

    return result


def get_rishiri_weather_hour(rishiri_time: str) -> int:
    """
    利尻空港での運航時刻（HH:MM）から、気象データ参照時間（整数 0-23）を返す。
    到着便は1時間前、出発便はその時刻を使う。
    """
    h = int(rishiri_time.split(':')[0])
    return max(0, h)


# ---------------------------------------------------------------------------
# 横風計算
# ---------------------------------------------------------------------------

def crosswind_component(wind_speed_ms: float, wind_dir_deg: float) -> float:
    """
    利尻空港 RWY07（方位070°）に対する横風成分を計算する（m/s）。

    Args:
        wind_speed_ms: 風速（m/s）
        wind_dir_deg:  風向き（気象台方式: 風が吹いてくる方向、度）

    Returns:
        横風成分の絶対値（m/s）

    Note:
        北風(360°) → 約94%が横風（最悪）
        南風(180°) → 約94%が横風（最悪）
        東風( 90°) → 約34%が横風（ほぼ向かい風）
        西風(270°) → 約34%が横風（ほぼ追い風）
    """
    angle = abs(RUNWAY_HEADING_DEG - wind_dir_deg) % 360
    if angle > 180:
        angle = 360 - angle
    return abs(wind_speed_ms * math.sin(math.radians(angle)))


def headwind_component(wind_speed_ms: float, wind_dir_deg: float) -> float:
    """
    向かい風成分を返す（負値は追い風）。
    RWY07（070°）への向かい風として計算する。
    """
    angle = abs(RUNWAY_HEADING_DEG - wind_dir_deg) % 360
    if angle > 180:
        angle = 360 - angle
    return wind_speed_ms * math.cos(math.radians(angle))


# ---------------------------------------------------------------------------
# リスク計算
# ---------------------------------------------------------------------------

def calculate_flight_risk(
    wind_speed: float,
    wind_dir: Optional[float],
    visibility: Optional[float],
    aircraft: str = 'ATR42-600',
) -> Tuple[str, float, List[str]]:
    """
    飛行機の欠航リスクを計算する。

    Args:
        wind_speed:  風速（m/s）
        wind_dir:    風向き（度）。None の場合は最悪横風と仮定。
        visibility:  視程（km）。None の場合は良好と仮定。
        aircraft:    機材種別（将来の機材別閾値拡張用）

    Returns:
        (risk_level, risk_score, risk_factors)
        risk_level: 'HIGH' / 'MEDIUM' / 'LOW' / 'MINIMAL'
        risk_score: 0〜100
        risk_factors: 判定根拠のリスト

    初期閾値（推定値 — 実データ30日分蓄積後に調整すること）:
        横風 >= 10 m/s → HIGH
        横風 >=  7 m/s → MEDIUM
        横風 >=  4 m/s → LOW
        視程 < 1.6 km  → HIGH（非精密進入 VOR/DME 最低値）
        視程 < 3.0 km  → MEDIUM
    """
    risk_score = 0.0
    risk_factors: List[str] = []

    # 横風成分の計算
    if wind_dir is not None:
        cw = crosswind_component(wind_speed, wind_dir)
    else:
        # 風向不明の場合は最悪ケース（北風 = 最大横風）と仮定
        cw = wind_speed * math.sin(math.radians(80))   # sin(80°) ≈ 0.985
        risk_factors.append('wind_dir unknown — assumed worst-case crosswind')

    if cw >= 10.0:
        risk_score += 60
        risk_factors.append(f'Crosswind {cw:.1f} m/s (≥10 m/s limit)')
    elif cw >= 7.0:
        risk_score += 35
        risk_factors.append(f'Crosswind {cw:.1f} m/s (≥7 m/s caution)')
    elif cw >= 4.0:
        risk_score += 15
        risk_factors.append(f'Crosswind {cw:.1f} m/s (≥4 m/s)')

    # 総風速が強い場合も加点（横風に加えて）
    if wind_speed >= 25:
        risk_score += 20
        risk_factors.append(f'Total wind {wind_speed:.1f} m/s (very strong)')
    elif wind_speed >= 18:
        risk_score += 10
        risk_factors.append(f'Total wind {wind_speed:.1f} m/s (strong)')

    # 視程リスク
    if visibility is not None:
        if visibility < 1.6:
            risk_score += 40
            risk_factors.append(f'Visibility {visibility:.1f} km (<1.6 km approach min)')
        elif visibility < 3.0:
            risk_score += 15
            risk_factors.append(f'Visibility {visibility:.1f} km (<3.0 km caution)')

    # リスクレベル判定
    if risk_score >= 60:
        risk_level = 'HIGH'
    elif risk_score >= 35:
        risk_level = 'MEDIUM'
    elif risk_score >= 15:
        risk_level = 'LOW'
    else:
        risk_level = 'MINIMAL'

    return risk_level, risk_score, risk_factors
