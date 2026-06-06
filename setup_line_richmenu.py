#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE リッチメニュー セットアップスクリプト

使い方:
  python setup_line_richmenu.py                        # プレースホルダー画像を自動生成して登録
  python setup_line_richmenu.py --image richmenu.png   # 指定画像で登録（本番用）
  python setup_line_richmenu.py --list                 # 登録済みメニューを確認
  python setup_line_richmenu.py --delete-all           # 登録済みメニューをすべて削除

必要な環境変数:
  LINE_CHANNEL_ACCESS_TOKEN

メニュー構成 (3列 × 2行, 2500×1686px):
  ┌──────────────┬──────────────┬──────────────┐
  │ 🗓️ 明日のリスク │ 📅 明後日のリスク│ 📊 週間ダッシュ │
  ├──────────────┼──────────────┼──────────────┤
  │ 📋 欠航実績   │ ⛴️ ハートランド │ ✈️ 飛行機予報  │
  └──────────────┴──────────────┴──────────────┘
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import argparse
import requests

# ローカル実行時: railway_local.json または .env から環境変数を読み込む
def _load_local_env():
    # railway_local.json を試みる
    local_json = os.path.join(os.path.dirname(__file__), 'railway_local.json')
    if os.path.exists(local_json):
        try:
            with open(local_json, encoding='utf-8') as f:
                data = json.load(f)
            for k, v in data.get('variables', {}).items():
                if k not in os.environ:
                    os.environ[k] = str(v)
            return
        except Exception:
            pass
    # .env を試みる
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

_load_local_env()

LINE_API = 'https://api.line.me/v2/bot'
LINE_DATA_API = 'https://api-data.line.me/v2/bot'
DASHBOARD_URL = 'https://web-production-a628.up.railway.app/'

W, H = 2500, 1686   # Large サイズ
# 3列 × 2行
CW1, CW2, CW3 = 833, 833, 834   # 列幅 (合計 2500)
RH = H // 2                      # 行高さ 843
# 列の x 開始位置
X1, X2, X3 = 0, 833, 1666

HARTLAND_URL = 'https://heartlandferry.jp/status/'

RICH_MENU_DEF = {
    'size': {'width': W, 'height': H},
    'selected': True,
    'name': 'フェリー・飛行機 欠航リスク予報メニュー',
    'chatBarText': 'メニューを開く 🚢✈️',
    'areas': [
        # ── 上段 ──
        {
            'bounds': {'x': X1, 'y': 0, 'width': CW1, 'height': RH},
            'action': {'type': 'message', 'label': '明日のリスク確認', 'text': '明日'}
        },
        {
            'bounds': {'x': X2, 'y': 0, 'width': CW2, 'height': RH},
            'action': {'type': 'message', 'label': '明後日のリスク確認', 'text': '明後日'}
        },
        {
            'bounds': {'x': X3, 'y': 0, 'width': CW3, 'height': RH},
            'action': {'type': 'uri', 'label': '週間ダッシュボード', 'uri': DASHBOARD_URL}
        },
        # ── 下段 ──
        {
            'bounds': {'x': X1, 'y': RH, 'width': CW1, 'height': RH},
            'action': {'type': 'message', 'label': '欠航実績', 'text': '実績'}
        },
        {
            'bounds': {'x': X2, 'y': RH, 'width': CW2, 'height': RH},
            'action': {'type': 'uri', 'label': 'ハートランドフェリー公式', 'uri': HARTLAND_URL}
        },
        {
            'bounds': {'x': X3, 'y': RH, 'width': CW3, 'height': RH},
            'action': {'type': 'message', 'label': '飛行機予報', 'text': '飛行機'}
        },
    ]
}


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _headers(content_type='application/json'):
    token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
    if not token:
        print('[ERROR] LINE_CHANNEL_ACCESS_TOKEN が設定されていません')
        sys.exit(1)
    return {'Authorization': f'Bearer {token}', 'Content-Type': content_type}


