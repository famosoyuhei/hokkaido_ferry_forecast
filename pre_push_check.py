#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
コミット前チェックスクリプト

使い方:
  python pre_push_check.py              # 変更済みファイルを自動検出してチェック
  python pre_push_check.py file.py      # 特定ファイルだけチェック

チェック内容:
  1. 変更した .py ファイルの構文 (py_compile)
  2. 変更した .yml ファイルの YAML 構文
  3. .db ファイルが git 管理下にないか
  4. railway.json に APIキーが含まれていないか
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import py_compile
import subprocess
import json

PASS = '✅'
FAIL = '❌'
WARN = '⚠️ '

errors = 0
warnings = 0


def check(label: str, ok: bool, detail: str = ''):
    global errors
    if ok:
        print(f'  {PASS} {label}')
    else:
        print(f'  {FAIL} {label}')
        if detail:
            print(f'     {detail}')
        errors += 1


def warn(label: str, detail: str = ''):
    global warnings
    print(f'  {WARN} {label}')
    if detail:
        print(f'     {detail}')
    warnings += 1


# ------------------------------------------------------------------
# 対象ファイルを決定
# ------------------------------------------------------------------

def get_changed_files():
    """git で変更されたファイルを取得する。"""
    result = subprocess.run(
        ['git', 'diff', '--name-only', 'HEAD'],
        capture_output=True, text=True
    )
    staged = subprocess.run(
        ['git', 'diff', '--name-only', '--cached'],
        capture_output=True, text=True
    )
    files = set(result.stdout.splitlines()) | set(staged.stdout.splitlines())
    return [f for f in files if os.path.exists(f)]


# ------------------------------------------------------------------
# チェック 1: Python 構文
# ------------------------------------------------------------------

def check_python_syntax(files):
    print('\n[Python 構文チェック]')
    py_files = [f for f in files if f.endswith('.py')]
    if not py_files:
        print(f'  (変更された .py ファイルなし)')
        return

    for f in sorted(py_files):
        try:
            py_compile.compile(f, doraise=True)
            check(f, True)
        except py_compile.PyCompileError as e:
            check(f, False, str(e))


# ------------------------------------------------------------------
# チェック 2: YAML 構文
# ------------------------------------------------------------------

def check_yaml_syntax(files):
    print('\n[GitHub Actions YAML チェック]')
    try:
        import yaml
    except ImportError:
        warn('PyYAML がインストールされていません (pip install pyyaml)')
        return

    yml_files = [f for f in files if f.endswith('.yml') and '.github' in f]
    if not yml_files:
        print(f'  (変更された .github/workflows/*.yml ファイルなし)')
        return

    for f in sorted(yml_files):
        try:
            with open(f, encoding='utf-8') as fh:
                data = yaml.safe_load(fh)
            jobs = list(data.get('jobs', {}).keys())
            # PyYAML では 'on:' が True キーになる
            triggers = data.get(True, {})
            check(f, True, f'jobs={jobs}, triggers={list(triggers.keys()) if triggers else []}')

            # GitHub Actions の既知のアンチパターンをチェック
            for job_name, job in data.get('jobs', {}).items():
                needs = job.get('needs')
                if needs == [] or needs == '':
                    warn(f'{f}: job "{job_name}" に needs: [] があります（省略推奨）')

                for step in job.get('steps', []):
                    run_script = step.get('run', '')
                    # マルチライン python3 -c の検出
                    if 'python3 -c "' in run_script or "python3 -c '" in run_script:
                        lines = run_script.split('\n')
                        for i, line in enumerate(lines):
                            if ('python3 -c "' in line or "python3 -c '" in line) and i + 1 < len(lines):
                                next_line = lines[i + 1]
                                if next_line and not next_line.startswith(' '):
                                    warn(
                                        f'{f}: step "{step.get("name", "?")}": '
                                        f'マルチライン python3 -c でインデントなし行が続いています。'
                                        f'YAML パースエラーの原因になります。'
                                    )

        except Exception as e:
            check(f, False, str(e))


