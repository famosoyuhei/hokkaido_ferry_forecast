#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync the accuracy export payload to Google Sheets (GitHub Actions version).

Replaces the n8n workflow "Hokkaido Ferry & Flight Accuracy to Google Sheets".
Fetches the read-only export from the Railway app and upserts every dataset
into its sheet tab, matching rows on the `key` column (same semantics as the
n8n Google Sheets appendOrUpdate nodes). Only rows whose values differ are
written; new keys are appended.

Required environment variables:
  ADMIN_TOKEN                 X-Admin-Token for the export endpoint
  GOOGLE_SERVICE_ACCOUNT_JSON Service-account key JSON (spreadsheet must be
                              shared with the service-account email as editor)
Optional:
  SPREADSHEET_ID              Target spreadsheet (default: accuracy sheet)
  EXPORT_URL                  Export endpoint (default: ?days=90)
"""

import json
import os
import sys
import urllib.request

EXPORT_URL = os.environ.get(
    'EXPORT_URL',
    'https://web-production-a628.up.railway.app/admin/export-accuracy-data?days=90',
)
SPREADSHEET_ID = os.environ.get(
    'SPREADSHEET_ID', '1C2kvlDZxo0XBagaZfZw3muShhm2Z3XGu9wMIK90kmUM'
)
SHEETS_API = 'https://sheets.googleapis.com/v4/spreadsheets'

DATASET_TABS = {
    'daily_metrics': 'Daily Metrics',
    'ferry_details': 'Ferry Details',
    'flight_details': 'Flight Details',
    'alerts': 'Alerts',
    'forecast_snapshots': 'Forecast Snapshots',
    'actual_snapshots': 'Actual Snapshots',
}


def fetch_payload() -> dict:
    token = os.environ.get('ADMIN_TOKEN')
    if not token:
        raise RuntimeError('ADMIN_TOKEN is not set')
    req = urllib.request.Request(
        EXPORT_URL, headers={'X-Admin-Token': token}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        if resp.status != 200:
            raise RuntimeError(f'Export endpoint returned HTTP {resp.status}')
        payload = json.load(resp)
    if payload.get('status') != 'success':
        raise RuntimeError(f"Export payload status is {payload.get('status')!r}")
    return payload


def access_token() -> str:
    from google.oauth2 import service_account
    import google.auth.transport.requests

    raw = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not raw:
        raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON is not set')
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw),
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def api(token: str, method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode('utf-8')
        return json.loads(raw) if raw else {}


def cell(value) -> str:
    """Serialize a payload value the way it should appear in a cell."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def get_values(token: str, tab: str) -> list[list[str]]:
    from urllib.parse import quote

    url = f"{SHEETS_API}/{SPREADSHEET_ID}/values/{quote(tab, safe='')}"
    result = api(token, 'GET', url)
    return result.get('values', [])


def sync_dataset(token: str, tab: str, rows: list[dict]) -> dict:
    existing = get_values(token, tab)
    if existing:
        header = [str(h).strip() for h in existing[0]]
        body = existing[1:]
    else:
        header, body = [], []

    # Extend the header with any payload fields the sheet does not have yet.
    new_fields = []
    for row in rows:
        for field in row:
            if field not in header and field not in new_fields:
                new_fields.append(field)
    if not header and rows:
        header = list(rows[0].keys())
        new_fields = [f for f in new_fields if f not in header]
    header_changed = bool(new_fields)
    header = header + new_fields

    if 'key' not in header:
        raise RuntimeError(f"Tab {tab!r} has no 'key' column")
    key_idx = header.index('key')

    existing_by_key: dict[str, tuple[int, list[str]]] = {}
    for i, raw_row in enumerate(body):
        padded = list(raw_row) + [''] * (len(header) - len(raw_row))
        key = padded[key_idx] if key_idx < len(padded) else ''
        if key and key not in existing_by_key:
            existing_by_key[key] = (i + 2, padded)  # 1-based, below header

    updates = []  # (row_number, values)
    inserts = []  # values
    unchanged = 0
    for row in rows:
        values = [cell(row.get(field)) for field in header]
        key = values[key_idx]
        if not key:
            continue
        if key in existing_by_key:
            row_number, current = existing_by_key[key]
            if current[: len(values)] != values:
                updates.append((row_number, values))
            else:
                unchanged += 1
        else:
            inserts.append(values)

    quoted = f"'{tab}'"
    value_ranges = []
    if header_changed or not existing:
        value_ranges.append(
            {'range': f'{quoted}!A1', 'majorDimension': 'ROWS', 'values': [header]}
        )
    for row_number, values in updates:
        value_ranges.append(
            {
                'range': f'{quoted}!A{row_number}',
                'majorDimension': 'ROWS',
                'values': [values],
            }
        )
    if value_ranges:
        api(
            token,
            'POST',
            f'{SHEETS_API}/{SPREADSHEET_ID}/values:batchUpdate',
            {'valueInputOption': 'RAW', 'data': value_ranges},
        )
    if inserts:
        from urllib.parse import quote

        url = (
            f"{SHEETS_API}/{SPREADSHEET_ID}/values/{quote(tab, safe='')}"
            ':append?valueInputOption=RAW&insertDataOption=INSERT_ROWS'
        )
        api(token, 'POST', url, {'majorDimension': 'ROWS', 'values': inserts})

    return {
        'tab': tab,
        'payload_rows': len(rows),
        'updated': len(updates),
        'inserted': len(inserts),
        'unchanged': unchanged,
    }


def main() -> int:
    payload = fetch_payload()
    datasets = payload.get('datasets') or {}
    token = access_token()
    summaries = []
    for dataset, tab in DATASET_TABS.items():
        rows = datasets.get(dataset) or []
        summaries.append(sync_dataset(token, tab, rows))
    for s in summaries:
        print(
            f"{s['tab']}: payload={s['payload_rows']} "
            f"updated={s['updated']} inserted={s['inserted']} "
            f"unchanged={s['unchanged']}"
        )
    period = payload.get('period') or {}
    print(f"Sync complete for period {period.get('start')}..{period.get('end')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
