#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE連携監査 — LINE Messaging API ボットの健全性と通知状況を監査する。

チェック項目:
  1. LINE SDK インストール確認
  2. 環境変数（LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET）の存在確認
  3. ユーザー登録状況（アクティブ数・総数・直近フォロー）
  4. 本日の朝通知送信状況（notification_log テーブル）
  5. Webhook 設定（環境変数ベース）
  6. 通知成功率（直近7日間の notification_log）

出力: stdout（コンソール） + JSON（オプション）
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional
from jst_utils import now_jst, today_jst_str

try:
    import linebot  # noqa: F401
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False


class LineAuditor:
    """LINE Messaging API ボットの統合状態を監査する。"""

    def __init__(self):
        data_dir = (
            os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
            or os.environ.get('RAILWAY_VOLUME_MOUNT')
            or '.'
        )
        self.notif_db = os.path.join(data_dir, 'notifications.db')

    # ------------------------------------------------------------------
    # 1. SDK と環境変数
    # ------------------------------------------------------------------

    def check_sdk_and_config(self) -> Dict:
        """LINE SDK のインストールと必須環境変数を確認する。"""
        token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        secret = os.getenv('LINE_CHANNEL_SECRET')

        has_token  = bool(token)
        has_secret = bool(secret)
        ok = LINE_SDK_AVAILABLE and has_token and has_secret

        issues = []
        if not LINE_SDK_AVAILABLE:
            issues.append('line-bot-sdk がインストールされていない（requirements.txt に line-bot-sdk>=3.5.0 を追加）')
        if not has_token:
            issues.append('LINE_CHANNEL_ACCESS_TOKEN が未設定')
        if not has_secret:
            issues.append('LINE_CHANNEL_SECRET が未設定')

        return {
            'ok': ok,
            'sdk_available': LINE_SDK_AVAILABLE,
            'token_set': has_token,
            'secret_set': has_secret,
            'issues': issues,
        }

    # ------------------------------------------------------------------
    # 2. ユーザー登録状況
    # ------------------------------------------------------------------

    def check_user_stats(self) -> Dict:
        """notifications.db の line_users テーブルからユーザー数統計を確認する。"""
        if not os.path.exists(self.notif_db):
            return {'ok': False, 'error': 'notifications.db が存在しない', 'db_path': self.notif_db}

        try:
            conn = sqlite3.connect(self.notif_db)

            # テーブル存在確認
            table_exists = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='line_users'"
            ).fetchone()[0]

            if not table_exists:
                conn.close()
                return {'ok': False, 'error': 'line_users テーブルが存在しない'}

            total = conn.execute('SELECT COUNT(*) FROM line_users').fetchone()[0]
            active = conn.execute(
                'SELECT COUNT(*) FROM line_users WHERE active=1'
            ).fetchone()[0]
            inactive = total - active

            # 直近7日間のフォロー
            since_7d = (now_jst() - timedelta(days=7)).strftime('%Y-%m-%d')
            new_7d = conn.execute(
                'SELECT COUNT(*) FROM line_users WHERE followed_at >= ?',
                (since_7d,)
            ).fetchone()[0]

            # 最近フォローしたユーザー（匿名化）
            recent_rows = conn.execute(
                'SELECT line_user_id, followed_at FROM line_users ORDER BY followed_at DESC LIMIT 3'
            ).fetchall()
            recent_users = [
                {'user_id_prefix': r[0][:8] + '...', 'followed_at': r[1]}
                for r in recent_rows
            ]

            conn.close()

            # アクティブ0人でも問題なし（リリース前は正常）
            ok = total >= 0
            warning = None
            if active == 0 and total > 0:
                warning = '全員アンフォロー中（アクティブ0人）'

            return {
                'ok': ok,
                'total_users': total,
                'active_users': active,
                'inactive_users': inactive,
                'new_users_last_7d': new_7d,
                'recent_users': recent_users,
                'warning': warning,
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 3. 本日の朝通知送信状況
    # ------------------------------------------------------------------

    def check_morning_notification_today(self) -> Dict:
        """本日の朝通知が実行されたかを notification_log から確認する。"""
        if not os.path.exists(self.notif_db):
            return {'ok': False, 'error': 'notifications.db が存在しない'}

        today = today_jst_str()

        try:
            conn = sqlite3.connect(self.notif_db)

            # notification_log テーブルが存在するか確認
            table_exists = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='notification_log'"
            ).fetchone()[0]

            if not table_exists:
                conn.close()
                return {
                    'ok': None,  # 不明（テーブルなし）
                    'note': 'notification_log テーブルが未作成（line_bot_service.py の _init_db を実行すると作成されます）',
                    'action': 'line_bot_service.LineBotService()._init_db() を呼び出すか、send_morning_notifications() を1回実行してください',
                }

            # 本日の実行記録
            row = conn.execute('''
                SELECT run_date, sent, skipped, errors, ran_at
                FROM notification_log
                WHERE run_date = ?
                ORDER BY ran_at DESC
                LIMIT 1
            ''', (today,)).fetchone()

            if not row:
                conn.close()
                return {
                    'ok': False,
                    'run_date': today,
                    'status': 'not_run',
                    'warning': '本日の朝通知が実行されていない',
                }

            run_date, sent, skipped, errors, ran_at = row

            # 直近7日間の統計
            since_7d = (now_jst() - timedelta(days=7)).strftime('%Y-%m-%d')
            rows_7d = conn.execute('''
                SELECT run_date, sent, skipped, errors
                FROM notification_log
                WHERE run_date >= ?
                ORDER BY run_date DESC
            ''', (since_7d,)).fetchall()

            conn.close()

            total_sent_7d = sum(r[1] for r in rows_7d)
            total_errors_7d = sum(r[3] for r in rows_7d)
            error_rate_7d = (
                total_errors_7d / (total_sent_7d + total_errors_7d)
                if (total_sent_7d + total_errors_7d) > 0 else 0
            )

            ok = errors == 0
            return {
                'ok': ok,
                'run_date': run_date,
                'ran_at': ran_at,
                'sent': sent,
                'skipped': skipped,
                'errors': errors,
                'last_7d_summary': {
                    'days_run': len(rows_7d),
                    'total_sent': total_sent_7d,
                    'total_errors': total_errors_7d,
                    'error_rate': round(error_rate_7d, 3),
                },
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 4. Webhook 設定確認
    # ------------------------------------------------------------------

    def check_webhook_config(self) -> Dict:
        """Railway の RAILWAY_PUBLIC_DOMAIN からWebhook URLが推測できるか確認する。"""
        public_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
        railway_url = os.getenv('RAILWAY_STATIC_URL', '')

        # 環境変数から推定
        if public_domain:
            webhook_url = f'https://{public_domain}/webhook/line'
        elif railway_url:
            webhook_url = f'{railway_url.rstrip("/")}/webhook/line'
        else:
            webhook_url = 'https://web-production-a628.up.railway.app/webhook/line'

        return {
            'ok': True,  # 設定の有無は LINE Developer Console で確認
            'expected_webhook_url': webhook_url,
            'railway_public_domain': public_domain or '(未設定)',
            'note': 'LINE Developers Console で上記URLがWebhook URLに設定されているか確認してください',
        }

    # ------------------------------------------------------------------
    # 総合実行
    # ------------------------------------------------------------------

    def run(self) -> Dict:
        """全チェックを実行し、結果サマリを返す。"""
        now = now_jst()
        print('=' * 72)
        print('LINE AUDIT — LINE INTEGRATION HEALTH CHECK')
        print(f'実行時刻: {now.strftime("%Y-%m-%d %H:%M:%S JST")}')
        print('=' * 72)

        checks = {
            'sdk_and_config':       ('SDK・環境変数',       self.check_sdk_and_config),
            'user_stats':           ('ユーザー登録状況',     self.check_user_stats),
            'morning_notification': ('本日の朝通知',         self.check_morning_notification_today),
            'webhook_config':       ('Webhook設定',         self.check_webhook_config),
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
            ok = result.get('ok')

            # ok=None は「不明」扱い（エラーではないが完全OKでもない）
            if ok is False:
                all_ok = False
                status = '❌'
            elif ok is None:
                status = '⚠️ '
            else:
                status = '✅'

            if key == 'sdk_and_config':
                sdk_str = '✓' if result.get('sdk_available') else '✗'
                token_str = '✓' if result.get('token_set') else '✗'
                secret_str = '✓' if result.get('secret_set') else '✗'
                print(f'  {status} SDK:{sdk_str}  ACCESS_TOKEN:{token_str}  SECRET:{secret_str}')
                for issue in result.get('issues', []):
                    print(f'     → {issue}')

            elif key == 'user_stats':
                total = result.get('total_users', '?')
                active = result.get('active_users', '?')
                new_7d = result.get('new_users_last_7d', '?')
                print(f'  {status} アクティブ:{active}人 / 総計:{total}人 / 直近7日新規:{new_7d}人')
                if result.get('warning'):
                    print(f'     ⚠️  {result["warning"]}')
                if result.get('error'):
                    print(f'     エラー: {result["error"]}')

            elif key == 'morning_notification':
                if result.get('status') == 'not_run':
                    print(f'  {status} 本日未実行 — {result.get("warning", "")}')
                elif result.get('note'):
                    print(f'  {status} {result.get("note")}')
                else:
                    sent = result.get('sent', '?')
                    skipped = result.get('skipped', '?')
                    errors = result.get('errors', '?')
                    ran_at = result.get('ran_at', '?')
                    print(f'  {status} 送信:{sent}人 スキップ:{skipped}人 エラー:{errors}件 ({ran_at})')
                    summary_7d = result.get('last_7d_summary', {})
                    if summary_7d:
                        print(f'     直近7日: 送信計{summary_7d.get("total_sent")}件 '
                              f'エラー率{summary_7d.get("error_rate", 0):.1%}')

            elif key == 'webhook_config':
                print(f'  {status} {result.get("expected_webhook_url", "?")}')
                if result.get('note'):
                    print(f'     📝 {result["note"]}')

        report['all_ok'] = all_ok
        print('\n' + '=' * 72)
        overall = '✅ ALL OK' if all_ok else '❌ ISSUES FOUND'
        print(f'総合結果: {overall}')
        print('=' * 72 + '\n')

        return report


def main():
    auditor = LineAuditor()
    report = auditor.run()

    output_path = os.getenv('LINE_AUDIT_OUTPUT')
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'[INFO] レポートを保存しました: {output_path}')

    return 0 if report.get('all_ok') else 1


if __name__ == '__main__':
    exit(main())
