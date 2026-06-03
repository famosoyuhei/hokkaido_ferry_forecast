#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system_review.py — AI社員総動員レビュー・修正プロンプト生成

各AI社員の視点からシステムを監査し、問題点を修正プロンプト形式で出力する。

Usage:
    python system_review.py                    # quick モード（直近2日）
    python system_review.py --mode full        # full モード（直近14日）
    python system_review.py --mode quick       # quick モード（直近2日）
    python system_review.py --output out.md    # ファイルへ出力

スラッシュコマンドからの呼び出し:
    /quick-review → python system_review.py --mode quick
    /full-review  → python system_review.py --mode full
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import pytz

from jst_utils import now_jst, today_jst_str, days_from_today_jst, get_active_routes_on

jst = pytz.timezone('Asia/Tokyo')

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

TRUST_CUTOFF = '2026-04-05'   # これ以前のデータはスクレイパーバグで全欠航誤記録
STALE_FORECAST_HOURS = 8      # 予報が何時間以上古ければ WARNING
STALE_ACTUAL_DAYS = 2         # 実測データが何日以上古ければ WARNING
MIN_DAILY_HOURS = 18          # 1日当たり最低限の実測時間数
HIGH_CANCEL_RATE = 0.85       # これ以上の欠航率は parser_error 疑い

REBUN_ROUTES = {'wakkanai_kafuka', 'kafuka_wakkanai', 'oshidomari_kafuka', 'kafuka_oshidomari'}
WINTER_MONTHS = {12, 1, 2, 3}

SEVERITY_ORDER = {'CRITICAL': 0, 'WARNING': 1, 'INFO': 2}

# 本番Railway URL（ローカル実行時に本番DBの鮮度をチェックするために使用）
PRODUCTION_URL = 'https://web-production-a628.up.railway.app'

# Railway上で動いているかどうかを判定（Trueならローカル DB = 本番DB なので API チェック不要）
_IS_ON_RAILWAY = bool(
    os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
    or os.environ.get('RAILWAY_ENVIRONMENT')
    or os.environ.get('RAILWAY_SERVICE_NAME')
)

EMPLOYEE_LABELS = {
    'forecast':   '🌊 海上気象予報取得AI',
    'actual':     '📡 海上気象実測取得AI',
    'ferry':      '⛴️  フェリー運航記録取得AI',
    'accuracy':   '🔬 予報精度監査AI',
    'synthesizer':'📋 問題点整理AI',
}


# ---------------------------------------------------------------------------
# Issue データクラス
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str       # 'CRITICAL' / 'WARNING' / 'INFO'
    employee: str       # employee key (see EMPLOYEE_LABELS)
    category: str       # category tag
    title: str          # 短いタイトル
    detail: str         # 詳細説明
    fix_hint: str = ''  # 修正ヒント（省略可）

    def sort_key(self):
        return (SEVERITY_ORDER.get(self.severity, 9), self.employee, self.title)


# ---------------------------------------------------------------------------
# DB ヘルパー
# ---------------------------------------------------------------------------

def _db(filename: str) -> str:
    data_dir = (
        os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
        or os.environ.get('RAILWAY_VOLUME_MOUNT')
        or '.'
    )
    return os.path.join(data_dir, filename)


def _connect(filename: str) -> Optional[sqlite3.Connection]:
    path = _db(filename)
    if not os.path.exists(path):
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return any(r[1] == column for r in rows)


def _date_range(start_date: str, end_date: str) -> List[str]:
    """start_date〜end_date の日付文字列リストを返す。"""
    dates = []
    d = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    while d <= end:
        dates.append(d.strftime('%Y-%m-%d'))
        d += timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# 1. 海上気象予報取得AI社員チェック
# ---------------------------------------------------------------------------

