#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE Messaging API Bot Service
公式アカウントのWebhookハンドラ・朝の欠航リスク通知送信を担う。

必要な環境変数:
  LINE_CHANNEL_ACCESS_TOKEN  Long-lived channel access token
  LINE_CHANNEL_SECRET        Webhook署名検証用シークレット
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import pytz

from jst_utils import get_active_routes_on, get_timetable_sailings
from flight_timetable_utils import get_active_flights_on

jst = pytz.timezone('Asia/Tokyo')

try:
    from linebot.v3 import WebhookParser
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.webhooks import (
        MessageEvent, FollowEvent, UnfollowEvent, TextMessageContent
    )
    from linebot.v3.messaging import (
        Configuration, ApiClient, MessagingApi,
        PushMessageRequest, ReplyMessageRequest, TextMessage,
        QuickReply, QuickReplyItem, MessageAction
    )
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False
    InvalidSignatureError = Exception  # fallback for type hints


ROUTE_DISPLAY = {
    'wakkanai_oshidomari': '稚内→鴛泊',
    'oshidomari_wakkanai': '鴛泊→稚内',
    'wakkanai_kafuka':     '稚内→香深',
    'kafuka_wakkanai':     '香深→稚内',
    'oshidomari_kafuka':   '鴛泊→香深',
    'kafuka_oshidomari':   '香深→鴛泊',
    'kutsugata_kafuka':    '沓形→香深',  # 夏季のみ（6/1〜9/30）
    'kafuka_kutsugata':    '香深→沓形',  # 夏季のみ（6/1〜9/30）
}
ROUTE_DISPLAY_REVERSE = {v: k for k, v in ROUTE_DISPLAY.items()}
RISK_EMOJI = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢', 'MINIMAL': '⚪'}
RISK_ORDER = ['HIGH', 'MEDIUM', 'LOW', 'MINIMAL']
WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日']

# ---------------------------------------------------------------------------
# 運航航路は jst_utils.get_active_routes_on() を使う。
# 正ソース: skills/ferry-cancellation-research/references/heartland_{year}_timetable.json
# 年が変わったら heartland_{year}_timetable.json を追加するだけでよい。
# ---------------------------------------------------------------------------

DASHBOARD_URL = 'https://web-production-a628.up.railway.app/'


