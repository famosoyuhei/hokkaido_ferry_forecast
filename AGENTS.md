# Hokkaido Ferry Forecast — Codex Agent Guide

**プロジェクト**: 北海道フェリー運航予報システム（稚内⇔利尻島・礼文島）
**本番URL**: https://web-production-a628.up.railway.app/
**最終更新**: 2026-05-30

---

## AI社員の定義

各AI社員の詳細なルールは `docs/ai_employees/` を参照。

| AI社員 | 定義ファイル | 対応スクリプト |
|---|---|---|
| 海上気象予報取得 | `docs/ai_employees/marine_forecast_employee.md` | `weather_forecast_collector.py` |
| 海上気象実測取得 | `docs/ai_employees/actual_weather_employee.md` | `actual_weather_collector.py` |
| フェリー運航記録取得 | `docs/ai_employees/ferry_operation_collector_employee.md` | `improved_ferry_collector.py` |
| 予報精度監査 | `docs/ai_employees/accuracy_auditor_employee.md` | `unified_accuracy_tracker.py` |
| 問題点整理・修正依頼 | `docs/ai_employees/issue_prompt_composer_employee.md` | `issue_prompt_composer.py` |
| 欠航リサーチスキル | `skills/ferry-cancellation-research/SKILL.md` | — |

自動化実行順は `docs/ai_employees/automation_blueprint.md` を参照。

---

## 実行スケジュール（JST）

| 時刻 | スクリプト | 目的 |
|---|---|---|
| 05:00 | `weather_forecast_collector.py` | 朝の予報更新 |
| 06:00 | `improved_ferry_collector.py` | 当日運航状況取得 |
| 06:30 | `actual_weather_collector.py` | 前日実測気象取得 |
| 07:00 | `unified_accuracy_tracker.py` | 精度監査 |
| 07:20 | `issue_prompt_composer.py` | 問題点整理（異常時のみ出力） |
| 11:00 | `weather_forecast_collector.py` | 昼の予報更新 |
| 17:00 | `weather_forecast_collector.py` | 夕の予報更新 |
| 23:00 | `weather_forecast_collector.py` | 夜の予報更新 |

---

## ハードルール（必ず守る）

### データ・セキュリティ
1. **DBファイルをコミットしない** — `.db` ファイルは Railway Volume で管理。`git ls-files | grep .db` でゼロであることを確認。
2. **JST を必ず明示する** — `datetime.now()` は Railway では UTC。`datetime.now(pytz.timezone('Asia/Tokyo'))` を使う。
3. **欠損値を 0 で埋めない** — 風速・波高・視程の欠損は NULL として保存し、精度計算から除外する。
4. **気象欠航以外を精度評価に混ぜない** — 整備運休・季節運休・ダイヤ切り替えは `is_likely_maintenance` フラグで除外する。
5. **ferry_status_enhanced を使う** — 便別運航記録は `ferry_status_enhanced`（`ferry_status` は旧テーブル）。
6. **2026-04-05 以前のデータを精度計算に使わない** — それ以前はスクレイパーのバグで全便欠航と誤記録されている。
7. **APIキー・シークレットをコミットしない** — `railway.json` は APIキーなしの Public 用。
8. **モデル閾値はデータ確認後に調整する** — 誤ったデータでのチューニングは逆効果。データの正確性を先に確認する。

### コミット前の必須チェック（2026-05-30 追加）
9. **Python ファイルを編集したらコミット前に構文確認する**
   ```bash
   python -m py_compile <編集したファイル>.py
   ```
   ImportError も検知したい場合は `python -c "import <module>"` も実行する。

10. **GitHub Actions の YAML を編集したら PyYAML で検証する**
    ```bash
    python -c "import yaml; yaml.safe_load(open('.github/workflows/<file>.yml', encoding='utf-8'))"
    ```
    jobs キーと on キー（PyYAML では `True` として扱われる）が存在することを確認する。

11. **GitHub Actions `run: |` ブロックにマルチライン Python を埋め込まない**
    - インデントされていない行（列0から始まる `import sys` など）がYAML ブロックを壊す。
    - 単一行 `python3 -c "import sys,json; ..."` にするか、外部スクリプトを呼ぶ。

### Flask/Railway での実装ルール（2026-05-30 追加）
12. **Flask 内から同一サーバーの HTTP エンドポイントを呼ばない**
    - `requests.get('https://web-production-a628.up.railway.app/api/...')` を admin エンドポイント内で実行すると gunicorn の単一ワーカーがデッドロックしてタイムアウトする。
    - 内部チェックは必ず SQLite を直接クエリする。

13. **subprocess でスクリプトを起動するときは `sys.executable` と絶対パスを使う**
    ```python
    # ❌ 間違い
    subprocess.run(['python', 'script.py'])
    # ✅ 正解
    import sys, os
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'script.py')])
    ```
    `python` コマンドは Railway 環境では venv の Python を指さないことがある。

### Railway デプロイの確認ルール（2026-05-30 追加）
14. **push 後、最低5分待ってから Railway エンドポイントをテストする**
    - Railway のビルド・デプロイには通常 2〜5 分かかる。
    - GitHub Actions のワークフローを即座に手動実行しても、デプロイ前の古いコードが動いている場合がある。
    - 動作確認前に `/api/stats` 等で Railway が応答していることを確認する。