class ForecastEmployee:
    """
    cancellation_forecast / weather_forecast テーブルを監査する。
    - 時刻表との航路カバレッジ照合
    - 予報鮮度チェック
    - 波高 NULL チェック（Marine API 未取得の疑い）
    - 全港の weather_forecast レコード確認
    """

    def run(self, start_date: str, end_date: str, mode: str) -> List[Issue]:
        issues: List[Issue] = []
        conn = _connect('ferry_weather_forecast.db')
        if conn is None:
            issues.append(Issue(
                severity='CRITICAL', employee='forecast',
                category='data_fetch_fail',
                title='ferry_weather_forecast.db が見つからない',
                detail=f'パス {_db("ferry_weather_forecast.db")} にDBが存在しない。',
                fix_hint='Railway Volume が正しくマウントされているか確認する。'
            ))
            return issues

        try:
            if not _table_exists(conn, 'cancellation_forecast'):
                issues.append(Issue(
                    severity='CRITICAL', employee='forecast',
                    category='schema_missing',
                    title='cancellation_forecast テーブルが存在しない',
                    detail='weather_forecast_collector.py が一度も成功していない可能性がある。',
                    fix_hint='python weather_forecast_collector.py を手動実行する。'
                ))
            else:
                issues += self._check_coverage(conn, start_date, end_date)
                issues += self._check_freshness(conn)
                issues += self._check_wave_nulls(conn, start_date, end_date)

            if mode == 'full' and _table_exists(conn, 'weather_forecast'):
                issues += self._check_port_coverage(conn, start_date, end_date)
        finally:
            conn.close()
        return issues

    def _check_coverage(self, conn, start_date: str, end_date: str) -> List[Issue]:
        """時刻表との航路カバレッジ照合（今日〜7日後を主対象）。"""
        issues = []
        today = today_jst_str()
        forecast_end = days_from_today_jst(7)
        check_start = max(start_date, today)

        for date_str in _date_range(check_start, min(end_date, forecast_end)):
            expected = set(get_active_routes_on(date_str))
            if not expected:
                continue

            rows = conn.execute(
                'SELECT DISTINCT route FROM cancellation_forecast WHERE forecast_for_date = ?',
                (date_str,)
            ).fetchall()
            found = {r['route'] for r in rows}
            missing = expected - found

            if missing:
                severity = 'CRITICAL' if date_str <= days_from_today_jst(1) else 'WARNING'
                issues.append(Issue(
                    severity=severity, employee='forecast',
                    category='coverage_gap',
                    title=f'予報なし: {date_str} / {sorted(missing)}',
                    detail=(
                        f'{date_str} に時刻表上の航路 {sorted(missing)} の予報が '
                        f'cancellation_forecast に存在しない。'
                        f'（期待: {sorted(expected)}、取得済み: {sorted(found)}）'
                    ),
                    fix_hint=(
                        'weather_forecast_collector.py を実行して予報を生成する。'
                        '沓形-香深便の場合は get_active_routes_on() が 6/1〜9/30 の範囲を'
                        '正しく返しているか確認する。'
                    )
                ))
        return issues

    def _check_freshness(self, conn) -> List[Issue]:
        """最新の予報生成時刻を確認。STALE_FORECAST_HOURS 以上古ければ WARNING。"""
        row = conn.execute(
            'SELECT MAX(generated_at) as last_gen FROM cancellation_forecast'
        ).fetchone()
        if not row or not row['last_gen']:
            return [Issue(
                severity='CRITICAL', employee='forecast',
                category='stale_data',
                title='cancellation_forecast にレコードがない',
                detail='テーブルが空。weather_forecast_collector.py が一度も成功していない可能性。',
                fix_hint='python weather_forecast_collector.py を手動実行する。'
            )]

        try:
            last_gen = datetime.fromisoformat(row['last_gen'].replace('Z', '+00:00'))
            if last_gen.tzinfo is None:
                last_gen = jst.localize(last_gen)
            age_hours = (now_jst() - last_gen).total_seconds() / 3600
        except Exception:
            return []

        if age_hours > STALE_FORECAST_HOURS * 3:
            return [Issue(
                severity='CRITICAL', employee='forecast',
                category='stale_data',
                title=f'予報データが {age_hours:.0f}時間 更新されていない',
                detail=f'最終生成: {row["last_gen"]}。{age_hours:.0f}時間以上更新なし（閾値: {STALE_FORECAST_HOURS}h）。',
                fix_hint='GitHub Actions / Railway Cron のログを確認する。weather_forecast_collector.py を手動実行する。'
            )]
        elif age_hours > STALE_FORECAST_HOURS:
            return [Issue(
                severity='WARNING', employee='forecast',
                category='stale_data',
                title=f'予報データが {age_hours:.0f}時間 更新されていない',
                detail=f'最終生成: {row["last_gen"]}。通常は1日4回（05:00/11:00/17:00/23:00 JST）更新される。',
                fix_hint='次回の定期実行で解消する見込み。24時間以上経過したら GitHub Actions を手動トリガーする。'
            )]
        return []

    def _check_wave_nulls(self, conn, start_date: str, end_date: str) -> List[Issue]:
        """wave_forecast が NULL の割合を確認（Marine API 未取得の疑い）。"""
        row = conn.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN wave_forecast IS NULL THEN 1 ELSE 0 END) as nulls
            FROM cancellation_forecast
            WHERE forecast_for_date >= ? AND forecast_for_date <= ?
        ''', (start_date, end_date)).fetchone()

        if not row or row['total'] == 0:
            return []

        null_rate = row['nulls'] / row['total']
        if null_rate > 0.5:
            return [Issue(
                severity='WARNING', employee='forecast',
                category='data_fetch_fail',
                title=f'wave_forecast の {null_rate*100:.0f}% が NULL',
                detail=(
                    f'期間 {start_date}〜{end_date} の cancellation_forecast '
                    f'{row["total"]}件中 {row["nulls"]}件（{null_rate*100:.0f}%）で波高が NULL。'
                    'Marine API の取得が失敗している可能性がある。'
                ),
                fix_hint='weather_forecast_collector.py の Marine API 呼び出し部分を確認する。'
            )]
        return []

    def _check_port_coverage(self, conn, start_date: str, end_date: str) -> List[Issue]:
        """4港（稚内/鴛泊/沓形/香深）すべての weather_forecast レコードがあるか確認。"""
        expected_ports = {'wakkanai', 'oshidomari', 'kutsugata', 'kafuka'}
        rows = conn.execute('''
            SELECT DISTINCT location FROM weather_forecast
            WHERE forecast_date >= ? AND forecast_date <= ?
        ''', (start_date, end_date)).fetchall()
        found_ports = {r['location'] for r in rows}
        missing = expected_ports - found_ports
        if missing:
            return [Issue(
                severity='WARNING', employee='forecast',
                category='coverage_gap',
                title=f'weather_forecast に港データなし: {sorted(missing)}',
                detail=(
                    f'期間 {start_date}〜{end_date} で港 {sorted(missing)} の '
                    'weather_forecast レコードが存在しない。'
                ),
                fix_hint='weather_forecast_collector.py の locations 設定を確認する。'
            )]
        return []


# ---------------------------------------------------------------------------
# 2. 海上気象実測取得AI社員チェック
# ---------------------------------------------------------------------------

class ActualWeatherEmployee:
    """
    actual_weather テーブルを監査する。
    - 日別・港別のカバレッジ
    - 時間解像度（1日24時間のうち何時間取得できているか）
    - データ鮮度（昨日分が取得済みか）
    - 風速・波高・視程の NULL 率
    """

    PORTS = ['wakkanai', 'oshidomari', 'kutsugata', 'kafuka']

    def run(self, start_date: str, end_date: str, mode: str) -> List[Issue]:
        issues: List[Issue] = []
        conn = _connect('ferry_weather_forecast.db')
        if conn is None:
            return issues  # DB 不在は ForecastEmployee が報告済み

        # actual_weather テーブルの存在確認
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='actual_weather'"
        ).fetchone()
        if not tbl:
            issues.append(Issue(
                severity='WARNING', employee='actual',
                category='schema_missing',
                title='actual_weather テーブルが存在しない',
                detail='Hindcast 精度計算に必要な actual_weather テーブルが未作成。',
                fix_hint='python actual_weather_collector.py を実行してテーブルを初期化する。'
            ))
            conn.close()
            return issues

        has_location = _column_exists(conn, 'actual_weather', 'location')
        if not has_location:
            issues.append(Issue(
                severity='WARNING', employee='actual',
                category='schema_missing',
                title='actual_weather テーブルが旧スキーマ（location カラムなし）',
                detail=(
                    'actual_weather に location カラムがない。旧バージョンのスキーマ。'
                    '港別カバレッジチェックをスキップする。'
                ),
                fix_hint='python actual_weather_collector.py を実行してスキーマを更新する。'
            ))

        try:
            issues += self._check_freshness(conn)
            issues += self._check_daily_coverage(conn, start_date, end_date, has_location)
            if mode == 'full':
                issues += self._check_null_rates(conn, start_date, end_date)
        finally:
            conn.close()
        return issues

    def _check_freshness(self, conn) -> List[Issue]:
        row = conn.execute('SELECT MAX(date) as last_date FROM actual_weather').fetchone()
        if not row or not row['last_date']:
            return [Issue(
                severity='WARNING', employee='actual',
                category='stale_data',
                title='actual_weather にデータがない',
                detail='テーブルが空。actual_weather_collector.py が実行されていない可能性。',
                fix_hint='python actual_weather_collector.py を手動実行する。'
            )]
        yesterday = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')
        if row['last_date'] < yesterday:
            gap_days = (
                datetime.strptime(yesterday, '%Y-%m-%d') -
                datetime.strptime(row['last_date'], '%Y-%m-%d')
            ).days
            severity = 'CRITICAL' if gap_days >= 3 else 'WARNING'
            return [Issue(
                severity=severity, employee='actual',
                category='stale_data',
                title=f'実測データが {gap_days}日 更新されていない（最終: {row["last_date"]}）',
                detail=(
                    f'actual_weather の最終日付は {row["last_date"]}。'
                    f'昨日（{yesterday}）のデータがない。'
                    f'Hindcast 精度計算が {gap_days}日分ずれる。'
                ),
                fix_hint='GitHub Actions actual-weather-collection ワークフローを確認する。'
            )]
        return []

    def _check_daily_coverage(
        self, conn, start_date: str, end_date: str, has_location: bool
    ) -> List[Issue]:
        issues = []
        yesterday = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')
        # actual_weather は過去分のみチェック
        check_end = min(end_date, yesterday)
        if check_end < start_date:
            return []

        if has_location:
            rows = conn.execute('''
                SELECT date, location, COUNT(*) as hour_count
                FROM actual_weather
                WHERE date >= ? AND date <= ?
                GROUP BY date, location
            ''', (start_date, check_end)).fetchall()

            # {date: {location: hour_count}}
            coverage: Dict[str, Dict[str, int]] = {}
            for r in rows:
                coverage.setdefault(r['date'], {})[r['location']] = r['hour_count']

            for date_str in _date_range(start_date, check_end):
                day_cov = coverage.get(date_str, {})
                missing_ports = [p for p in self.PORTS if p not in day_cov]
                low_coverage = [
                    f'{p}({day_cov[p]}h)' for p in self.PORTS
                    if p in day_cov and day_cov[p] < MIN_DAILY_HOURS
                ]
                if len(missing_ports) == len(self.PORTS):
                    issues.append(Issue(
                        severity='WARNING', employee='actual',
                        category='coverage_gap',
                        title=f'実測データ完全欠落: {date_str}',
                        detail=f'{date_str} の actual_weather が全港で0件。',
                        fix_hint='python actual_weather_collector.py を手動実行する。'
                    ))
                elif missing_ports:
                    issues.append(Issue(
                        severity='WARNING', employee='actual',
                        category='coverage_gap',
                        title=f'実測データ欠落: {date_str} / 港={missing_ports}',
                        detail=f'{date_str} で港 {missing_ports} のデータがない。',
                        fix_hint='actual_weather_collector.py の locations 設定を確認する。'
                    ))
                elif low_coverage:
                    issues.append(Issue(
                        severity='WARNING', employee='actual',
                        category='coverage_gap',
                        title=f'時間解像度不足: {date_str} / {low_coverage}',
                        detail=f'{date_str} で時間数が少ない港がある（期待: ≥{MIN_DAILY_HOURS}h）。',
                        fix_hint='Open-Meteo Archive API の取得時間範囲を確認する。'
                    ))
        else:
            # 旧スキーマ: 日別の件数だけ確認
            rows = conn.execute('''
                SELECT date, COUNT(*) as cnt
                FROM actual_weather WHERE date >= ? AND date <= ?
                GROUP BY date
            ''', (start_date, check_end)).fetchall()
            found_dates = {r['date'] for r in rows}
            for date_str in _date_range(start_date, check_end):
                if date_str not in found_dates:
                    issues.append(Issue(
                        severity='WARNING', employee='actual',
                        category='coverage_gap',
                        title=f'実測データ欠落: {date_str}',
                        detail=f'{date_str} の actual_weather が0件。',
                        fix_hint='python actual_weather_collector.py を手動実行する。'
                    ))
        return issues

    def _check_null_rates(self, conn, start_date: str, end_date: str) -> List[Issue]:
        issues = []
        yesterday = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')
        check_end = min(end_date, yesterday)
        if check_end < start_date:
            return []

        row = conn.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN wind_speed IS NULL THEN 1 ELSE 0 END) as null_wind,
                SUM(CASE WHEN wave_height IS NULL THEN 1 ELSE 0 END) as null_wave,
                SUM(CASE WHEN visibility IS NULL THEN 1 ELSE 0 END) as null_vis
            FROM actual_weather WHERE date >= ? AND date <= ?
        ''', (start_date, check_end)).fetchone()

        if not row or row['total'] == 0:
            return []

        t = row['total']
        for col, cnt in [('wind_speed', row['null_wind']),
                         ('wave_height', row['null_wave']),
                         ('visibility', row['null_vis'])]:
            rate = cnt / t
            if rate > 0.3:
                issues.append(Issue(
                    severity='WARNING', employee='actual',
                    category='data_fetch_fail',
                    title=f'actual_weather.{col} の NULL 率 {rate*100:.0f}%',
                    detail=(
                        f'期間 {start_date}〜{check_end} の actual_weather で '
                        f'{col} が {cnt}/{t}件（{rate*100:.0f}%）NULL。'
                        '精度計算の除外母集団が増える。'
                    ),
                    fix_hint=f'actual_weather_collector.py の {col} 取得ロジックを確認する。'
                ))
        return issues


