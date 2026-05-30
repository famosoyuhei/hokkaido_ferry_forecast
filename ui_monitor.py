#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Monitor — ダッシュボードのAPIレスポンス・データ鮮度・航路カバレッジを監査する。

チェック項目:
  1. 全APIエンドポイントの応答確認（/api/stats, /api/forecast, /api/today, /api/routes）
  2. データ鮮度（最終収集から8時間以内か）
  3. 航路カバレッジ（8航路すべてに予報データがあるか）
  4. リスクレベルの妥当性（HIGH/MEDIUM/LOW/MINIMAL のみか）
  5. cancellation_forecast の直近登録件数

出力: stdout（コンソール） + JSON（オプション）
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from jst_utils import now_jst, today_jst_str

DASHBOARD_URL = os.getenv(
    'DASHBOARD_URL', 'https://web-production-a628.up.railway.app'
).rstrip('/')

EXPECTED_ROUTES = {
    'wakkanai_oshidomari', 'oshidomari_wakkanai',
    'wakkanai_kafuka',     'kafuka_wakkanai',
    'wakkanai_kutsugata',  'kutsugata_wakkanai',
    'oshidomari_kafuka',   'kafuka_oshidomari',
}

VALID_RISK_LEVELS = {'HIGH', 'MEDIUM', 'LOW', 'MINIMAL'}

# データ鮮度の閾値
MAX_STALE_HOURS = 8