def _check(resp, label):
    if resp.status_code in (200, 204):
        print(f'[OK] {label}')
        return True
    print(f'[ERROR] {label}: {resp.status_code} {resp.text}')
    return False


# ---------------------------------------------------------------------------
# LINE API 操作
# ---------------------------------------------------------------------------

def list_rich_menus():
    resp = requests.get(f'{LINE_API}/richmenu/list', headers=_headers())
    if resp.status_code == 200:
        menus = resp.json().get('richmenus', [])
        if not menus:
            print('登録済みのリッチメニューはありません。')
        for m in menus:
            print(f"  ID: {m['richMenuId']}  name: {m['name']}")
        return menus
    print(f'[ERROR] 一覧取得失敗: {resp.status_code} {resp.text}')
    return []


def delete_all_rich_menus():
    menus = list_rich_menus()
    for m in menus:
        mid = m['richMenuId']
        resp = requests.delete(f'{LINE_API}/richmenu/{mid}', headers=_headers())
        _check(resp, f'削除: {mid}')


def create_rich_menu() -> str:
    resp = requests.post(
        f'{LINE_API}/richmenu',
        headers=_headers(),
        data=json.dumps(RICH_MENU_DEF, ensure_ascii=False).encode('utf-8')
    )
    if not _check(resp, 'リッチメニュー作成'):
        sys.exit(1)
    menu_id = resp.json()['richMenuId']
    print(f'  → richMenuId: {menu_id}')
    return menu_id


def upload_image(menu_id: str, image_path: str):
    ext = os.path.splitext(image_path)[1].lower()
    content_type = 'image/png' if ext == '.png' else 'image/jpeg'
    with open(image_path, 'rb') as f:
        resp = requests.post(
            f'{LINE_DATA_API}/richmenu/{menu_id}/content',
            headers={
                'Authorization': f'Bearer {os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")}',
                'Content-Type': content_type,
            },
            data=f.read()
        )
    _check(resp, f'画像アップロード: {image_path}')


def set_default_rich_menu(menu_id: str):
    resp = requests.post(
        f'{LINE_API}/user/all/richmenu/{menu_id}',
        headers=_headers()
    )
    _check(resp, 'デフォルトメニューに設定')


# ---------------------------------------------------------------------------
# プレースホルダー画像生成
# ---------------------------------------------------------------------------