# ---------------------------------------------------------------------------
# 3. フェリー運航記録取得AI社員チェック
# ---------------------------------------------------------------------------

class FerryCollectorEmployee:
    """
    ferry_status_enhanced テーブルを監査する。
    - スクレイプ日別のカバレッジ（欠落日）
    - 航路カバレッジ（時刻表との比較）
    - 異常高欠航率（parser_error の疑い）
    - 重複レコード
    """

    def run(self, start_date: str, end_date: str, mode: str) -> List[Issue]:
        issues: List[Issue] = []
        conn = _connect('heartland_ferry_real_data.db')
        if conn is None:
            issues.append(Issue(
                severity='CRITICAL', employee='ferry',
                category='data_fetch_fail',
                title='heartland_ferry_real_data.db が見つからない',
                detail=f'パス {_db("heartland_ferry_real_data.db")} にDBが存在しない。',
                fix_hint='Railway Volume が正しくマウントされているか確認する。'
            ))
            return issues

        try:
            issues += self._check_freshness(conn)
            issues += self._check_daily_coverage(conn, start_date, end_date)
            issues += self._check_high_cancel_rate(conn, start_date, end_date)
            if mode == 'full':
                issues += self._check_duplicates(conn, start_date, end_date)
                issues += self._check_route_coverage(conn, start_date, end_date)
        finally:
            conn.close()
        return issues

    def _check_freshness(self, conn) -> List[Issue]:
        row = conn.execute(
            'SELECT MAX(scrape_date) as last FROM ferry_status_enhanced'
        ).fetchone()
        if not row or not row['last']:
            return [Issue(
                severity='CRITICAL', employee='ferry',
                category='data_fetch_fail',
                title='ferry_status_enhanced にレコードがない',
                detail='テーブルが空。improved_ferry_collector.py が未実行の可能性。',
                fix_hint='python improved_ferry_collector.py を手動実行する。'
            )]
        yesterday = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')
        if row['last'] < yesterday:
            gap = (
                datetime.strptime(yesterday, '%Y-%m-%d') -
                datetime.strptime(row['last'], '%Y-%m-%d')
            ).days
            severity = 'CRITICAL' if gap >= 2 else 'WARNING'
            return [Issue(
                severity=severity, employee='ferry',
                category='stale_data',
                title=f'フェリー運航記録が {gap}日 更新されていない（最終: {row["last"]}）',
                detail=(
                    f'ferry_status_enhanced の最終スクレイプ日: {row["last"]}。'
                    f'昨日（{yesterday}）のデータがない。精度計算ができない。'
                ),
                fix_hint='GitHub Actions ferry-collection ワークフローを確認する。'
            )]
        return []

    def _check_daily_coverage(self, conn, start_date: str, end_date: str) -> List[Issue]:
        issues = []
        yesterday = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')
        check_end = min(end_date, yesterday)
        if check_end < start_date or check_end < TRUST_CUTOFF:
            return []
        check_start = max(start_date, TRUST_CUTOFF)

        rows = conn.execute('''
            SELECT scrape_date, COUNT(*) as cnt
            FROM ferry_status_enhanced
            WHERE scrape_date >= ? AND scrape_date <= ?
            GROUP BY scrape_date
        ''', (check_start, check_end)).fetchall()
        scraped_dates = {r['scrape_date']: r['cnt'] for r in rows}

        for date_str in _date_range(check_start, check_end):
            expected_routes = get_active_routes_on(date_str)
            if not expected_routes:
                continue
            if date_str not in scraped_dates:
                issues.append(Issue(
                    severity='WARNING', employee='ferry',
                    category='coverage_gap',
                    title=f'フェリー運航記録 欠落: {date_str}',
                    detail=(
                        f'{date_str} の ferry_status_enhanced が0件。'
                        f'スクレイパーが実行されていないか失敗した可能性。'
                    ),
                    fix_hint='GitHub Actions ferry-collection ワークフローを確認・修復し、欠落日分のバックフィルを行う。'
                ))
        return issues

    def _check_high_cancel_rate(self, conn, start_date: str, end_date: str) -> List[Issue]:
        """1日の欠航率が HIGH_CANCEL_RATE 以上の日を検出（parser_error 疑い）。"""
        issues = []
        check_start = max(start_date, TRUST_CUTOFF)
        rows = conn.execute('''
            SELECT
                scrape_date,
                COUNT(*) as total,
                SUM(is_cancelled) as cancelled
            FROM ferry_status_enhanced
            WHERE scrape_date >= ? AND scrape_date <= ?
            GROUP BY scrape_date
            HAVING total >= 4
        ''', (check_start, end_date)).fetchall()

        for r in rows:
            if r['total'] == 0:
                continue
            rate = r['cancelled'] / r['total']
            if rate >= HIGH_CANCEL_RATE:
                issues.append(Issue(
                    severity='WARNING', employee='ferry',
                    category='parser_error',
                    title=f'異常高欠航率: {r["scrape_date"]} ({r["cancelled"]}/{r["total"]}便欠航)',
                    detail=(
                        f'{r["scrape_date"]} は {r["total"]}便中 {r["cancelled"]}便が欠航記録'
                        f'（欠航率 {rate*100:.0f}%）。'
                        'パーサーエラーまたは実際の全便欠航（荒天・整備）の可能性がある。'
                        '気象データと照合して判断すること。'
                    ),
                    fix_hint=(
                        'ferry_status_enhanced の is_likely_maintenance フラグを確認する。'
                        'actual_weather のその日の風速・波高も確認する。'
                    )
                ))
        return issues

    def _check_duplicates(self, conn, start_date: str, end_date: str) -> List[Issue]:
        row = conn.execute('''
            SELECT COUNT(*) as dup_count
            FROM (
                SELECT scrape_date, route, departure_time, COUNT(*) as cnt
                FROM ferry_status_enhanced
                WHERE scrape_date >= ? AND scrape_date <= ?
                GROUP BY scrape_date, route, departure_time
                HAVING cnt > 1
            )
        ''', (start_date, end_date)).fetchone()
        if row and row['dup_count'] > 0:
            return [Issue(
                severity='WARNING', employee='ferry',
                category='audit_population_dirty',
                title=f'ferry_status_enhanced に重複レコード {row["dup_count"]}件',
                detail=(
                    f'期間 {start_date}〜{end_date} で同一 (scrape_date, route, departure_time) '
                    f'の重複レコードが {row["dup_count"]}件。精度計算が二重になる。'
                ),
                fix_hint=(
                    'improved_ferry_collector.py の UNIQUE INDEX 制約を確認する。'
                    'INSERT OR REPLACE になっているか確認する。'
                )
            )]
        return []

    def _check_route_coverage(self, conn, start_date: str, end_date: str) -> List[Issue]:
        """スクレイプされた航路が時刻表の期待航路と乖離していないか確認。"""
        issues = []
        yesterday = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')
        check_end = min(end_date, yesterday)
        check_start = max(start_date, TRUST_CUTOFF)
        if check_end < check_start:
            return []

        rows = conn.execute('''
            SELECT scrape_date, route, COUNT(*) as cnt
            FROM ferry_status_enhanced
            WHERE scrape_date >= ? AND scrape_date <= ?
            GROUP BY scrape_date, route
        ''', (check_start, check_end)).fetchall()

        # {date: set(routes)}
        scraped: Dict[str, set] = {}
        for r in rows:
            scraped.setdefault(r['scrape_date'], set()).add(r['route'])

        for date_str, found_routes in scraped.items():
            expected = set(get_active_routes_on(date_str))
            if not expected:
                continue
            missing = expected - found_routes
            extra = found_routes - expected
            if extra:
                issues.append(Issue(
                    severity='WARNING', employee='ferry',
                    category='route_mapping_error',
                    title=f'時刻表にない航路が記録されている: {date_str} / {sorted(extra)}',
                    detail=(
                        f'{date_str} の ferry_status_enhanced に時刻表外の航路 {sorted(extra)} が存在する。'
                        'DIRECTION_MAP の誤マッピングの可能性がある。'
                    ),
                    fix_hint='improved_ferry_collector.py の DIRECTION_MAP を確認する。'
                ))
        return issues


