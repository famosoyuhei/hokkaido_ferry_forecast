#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-off correction: ferry_status_enhanced wind_speed unit fix.

Background: ImprovedFerryCollector.get_weather_data() fetched Open-Meteo
current weather WITHOUT specifying wind_speed_unit, so windspeed_10m was
returned in km/h (Open-Meteo default) but stored and labelled as m/s.
The collector was fixed on 2026-11-19 (commit c139a33) to request m/s.
This script converts the historical rows stored before the fix: km/h -> m/s.

Targets:
  - DB  heartland_ferry_real_data.db, table ferry_status_enhanced.wind_speed
  - CSV data/ferry_cancellation_log.csv, columns 風速_ms and wind_speed

Correction rule:
  Only rows from a REAL weather fetch are converted. Real-fetch rows have
  wave_height NULL in the DB (the collector stores None) and an empty 波高_m
  in the CSV. Fallback default rows (weather fetch failed: temp 15.0,
  wind 10.0, visibility 10.0, wave_height 2.0) are NOT measurements and are
  left untouched.

Safety:
  - Dry-run by default; pass --apply to write.
  - On apply, backup copies are written next to the originals
    (*.bak-windfix-YYYYMMDD).
  - A marker row in table data_corrections prevents running twice.

Usage:
  python fix_ferry_wind_units.py            # dry-run (report only)
  python fix_ferry_wind_units.py --apply    # perform the correction
"""

import argparse
import csv
import io
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytz

JST = pytz.timezone('Asia/Tokyo')
MARKER = 'ferry_wind_kmh_to_ms_2026-11-19'


def db_stats(conn, where):
    row = conn.execute(f'''
        SELECT COUNT(*), MIN(wind_speed), MAX(wind_speed), AVG(wind_speed)
        FROM ferry_status_enhanced WHERE {where}
    ''').fetchone()
    return row  # (count, min, max, avg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='actually write changes')
    args = parser.parse_args()

    data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
    db_path = Path(data_dir) / 'heartland_ferry_real_data.db'
    csv_path = Path(data_dir) / 'data' / 'ferry_cancellation_log.csv'
    today = datetime.now(JST).strftime('%Y%m%d')

    print('=' * 70)
    print('FERRY WIND UNIT CORRECTION (km/h stored as m/s -> true m/s)')
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f'DB:  {db_path}')
    print(f'CSV: {csv_path}')
    print('=' * 70)

    if not db_path.exists():
        print('[ERROR] DB not found')
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        # --- idempotency guard -------------------------------------------------
        conn.execute('''
            CREATE TABLE IF NOT EXISTS data_corrections (
                name TEXT PRIMARY KEY,
                applied_at TEXT,
                detail TEXT
            )
        ''')
        already = conn.execute(
            'SELECT applied_at FROM data_corrections WHERE name = ?', (MARKER,)
        ).fetchone()
        if already:
            print(f'[SKIP] Correction already applied at {already[0]}')
            return 0

        # --- report ------------------------------------------------------------
        total = conn.execute('SELECT COUNT(*) FROM ferry_status_enhanced').fetchone()[0]
        real_where = 'wave_height IS NULL AND wind_speed IS NOT NULL'
        fallback_where = 'wave_height IS NOT NULL'
        cnt, mn, mx, avg = db_stats(conn, real_where)
        fcnt = conn.execute(
            f'SELECT COUNT(*) FROM ferry_status_enhanced WHERE {fallback_where}'
        ).fetchone()[0]
        print(f'Total rows:            {total}')
        print(f'Real-fetch rows (fix): {cnt}  wind min={mn} max={mx} avg={avg:.2f}' if cnt else
              f'Real-fetch rows (fix): {cnt}')
        print(f'Fallback rows (keep):  {fcnt}')
        print('Monthly max wind_speed among real-fetch rows (stored values):')
        for ym, c, m in conn.execute(f'''
            SELECT substr(scrape_date,1,7), COUNT(*), MAX(wind_speed)
            FROM ferry_status_enhanced WHERE {real_where}
            GROUP BY 1 ORDER BY 1
        ''').fetchall():
            print(f'  {ym}: rows={c} max={m}  -> after fix max={m/3.6:.2f} m/s')

        # --- CSV report ----------------------------------------------------------
        csv_rows = []
        csv_fix_idx = []
        if csv_path.exists():
            with open(csv_path, encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                csv_rows = list(reader)
            for i, r in enumerate(csv_rows):
                wave = (r.get('波高_m') or '').strip()
                wind = (r.get('風速_ms') or '').strip()
                if wave == '' and wind != '':
                    csv_fix_idx.append(i)
            print(f'CSV rows: {len(csv_rows)}, real-fetch rows to fix: {len(csv_fix_idx)}')
        else:
            fieldnames = None
            print('CSV not found (skipped)')

        if not args.apply:
            print('[DRY-RUN] No changes written. Re-run with --apply to correct.')
            return 0

        # --- backup --------------------------------------------------------------
        db_bak = db_path.with_suffix(f'.db.bak-windfix-{today}')
        shutil.copy2(db_path, db_bak)
        print(f'[BACKUP] DB -> {db_bak}')
        if csv_path.exists():
            csv_bak = csv_path.with_suffix(f'.csv.bak-windfix-{today}')
            shutil.copy2(csv_path, csv_bak)
            print(f'[BACKUP] CSV -> {csv_bak}')

        # --- apply DB --------------------------------------------------------------
        cur = conn.execute(f'''
            UPDATE ferry_status_enhanced
            SET wind_speed = ROUND(wind_speed / 3.6, 2)
            WHERE {real_where}
        ''')
        print(f'[APPLY] DB rows updated: {cur.rowcount}')
        conn.execute(
            'INSERT INTO data_corrections (name, applied_at, detail) VALUES (?, ?, ?)',
            (MARKER, datetime.now(JST).isoformat(),
             f'wind_speed /= 3.6 for wave_height IS NULL rows; updated={cur.rowcount}')
        )
        conn.commit()
        cnt2, mn2, mx2, avg2 = db_stats(conn, real_where)
        print(f'After fix: rows={cnt2} min={mn2} max={mx2} avg={avg2:.2f}')
    finally:
        conn.close()

    # --- apply CSV ---------------------------------------------------------------
    if csv_path.exists() and csv_fix_idx:
        for i in csv_fix_idx:
            r = csv_rows[i]
            for col in ('風速_ms', 'wind_speed'):
                v = (r.get(col) or '').strip()
                if v:
                    try:
                        r[col] = f'{float(v) / 3.6:.2f}'
                    except ValueError:
                        pass
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f'[APPLY] CSV rows updated: {len(csv_fix_idx)}')

    print('[SUCCESS] Correction complete')
    return 0


if __name__ == '__main__':
    sys.exit(main())