class LineBotService:
    """LINE Messaging API を使った欠航リスク通知サービス。"""

    def __init__(self):
        self.channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
        self.channel_secret = os.getenv('LINE_CHANNEL_SECRET', '')
        self.enabled = bool(
            LINE_SDK_AVAILABLE
            and self.channel_access_token
            and self.channel_secret
        )

        data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
        self.notif_db = os.path.join(data_dir, 'notifications.db')
        self.forecast_db = os.path.join(data_dir, 'ferry_weather_forecast.db')
        self.ferry_db = os.path.join(data_dir, 'heartland_ferry_real_data.db')

        self._init_db()

        if self.enabled:
            self._parser = WebhookParser(self.channel_secret)
            print('LINE Bot Service: enabled')
        elif not LINE_SDK_AVAILABLE:
            print('LINE Bot Service: disabled (line-bot-sdk not installed)')
        else:
            print('LINE Bot Service: disabled (env vars not set)')

    # ------------------------------------------------------------------
    # DB 初期化
    # ------------------------------------------------------------------

    def _init_db(self):
        conn = sqlite3.connect(self.notif_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS line_users (
                line_user_id  TEXT PRIMARY KEY,
                display_name  TEXT,
                subscribed_routes TEXT DEFAULT '[]',
                min_risk_level    TEXT DEFAULT 'HIGH',
                active        BOOLEAN DEFAULT 1,
                followed_at   TEXT,
                updated_at    TEXT
            )
        ''')
        # 朝通知の実行ログ（line_audit.py が参照）
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notification_log (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                sent     INTEGER NOT NULL DEFAULT 0,
                skipped  INTEGER NOT NULL DEFAULT 0,
                errors   INTEGER NOT NULL DEFAULT 0,
                ran_at   TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Webhook 処理
    # ------------------------------------------------------------------

    def verify_and_parse(self, body: str, signature: str) -> list:
        """署名を検証してイベントリストを返す。InvalidSignatureError を伝播させる。"""
        if not self.enabled:
            raise RuntimeError('LINE Bot not configured')
        return self._parser.parse(body, signature)

    def handle_events(self, events: list):
        for event in events:
            try:
                if isinstance(event, FollowEvent):
                    self._on_follow(event)
                elif isinstance(event, UnfollowEvent):
                    self._on_unfollow(event)
                elif isinstance(event, MessageEvent):
                    if isinstance(event.message, TextMessageContent):
                        self._on_message(event)
            except Exception as e:
                print(f'[LINE] Event handling error: {e}')

    def _on_follow(self, event):
        user_id = event.source.user_id
        now = datetime.now(jst).isoformat()
        conn = sqlite3.connect(self.notif_db)
        conn.execute('''
            INSERT OR REPLACE INTO line_users
                (line_user_id, active, followed_at, updated_at)
            VALUES (?, 1, COALESCE(
                (SELECT followed_at FROM line_users WHERE line_user_id = ?), ?
            ), ?)
        ''', (user_id, user_id, now, now))
        conn.commit()
        conn.close()
        print(f'[LINE] Follow: {user_id[:12]}...')

        welcome = (
            '🚢 フェリー欠航リスク予報へようこそ！\n\n'
            '毎朝6:30ごろ、欠航リスクが高い日のみ通知をお届けします。\n'
            '（HIGH リスクの便がない日は通知しません）\n\n'
            '━ 対象航路 ━\n'
            '稚内⇔鴛泊（利尻）\n'
            '稚内⇔香深（礼文）\n'
            '稚内⇔沓形（利尻）\n'
            '鴛泊⇔香深\n\n'
            '「予報」と送ると今日のリスクを確認できます。\n\n'
            '📦 仕入れ計画などで特定の航路を継続的に見たい方へ:\n'
            '「航路設定」と送ると航路を1つ選べます。設定すると、\n'
            'リスクの高低に関わらず毎朝その航路の状況と\n'
            '今後7日間の見通しをお届けします。\n\n'
            f'詳細予報: {DASHBOARD_URL}'
        )
        self._push(user_id, welcome)

    def _on_unfollow(self, event):
        user_id = event.source.user_id
        now = datetime.now(jst).isoformat()
        conn = sqlite3.connect(self.notif_db)
        conn.execute(
            'UPDATE line_users SET active=0, updated_at=? WHERE line_user_id=?',
            (now, user_id)
        )
        conn.commit()
        conn.close()
        print(f'[LINE] Unfollow: {user_id[:12]}...')

    def _on_message(self, event):
        user_id = event.source.user_id
        text = event.message.text.strip()

        if text in ('予報', '今日', 'フェリー', '確認', '今日は？', 'リスク'):
            msg = self._format_notification(for_user_id=user_id)
            if msg is None:
                today = datetime.now(jst)
                today_str = today.strftime(f'%m/%d（{WEEKDAYS[today.weekday()]}）')
                msg = (
                    f'✅ {today_str}\n'
                    '現在、欠航リスクが高い便はありません。\n\n'
                    f'詳細予報: {DASHBOARD_URL}'
                )
            self._reply(event.reply_token, msg)

        elif text in ('明日', 'あした', '明日は？', '明日のリスク'):
            msg = self._format_tomorrow_message()
            self._reply(event.reply_token, msg)

        elif text in ('明後日', 'あさって', '明後日は？', '明後日のリスク'):
            msg = self._format_asatte_message()
            self._reply(event.reply_token, msg)

        elif text in ('実績', '欠航実績', '実績確認'):
            msg = self._format_jisseki_message()
            self._reply(event.reply_token, msg)

        elif text in ('飛行機', 'フライト', '✈️', '飛行機予報', '利尻便', '飛行機リスク'):
            msg = self._format_flight_message()
            self._reply(event.reply_token, msg)

        elif text in ('週間', '1週間', '週間予報', '7日間', '今週'):
            msg = self._format_weekly_message(user_id)
            self._reply(event.reply_token, msg)

        elif text in ('航路設定', '路線設定', '航路変更', 'ルート設定', '通知設定'):
            self._send_route_menu(event.reply_token)

        elif text in ROUTE_DISPLAY_REVERSE:
            route_key = ROUTE_DISPLAY_REVERSE[text]
            self._set_subscribed_routes(user_id, [route_key])
            self._reply(event.reply_token,
                f'✅ 「{text}」に絞った通知に設定しました。\n\n'
                '毎朝、この航路の本日の状況と今後7日間の見通しを\n'
                'リスクの高低に関わらずお届けします。\n\n'
                '「週間」でいつでも見通しを確認できます。\n'
                '解除するには「全航路」と送ってください。'
            )

        elif text in ('全航路', '航路解除', '解除'):
            self._set_subscribed_routes(user_id, [])
            self._reply(event.reply_token,
                '✅ 航路の絞り込みを解除しました。\n'
                '全航路を対象に、リスクが高い日のみ通知します。'
            )

        elif text in ('ヘルプ', 'help', '？', '?', 'コマンド'):
            self._reply(event.reply_token,
                '【コマンド一覧】\n'
                '「予報」または「今日」: 今日のフェリーリスク確認\n'
                '「明日」: 明日のフェリーリスク確認\n'
                '「明後日」: 明後日のフェリーリスク確認\n'
                '「実績」: 直近7日間の欠航実績\n'
                '「飛行機」: 利尻空港の飛行機予報\n'
                '「航路設定」: 通知する航路を1つ選ぶ（仕入れ計画向け）\n'
                '「週間」: 設定した航路の7日間見通し\n'
                '「全航路」: 航路の絞り込みを解除\n\n'
                '航路を設定していない場合、欠航リスクが高い日のみ\n'
                '毎朝自動通知します。設定している場合は毎朝、\n'
                'リスクの高低に関わらずその航路の状況を届けます。\n'
                f'詳細: {DASHBOARD_URL}'
            )

    # ------------------------------------------------------------------
    # メッセージ生成
    # ------------------------------------------------------------------

    def _query_risks(self, date_str: str):
        """
        指定日の航路別リスクをDBから取得する共通ヘルパー。
        [(route, risk_level, wind_forecast, wave_forecast)] を返す。
        DB エラー時は None を返す。
        （通知・実績など、航路単位で1件あれば足りる用途向け）
        """
        try:
            conn = sqlite3.connect(self.forecast_db)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT route, risk_level, wind_forecast, wave_forecast
                FROM cancellation_forecast
                WHERE forecast_for_date = ?
                  AND id IN (
                      SELECT MAX(id) FROM cancellation_forecast
                      WHERE forecast_for_date = ?
                      GROUP BY route
                  )
            ''', (date_str, date_str))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f'[LINE] _query_risks({date_str}) error: {e}')
            return None

    def _query_hourly_risks(self, date_str: str) -> Optional[Dict]:
        """
        指定日の全 forecast_hour × route のリスクを取得する。
        便別表示用: {(route, forecast_hour): (risk_level, wind, wave)} を返す。

        各 (route, forecast_hour) ごとの最新レコード（MAX(id)）を使用。
        DB エラー時は None を返す。
        """
        try:
            conn = sqlite3.connect(self.forecast_db)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT route, forecast_hour, risk_level, wind_forecast, wave_forecast
                FROM cancellation_forecast
                WHERE forecast_for_date = ?
                  AND id IN (
                      SELECT MAX(id) FROM cancellation_forecast
                      WHERE forecast_for_date = ?
                      GROUP BY route, forecast_hour
                  )
                ORDER BY route, forecast_hour
            ''', (date_str, date_str))
            result: Dict = {}
            for route, hour, risk, wind, wave in cursor.fetchall():
                result[(route, hour)] = (risk, wind, wave)
            conn.close()
            return result
        except Exception as e:
            print(f'[LINE] _query_hourly_risks({date_str}) error: {e}')
            return None

    def _get_today_risks(self) -> Dict[str, dict]:
        """本日の航路別リスクを返す。{route: {risk, wind, wave}}"""
        today = datetime.now(jst).strftime('%Y-%m-%d')
        rows = self._query_risks(today)
        if not rows:
            return {}
        result = {}
        active_routes = set(get_active_routes_on(today))
        for route, risk, wind, wave in rows:
            if route not in active_routes or route not in ROUTE_DISPLAY:
                continue
            result[route] = {'risk': risk, 'wind': wind, 'wave': wave}
        return result

    def _get_forecast_days(self, n: int = 3) -> List[dict]:
        """今後N日間の日別最高リスクを返す。[{date, risk, wind, wave}]"""
        today = datetime.now(jst)
        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()
        rows = []
        for i in range(1, n + 1):
            d = (today + timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT risk_level, AVG(wind_forecast), AVG(wave_forecast)
                FROM cancellation_forecast
                WHERE forecast_for_date = ?
                GROUP BY risk_level
                ORDER BY CASE risk_level
                    WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 3 ELSE 4 END
                LIMIT 1
            ''', (d,))
            row = cursor.fetchone()
            if row:
                rows.append({'date': d, 'risk': row[0], 'wind': row[1], 'wave': row[2]})
            else:
                rows.append({'date': d, 'risk': None, 'wind': None, 'wave': None})
        conn.close()
        return rows

    def _get_route_forecast_days(self, route: str, days_ahead: int = 7) -> List[dict]:
        """
        指定航路の明日から今後N日間の日別最悪リスクを返す。
        [{date, risk, wind, wave}]（データがない日は risk=None）
        """
        today = datetime.now(jst)
        start_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT forecast_for_date, risk_level, wind_forecast, wave_forecast
            FROM cancellation_forecast
            WHERE route = ?
              AND forecast_for_date BETWEEN ? AND ?
              AND id IN (
                  SELECT MAX(id) FROM cancellation_forecast
                  WHERE route = ? AND forecast_for_date BETWEEN ? AND ?
                  GROUP BY forecast_for_date, forecast_hour
              )
            ORDER BY forecast_for_date
        ''', (route, start_date, end_date, route, start_date, end_date))
        rows = cursor.fetchall()
        conn.close()

        by_date: Dict[str, list] = {}
        for date, risk, wind, wave in rows:
            by_date.setdefault(date, []).append((risk, wind, wave))

        result = []
        for i in range(1, days_ahead + 1):
            d_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
            entries = by_date.get(d_str)
            if not entries:
                result.append({'date': d_str, 'risk': None, 'wind': None, 'wave': None})
                continue
            entries.sort(key=lambda e: RISK_ORDER.index(e[0]) if e[0] in RISK_ORDER else len(RISK_ORDER))
            worst_risk, wind, wave = entries[0]
            result.append({'date': d_str, 'risk': worst_risk, 'wind': wind, 'wave': wave})
        return result

    def _format_weekly_message(self, user_id: str) -> str:
        """ユーザーが設定した航路の7日間見通しを返す。航路未設定なら設定を促す。"""
        conn = sqlite3.connect(self.notif_db)
        row = conn.execute(
            'SELECT subscribed_routes FROM line_users WHERE line_user_id=?', (user_id,)
        ).fetchone()
        conn.close()

        routes = json.loads(row[0] or '[]') if row else []
        routes = [r for r in routes if r in ROUTE_DISPLAY]
        if not routes:
            return (
                '📅 週間予報を見るには、まず航路を設定してください。\n\n'
                '「航路設定」と送ると、対象航路を選べます。'
            )

        lines = ['📅 週間予報（明日から7日間）', '']
        for route in routes:
            name = ROUTE_DISPLAY[route]
            lines.append(f'━━ {name} ━━')
            for f in self._get_route_forecast_days(route, days_ahead=7):
                d = datetime.strptime(f['date'], '%Y-%m-%d')
                d_str = d.strftime(f'%m/%d（{WEEKDAYS[d.weekday()]}）')
                if not f['risk']:
                    lines.append(f'{d_str}  ❓ 予報データなし')
                    continue
                emoji = RISK_EMOJI.get(f['risk'], '❓')
                parts = []
                if f['wind']:
                    parts.append(f"風{f['wind']:.0f}m/s")
                if f['wave']:
                    parts.append(f"波{f['wave']:.1f}m")
                detail = '（' + ' '.join(parts) + '）' if parts else ''
                lines.append(f'{d_str}  {emoji} {f["risk"]}{detail}')
            lines.append('')

        lines.append('※ 先の日ほど予報精度は下がります。仕入れ判断は直前の更新も確認してください。')
        lines.append(f'詳細: {DASHBOARD_URL}')
        return '\n'.join(lines)

    def _send_route_menu(self, reply_token: str):
        """航路選択のクイックリプライを送る。"""
        if not self.enabled:
            return
        items = [
            QuickReplyItem(action=MessageAction(label=name, text=name))
            for name in ROUTE_DISPLAY.values()
        ]
        items.append(QuickReplyItem(action=MessageAction(label='全航路（解除）', text='全航路')))

        configuration = Configuration(access_token=self.channel_access_token)
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(
                    text='通知を絞り込む航路を選んでください👇\n（設定すると毎朝その航路の7日間見通しが届きます）',
                    quick_reply=QuickReply(items=items)
                )]
            ))

    def _set_subscribed_routes(self, user_id: str, routes: List[str]):
        """ユーザーの購読航路を更新する。"""
        now = datetime.now(jst).isoformat()
        conn = sqlite3.connect(self.notif_db)
        conn.execute(
            'UPDATE line_users SET subscribed_routes=?, updated_at=? WHERE line_user_id=?',
            (json.dumps(routes, ensure_ascii=False), now, user_id)
        )
        conn.commit()
        conn.close()

    def _format_risk_message(self, date_str: str, header: str) -> str:
        """
        指定日の便別欠航リスクをメッセージ化する共通ヘルパー。

        変更点（v2）:
        - 1航路1行 → 便ごとに出発時刻 + リスクを表示
        - forecast_hour × route の時間別予報を取得し、
          各便の出発時刻に最も近い forecast_hour のリスクを割り当てる
        - 同じ航路でも便ごとに気象が変われば異なるリスクが表示される
        """
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_display = date_obj.strftime(f'%m/%d（{WEEKDAYS[date_obj.weekday()]}）')

        # 1. 当日の運航便を時刻表で確定
        active = get_active_routes_on(date_str)
        if not active:
            return (
                f'{header}の欠航リスク\n{date_display}\n\n'
                '運航便なし（時刻表）\n'
                f'詳細: {DASHBOARD_URL}'
            )

        # 2. 時間別リスクを取得（None = DBエラー）
        hourly = self._query_hourly_risks(date_str)
        if hourly is None:
            return (
                f'{header} {date_display} の予報\n\n'
                'データ取得中にエラーが発生しました。\n'
                f'詳細: {DASHBOARD_URL}'
            )

        lines = [f'{header}の欠航リスク', date_display, '']
        has_alert = False

        # 利用可能な forecast_hour リスト（ソート済み）
        avail_hours = sorted({h for (_, h) in hourly.keys()})

        def _nearest_risk(route: str, dep_hour: int):
            """出発時刻の hour に最も近い forecast_hour のリスクを返す。"""
            if not avail_hours:
                return None, None, None
            best_h = min(avail_hours, key=lambda h: abs(h - dep_hour))
            return hourly.get((route, best_h), (None, None, None))

        # リスク優先度（各航路の最悪便で並べ替え）
        def route_worst_risk(route):
            sailings = get_timetable_sailings(route, date_str)
            worst = len(RISK_ORDER)
            for dep, _ in sailings:
                dep_h = int(dep.split(':')[0])
                risk, _, _ = _nearest_risk(route, dep_h)
                idx = RISK_ORDER.index(risk) if risk in RISK_ORDER else len(RISK_ORDER)
                worst = min(worst, idx)
            return worst

        for route in sorted(active, key=route_worst_risk):
            name = ROUTE_DISPLAY.get(route, route)
            sailings = get_timetable_sailings(route, date_str)

            if not sailings:
                lines.append(f'❓ {name}  （時刻表データなし）')
                continue

            for dep_time, arr_time in sailings:
                dep_h = int(dep_time.split(':')[0])
                risk, wind, wave = _nearest_risk(route, dep_h)

                if risk is None:
                    lines.append(f'❓ {name} {dep_time}発  （予報データなし）')
                    continue

                emoji = RISK_EMOJI.get(risk, '❓')
                parts = []
                if wind:
                    parts.append(f'風{wind:.0f}m/s')
                if wave:
                    parts.append(f'波{wave:.1f}m')
                detail = '（' + ' '.join(parts) + '）' if parts else ''
                lines.append(f'{emoji} {name} {dep_time}発  {risk}{detail}')
                if risk in ('HIGH', 'MEDIUM'):
                    has_alert = True

        lines.append('')
        if has_alert:
            lines.append('⚠️ 仕入れ計画をご確認ください')
        else:
            lines.append('✅ 欠航リスクは低い見込みです')

        # ── 飛行機セクション（データがある場合のみ追加）──
        flight_lines = self._flight_summary_lines(date_str)
        if flight_lines:
            lines.append('')
            lines += flight_lines

        lines.append(f'詳細: {DASHBOARD_URL}')
        return '\n'.join(lines)

    def _flight_summary_lines(self, date_str: str) -> list:
        """
        指定日の飛行機リスクを1〜2行にまとめて返す（フェリーメッセージに埋め込む用）。
        データなし・全便MINIMAL・エラーの場合は空リストを返す。
        """
        try:
            flights = get_active_flights_on(date_str)
            if not flights:
                return []
            rows = self._query_flight_risks(date_str)
            if not rows:
                return []

            risk_map = {(r[1], r[4]): r for r in rows}
            worst_risk = 'MINIMAL'
            risk_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'MINIMAL': 1}
            alerts = []

            for f in flights:
                key = (f['flight_no'], f['rishiri_role'])
                if key in risk_map:
                    _, _, _, _, _, risk, wind, cw = risk_map[key]
                    if risk_priority.get(risk, 0) > risk_priority.get(worst_risk, 0):
                        worst_risk = risk
                    if risk in ('HIGH', 'MEDIUM'):
                        role_jp = '着' if f['rishiri_role'] == 'arrival' else '発'
                        emoji = RISK_EMOJI.get(risk, '❓')
                        alerts.append(f'  {emoji} {f["flight_no"]} {f["rishiri_time"]}{role_jp}')

            emoji_worst = RISK_EMOJI.get(worst_risk, '❓')
            if worst_risk in ('HIGH', 'MEDIUM'):
                result = [f'✈️ 飛行機: {emoji_worst} {worst_risk}'] + alerts
            else:
                result = [f'✈️ 飛行機: {emoji_worst} MINIMAL（全便低リスク）']
            return result
        except Exception:
            return []

    def _format_tomorrow_message(self) -> str:
        """明日の全航路リスクを返す。"""
        tomorrow = datetime.now(jst) + timedelta(days=1)
        return self._format_risk_message(tomorrow.strftime('%Y-%m-%d'), '🗓️ 明日')

    def _format_asatte_message(self) -> str:
        """明後日の全航路リスクを返す。"""
        asatte = datetime.now(jst) + timedelta(days=2)
        return self._format_risk_message(asatte.strftime('%Y-%m-%d'), '📅 明後日')

    def _format_jisseki_message(self) -> str:
        """直近7日間の欠航実績を ferry_status_enhanced から返す。"""
        today = datetime.now(jst)
        start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')

        try:
            conn = sqlite3.connect(self.ferry_db)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT scrape_date, route, departure_time, is_cancelled
                FROM ferry_status_enhanced
                WHERE scrape_date >= ?
                ORDER BY scrape_date DESC, route, departure_time
            ''', (start_date,))
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            return (
                '📋 欠航実績の取得に失敗しました。\n'
                f'詳細: {DASHBOARD_URL}'
            )

        if not rows:
            return (
                '📋 直近7日間の欠航実績\n\n'
                'データがありません。\n'
                f'詳細: {DASHBOARD_URL}'
            )

        # 日別集計
        daily_totals: Dict[str, int] = {}
        daily_cancelled: Dict[str, int] = {}
        cancelled_routes_by_day: Dict[str, List[str]] = {}

        for scrape_date, route, dep_time, is_cancelled in rows:
            daily_totals[scrape_date] = daily_totals.get(scrape_date, 0) + 1
            if is_cancelled:
                daily_cancelled[scrape_date] = daily_cancelled.get(scrape_date, 0) + 1
                name = ROUTE_DISPLAY.get(route, route)
                cancelled_routes_by_day.setdefault(scrape_date, []).append(name)

        lines = ['📋 直近7日間の欠航実績', '']

        for date_str in sorted(daily_totals.keys(), reverse=True):
            d = datetime.strptime(date_str, '%Y-%m-%d')
            d_label = d.strftime(f'%m/%d（{WEEKDAYS[d.weekday()]}）')
            cancelled = daily_cancelled.get(date_str, 0)
            total = daily_totals[date_str]

            if cancelled > 0:
                lines.append(f'🔴 {d_label}: {cancelled}/{total}便欠航')
                seen: List[str] = []
                for r in (cancelled_routes_by_day.get(date_str) or []):
                    if r not in seen:
                        seen.append(r)
                for r in seen[:4]:
                    lines.append(f'   ↳ {r}')
            else:
                lines.append(f'✅ {d_label}: 全便運航')

        lines.append('')
        lines.append(f'詳細: {DASHBOARD_URL}')
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # 飛行機予報
    # ------------------------------------------------------------------

    def _query_flight_risks(self, date_str: str) -> Optional[List]:
        """
        flight_cancellation_forecast から指定日の便別リスクを取得する。
        [(route_key, flight_no, airline, rishiri_time, rishiri_role,
          risk_level, wind_speed, crosswind_component)] のリストを返す。
        DB エラー時は None を返す。
        """
        try:
            conn = sqlite3.connect(self.forecast_db)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT route_key, flight_no, airline, rishiri_time, rishiri_role,
                       risk_level, wind_speed, crosswind_component
                FROM flight_cancellation_forecast
                WHERE forecast_for_date = ?
                  AND id IN (
                      SELECT MAX(id) FROM flight_cancellation_forecast
                      WHERE forecast_for_date = ?
                      GROUP BY route_key, flight_no
                  )
                ORDER BY rishiri_time
            ''', (date_str, date_str))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return None

    def _format_flight_message(self) -> str:
        """
        今日と明日の飛行機予報をフォーマットして返す。
        """
        now = datetime.now(jst)
        today_str    = now.strftime('%Y-%m-%d')
        tomorrow_str = (now + timedelta(days=1)).strftime('%Y-%m-%d')

        lines = ['✈️ 利尻空港 飛行機予報', '']

        for date_str, label in [(today_str, '今日'), (tomorrow_str, '明日')]:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_disp = date_obj.strftime(f'%m/%d（{WEEKDAYS[date_obj.weekday()]}）')

            # 時刻表で就航便を確認
            flights = get_active_flights_on(date_str)
            if not flights:
                lines.append(f'[{label} {date_disp}]')
                lines.append('就航便なし（時刻表）')
                lines.append('')
                continue

            # DBからリスクを取得
            rows = self._query_flight_risks(date_str)

            lines.append(f'[{label} {date_disp}]')

            if rows is None:
                lines.append('データ取得エラー')
                lines.append('')
                continue

            if not rows:
                # テーブルはあるがデータなし（次回収集待ち）
                lines.append('予報データ準備中…')
                lines.append(f'（就航便: {len(flights)}便）')
                lines.append('')
                continue

            # {(flight_no, rishiri_role): データ} のマップ
            risk_map = {
                (r[1], r[4]): r  # (flight_no, role): row
                for r in rows
            }

            has_alert = False
            for f in flights:
                key = (f['flight_no'], f['rishiri_role'])
                role_jp = '着' if f['rishiri_role'] == 'arrival' else '発'
                airline = f['airline']
                time_str = f['rishiri_time']

                if key in risk_map:
                    _, _, _, _, _, risk, wind, cw = risk_map[key]
                    emoji = RISK_EMOJI.get(risk, '❓')
                    detail_parts = []
                    if wind:
                        detail_parts.append(f'風{wind:.0f}m/s')
                    if cw:
                        detail_parts.append(f'横風{cw:.1f}m/s')
                    detail = '（' + ' '.join(detail_parts) + '）' if detail_parts else ''
                    lines.append(f'{emoji} [{airline}] {f["flight_no"]} {time_str}{role_jp} {risk}{detail}')
                    if risk in ('HIGH', 'MEDIUM'):
                        has_alert = True
                else:
                    lines.append(f'❓ [{airline}] {f["flight_no"]} {time_str}{role_jp} 予報データなし')

            if has_alert:
                lines.append('⚠️ フライト変更をご確認ください')
            else:
                lines.append('✅ 欠航リスクは低い見込みです')
            lines.append('')

        lines.append(f'詳細: {DASHBOARD_URL}')
        return '\n'.join(lines)

    def _format_notification(
        self,
        for_user_id: Optional[str] = None,
        route_filter: Optional[List[str]] = None,
        min_risk: str = 'HIGH',
    ) -> Optional[str]:
        """
        通知メッセージを生成する。

        - 航路を1つに絞っているユーザー（仕入れ計画向け・digest モード）:
          リスクの高低に関わらず、本日の状況 + 今後7日間の見通しを毎朝送る
          （定点観測レポート）。予報データが1件もない場合のみ None。
        - それ以外のユーザー: 従来通りアラート専用。HIGH/MEDIUM リスクが
          1件もなければ None を返し、送信をスキップする。

        for_user_id が指定された場合、その user の設定（購読航路・閾値）を
        DB から読み込んで route_filter / min_risk を上書きする。
        """
        # ユーザー設定の読み込み
        if for_user_id:
            conn = sqlite3.connect(self.notif_db)
            row = conn.execute(
                'SELECT subscribed_routes, min_risk_level FROM line_users WHERE line_user_id=?',
                (for_user_id,)
            ).fetchone()
            conn.close()
            if row:
                routes_json, min_risk_val = row
                route_filter = json.loads(routes_json or '[]') or None
                min_risk = min_risk_val or 'HIGH'

        single_route = route_filter[0] if route_filter and len(route_filter) == 1 else None
        digest_mode = single_route is not None

        today_risks = self._get_today_risks()
        today = datetime.now(jst)
        today_str = today.strftime(f'%m/%d（{WEEKDAYS[today.weekday()]}）')

        threshold_idx = RISK_ORDER.index(min_risk)

        def is_alerted(risk: Optional[str]) -> bool:
            if not risk:
                return False
            return RISK_ORDER.index(risk) <= threshold_idx

        if digest_mode:
            future_days = self._get_route_forecast_days(single_route, days_ahead=7)
            today_info = today_risks.get(single_route)

            has_data = today_info is not None or any(f['risk'] for f in future_days)
            if not has_data:
                return None  # まだ予報データが収集されていない

            route_name = ROUTE_DISPLAY.get(single_route, single_route)
            lines = [f'🚢 {route_name} 定点予報', today_str, '']

            lines.append('━━ 本日 ━━')
            if today_info:
                emoji = RISK_EMOJI.get(today_info['risk'], '❓')
                parts = []
                if today_info['wind']:
                    parts.append(f"風{today_info['wind']:.0f}m/s")
                if today_info['wave']:
                    parts.append(f"波{today_info['wave']:.1f}m")
                detail = '（' + ' '.join(parts) + '）' if parts else ''
                lines.append(f"{emoji} {today_info['risk']}{detail}")
            else:
                lines.append('❓ 予報データなし（本日運航なし、または未収集）')

            lines.append('')
            lines.append('━━ 今後7日間の見通し ━━')
            for f in future_days:
                d = datetime.strptime(f['date'], '%Y-%m-%d')
                d_str = d.strftime(f'%m/%d({WEEKDAYS[d.weekday()]})')
                if not f['risk']:
                    lines.append(f'{d_str}  ❓ データなし')
                    continue
                emoji = RISK_EMOJI.get(f['risk'], '❓')
                wind_str = f" 風{f['wind']:.0f}m/s" if f['wind'] else ''
                lines.append(f"{d_str}  {emoji} {f['risk']}{wind_str}")

            lines.append('')
            any_alert = is_alerted(today_info['risk']) if today_info else False
            any_alert = any_alert or any(is_alerted(f['risk']) for f in future_days)
            if any_alert:
                lines.append('⚠️ 仕入れ計画をご確認ください')
            else:
                lines.append('✅ 直近は欠航リスクが低い見込みです')
            lines.append('※ 先の日ほど予報精度は下がります。直前の更新も確認してください。')

        else:
            future_risks = self._get_forecast_days(3)

            filtered_today = {
                r: v for r, v in today_risks.items()
                if (route_filter is None or r in route_filter) and is_alerted(v['risk'])
            }

            has_future_alert = any(is_alerted(f['risk']) for f in future_risks)

            if not filtered_today and not has_future_alert:
                return None

            lines = [f'🚢 フェリー欠航リスク通知', today_str, '']

            lines.append('━━ 本日のリスク ━━')
            if filtered_today:
                sorted_routes = sorted(
                    filtered_today.items(),
                    key=lambda x: RISK_ORDER.index(x[1]['risk'])
                )
                for route, info in sorted_routes:
                    if route not in ROUTE_DISPLAY:
                        continue  # 廃止済み航路キーはスキップ
                    emoji = RISK_EMOJI.get(info['risk'], '❓')
                    name = ROUTE_DISPLAY[route]
                    parts = []
                    if info['wind']:
                        parts.append(f"風{info['wind']:.0f}m/s")
                    if info['wave']:
                        parts.append(f"波{info['wave']:.1f}m")
                    detail = '（' + ' '.join(parts) + '）' if parts else ''
                    lines.append(f"{emoji} {name}  {info['risk']}{detail}")
            else:
                lines.append('⚪ 欠航リスクなし')

            lines.append('')
            lines.append('━━ 今後3日間 ━━')
            for f in future_risks:
                if not f['risk']:
                    continue
                d = datetime.strptime(f['date'], '%Y-%m-%d')
                d_str = d.strftime(f'%m/%d({WEEKDAYS[d.weekday()]})')
                emoji = RISK_EMOJI.get(f['risk'], '❓')
                lines.append(f"{d_str} {emoji} {f['risk']}")

            lines.append('')

            has_high = any(v['risk'] == 'HIGH' for v in filtered_today.values())
            if has_high:
                lines.append('⚠️ 仕入れ計画をご確認ください')

        lines.append(f'詳細: {DASHBOARD_URL}')

        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # 送信
    # ------------------------------------------------------------------

    def _push(self, user_id: str, text: str):
        """特定ユーザーにプッシュ通知を送る。"""
        if not self.enabled:
            return
        configuration = Configuration(access_token=self.channel_access_token)
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)]
            ))

    def _reply(self, reply_token: str, text: str):
        """ユーザーのメッセージに返信する。"""
        if not self.enabled:
            return
        configuration = Configuration(access_token=self.channel_access_token)
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            ))

    def send_morning_notifications(self) -> dict:
        """
        全アクティブユーザーに朝の通知を送る。
        HIGH リスクがない日はユーザーに送信しない。
        Returns: {'sent': N, 'skipped': M, 'errors': K}
        """
        if not self.enabled:
            print('[LINE] Disabled — skipping morning notifications')
            return {'sent': 0, 'skipped': 0, 'errors': 0}

        conn = sqlite3.connect(self.notif_db)
        users = conn.execute(
            'SELECT line_user_id, subscribed_routes, min_risk_level FROM line_users WHERE active=1'
        ).fetchall()
        conn.close()

        if not users:
            print('[LINE] No active users to notify')
            return {'sent': 0, 'skipped': 0, 'errors': 0}

        sent = skipped = errors = 0
        for user_id, routes_json, min_risk in users:
            routes = json.loads(routes_json or '[]') or None
            msg = self._format_notification(
                route_filter=routes,
                min_risk=min_risk or 'HIGH'
            )
            if msg is None:
                skipped += 1
                continue
            try:
                self._push(user_id, msg)
                sent += 1
                print(f'[LINE] Sent to {user_id[:12]}...')
            except Exception as e:
                errors += 1
                print(f'[LINE] Error sending to {user_id[:12]}...: {e}')

        print(f'[LINE] Morning notifications done: sent={sent} skipped={skipped} errors={errors}')

        # 実行ログを notification_log に保存
        try:
            now = datetime.now(jst).isoformat()
            today_str = datetime.now(jst).strftime('%Y-%m-%d')
            conn = sqlite3.connect(self.notif_db)
            conn.execute(
                'INSERT INTO notification_log (run_date, sent, skipped, errors, ran_at) VALUES (?, ?, ?, ?, ?)',
                (today_str, sent, skipped, errors, now)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f'[LINE] notification_log 保存失敗: {e}')

        return {'sent': sent, 'skipped': skipped, 'errors': errors}

    def get_stats(self) -> dict:
        """管理用統計を返す。"""
        try:
            conn = sqlite3.connect(self.notif_db)
            total = conn.execute('SELECT COUNT(*) FROM line_users').fetchone()[0]
            active = conn.execute(
                'SELECT COUNT(*) FROM line_users WHERE active=1'
            ).fetchone()[0]
            conn.close()
        except Exception:
            total = active = 0
        return {
            'enabled': self.enabled,
            'sdk_available': LINE_SDK_AVAILABLE,
            'total_users': total,
            'active_users': active,
        }


# シングルトン
_service: Optional['LineBotService'] = None


def get_service() -> 'LineBotService':
    global _service
    if _service is None:
        _service = LineBotService()
    return _service