# ---------------------------------------------------------------------------
# 4. 予報精度監査AI社員チェック（full モードのみ）
# ---------------------------------------------------------------------------

class AccuracyAuditorEmployee:
    """
    unified_operation_accuracy / unified_daily_summary を監査する。
    - FN / FP 件数・率
    - ルート別の FN 集中
    - 気象条件帯別の失敗パターン
    - データ充足性（信頼できるデータは 2026-04-05 以降のみ）
    """

    def run(self, start_date: str, end_date: str) -> Tuple[List[Issue], Dict]:
        """Issues と集計データ（修正プロンプト生成用）を返す。"""
        issues: List[Issue] = []
        stats: Dict = {}

        conn = _connect('ferry_weather_forecast.db')
        if conn is None:
            return issues, stats

        # unified_operation_accuracy の存在確認
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='unified_operation_accuracy'"
        ).fetchone()
        if not tbl:
            issues.append(Issue(
                severity='INFO', employee='accuracy',
                category='schema_missing',
                title='unified_operation_accuracy テーブルが存在しない',
                detail='精度計算がまだ実行されていない。unified_accuracy_tracker.py を先に実行する必要がある。',
                fix_hint=f'python unified_accuracy_tracker.py {start_date} {end_date}'
            ))
            conn.close()
            return issues, stats

        trust_start = max(start_date, TRUST_CUTOFF)

        try:
            issues_a, stats = self._check_fn_fp(conn, trust_start, end_date)
            issues += issues_a
            issues += self._check_data_sufficiency(conn, trust_start, end_date)
        finally:
            conn.close()
        return issues, stats

    def _check_fn_fp(self, conn, start_date: str, end_date: str) -> Tuple[List[Issue], Dict]:
        issues = []
        rows = conn.execute('''
            SELECT
                operation_date, route, departure_time,
                predicted_risk, actual_status,
                actual_wind, actual_wave, actual_visibility,
                false_positive, false_negative, is_correct,
                is_likely_maintenance
            FROM unified_operation_accuracy
            WHERE operation_date >= ? AND operation_date <= ?
              AND is_likely_maintenance = 0
        ''', (start_date, end_date)).fetchall()

        total = len(rows)
        fn_rows = [r for r in rows if r['false_negative']]
        fp_rows = [r for r in rows if r['false_positive']]
        correct = sum(1 for r in rows if r['is_correct'])

        accuracy = correct / total * 100 if total > 0 else None

        stats = {
            'total': total,
            'correct': correct,
            'fn_count': len(fn_rows),
            'fp_count': len(fp_rows),
            'accuracy': accuracy,
            'fn_rows': [dict(r) for r in fn_rows],
            'fp_rows': [dict(r) for r in fp_rows],
            'start_date': start_date,
            'end_date': end_date,
        }

        if total < 10:
            issues.append(Issue(
                severity='INFO', employee='accuracy',
                category='coverage_gap',
                title=f'精度計算のサンプル数が少ない（{total}件）',
                detail=f'期間 {start_date}〜{end_date} の評価対象が {total}件のみ。統計的信頼性が低い。',
                fix_hint='unified_accuracy_tracker.py を広い期間で実行してデータを蓄積する。'
            ))
            return issues, stats

        if accuracy is not None and accuracy < 70:
            issues.append(Issue(
                severity='WARNING', employee='accuracy',
                category='threshold_mismatch',
                title=f'精度低下: {accuracy:.1f}% (FN={len(fn_rows)}, FP={len(fp_rows)})',
                detail=(
                    f'期間 {start_date}〜{end_date} の精度が {accuracy:.1f}%。'
                    f'FN={len(fn_rows)}件（欠航見逃し）、FP={len(fp_rows)}件（過剰警報）。'
                )
            ))

        # FN の詳細分析
        if fn_rows:
            fn_winds = [r['actual_wind'] for r in fn_rows if r['actual_wind'] is not None]
            avg_wind = sum(fn_winds) / len(fn_winds) if fn_winds else None
            rebun_fn = [r for r in fn_rows if r['route'] in REBUN_ROUTES]
            winter_fn = [r for r in fn_rows
                         if r['operation_date'] and int(r['operation_date'][5:7]) in WINTER_MONTHS]

            issues.append(Issue(
                severity='WARNING' if len(fn_rows) >= 3 else 'INFO',
                employee='accuracy',
                category='cancel_signal_underweighted',
                title=f'False Negative {len(fn_rows)}件（欠航見逃し）',
                detail=(
                    f'欠航したのに LOW/MINIMAL と予測したケースが {len(fn_rows)}件。'
                    f'FN 時の平均風速: {f"{avg_wind:.1f}m/s" if avg_wind else "N/A"}。'
                    f'礼文関連航路 FN: {len(rebun_fn)}件、冬季 FN: {len(winter_fn)}件。'
                ),
                fix_hint=(
                    '閾値が緩すぎる可能性（threshold_too_low）。'
                    'weather_forecast_collector.py の calculate_cancellation_risk() を確認する。'
                )
            ))
            stats['avg_fn_wind'] = avg_wind
            stats['rebun_fn_count'] = len(rebun_fn)
            stats['winter_fn_count'] = len(winter_fn)

        if fp_rows:
            fp_winds = [r['actual_wind'] for r in fp_rows if r['actual_wind'] is not None]
            avg_fp_wind = sum(fp_winds) / len(fp_winds) if fp_winds else None
            issues.append(Issue(
                severity='INFO', employee='accuracy',
                category='safety_signal_overweighted',
                title=f'False Positive {len(fp_rows)}件（過剰警報）',
                detail=(
                    f'通常運航なのに HIGH/MEDIUM と予測したケースが {len(fp_rows)}件。'
                    f'FP 時の平均風速: {f"{avg_fp_wind:.1f}m/s" if avg_fp_wind else "N/A"}。'
                ),
                fix_hint='閾値が厳しすぎる可能性（threshold_too_high）。実測データと予報データの乖離も確認する。'
            ))

        return issues, stats

    def _check_data_sufficiency(self, conn, start_date: str, end_date: str) -> List[Issue]:
        """2026-04-05 以前のデータが混入していないか確認。"""
        row = conn.execute('''
            SELECT COUNT(*) as cnt FROM unified_operation_accuracy
            WHERE operation_date < ? AND operation_date >= ?
        ''', (TRUST_CUTOFF, start_date)).fetchone()
        if row and row['cnt'] > 0:
            return [Issue(
                severity='WARNING', employee='accuracy',
                category='audit_population_dirty',
                title=f'信頼できない期間のデータが {row["cnt"]}件 混入',
                detail=(
                    f'{TRUST_CUTOFF} 以前のデータが {row["cnt"]}件。'
                    'スクレイパーバグで全便欠航と誤記録されているため精度計算を汚染する。'
                ),
                fix_hint=(
                    'unified_accuracy_tracker.py のクエリに '
                    f'AND operation_date >= \'{TRUST_CUTOFF}\' を追加する。'
                )
            )]
        return []


