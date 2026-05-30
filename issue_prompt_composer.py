#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Issue Prompt Composer
精度監査結果から修正依頼プロンプトを生成する。
docs/ai_employees/issue_prompt_composer_employee.md の仕様に従う。

Usage:
    python issue_prompt_composer.py               # 直近14日
    python issue_prompt_composer.py --days 30
    python issue_prompt_composer.py --start 2026-04-05 --end 2026-04-30
    python issue_prompt_composer.py --output issue_prompt.md
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz

jst = pytz.timezone('Asia/Tokyo')

# Routes associated with Rebun/Kafuka (more exposed, higher cancellation risk)
REBUN_ROUTES = {'wakkanai_kafuka', 'kafuka_wakkanai', 'oshidomari_kafuka', 'kafuka_oshidomari'}
WINTER_MONTHS = {12, 1, 2, 3}


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

def classify_fn(row: Dict) -> List[str]:
    """
    Return a list of failure category tags for a False Negative record.
    FN = predicted LOW/MINIMAL, actual CANCELLED.
    """
    tags = []
    wind = row['actual_wind']
    wave = row['actual_wave']
    month = _month_of(row['operation_date'])
    route = row['route']
    is_maint = row['is_likely_maintenance']

    if is_maint:
        tags.append('maintenance_or_no_service')
        return tags  # don't add weather tags for maintenance days

    if wind is not None and wind < 20:
        tags.append('threshold_too_low')

    if route in REBUN_ROUTES:
        tags.append('route_factor_missing')

    if month in WINTER_MONTHS:
        tags.append('seasonal_factor_missing')

    if wind is None or wave is None:
        tags.append('source_resolution_limit')

    if not tags:
        tags.append('threshold_too_low')  # default for unclassified FN

    return tags


def classify_fp(row: Dict) -> List[str]:
    """
    Return failure category tags for a False Positive record.
    FP = predicted HIGH/MEDIUM, actual OPERATED.
    """
    tags = []
    wind = row['actual_wind']
    pred_risk = row['predicted_risk']
    is_maint = row['is_likely_maintenance']

    if is_maint:
        return ['maintenance_or_no_service']

    if pred_risk == 'HIGH' and wind is not None and wind < 20:
        tags.append('threshold_too_high')
    elif pred_risk in ('HIGH', 'MEDIUM') and wind is not None and wind < 15:
        tags.append('threshold_too_high')
    else:
        tags.append('source_resolution_limit')

    return tags


def _month_of(date_str: str) -> int:
    try:
        return int(date_str[5:7])
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------

def _db_path(filename: str) -> str:
    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    return os.path.join(data_dir, filename)


