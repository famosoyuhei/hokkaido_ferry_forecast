#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flight_status_collector.py — 飛行機運航記録取得AI（利尻空港発着便）

FlightAware AeroAPI v4 を使って利尻空港（RJER）の実際の運航可否を取得し、
heartland_ferry_real_data.db の flight_status_rishiri テーブルに保存する。

実行タイミング（GitHub Actions）:
  毎日 20:00 UTC (05:00 JST 翌日) — 当日の最終便（JAL2788 17:15着）が終わった後

使用API:
  FlightAware AeroAPI v4
  https://flightaware.com/aeroapi/portal/documentation
  環境変数: FLIGHTAWARE_API_KEY

AGENTS.md ルール19〜23 遵守:
  - 滑走路方位はモジュール定数（RUNWAY_HEADING_DEG=70）を参照
  - 便リストは flight_timetable_utils.get_active_flights_on() で動的取得
  - 精度検証前に閾値変更禁止
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytz

from jst_utils import now_jst, today_jst_str
from flight_timetable_utils import get_active_flights_on

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

AIRPORT_ICAO = 'RJER'      # 利尻空港

FLIGHTAWARE_BASE = 'https://aeroapi.flightaware.com/aeroapi'

# FlightAware の1リクエストあたりのコスト節約のため、1日1回まとめて取得する
MAX_RETRIES = 3
RETRY_DELAY = 15  # 秒