# ---------------------------------------------------------------------------
# 5. 問題点整理AI社員（Synthesizer）— 修正プロンプト生成
# ---------------------------------------------------------------------------

class IssueSynthesizer:
    """全AI社員の Issue を集約し、修正依頼プロンプトを生成する。"""

    def generate(
        self,
        all_issues: List[Issue],
        accuracy_stats: Dict,
        mode: str,
        start_date: str,
        end_date: str,
    ) -> str:
        now_str = now_jst().strftime('%Y-%m-%d %H:%M JST')
        sorted_issues = sorted(all_issues, key=lambda i: i.sort_key())

        criticals = [i for i in sorted_issues if i.severity == 'CRITICAL']
        warnings  = [i for i in sorted_issues if i.severity == 'WARNING']
        infos     = [i for i in sorted_issues if i.severity == 'INFO']

        lines = []
        lines.append(f'# システム総合レビュー結果（{mode.upper()} モード）')
        lines.append(f'実行日時: {now_str}  |  対象期間: {start_date} 〜 {end_date}')
        lines.append('')

        # ── サマリバー ──
        c_mark = f'🔴 CRITICAL {len(criticals)}件' if criticals else '🟢 CRITICAL 0件'
        w_mark = f'🟡 WARNING {len(warnings)}件'  if warnings  else '🟢 WARNING 0件'
        i_mark = f'ℹ️  INFO {len(infos)}件'
        lines.append(f'## 総合ステータス: {c_mark}  {w_mark}  {i_mark}')
        lines.append('')

        # ── 精度サマリ（accuracy_stats がある場合）──
        if accuracy_stats.get('total', 0) >= 10:
            acc = accuracy_stats.get('accuracy')
            lines.append('## 予報精度サマリ（信頼期間内）')
            lines.append(f'- 評価件数: {accuracy_stats["total"]}件')
            lines.append(f'- 精度: {f"{acc:.1f}%" if acc is not None else "N/A"}')
            lines.append(f'- False Negative（欠航見逃し）: {accuracy_stats["fn_count"]}件')
            lines.append(f'- False Positive（過剰警報）: {accuracy_stats["fp_count"]}件')
            lines.append('')

        # ── 発見された問題 ──
        if not (criticals or warnings or infos):
            lines.append('## ✅ 問題は検出されませんでした')
            lines.append('')
            lines.append('全AI社員のチェックを通過しました。')
            return '\n'.join(lines)

        for severity, group, icon in [
            ('CRITICAL', criticals, '🔴'),
            ('WARNING',  warnings,  '🟡'),
            ('INFO',     infos,     'ℹ️ '),
        ]:
            if not group:
                continue
            lines.append(f'## {icon} {severity} — {len(group)}件')
            for issue in group:
                emp_label = EMPLOYEE_LABELS.get(issue.employee, issue.employee)
                lines.append(f'### [{emp_label}] {issue.title}')
                lines.append(f'- カテゴリ: `{issue.category}`')
                lines.append(f'- 詳細: {issue.detail}')
                if issue.fix_hint:
                    lines.append(f'- 対処: {issue.fix_hint}')
                lines.append('')

        # ── 修正プロンプト ──
        if criticals or warnings:
            lines.append('---')
            lines.append('')
            lines.append(self._generate_fix_prompt(
                criticals + warnings, accuracy_stats, start_date, end_date, mode
            ))

        return '\n'.join(lines)

    def _generate_fix_prompt(
        self,
        action_issues: List[Issue],
        stats: Dict,
        start_date: str,
        end_date: str,
        mode: str,
    ) -> str:
        """issue_prompt_composer_employee.md 形式の修正依頼プロンプトを生成する。"""

        # 最優先課題の特定
        critical_issues = [i for i in action_issues if i.severity == 'CRITICAL']
        primary = critical_issues[0] if critical_issues else action_issues[0]

        # タイトル決定
        if critical_issues:
            title = f'緊急修正: {primary.title}'
        elif stats.get('fn_count', 0) > stats.get('fp_count', 0):
            title = '欠航見逃し（False Negative）の改善'
        elif stats.get('fp_count', 0) > 0:
            title = '過剰欠航警報（False Positive）の改善'
        else:
            title = f'システム品質改善（{len(action_issues)}件の問題）'

        lines = []
        lines.append(f'# 修正依頼: {title}')
        lines.append('')

        # 背景
        lines.append('## 背景')
        lines.append(
            f'`python system_review.py --mode {mode}` による {start_date}〜{end_date} の監査で、'
            f'{len([i for i in action_issues if i.severity=="CRITICAL"])}件のCRITICALと'
            f'{len([i for i in action_issues if i.severity=="WARNING"])}件のWARNINGが検出された。'
        )
        if stats.get('total', 0) >= 10 and stats.get('accuracy') is not None:
            lines.append(
                f'予報精度: {stats["accuracy"]:.1f}%  '
                f'FN={stats["fn_count"]}件  FP={stats["fp_count"]}件。'
            )
        lines.append('')

        # 観測された問題
        lines.append('## 観測された問題')
        for issue in action_issues:
            emp = EMPLOYEE_LABELS.get(issue.employee, issue.employee)
            lines.append(f'- [{emp}] `{issue.category}`: {issue.title}')
        lines.append('')

        # 根拠データ
        lines.append('## 根拠データ')
        lines.append('- 予報: `cancellation_forecast` テーブル（`ferry_weather_forecast.db`）')
        lines.append('- 実測: `actual_weather` テーブル（Open-Meteo Archive/ERA5）')
        lines.append('- 運航実績: `ferry_status_enhanced` テーブル（`heartland_ferry_real_data.db`）')
        lines.append('- 監査結果: `unified_operation_accuracy` / `unified_daily_summary`')
        if stats.get('fn_rows'):
            lines.append('')
            lines.append('False Negative の例（最大3件）:')
            for r in stats['fn_rows'][:3]:
                wind = f"{r['actual_wind']:.1f}m/s" if r['actual_wind'] else 'wind=N/A'
                wave = f"wave={r['actual_wave']:.2f}m" if r['actual_wave'] else 'wave=N/A'
                lines.append(
                    f'  - {r["operation_date"]} {r["route"]} {r["departure_time"]} | '
                    f'pred={r["predicted_risk"]} | actual={r["actual_status"]} | {wind} {wave}'
                )
        lines.append('')

        # 修正してほしいこと — 同一 fix_hint は1回のみ出力、複数件は件数を付記
        lines.append('## 修正してほしいこと')
        step = 1
        # fix_hint をキーにしてグループ化（出現順を保持）
        hint_to_issues: Dict[str, List[Issue]] = {}
        for issue in action_issues:
            if not issue.fix_hint:
                continue
            hint_to_issues.setdefault(issue.fix_hint, []).append(issue)
        for hint, grouped in hint_to_issues.items():
            if len(grouped) == 1:
                lines.append(f'{step}. {hint}')
            else:
                lines.append(f'{step}. {hint}  （同種問題: {len(grouped)}件）')
            step += 1
        if stats.get('fn_count', 0) > 0:
            lines.append(
                f'{step}. `weather_forecast_collector.py` の `calculate_cancellation_risk()` と '
                '`unified_accuracy_tracker.py` の `_calc_risk()` を同期して修正する（両者は常に同一ロジックであること）。'
            )
            step += 1
        lines.append('')

        # 触ってよい主なファイル
        touched_files = []
        cats = {i.category for i in action_issues}
        if 'threshold_mismatch' in cats or 'cancel_signal_underweighted' in cats:
            touched_files += [
                '`weather_forecast_collector.py` — `calculate_cancellation_risk()`',
                '`unified_accuracy_tracker.py` — `_calc_risk()`',
            ]
        if 'data_fetch_fail' in cats or 'stale_data' in cats:
            touched_files += [
                '`actual_weather_collector.py` — `collect_for_date()`',
                '`improved_ferry_collector.py` — `scrape_ferry_status()`',
                '`.github/workflows/` — Cron ワークフロー',
            ]
        if 'coverage_gap' in cats:
            touched_files += [
                '`jst_utils.py` — `get_active_routes_on()` / `get_timetable_sailings()`',
                '`weather_forecast_collector.py` — `generate_cancellation_forecasts()`',
            ]
        if 'parser_error' in cats or 'route_mapping_error' in cats:
            touched_files.append('`improved_ferry_collector.py` — `DIRECTION_MAP`')

        if touched_files:
            lines.append('## 触ってよい主なファイル')
            for f in dict.fromkeys(touched_files):  # 重複除去して順序保持
                lines.append(f'- {f}')
            lines.append('')

        # 受け入れ条件
        lines.append('## 受け入れ条件')
        lines.append(
            f'- `python system_review.py --mode {mode}` を再実行して CRITICAL / WARNING が解消していること。'
        )
        if stats.get('fn_count', 0) > 0:
            lines.append(
                f'- `python unified_accuracy_tracker.py {start_date} {end_date}` を実行し、'
                'FN 件数が減少していること。'
            )
        lines.append('- FP 件数が変更前より増加していないこと。')
        lines.append('')

        # 注意
        lines.append('## 注意')
        lines.append('- APIキーやDB本体をコミットしない（`.gitignore` の `.db` を確認）。')
        lines.append('- `datetime.now()` は Railway では UTC。必ず `jst_utils.now_jst()` を使う。')
        lines.append('- 欠損値を 0 で埋めない。欠損は NULL として保存し精度計算から除外する。')
        lines.append(f'- 信頼できるデータは {TRUST_CUTOFF} 以降のみ（それ以前はスクレイパーバグで全欠航誤記録）。')
        lines.append('- 航路リストはハードコード禁止。`jst_utils.get_active_routes_on(date_str)` を使う。')
        lines.append('- コミット前に禁止パターン grep を実行する（AGENTS.md ルール18 参照）。')

        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# 本番DBヘルスチェック（ローカル実行時に Railway /api/db-health を参照）