# ------------------------------------------------------------------
# チェック 3: DB ファイルが git に含まれていないか
# ------------------------------------------------------------------

def check_no_db_in_git():
    print('\n[DB ファイルの git 管理確認]')
    result = subprocess.run(
        ['git', 'ls-files'],
        capture_output=True, text=True
    )
    db_files = [f for f in result.stdout.splitlines() if f.endswith('.db')]
    check(
        '.db ファイルが git 管理下にない',
        len(db_files) == 0,
        f'管理されているDBファイル: {db_files}' if db_files else ''
    )


# ------------------------------------------------------------------
# チェック 4: railway.json に APIキーが含まれていないか
# ------------------------------------------------------------------

def check_railway_json():
    print('\n[railway.json セキュリティ確認]')
    if not os.path.exists('railway.json'):
        print(f'  (railway.json が存在しません)')
        return

    try:
        with open('railway.json', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        # よくある APIキーパターンを検出
        suspicious_patterns = [
            'API_KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'WEBHOOK',
            'ACCESS_TOKEN', 'PRIVATE'
        ]
        variables = {}
        for section in data.values():
            if isinstance(section, dict):
                variables.update(section)

        found = [k for k in variables if any(p in k.upper() for p in suspicious_patterns)]
        check(
            'railway.json に APIキー/トークンが含まれていない',
            len(found) == 0,
            f'疑わしいキー: {found}' if found else ''
        )
    except Exception as e:
        warn(f'railway.json の確認中にエラー: {e}')


# ------------------------------------------------------------------
# チェック 5: Flask HTTP ループバックの検出
# ------------------------------------------------------------------

def check_no_http_loopback(files):
    print('\n[Flask HTTP ループバック検出]')
    py_files = [f for f in files if f.endswith('.py')]
    railway_url = 'web-production-a628.up.railway.app'

    found_loopback = []
    for f in py_files:
        try:
            with open(f, encoding='utf-8') as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                if railway_url in line and ('requests.get' in line or 'requests.post' in line):
                    # Flask ルート関数内かどうかは簡易チェック
                    found_loopback.append(f'{f}:{i}: {line.strip()}')
        except Exception:
            pass

    if found_loopback:
        for item in found_loopback:
            warn(f'Flask 内からの HTTP ループバックの可能性: {item}')
    else:
        check('Flask 内 HTTP ループバックなし', True)


# ------------------------------------------------------------------
# チェック 6: subprocess で `python` を使っていないか
# ------------------------------------------------------------------

def check_subprocess_python(files):
    print('\n[subprocess python コマンド確認]')
    py_files = [f for f in files if f.endswith('.py')]
    found = []
    for f in py_files:
        try:
            with open(f, encoding='utf-8') as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                if "'python'" in line and 'subprocess' in line:
                    found.append(f'{f}:{i}: {line.strip()}')
        except Exception:
            pass

    if found:
        for item in found:
            warn(f"subprocess(['python', ...]) → [sys.executable, ...] を推奨: {item}")
    else:
        check("subprocess で 'python' 直書きなし", True)


# ------------------------------------------------------------------
# メイン
# ------------------------------------------------------------------

def main():
    print('=' * 60)
    print('プッシュ前チェック')
    print('=' * 60)

    if len(sys.argv) > 1:
        files = [f for f in sys.argv[1:] if os.path.exists(f)]
        print(f'対象ファイル: {files}')
    else:
        files = get_changed_files()
        print(f'変更ファイル ({len(files)}件): {files}')

    check_python_syntax(files)
    check_yaml_syntax(files)
    check_no_db_in_git()
    check_railway_json()
    check_no_http_loopback(files)
    check_subprocess_python(files)

    print('\n' + '=' * 60)
    if errors == 0 and warnings == 0:
        print(f'✅ 全チェック通過 — コミット・プッシュOK')
    elif errors == 0:
        print(f'⚠️  エラーなし、警告 {warnings}件 — 確認してからプッシュ')
    else:
        print(f'❌ エラー {errors}件、警告 {warnings}件 — 修正してからプッシュ')
    print('=' * 60)

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
