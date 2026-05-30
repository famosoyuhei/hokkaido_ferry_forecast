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

jst = pytz.timezone('Asia/Tokyo')

try:
    from linebot.v3 import WebhookParser
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.webhooks import (
        MessageEvent, FollowEvent, UnfollowEvent, TextMessageContent
    )
    from linebot.v3.messaging import (
        Configuration, ApiClient, MessagingApi,
        PushMessageRequest, ReplyMessageRequest, TextMessage
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
    'wakkanai_kutsugata':  '稚内→沓形',
    'kutsugata_wakkanai':  '沓形→稚内',
    'oshidomari_kafuka':   '鴛泊→香深',
    'kafuka_oshidomari':   '香深→鴛泊',
}
RISK_EMOJI = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢', 'MINIMAL': '⚪'}
RISK_ORDER = ['HIGH', 'MEDIUM', 'LOW', 'MINIMAL']
WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日']

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

        elif text in ('ヘルプ', 'help', '？', '?', 'コマンド'):
            self._reply(event.reply_token,
                '【コマンド一覧】\n'
                '「予報」または「今日」: 現在のリスク確認\n\n'
                '欠航リスクが高い日は毎朝自動通知します。\n'
                f'詳細: {DASHBOARD_URL}'
            )

    # ------------------------------------------------------------------
    # メッセージ生成
    # ------------------------------------------------------------------

    def _get_today_risks(self) -> Dict[str, dict]:
        """本日の航路別リスクを返す。{route: {risk, wind, wave}}"""
        today = datetime.now(jst).strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.forecast_db)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cf.route, cf.risk_level, cf.wind_forecast, cf.wave_forecast
            FROM cancellation_forecast cf
            INNER JOIN (
                SELECT forecast_for_date, route, MAX(forecast_hour) as max_hour
                FROM cancellation_forecast
                WHERE forecast_for_date = ?
                GROUP BY forecast_for_date, route
            ) latest
            ON cf.forecast_for_date = latest.forecast_for_date
            AND cf.route = latest.route
            AND cf.forecast_hour = latest.max_hour
        ''', (today,))
        result = {}
        for route, risk, wind, wave in cursor.fetchall():
            result[route] = {'risk': risk, 'wind': wind, 'wave': wave}
        conn.close()
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

    def _format_notification(
        self,
        for_user_id: Optional[str] = None,
        route_filter: Optional[List[str]] = None,
        min_risk: str = 'HIGH',
    ) -> Optional[str]:
        """
        通知メッセージを生成する。
        HIGH/MEDIUM リスクが1件もない場合は None を返す（送信スキップ）。
        for_user_id が指定された場合、その user の設定を読み込む。
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

        today_risks = self._get_today_risks()
        future_risks = self._get_forecast_days(3)
        today = datetime.now(jst)

        # アラート対象の絞り込み
        threshold_idx = RISK_ORDER.index(min_risk)

        def is_alerted(risk: Optional[str]) -> bool:
            if not risk:
                return False
            return RISK_ORDER.index(risk) <= threshold_idx

        filtered_today = {
            r: v for r, v in today_risks.items()
            if (route_filter is None or r in route_filter) and is_alerted(v['risk'])
        }

        has_future_alert = any(is_alerted(f['risk']) for f in future_risks)

        if not filtered_today and not has_future_alert:
            return None

        # メッセージ組み立て
        today_str = today.strftime(f'%m/%d（{WEEKDAYS[today.weekday()]}）')
        lines = [f'🚢 フェリー欠航リスク通知', today_str, '']

        # 本日のリスク
        lines.append('━━ 本日のリスク ━━')
        if filtered_today:
            sorted_routes = sorted(
                filtered_today.items(),
                key=lambda x: RISK_ORDER.index(x[1]['risk'])
            )
            for route, info in sorted_routes:
                emoji = RISK_EMOJI.get(info['risk'], '❓')
                name = ROUTE_DISPLAY.get(route, route)
                parts = []
                if info['wind']:
                    parts.append(f"風{info['wind']:.0f}m/s")
                if info['wave']:
                    parts.append(f"波{info['wave']:.1f}m")
                detail = '（' + ' '.join(parts) + '）' if parts else ''
                lines.append(f"{emoji} {name}  {info['risk']}{detail}")
        else:
            lines.append('⚪ 欠航リスクなし')

        # 今後3日間
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