class FlightStatusCollector:
    """飛行機運航記録取得AI — FlightAware AeroAPI 経由で利尻空港の便を取得する。"""

    def __init__(self):
        data_dir = (
            os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
            or os.environ.get('RAILWAY_VOLUME_MOUNT')
            or '.'
        )
        self.db_file = os.path.join(data_dir, 'heartland_ferry_real_data.db')
        self.api_key = os.environ.get('FLIGHTAWARE_API_KEY', '')
        self.jst = pytz.timezone('Asia/Tokyo')

        self._init_table()

    # ------------------------------------------------------------------
    # DBテーブル初期化
    # ------------------------------------------------------------------

    def _init_table(self):
        """flight_status_rishiri テーブルを作成する。"""
        conn = sqlite3.connect(self.db_file)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS flight_status_rishiri (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                scrape_date      TEXT NOT NULL,
                flight_no        TEXT NOT NULL,
                airline          TEXT,
                aircraft         TEXT,
                route_key        TEXT,
                rishiri_role     TEXT,
                scheduled_time   TEXT,
                actual_time      TEXT,
                status           TEXT,
                is_cancelled     INTEGER NOT NULL DEFAULT 0,
                is_diverted      INTEGER NOT NULL DEFAULT 0,
                cancellation_reason TEXT,
                collected_at     TEXT NOT NULL,
                UNIQUE(scrape_date, flight_no, rishiri_role)
            )
        ''')
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # FlightAware API
    # ------------------------------------------------------------------

    def _api_get(self, path: str, params: Dict = None) -> Optional[Dict]:
        """FlightAware AeroAPI GET リクエストを送信する。"""
        if not self.api_key:
            print('[WARNING] FLIGHTAWARE_API_KEY が設定されていません。スキップします。')
            return None

        import urllib.request
        import urllib.parse

        url = f'{FLIGHTAWARE_BASE}{path}'
        if params:
            url += '?' + urllib.parse.urlencode(params)

        req = urllib.request.Request(url, headers={
            'x-apikey': self.api_key,
            'Accept': 'application/json; charset=UTF-8',
        })

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except Exception as e:
                print(f'  [API] attempt {attempt}/{MAX_RETRIES} failed: {e}')
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        return None

    def _fetch_airport_flights(self, date_str: str) -> List[Dict]:
        """
        指定日（JST）の RJER 発着便を FlightAware から取得する。
        AeroAPI v4: GET /airports/{id}/flights  (scheduled range)
        """
        # JST 日付 → UTC 時刻範囲に変換
        jst_start = self.jst.localize(datetime.strptime(f'{date_str} 00:00', '%Y-%m-%d %H:%M'))
        jst_end   = self.jst.localize(datetime.strptime(f'{date_str} 23:59', '%Y-%m-%d %H:%M'))
        utc_start = jst_start.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%MZ')
        utc_end   = jst_end.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%MZ')

        data = self._api_get(
            f'/airports/{AIRPORT_ICAO}/flights',
            {'start': utc_start, 'end': utc_end, 'max_pages': 2}
        )
        if not data:
            return []

        arrivals   = data.get('arrivals', [])
        departures = data.get('departures', [])
        return arrivals + departures

    # ------------------------------------------------------------------
    # 解析・保存
    # ------------------------------------------------------------------

    def _parse_status(self, flight: Dict) -> Dict:
        """
        FlightAware フライトオブジェクトからステータスを抽出する。
        https://flightaware.com/aeroapi/portal/documentation#get-/flights/{id}
        """
        status = flight.get('status', '').lower()
        cancelled  = 'cancelled' in status or flight.get('cancelled', False)
        diverted   = 'diverted'  in status or flight.get('diverted', False)

        scheduled  = (flight.get('scheduled_off') or flight.get('scheduled_on') or '')[:16]
        actual     = (flight.get('actual_off')    or flight.get('actual_on')    or '')[:16]

        # 利尻での役割（到着 or 出発）を判定
        dest = (flight.get('destination', {}) or {}).get('code_icao', '')
        orig = (flight.get('origin', {}) or {}).get('code_icao', '')
        if dest == AIRPORT_ICAO:
            role = 'arrival'
        elif orig == AIRPORT_ICAO:
            role = 'departure'
        else:
            role = 'unknown'

        return {
            'flight_no':   flight.get('ident', ''),
            'status':      status,
            'is_cancelled': int(cancelled),
            'is_diverted':  int(diverted),
            'scheduled_time': scheduled,
            'actual_time':    actual,
            'rishiri_role':   role,
            'cancellation_reason': flight.get('reason_description', ''),
        }

    def _infer_completed_scheduled_status(self, date_str: str, sched: Dict) -> Dict:
        """
        Use a conservative fallback for completed timetable flights when
        FlightAware returned no matching cancellation/diversion record.

        This keeps the accuracy dataset daily-complete while marking the value
        as inferred rather than pretending it came from an explicit status feed.
        """
        try:
            rishiri_dt = self.jst.localize(
                datetime.strptime(f"{date_str} {sched['rishiri_time']}", '%Y-%m-%d %H:%M')
            )
        except Exception:
            rishiri_dt = self.jst.localize(datetime.strptime(f'{date_str} 23:59', '%Y-%m-%d %H:%M'))

        if now_jst() <= rishiri_dt + timedelta(hours=2):
            return {}

        return {
            'scheduled_time': sched['rishiri_time'],
            'actual_time': '',
            'status': 'operated_inferred',
            'is_cancelled': 0,
            'is_diverted': 0,
            'cancellation_reason': '',
        }

    def collect_for_date(self, date_str: str) -> int:
        """
        指定日の利尻空港発着便を収集・保存する。
        時刻表と照合して is_cancelled を補完する。

        Returns:
            保存レコード数
        """
        print(f'\n[Flight] {date_str} の運航状況を取得中...')

        # 時刻表から当日の予定便を取得
        scheduled_flights = {f['flight_no']: f for f in get_active_flights_on(date_str)}
        if not scheduled_flights:
            print(f'  [INFO] {date_str} は就航便なし（時刻表）')
            return 0

        # FlightAware からフライト情報を取得
        raw_flights = self._fetch_airport_flights(date_str)

        if not raw_flights and not self.api_key:
            # APIキーなし → 時刻表のみで「運航状況不明」レコードを作成
            print('  [INFO] APIキーなし。時刻表ベースの骨格レコードのみ登録します。')
            raw_flights = []

        # flight_no → parsed_status のマッピング
        fetched: Dict[str, Dict] = {}
        for f in raw_flights:
            parsed = self._parse_status(f)
            fn = parsed['flight_no']
            # 同便名で複数ある場合（往復など）は role で区別
            key = f"{fn}_{parsed['rishiri_role']}"
            fetched[key] = parsed

        conn = sqlite3.connect(self.db_file)
        saved = 0
        collected_at = now_jst().isoformat()

        for flight_no, sched in scheduled_flights.items():
            role = sched['rishiri_role']
            key  = f'{flight_no}_{role}'
            info = fetched.get(key, {})
            if not info:
                info = self._infer_completed_scheduled_status(date_str, sched)

            try:
                conn.execute('''
                    INSERT OR REPLACE INTO flight_status_rishiri
                    (scrape_date, flight_no, airline, aircraft, route_key,
                     rishiri_role, scheduled_time, actual_time, status,
                     is_cancelled, is_diverted, cancellation_reason, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    date_str,
                    flight_no,
                    sched['airline'],
                    sched['aircraft'],
                    sched['route_key'],
                    role,
                    info.get('scheduled_time', sched['rishiri_time']),
                    info.get('actual_time', ''),
                    info.get('status', 'unknown'),
                    info.get('is_cancelled', 0),
                    info.get('is_diverted',  0),
                    info.get('cancellation_reason', ''),
                    collected_at,
                ))
                saved += 1
            except Exception as e:
                print(f'  [WARNING] insert error for {flight_no}: {e}')

        conn.commit()
        conn.close()

        cancelled = sum(1 for f in fetched.values() if f.get('is_cancelled'))
        print(f'  [OK] {saved}件保存（うち欠航: {cancelled}件）')
        return saved

    def run(self, date_str: Optional[str] = None) -> bool:
        """
        デフォルトは昨日分を収集する。
        GitHub Actions から呼ばれる際は引数なしで実行。
        """
        if date_str is None:
            date_str = (now_jst() - timedelta(days=1)).strftime('%Y-%m-%d')

        print('=' * 72)
        print('FLIGHT STATUS COLLECTOR — Rishiri Airport (RJER)')
        print(f'対象日: {date_str}  実行時刻: {now_jst().strftime("%Y-%m-%d %H:%M JST")}')
        print('=' * 72)

        if not self.api_key:
            print('[WARNING] FLIGHTAWARE_API_KEY が未設定です。')
            print('  実際の欠航実績が取得できないため、精度計算は不完全になります。')
            print('  Railway Variables に FLIGHTAWARE_API_KEY を設定してください。')

        saved = self.collect_for_date(date_str)

        print('\n' + '=' * 72)
        print(f'[{"OK" if saved > 0 else "WARN"}] 飛行機運航記録収集完了: {saved}件')
        print('=' * 72)
        return saved >= 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description='飛行機運航記録取得AI（利尻空港）')
    parser.add_argument('--date', default=None, help='対象日 YYYY-MM-DD（省略時=昨日）')
    args = parser.parse_args()

    collector = FlightStatusCollector()
    success = collector.run(args.date)
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