def fetch_failures(start_date: str, end_date: str) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Returns (fn_records, fp_records, daily_summaries) for the given date range.
    Maintenance-flagged records are included but tagged.
    """
    conn = sqlite3.connect(_db_path('ferry_weather_forecast.db'))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            operation_date, route, departure_time,
            predicted_risk, predicted_score,
            actual_status, actual_wind, actual_wave, actual_visibility,
            false_positive, false_negative, is_correct,
            is_likely_maintenance, data_source
        FROM unified_operation_accuracy
        WHERE operation_date >= ? AND operation_date <= ?
        ORDER BY operation_date, route, departure_time
    ''', (start_date, end_date))
    rows = [dict(r) for r in cursor.fetchall()]

    cursor.execute('''
        SELECT
            summary_date, total_predictions, correct_predictions, accuracy_rate,
            true_positives, true_negatives, false_positives, false_negatives,
            precision_score, recall_score, f1_score
        FROM unified_daily_summary
        WHERE summary_date >= ? AND summary_date <= ?
        ORDER BY summary_date
    ''', (start_date, end_date))
    summaries = [dict(r) for r in cursor.fetchall()]

    conn.close()

    fn_records = [r for r in rows if r['false_negative'] and not r['is_likely_maintenance']]
    fp_records = [r for r in rows if r['false_positive'] and not r['is_likely_maintenance']]
    return fn_records, fp_records, summaries


def count_ferry_records(start_date: str, end_date: str) -> int:
    try:
        conn = sqlite3.connect(_db_path('heartland_ferry_real_data.db'))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM ferry_status_enhanced
            WHERE scrape_date >= ? AND scrape_date <= ?
        ''', (start_date, end_date))
        n = cursor.fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

def _route_list(records: List[Dict]) -> str:
    routes = sorted(set(r['route'] for r in records))
    return ', '.join(routes) if routes else '(なし)'


def _example_rows(records: List[Dict], n: int = 3) -> str:
    lines = []
    for r in records[:n]:
        wind = f"{r['actual_wind']:.1f}m/s" if r['actual_wind'] is not None else 'wind=N/A'
        wave = f"wave={r['actual_wave']:.2f}m" if r['actual_wave'] is not None else 'wave=N/A'
        vis  = f"vis={r['actual_visibility']:.1f}km" if r['actual_visibility'] is not None else 'vis=N/A'
        lines.append(
            f"  - {r['operation_date']} {r['route']} {r['departure_time']} | "
            f"pred={r['predicted_risk']} | actual={r['actual_status']} | {wind} {wave} {vis}"
        )
    return '\n'.join(lines)


def _avg(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _fmt(v: Optional[float], unit: str = '', fmt: str = '.1f') -> str:
    if v is None:
        return 'N/A'
    return f"{v:{fmt}}{unit}"


def generate_fn_prompt(fn_records: List[Dict], fp_records: List[Dict],
                       summaries: List[Dict], start_date: str, end_date: str,
                       ferry_count: int) -> str:
    """Generate a fix-request prompt focused on False Negatives."""

    # Categorize
    tag_counts: Dict[str, int] = {}
    for r in fn_records:
        for tag in classify_fn(r):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    dominant_tag = max(tag_counts, key=tag_counts.get) if tag_counts else 'threshold_too_low'

    # Aggregate metrics
    total_fn = len(fn_records)
    total_fp = len(fp_records)
    fn_winds = [r['actual_wind'] for r in fn_records]
    fn_waves = [r['actual_wave'] for r in fn_records]
    avg_fn_wind = _avg(fn_winds)
    avg_fn_wave = _avg(fn_waves)

    rebun_fn = [r for r in fn_records if r['route'] in REBUN_ROUTES]
    winter_fn = [r for r in fn_records if _month_of(r['operation_date']) in WINTER_MONTHS]

    affected_routes = _route_list(fn_records)
    affected_dates = sorted(set(r['operation_date'] for r in fn_records))
    date_range_str = f"{affected_dates[0]} 〜 {affected_dates[-1]}" if affected_dates else '(なし)'

    # Summary stats
    if summaries:
        avg_acc = sum(s['accuracy_rate'] for s in summaries) / len(summaries)
        total_preds = sum(s['total_predictions'] for s in summaries)
        total_fn_sum = sum(s['false_negatives'] for s in summaries)
        total_fp_sum = sum(s['false_positives'] for s in summaries)
    else:
        avg_acc = total_preds = total_fn_sum = total_fp_sum = 0

    # Title
    if dominant_tag == 'threshold_too_low':
        title = f"欠航予測漏れ（False Negative）: 低〜中風速帯での欠航見逃し"
    elif dominant_tag == 'route_factor_missing':
        title = f"欠航予測漏れ（False Negative）: 礼文/香深航路の露出補正なし"
    elif dominant_tag == 'seasonal_factor_missing':
        title = f"欠航予測漏れ（False Negative）: 冬季の低風速帯欠航見逃し"
    else:
        title = f"欠航予測漏れ（False Negative）: {total_fn}件 ({start_date}〜{end_date})"

    lines = []
    lines.append(f"# 修正依頼: {title}")
    lines.append("")
    lines.append("## 背景")
    lines.append(f"{start_date}〜{end_date}（{len(summaries)}日間）の精度監査で、")
    lines.append(f"合計 **{total_fn}件の False Negative**（欠航したのにLOW/MINIMALと予測）が検出された。")
    lines.append(f"対象期間の平均精度: {avg_acc:.1f}%（予測件数: {total_preds}件）。")
    lines.append(f"対象航路: {affected_routes}")
    lines.append(f"対象日: {date_range_str}")
    lines.append("")

    lines.append("## 観測された問題")
    lines.append(f"- False Negative: {total_fn}件（気象は {_fmt(avg_fn_wind, 'm/s')} 風速、波高 {_fmt(avg_fn_wave, 'm')} 平均でも欠航）")
    if total_fp > 0:
        lines.append(f"- False Positive: {total_fp}件（過剰警報も発生）")
    if rebun_fn:
        lines.append(f"- 礼文/香深関連航路の FN: {len(rebun_fn)}件")
    if winter_fn:
        lines.append(f"- 冬季（12〜3月）の FN: {len(winter_fn)}件")

    # Dominant tag specific observations
    if dominant_tag == 'threshold_too_low':
        lines.append(f"- 欠航時の平均実測風速 {_fmt(avg_fn_wind, 'm/s')} は現行閾値（LOW=20m/s未満）以下だが全件欠航")
    elif dominant_tag == 'route_factor_missing':
        lines.append("- 礼文島（香深港）は広域気象と比較してより厳しい条件になりやすいが、補正がない")
    elif dominant_tag == 'seasonal_factor_missing':
        lines.append("- 冬季（12〜3月）は同じ風速・波高でも欠航しやすいが、季節補正がない")
    lines.append("")

    lines.append("## 根拠データ")
    lines.append(f"- 予報: `cancellation_forecast` テーブル（期間内 {total_preds}件の予測）")
    lines.append(f"- 実測: `actual_weather` テーブル（Open-Meteo Archive/ERA5）")
    lines.append(f"- 運航実績: `ferry_status_enhanced` テーブル（{ferry_count}件のスクレイピング記録）")
    lines.append(f"- 監査結果: `unified_operation_accuracy` — FN={total_fn_sum}, FP={total_fp_sum}")
    lines.append("")
    lines.append("False Negative の例（最大3件）:")
    lines.append(_example_rows(fn_records, 3))
    if total_fp > 0:
        lines.append("")
        lines.append("False Positive の例（最大3件）:")
        lines.append(_example_rows(fp_records, 3))
    lines.append("")

    lines.append("## 修正してほしいこと")
    i = 1
    if dominant_tag == 'threshold_too_low':
        lines.append(f"{i}. `weather_forecast_collector.py` の `calculate_cancellation_risk()` で、"
                     "風速15〜20m/s帯のスコアを見直す（現行: 20点、実態: 欠航多発）。")
        i += 1
        lines.append(f"{i}. `unified_accuracy_tracker.py` の `_calc_risk()` も同じ変更を適用する（両者は同期が必要）。")
        i += 1
    if rebun_fn:
        lines.append(f"{i}. 礼文/香深関連航路（`wakkanai_kafuka`, `kafuka_wakkanai`, `oshidomari_kafuka`, `kafuka_oshidomari`）"
                     "に対して、リスクスコアに1段階上乗せを検討する。")
        i += 1
    if winter_fn:
        lines.append(f"{i}. 冬季（12〜3月）の低風速帯（8〜15m/s）欠航パターンを集計し、"
                     "季節別の閾値変更が統計的に支持されるか確認する。")
        i += 1
    lines.append("")

    lines.append("## 触ってよい主なファイル")
    lines.append("- `weather_forecast_collector.py` — `calculate_cancellation_risk()`")
    lines.append("- `unified_accuracy_tracker.py` — `_calc_risk()`")
    if rebun_fn:
        lines.append("- `unified_accuracy_tracker.py` — `_get_route_weather()` （航路別補正の追加先）")
    lines.append("")

    lines.append("## 受け入れ条件")
    lines.append(f"- 変更後に `python unified_accuracy_tracker.py {start_date} {end_date}` を実行し、"
                 "FN件数が減少していること。")
    lines.append("- FP件数が変更前より増加していないこと（過剰警報への影響を確認）。")
    lines.append(f"- `sqlite3 ferry_weather_forecast.db "
                 f"\"SELECT COUNT(*) FROM unified_operation_accuracy WHERE false_negative=1 "
                 f"AND operation_date >= '{start_date}' AND operation_date <= '{end_date}'\"` "
                 "の件数が減少していること。")
    lines.append("")

    lines.append("## 注意")
    lines.append("- APIキーやDB本体をコミットしない。")
    lines.append("- JSTを維持する（`datetime.now(pytz.timezone('Asia/Tokyo'))`）。")
    lines.append("- 気象欠航ではない運休（整備・季節ダイヤ）を精度評価に混ぜない。")
    lines.append("- 信頼できるデータは2026-04-05以降のみ（それ以前はスクレイパーバグで全欠航誤記録）。")
    lines.append("- 閾値を変更する前に実測データの正確性を確認すること。")

    return '\n'.join(lines)


def generate_fp_only_prompt(fp_records: List[Dict], summaries: List[Dict],
                             start_date: str, end_date: str, ferry_count: int) -> str:
    """Generate a fix-request prompt focused only on False Positives (no FNs)."""
    total_fp = len(fp_records)
    fp_winds = [r['actual_wind'] for r in fp_records]
    avg_fp_wind = _avg(fp_winds)
    affected_routes = _route_list(fp_records)
    avg_acc = sum(s['accuracy_rate'] for s in summaries) / len(summaries) if summaries else 0

    lines = []
    lines.append("# 修正依頼: 過剰欠航警報（False Positive）: 通常運航を欠航予測")
    lines.append("")
    lines.append("## 背景")
    lines.append(f"{start_date}〜{end_date}（{len(summaries)}日間）の精度監査で、")
    lines.append(f"合計 **{total_fp}件の False Positive**（通常運航なのにHIGH/MEDIUMと予測）が検出された。")
    lines.append(f"平均精度: {avg_acc:.1f}%。対象航路: {affected_routes}")
    lines.append("")
    lines.append("## 観測された問題")
    lines.append(f"- False Positive: {total_fp}件（実測風速平均 {_fmt(avg_fp_wind, 'm/s')} でも HIGH/MEDIUM 予測）")
    lines.append("- ユーザーが不必要な在庫積み増しを行う可能性がある")
    lines.append("")
    lines.append("## 根拠データ")
    lines.append("- 実測: `actual_weather` テーブル")
    lines.append("- 運航実績: `ferry_status_enhanced` テーブル")
    lines.append("- 監査結果: `unified_operation_accuracy`")
    lines.append("")
    lines.append("False Positive の例（最大3件）:")
    lines.append(_example_rows(fp_records, 3))
    lines.append("")
    lines.append("## 修正してほしいこと")
    lines.append("1. FP が発生した日の実測気象と予報気象の差を比較し、予報精度の問題か閾値の問題かを切り分ける。")
    lines.append("2. 予報精度の問題なら `weather_forecast_collector.py` のデータソース選択を見直す。")
    lines.append("3. 閾値の問題なら `calculate_cancellation_risk()` の HIGH→MEDIUM の判定スコアを調整する。")
    lines.append("")
    lines.append("## 触ってよい主なファイル")
    lines.append("- `weather_forecast_collector.py` — `calculate_cancellation_risk()`")
    lines.append("- `unified_accuracy_tracker.py` — `_calc_risk()`")
    lines.append("")
    lines.append("## 受け入れ条件")
    lines.append(f"- FP件数が変更後に減少していること。")
    lines.append("- FN件数が増加していないこと（安全側への影響を確認）。")
    lines.append("")
    lines.append("## 注意")
    lines.append("- APIキーやDB本体をコミットしない。")
    lines.append("- JSTを維持する。")
    lines.append("- 気象欠航ではない運休を精度評価に混ぜない。")
    lines.append("- 閾値変更はFNへの影響を必ず確認してから行う。")

    return '\n'.join(lines)


def generate_no_issues_report(summaries: List[Dict], start_date: str, end_date: str) -> str:
    avg_acc = sum(s['accuracy_rate'] for s in summaries) / len(summaries) if summaries else 0
    total_fn = sum(s['false_negatives'] for s in summaries)
    total_fp = sum(s['false_positives'] for s in summaries)
    total_preds = sum(s['total_predictions'] for s in summaries)

    lines = []
    lines.append(f"# 精度監査サマリ: {start_date}〜{end_date}")
    lines.append("")
    lines.append(f"対象期間: {start_date} 〜 {end_date}（{len(summaries)}日間）")
    lines.append(f"予測件数: {total_preds}件")
    lines.append(f"平均精度: {avg_acc:.1f}%")
    lines.append(f"False Negative（整備除く）: {total_fn}件")
    lines.append(f"False Positive（整備除く）: {total_fp}件")
    lines.append("")
    if not summaries:
        lines.append("⚠ 対象期間に精度データがありません。`unified_accuracy_tracker.py` を先に実行してください。")
    else:
        lines.append("✅ 修正が必要な問題は検出されませんでした。")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Generate fix-request prompts from accuracy audit results.')
    parser.add_argument('--days', type=int, default=14, help='過去N日間を対象（デフォルト: 14）')
    parser.add_argument('--start', type=str, help='開始日 YYYY-MM-DD（指定時は --days を無視）')
    parser.add_argument('--end', type=str, help='終了日 YYYY-MM-DD（省略時は昨日）')
    parser.add_argument('--output', type=str, help='出力ファイルパス（省略時は標準出力）')
    args = parser.parse_args()

    now_jst = datetime.now(jst)
    yesterday = (now_jst - timedelta(days=1)).strftime('%Y-%m-%d')

    end_date = args.end or yesterday
    if args.start:
        start_date = args.start
    else:
        start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=args.days - 1)
        start_date = start_dt.strftime('%Y-%m-%d')

    print(f"Issue Prompt Composer — {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")
    print(f"対象期間: {start_date} 〜 {end_date}")

    fn_records, fp_records, summaries = fetch_failures(start_date, end_date)
    ferry_count = count_ferry_records(start_date, end_date)

    print(f"False Negative（整備除く）: {len(fn_records)}件")
    print(f"False Positive（整備除く）: {len(fp_records)}件")
    print(f"日次サマリ: {len(summaries)}件")
    print(f"フェリー運航記録: {ferry_count}件")

    if len(fn_records) > 0:
        prompt = generate_fn_prompt(fn_records, fp_records, summaries, start_date, end_date, ferry_count)
    elif len(fp_records) > 0:
        prompt = generate_fp_only_prompt(fp_records, summaries, start_date, end_date, ferry_count)
    else:
        prompt = generate_no_issues_report(summaries, start_date, end_date)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"\n出力先: {args.output}")
    else:
        print("\n" + "=" * 80)
        print(prompt)
        print("=" * 80)


if __name__ == '__main__':
    main()