def generate_placeholder(output='richmenu_placeholder.png'):
    """
    Pillow でシンプルなプレースホルダー画像を生成する（3列×2行）。
    絵文字は Segoe UI Emoji で描画（Meiryo では□になる文字を回避）。
    本番では、このファイルをデザインしたものに差し替えること。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('[ERROR] Pillow がインストールされていません: pip install Pillow')
        sys.exit(1)

    img = Image.new('RGB', (W, H), color='#1a3a5c')  # 濃紺背景
    draw = ImageDraw.Draw(img)

    # グリッド線（2本の縦線 + 1本の横線）
    draw.line([(X2, 0), (X2, H)], fill='#ffffff', width=4)
    draw.line([(X3, 0), (X3, H)], fill='#ffffff', width=4)
    draw.line([(0, RH), (W, RH)], fill='#ffffff', width=4)

    # 外枠
    draw.rectangle([(0, 0), (W - 1, H - 1)], outline='#ffffff', width=4)

    # 各ボタンの設定: (x, y, 列幅, emoji, label, bg_color)
    cells = [
        (X1, 0,  CW1, '🗓️', '明日のリスク',   '#2563eb'),
        (X2, 0,  CW2, '📅', '明後日のリスク',  '#0891b2'),
        (X3, 0,  CW3, '📊', '週間ダッシュ',    '#7c3aed'),
        (X1, RH, CW1, '📋', '欠航実績',        '#b45309'),
        (X2, RH, CW2, '⛴️', 'ハートランド公式', '#0f766e'),
        (X3, RH, CW3, '✈️', '飛行機予報',      '#1d4ed8'),
    ]

    # 絵文字: Segoe UI Emoji（Windows標準 — Meiryo はモダン絵文字を含まない）
    # テキスト: Meiryo
    EMOJI_FONT_PATH = 'C:/Windows/Fonts/seguiemj.ttf'
    MEIRYO_PATH     = 'C:/Windows/Fonts/meiryo.ttc'
    try:
        font_emoji = ImageFont.truetype(EMOJI_FONT_PATH, 160)
    except Exception:
        font_emoji = None
        print('[WARN] Segoe UI Emoji が見つかりません。絵文字なしで生成します。')

    try:
        font_label = ImageFont.truetype(MEIRYO_PATH, 72)
    except Exception:
        font_label = ImageFont.load_default()

    for (cx, cy, cw, emoji, label, bg_color) in cells:
        cx2 = cx + cw
        cy2 = cy + RH
        center_x = cx + cw // 2
        center_y = cy + RH // 2

        # セル背景
        draw.rectangle([(cx + 6, cy + 6), (cx2 - 6, cy2 - 6)], fill=bg_color)

        if font_emoji:
            # 絵文字を上寄りに配置
            draw.text((center_x, center_y - 90), emoji,
                      fill='white', font=font_emoji, anchor='mm')
            # ラベルを下寄りに配置
            draw.text((center_x, center_y + 110), label,
                      fill='white', font=font_label, anchor='mm')
        else:
            # 絵文字フォントなし: テキストのみを中央に配置
            draw.text((center_x, center_y), label,
                      fill='white', font=font_label, anchor='mm')

    img.save(output)
    print(f'[OK] プレースホルダー画像を生成しました: {output}')
    print(f'     サイズ: {W}×{H}px  (3列×2行)')
    print(f'     ※ 本番前にデザイン済み画像に差し替えてください')
    return output


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='LINE リッチメニュー セットアップ')
    parser.add_argument('--image', help='アップロードする画像パス（省略時はプレースホルダーを自動生成）')
    parser.add_argument('--list', action='store_true', help='登録済みメニューを一覧表示')
    parser.add_argument('--delete-all', action='store_true', help='登録済みメニューをすべて削除')
    args = parser.parse_args()

    print('=' * 60)
    print('LINE リッチメニュー セットアップ')
    print('=' * 60)

    if args.list:
        list_rich_menus()
        return

    if args.delete_all:
        delete_all_rich_menus()
        return

    # 既存メニューを削除してから登録（重複防止）
    print('\n[STEP 1] 既存のリッチメニューを確認・削除...')
    delete_all_rich_menus()

    # 画像を準備
    print('\n[STEP 2] 画像を準備...')
    image_path = args.image
    if not image_path:
        image_path = generate_placeholder()
    elif not os.path.exists(image_path):
        print(f'[ERROR] 画像ファイルが見つかりません: {image_path}')
        sys.exit(1)
    else:
        print(f'[OK] 指定画像を使用: {image_path}')

    # リッチメニュー作成
    print('\n[STEP 3] リッチメニューを作成...')
    menu_id = create_rich_menu()

    # 画像アップロード
    print('\n[STEP 4] 画像をアップロード...')
    upload_image(menu_id, image_path)

    # デフォルト設定
    print('\n[STEP 5] デフォルトメニューに設定...')
    set_default_rich_menu(menu_id)

    print('\n' + '=' * 60)
    print('✅ リッチメニューの登録が完了しました')
    print(f'   richMenuId: {menu_id}')
    print()
    print('ボタン動作 (3列×2行):')
    print('  上段左  [明日のリスク確認]   → message: 明日')
    print('  上段中  [明後日のリスク確認]  → message: 明後日')
    print('  上段右  [週間ダッシュボード]  → URI: ' + DASHBOARD_URL)
    print('  下段左  [欠航実績]            → message: 実績')
    print('  下段中  [ハートランドフェリー] → URI: ' + HARTLAND_URL)
    print('  下段右  [飛行機予報]           → message: 飛行機')
    print()
    print('本番画像への差し替え:')
    print('  python setup_line_richmenu.py --image your_design.png')
    print('=' * 60)


if __name__ == '__main__':
    main()