---

## データベース

| DB | パス（本番） | 主要テーブル |
|---|---|---|
| ferry_weather_forecast.db | `/data/ferry_weather_forecast.db` | `actual_weather`, `cancellation_forecast`, `unified_operation_accuracy`, `unified_daily_summary` |
| heartland_ferry_real_data.db | `/data/heartland_ferry_real_data.db` | `ferry_status_enhanced` |

ローカルでは `.`（カレントディレクトリ）に保存される。
`os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')` で切り替え。

---

## 対象港・航路キー

港キー: `wakkanai`, `oshidomari`, `kutsugata`, `kafuka`

航路キー:
- `wakkanai_oshidomari` / `oshidomari_wakkanai`
- `wakkanai_kafuka` / `kafuka_wakkanai`
- `oshidomari_kafuka` / `kafuka_oshidomari`
- `kutsugata_kafuka` / `kafuka_kutsugata`（夏季のみ 6/1〜9/30）

※ `wakkanai_kutsugata` / `kutsugata_wakkanai` は存在しない（稚内-沓形の直行便なし）

2026年時刻表（便別出港・到着時刻）の正式データは `skills/ferry-cancellation-research/references/heartland_2026_timetable.json` を参照。
`memory.md` は人間向け参照用、JSON が機械処理の唯一の正ソース。

---

## 2026年時刻表切り替え日（ハードルール）

以下の日付で便数・出港時刻・運航航路が変わる。**切り替え日をまたぐ処理では必ず JSON で当日ダイヤを確認すること。**

| 切り替え日 | 変化内容 |
|---|---|
| **2026-04-28**（4/27→4/28） | 便数増：稚内-鴛泊・稚内-香深が1日2便→3便へ |
| **2026-06-01**（5/31→6/1） | 夏ダイヤ開始：沓形-香深便（`kutsugata_kafuka` / `kafuka_kutsugata`）が新設、全航路で出港時刻が変わる |
| **2026-10-01**（9/30→10/1） | 秋ダイヤ：沓形-香深便が終了、稚内-香深に鴛泊経由便が復活 |
| **2026-11-01**（10/31→11/1） | 冬ダイヤ：全航路が1日2便に減便 |

**必須ルール:**

1. `heartland_2026_timetable.json` の `schedules` を `start_date ≤ 対象日 ≤ end_date` で検索して当日ダイヤを決定する。
2. 時刻表にない便を欠航・運航どちらとも記録しない。
3. 沓形-香深便は 2026-06-01〜2026-09-30 以外の日には存在しない。
4. 切り替え当日の気象収集・精度評価は「新ダイヤ」で行う。
5. 便数が変わる日に前後で取得件数が違うのは正常。`parser_error` と混同しない。

---

## リスクロジック（現行）

```python
# weather_forecast_collector.py の calculate_cancellation_risk() と同一
if wind >= 35:   score += 70
elif wind >= 30: score += 60
elif wind >= 25: score += 50
elif wind >= 20: score += 35
elif wind >= 15: score += 20
elif wind >= 10: score += 10

if wave >= 4.0:   score += 40
elif wave >= 3.0: score += 30
elif wave >= 2.0: score += 15

if vis < 1.0:   score += 20
elif vis < 3.0: score += 10

# 判定
score >= 70 → HIGH
score >= 40 → MEDIUM
score >= 20 → LOW
else        → MINIMAL
```

このロジックは `unified_accuracy_tracker.py` の `_calc_risk()` と完全に同期している。変更するときは両方同時に変更する。

---

## 外部APIエンドポイント（参照用）

| API | 用途 |
|---|---|
| https://api.open-meteo.com/v1/forecast | 風速・視程予報（稚内・鴛泊・沓形・香深の緯度経度で4港取得） |
| https://marine-api.open-meteo.com/v1/marine | 波高予報 |
| https://archive-api.open-meteo.com/v1/archive | 実測/再解析（ERA5）|
| https://www.jma.go.jp/bosai/forecast/ | 気象庁天気予報 |
| https://heartlandferry.jp/status/ | ハートランドフェリー運航状況 |

---

## 修正依頼プロンプトの生成

`issue_prompt_composer.py` を実行すると `docs/ai_employees/issue_prompt_composer_employee.md` の形式に従った Markdown プロンプトが生成される。

```bash
python issue_prompt_composer.py           # デフォルト: 直近14日
python issue_prompt_composer.py --days 30 # 直近30日
python issue_prompt_composer.py --output issue_prompt.md  # ファイルへ出力
```

生成されたプロンプトは Claude Code または Codex に貼り付けて修正依頼として使う。

---

## 開発作業の注意

- コードを変更したら `git status` でステージングを確認してからコミット
- `forecast_dashboard.py` の変更は `/api/stats` エンドポイントで動作確認
- `weather_forecast_collector.py` の `calculate_cancellation_risk()` を変更したら `unified_accuracy_tracker.py` の `_calc_risk()` も同じ変更を適用する
- 新規スクリプトは既存の `actual_weather_collector.py` を参考にして JST・DB パス・エラーハンドリングを揃える