class UiMonitor:
    """ダッシュボードUIとAPIの健全性を監査する。"""

    def __init__(self):
        data_dir = (
            os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
            or os.environ.get('RAILWAY_VOLUME_MOUNT')
            or '.'
        )
        self.forecast_db = os.path.join(data_dir, 'ferry_weather_forecast.db')
        self.results: Dict = {}

    # ------------------------------------------------------------------
    # 1. API エンドポイント確認
    # ------------------------------------------------------------------

    def check_api_health(self) -> Dict:
        """各APIエンドポイントを叩いてステータスコードとキー存在を確認する。"""
        endpoints = {
            '/api/stats':    ['total_forecasts', 'last_update'],
            '/api/forecast': None,          # list か dict を期待
            '/api/today':    None,
            '/api/routes':   None,
        }
        report = {}
        for path, required_keys in endpoints.items():
            url = DASHBOARD_URL + path
            try:
                r = requests.get(url, timeout=10)
                ok = r.status_code == 200
                body = None
                missing_keys = []
                if ok:
                    try:
                        body = r.json()
                        if required_keys:
                            missing_keys = [
                                k for k in required_keys
                                if k not in (body if isinstance(body, dict) else {})
                            ]
                    except Exception:
                        ok = False
                report[path] = {
                    'status_code': r.status_code,
                    'ok': ok and not missing_keys,
                    'missing_keys': missing_keys,
                    'response_ms': int(r.elapsed.total_seconds() * 1000),
                }
            except requests.exceptions.RequestException as e:
                report[path] = {
                    'status_code': None,
                    'ok': False,
                    'error': str(e),
                }
        return report

    # ------------------------------------------------------------------
    # 2. データ鮮度チェック
    # ------------------------------------------------------------------

    def check_data_freshness(self) -> Dict:
        """forecast_collection_log の最終成功収集が MAX_STALE_HOURS 以内か確認する。"""
        if not os.path.exists(self.forecast_db):
            return {'ok': False, 'error': 'DB not found', 'db_path': self.forecast_db}

        now = now_jst()
        try:
            conn = sqlite3.connect(self.forecast_db)
            row = conn.execute('''
                SELECT timestamp
                FROM forecast_collection_log
                WHERE status = 'SUCCESS'
                ORDER BY timestamp DESC
                LIMIT 1
            ''').fetchone()
            conn.close()

            if not row:
                return {'ok': False, 'error': 'No successful collection records'}

            last_ts_str = row[0]
            # タイムゾーンなしISO文字列の場合、JSTとして解釈
            try:
                from datetime import timezone
                import pytz
                jst = pytz.timezone('Asia/Tokyo')
                last_dt = datetime.fromisoformat(last_ts_str)
                if last_dt.tzinfo is None:
                    last_dt = jst.localize(last_dt)
                staleness_h = (now - last_dt).total_seconds() / 3600
            except Exception:
                staleness_h = 999

            return {
                'ok': staleness_h <= MAX_STALE_HOURS,
                'last_success': last_ts_str,
                'staleness_hours': round(staleness_h, 1),
                'threshold_hours': MAX_STALE_HOURS,
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 3. 航路カバレッジチェック
    # ------------------------------------------------------------------

    def check_route_coverage(self) -> Dict:
        """今後7日間の cancellation_forecast に 8 航路分のデータがあるか確認する。"""
        if not os.path.exists(self.forecast_db):
            return {'ok': False, 'error': 'DB not found'}

        today = today_jst_str()
        end_date = (datetime.strptime(today, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')

        try:
            conn = sqlite3.connect(self.forecast_db)
            rows = conn.execute('''
                SELECT DISTINCT route
                FROM cancellation_forecast
                WHERE forecast_for_date >= ? AND forecast_for_date <= ?
            ''', (today, end_date)).fetchall()
            conn.close()

            found = {r[0] for r in rows}
            missing = EXPECTED_ROUTES - found
            extra = found - EXPECTED_ROUTES

            return {
                'ok': len(missing) == 0,
                'found_routes': sorted(found),
                'missing_routes': sorted(missing),
                'extra_routes': sorted(extra),
                'coverage': f'{len(found)}/{len(EXPECTED_ROUTES)}',
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 4. リスクレベル妥当性チェック
    # ------------------------------------------------------------------

    def check_risk_level_validity(self) -> Dict:
        """直近7日間の cancellation_forecast に無効なリスクレベルがないか確認する。"""
        if not os.path.exists(self.forecast_db):
            return {'ok': False, 'error': 'DB not found'}

        today = today_jst_str()
        end_date = (datetime.strptime(today, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')

        try:
            conn = sqlite3.connect(self.forecast_db)
            rows = conn.execute('''
                SELECT risk_level, COUNT(*) as cnt
                FROM cancellation_forecast
                WHERE forecast_for_date >= ? AND forecast_for_date <= ?
                GROUP BY risk_level
            ''', (today, end_date)).fetchall()
            conn.close()

            level_counts = {row[0]: row[1] for row in rows}
            invalid = {k: v for k, v in level_counts.items() if k not in VALID_RISK_LEVELS}

            return {
                'ok': len(invalid) == 0,
                'risk_level_counts': level_counts,
                'invalid_levels': invalid,
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 5. 直近登録件数チェック
    # ------------------------------------------------------------------

    def check_record_counts(self) -> Dict:
        """weather_forecast と cancellation_forecast の件数が正常範囲内か確認する。"""
        if not os.path.exists(self.forecast_db):
            return {'ok': False, 'error': 'DB not found'}

        today = today_jst_str()
        end_date = (datetime.strptime(today, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')

        try:
            conn = sqlite3.connect(self.forecast_db)

            total_forecast = conn.execute(
                'SELECT COUNT(*) FROM cancellation_forecast'
            ).fetchone()[0]

            week_forecast = conn.execute(
                'SELECT COUNT(*) FROM cancellation_forecast WHERE forecast_for_date >= ? AND forecast_for_date <= ?',
                (today, end_date)
            ).fetchone()[0]

            total_weather = conn.execute(
                'SELECT COUNT(*) FROM weather_forecast'
            ).fetchone()[0]

            conn.close()

            # 7日×8航路×1時間 = 最低 56 件は欲しい（hour単位収集なら数百件）
            week_ok = week_forecast >= 56

            return {
                'ok': week_ok,
                'total_cancellation_forecast': total_forecast,
                'week_cancellation_forecast': week_forecast,
                'total_weather_forecast': total_weather,
                'warning': None if week_ok else f'週間予報が{week_forecast}件（最低56件を下回る）',
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 総合実行
    # ------------------------------------------------------------------

    def run(self) -> Dict:
        """全チェックを実行し、結果サマリを返す。"""
        now = now_jst()
        print('=' * 72)
        print('UI MONITOR — DASHBOARD HEALTH CHECK')
        print(f'実行時刻: {now.strftime("%Y-%m-%d %H:%M:%S JST")}')
        print('=' * 72)

        checks = {
            'api_health':        ('APIエンドポイント',     self.check_api_health),
            'data_freshness':    ('データ鮮度',             self.check_data_freshness),
            'route_coverage':    ('航路カバレッジ',         self.check_route_coverage),
            'risk_level_valid':  ('リスクレベル妥当性',     self.check_risk_level_validity),
            'record_counts':     ('レコード件数',           self.check_record_counts),
        }

        all_ok = True
        report = {'checked_at': now.isoformat(), 'checks': {}}

        for key, (label, fn) in checks.items():
            print(f'\n[{label}]')
            try:
                result = fn()
            except Exception as e:
                result = {'ok': False, 'error': str(e)}

            report['checks'][key] = result

            # api_health は各エンドポイントを個別表示
            if key == 'api_health':
                for path, info in result.items():
                    status = '✅' if info.get('ok') else '❌'
                    ms = info.get('response_ms', '-')
                    print(f'  {status} {path} ({ms}ms)')
                    if not info.get('ok'):
                        all_ok = False
                        if info.get('missing_keys'):
                            print(f'     missing keys: {info["missing_keys"]}')
                        if info.get('error'):
                            print(f'     error: {info["error"]}')
            else:
                ok = result.get('ok', False)
                status = '✅' if ok else '❌'
                if not ok:
                    all_ok = False
                print(f'  {status}', end=' ')

                if key == 'data_freshness':
                    if ok:
                        print(f"最終収集: {result.get('last_success', '不明')} "
                              f"({result.get('staleness_hours', '?')}時間前)")
                    else:
                        print(result.get('error', result.get('warning', 'NG')))

                elif key == 'route_coverage':
                    print(f"カバレッジ: {result.get('coverage', '?')}")
                    if result.get('missing_routes'):
                        print(f"     未収録航路: {result['missing_routes']}")

                elif key == 'risk_level_valid':
                    counts = result.get('risk_level_counts', {})
                    print(f"分布: {counts}")
                    if result.get('invalid_levels'):
                        print(f"     無効値: {result['invalid_levels']}")

                elif key == 'record_counts':
                    print(
                        f"週間予報: {result.get('week_cancellation_forecast', '?')}件 / "
                        f"累計: {result.get('total_cancellation_forecast', '?')}件"
                    )
                    if result.get('warning'):
                        print(f"     ⚠️  {result['warning']}")

        report['all_ok'] = all_ok
        print('\n' + '=' * 72)
        overall = '✅ ALL OK' if all_ok else '❌ ISSUES FOUND'
        print(f'総合結果: {overall}')
        print('=' * 72 + '\n')

        return report


def main():
    monitor = UiMonitor()
    report = monitor.run()

    # JSONオプション出力
    output_path = os.getenv('UI_MONITOR_OUTPUT')
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'[INFO] レポートを保存しました: {output_path}')

    return 0 if report.get('all_ok') else 1


if __name__ == '__main__':
    exit(main())
