#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JST (Japan Standard Time) utility functions.

Use these instead of datetime.now() or SQLite date('now') to avoid UTC
mismatches on Railway (and any other UTC-hosted server).

Usage:
    from jst_utils import now_jst, today_jst_str, jst_isoformat

    # Replace datetime.now() → now_jst()
    # Replace datetime.now().date().isoformat() → today_jst_str()
    # Replace datetime.now().isoformat() → jst_isoformat()

    # In SQLite queries replace date('now') with a parameter:
    #   WHERE forecast_for_date >= date('now')
    #   →
    #   WHERE forecast_for_date >= ?   params: (today_jst_str(),)
"""

from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo          # Python 3.9+
    _JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz                            # fallback (Python 3.8 / pytz installed)
    _JST = pytz.timezone("Asia/Tokyo")


def now_jst() -> datetime:
    """Return timezone-aware datetime in JST (replaces datetime.now())."""
    return datetime.now(_JST)


def today_jst_str() -> str:
    """Return today's date in JST as ISO string 'YYYY-MM-DD'
    (replaces datetime.now().date().isoformat() and SQLite date('now')).
    """
    return now_jst().date().isoformat()


def jst_isoformat() -> str:
    """Return current JST datetime as ISO 8601 string
    (replaces datetime.now().isoformat() for timestamps stored in DB).
    """
    return now_jst().isoformat()


def days_from_today_jst(days: int) -> str:
    """Return ISO date string N days from today (JST).
    Replaces: (datetime.now().date() + timedelta(days=N)).isoformat()
    """
    return (now_jst().date() + timedelta(days=days)).isoformat()