# ---------------------------------------------------------------------------

def _fetch_production_health() -> Optional[Dict]:
    """
    Railway本番の /api/db-health を取得する。
    - Railway上で実行中の場合はローカルDBが本番DBなので None を返す（API不要）。
    - 接続失敗時も None を返す（ローカルDBフォールバック）。
    """
    if _IS_ON_RAILWAY:
        return None  # 自分自身が本番 → ループ回避のためスキップ
    try:
        import urllib.request
        import json as _json
        url = f'{PRODUCTION_URL}/api/db-health'
        req = urllib.request.Request(url, headers={'User-Agent': 'system_review/1.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return _json.loads(resp.read())
    except Exception:
        return None


def _add_production_health_info(issues: List[Issue], prod: Dict) -> None:
    """本番DB最終日付を INFO として issues に追加する。"""
    aw  = prod.get('actual_weather', {})
    fse = prod.get('ferry_status_enhanced', {})
    cf  = prod.get('cancellation_forecast', {})
    lines = []
    if isinstance(cf, dict) and cf.get('max_date'):
        lines.append(f'cancellation_forecast 最終日: {cf["max_date"]} ({cf.get("total_records","?")}件)')
    if isinstance(aw, dict) and aw.get('max_date'):
        lines.append(f'actual_weather 最終日: {aw["max_date"]} ({aw.get("total_records","?")}件)')
    if isinstance(fse, dict) and fse.get('max_date'):
        lines.append(f'ferry_status_enhanced 最終日: {fse["max_date"]} ({fse.get("total_records","?")}件)')
    if lines:
        issues.append(Issue(
            severity='INFO', employee='forecast',
            category='production_health',
            title='本番DBは最新データあり ✅',
            detail='Railway本番 /api/db-health による確認: ' + ' / '.join(lines),
            fix_hint='',
        ))


def _filter_by_production_health(issues: List[Issue], prod: Dict) -> Tuple[List[Issue], List[str]]:
    """
    本番DBが最新であれば、ローカルDB検査由来の誤報（stale_data / coverage_gap）を除去する。
    戻り値: (フィルタ後の issues, 除去理由サマリー)
    """
    now = now_jst()
    yesterday    = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    two_days_ago = (now - timedelta(days=2)).strftime('%Y-%m-%d')

    # 本番で「最新」とみなすテーブルを列挙
    fresh = set()

    aw = prod.get('actual_weather', {})
    if isinstance(aw, dict) and (aw.get('max_date') or '') >= two_days_ago:
        fresh.add('actual_weather')

    fse = prod.get('ferry_status_enhanced', {})
    if isinstance(fse, dict) and (fse.get('max_date') or '') >= two_days_ago:
        fresh.add('ferry_status_enhanced')

    cf = prod.get('cancellation_forecast', {})
    if isinstance(cf, dict) and (cf.get('max_date') or '') >= yesterday:
        fresh.add('cancellation_forecast')

    # フィルタリング
    filtered, suppressed = [], []
    for issue in issues:
        suppress = False

        # ActualWeatherEmployee は employee='actual' を使う
        if issue.employee == 'actual' and issue.category in ('stale_data', 'coverage_gap', 'schema_missing', 'data_fetch_fail'):
            if 'actual_weather' in fresh:
                suppress = True

        elif issue.employee == 'ferry' and issue.category in ('stale_data', 'coverage_gap', 'data_fetch_fail'):
            if 'ferry_status_enhanced' in fresh:
                suppress = True

        elif issue.employee == 'forecast' and issue.category in ('stale_data', 'coverage_gap', 'schema_missing', 'data_fetch_fail'):
            if 'cancellation_forecast' in fresh:
                suppress = True

        if suppress:
            suppressed.append(f'[{issue.employee}] {issue.category}: {issue.title}')
        else:
            filtered.append(issue)

    return filtered, suppressed


# ---------------------------------------------------------------------------
# オーケストレーター
# ---------------------------------------------------------------------------

def run_review(mode: str) -> str:
    now = now_jst()
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    if mode == 'quick':
        days = 2
    else:
        days = 14

    start_date = (now - timedelta(days=days - 1)).strftime('%Y-%m-%d')
    end_date = yesterday

    print(f'[system_review] モード={mode}  対象期間={start_date}〜{end_date}', flush=True)

    # 本番ヘルスを先に取得（ローカル実行時の誤報抑制に使用）
    prod_health: Optional[Dict] = None
    if not _IS_ON_RAILWAY:
        print('[system_review] 0/5 本番DB鮮度チェック中...', flush=True)
        prod_health = _fetch_production_health()
        if prod_health:
            aw_max  = prod_health.get('actual_weather', {}).get('max_date', '?')
            fse_max = prod_health.get('ferry_status_enhanced', {}).get('max_date', '?')
            cf_max  = prod_health.get('cancellation_forecast', {}).get('max_date', '?')
            print(
                f'[system_review]   本番DB鮮度: actual_weather={aw_max} / '
                f'ferry_status_enhanced={fse_max} / cancellation_forecast={cf_max}',
                flush=True
            )
        else:
            print('[system_review]   本番API未応答。ローカルDBのみでチェックします。', flush=True)

    all_issues: List[Issue] = []
    accuracy_stats: Dict = {}

    # 1. 海上気象予報取得AI
    print('[system_review] 1/5 海上気象予報取得AI チェック中...', flush=True)
    all_issues += ForecastEmployee().run(start_date, end_date, mode)

    # 2. 海上気象実測取得AI
    print('[system_review] 2/5 海上気象実測取得AI チェック中...', flush=True)
    all_issues += ActualWeatherEmployee().run(start_date, end_date, mode)

    # 3. フェリー運航記録取得AI
    print('[system_review] 3/5 フェリー運航記録取得AI チェック中...', flush=True)
    all_issues += FerryCollectorEmployee().run(start_date, end_date, mode)

    # 4. 予報精度監査AI（full モードのみ）
    if mode == 'full':
        print('[system_review] 4/5 予報精度監査AI チェック中...', flush=True)
        acc_issues, accuracy_stats = AccuracyAuditorEmployee().run(start_date, end_date)
        all_issues += acc_issues
    else:
        print('[system_review] 4/5 予報精度監査AI スキップ（quick モード）', flush=True)

    # 本番ヘルスで正常確認済みの誤報を除去
    if prod_health:
        all_issues, suppressed = _filter_by_production_health(all_issues, prod_health)
        if suppressed:
            print(
                f'[system_review]   本番DBが最新のため {len(suppressed)}件のローカル誤報を除外しました。',
                flush=True
            )
        # 本番が正常であることを INFO として追加
        _add_production_health_info(all_issues, prod_health)

    # 5. 問題点整理AI → 修正プロンプト生成
    print('[system_review] 5/5 問題点整理AI レポート生成中...', flush=True)
    report = IssueSynthesizer().generate(
        all_issues, accuracy_stats, mode, start_date, end_date
    )

    total = len(all_issues)
    crits = sum(1 for i in all_issues if i.severity == 'CRITICAL')
    warns = sum(1 for i in all_issues if i.severity == 'WARNING')
    print(
        f'[system_review] 完了: 合計{total}件 '
        f'(CRITICAL={crits}, WARNING={warns}, INFO={total-crits-warns})',
        flush=True
    )
    return report


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='AI社員総動員レビュー・修正プロンプト生成'
    )
    parser.add_argument(
        '--mode', choices=['quick', 'full'], default='quick',
        help='quick=直近2日間の簡易チェック / full=直近14日間の総合監査（デフォルト: quick）'
    )
    parser.add_argument(
        '--output', type=str, default='',
        help='出力ファイルパス（省略時は標準出力）'
    )
    args = parser.parse_args()

    report = run_review(args.mode)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f'[system_review] 出力先: {args.output}')
    else:
        print('\n' + '=' * 72)
        print(report)
        print('=' * 72)


if __name__ == '__main__':
    main()
